import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.recording_library import RecordingLibraryService
from utils.media_metadata import MediaMetadataResult


class TestRecordingLibraryScan(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.video_dir = self.base_path / "videos"
        self.video_dir.mkdir()
        self.service = RecordingLibraryService(self.base_path / "appdata" / "QuickRec" / "recordings.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_preview_only_scans_current_level_quickrec_mp4_files(self):
        expected = self.video_dir / "QuickRec_20260710_150000.mp4"
        expected.write_bytes(b"video")
        uppercase = self.video_dir / "QUICKREC_20260710_140000.MP4"
        uppercase.write_bytes(b"video")
        (self.video_dir / "other.mp4").write_bytes(b"other")
        child = self.video_dir / "child"
        child.mkdir()
        (child / "QuickRec_20260710_130000.mp4").write_bytes(b"nested")

        with patch(
            "services.recording_library.probe_media",
            return_value=MediaMetadataResult(True, duration_sec=1, width=320, height=240, fps=30),
        ):
            result = self.service.preview_directory(self.video_dir)

        self.assertTrue(result.ok)
        self.assertFalse(result.cancelled)
        self.assertEqual({Path(item.file_path).name for item in result.items}, {expected.name, uppercase.name})
        self.assertEqual(self.service.load().items, [])

    def test_cancelled_preview_does_not_change_central_index(self):
        for index in range(3):
            (self.video_dir / f"QuickRec_20260710_15000{index}.mp4").write_bytes(b"video")

        result = self.service.preview_directory(self.video_dir, cancel_requested=lambda: True)

        self.assertTrue(result.cancelled)
        self.assertEqual(result.items, [])
        self.assertFalse(self.service.library_path.exists())

    def test_commit_scan_writes_preview_items_once(self):
        video = self.video_dir / "QuickRec_20260710_150000.mp4"
        video.write_bytes(b"video")
        with patch(
            "services.recording_library.probe_media",
            return_value=MediaMetadataResult(True, duration_sec=1, width=320, height=240, fps=30),
        ):
            preview = self.service.preview_directory(self.video_dir)

        first = self.service.commit_scan(preview, imported_at="2026-07-10T16:00:00+08:00")
        second = self.service.commit_scan(preview, imported_at="2026-07-10T16:05:00+08:00")

        self.assertTrue(first.ok)
        self.assertTrue(second.ok)
        self.assertEqual(len(second.items), 1)
        self.assertEqual(second.items[0].source_type, "rebuild")
        self.assertEqual(second.items[0].imported_at, "2026-07-10T16:00:00+08:00")

    def test_commit_scan_replaces_corrupt_index_when_no_backup_exists(self):
        video = self.video_dir / "QuickRec_20260710_150000.mp4"
        video.write_bytes(b"video")
        self.service.library_path.parent.mkdir(parents=True)
        self.service.library_path.write_text("{broken json", encoding="utf-8")
        with patch(
            "services.recording_library.probe_media",
            return_value=MediaMetadataResult(True, duration_sec=1, width=320, height=240, fps=30),
        ):
            preview = self.service.preview_directory(self.video_dir)

        result = self.service.commit_scan(preview, imported_at="2026-07-10T16:00:00+08:00")

        self.assertTrue(result.ok)
        self.assertEqual([Path(item.file_path) for item in result.items], [video])
        self.assertTrue(list(self.service.library_path.parent.glob("recordings.corrupt-*.json")))

    @patch(
        "services.recording_library.probe_media",
        return_value=MediaMetadataResult(True, duration_sec=4.5, width=1920, height=1080, fps=60.0),
    )
    def test_preview_enriches_media_metadata(self, _probe):
        video = self.video_dir / "QuickRec_20260710_150000.mp4"
        video.write_bytes(b"video")

        result = self.service.preview_directory(self.video_dir)

        self.assertTrue(result.ok)
        self.assertEqual(result.items[0].duration_sec, 4.5)
        self.assertEqual((result.items[0].width, result.items[0].height), (1920, 1080))
        self.assertEqual(result.items[0].fps, 60.0)

    @patch(
        "services.recording_library.probe_media",
        return_value=MediaMetadataResult(False, error="invalid video"),
    )
    def test_preview_skips_video_when_metadata_probe_fails(self, _probe):
        video = self.video_dir / "QuickRec_20260710_150000.mp4"
        video.write_bytes(b"video")

        result = self.service.preview_directory(self.video_dir)

        self.assertTrue(result.ok)
        self.assertEqual(result.items, [])
        self.assertEqual(result.failed_count, 1)

    @patch("services.recording_library.probe_media")
    def test_preview_single_bad_file_does_not_block_valid_file(self, probe):
        good = self.video_dir / "QuickRec_20260710_150000.mp4"
        bad = self.video_dir / "QuickRec_20260710_150001.mp4"
        good.write_bytes(b"video")
        bad.write_bytes(b"broken")
        probe.side_effect = lambda path, **_kwargs: (
            MediaMetadataResult(True, duration_sec=1, width=320, height=240, fps=30)
            if Path(path).name == good.name
            else MediaMetadataResult(False, error="invalid media")
        )

        result = self.service.preview_directory(self.video_dir)

        self.assertTrue(result.ok)
        self.assertEqual([Path(item.file_path).name for item in result.items], [good.name])
        self.assertEqual(result.failed_count, 1)

    def test_relink_candidates_match_missing_item_by_filename_without_changing_index(self):
        old_path = self.base_path / "old" / "QuickRec_20260710_150000.mp4"
        missing = self.service.add_recording(
            old_path,
            metadata={"mode": "fullscreen", "audio_source": "none"},
            diagnostic_dir=None,
        )
        self.assertFalse(missing.ok)

        from utils.recording_library_store import MaterialItem

        item = MaterialItem(
            id="missing-id",
            file_path=str(old_path),
            file_name=old_path.name,
            directory=str(old_path.parent),
            mode="fullscreen",
            audio_source="none",
            created_at="2026-07-10T15:00:00+08:00",
        )
        self.assertTrue(self.service.add(item).ok)
        moved = self.video_dir / old_path.name
        moved.write_bytes(b"video")
        with patch(
            "services.recording_library.probe_media",
            return_value=MediaMetadataResult(True, duration_sec=1, width=320, height=240, fps=30),
        ):
            scan = self.service.preview_directory(self.video_dir)

        candidates = self.service.find_relink_candidates(scan.items)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].item_id, "missing-id")
        self.assertEqual(candidates[0].candidate_path, str(moved))
        self.assertIn("filename", candidates[0].match_reasons)
        self.assertEqual(self.service.load().items[0].file_path, str(old_path))


if __name__ == "__main__":
    unittest.main()
