import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.recording_library import RecordingLibraryService
from utils.media_metadata import MediaMetadataResult
from utils.recording_library_store import LibraryWriteResult, MaterialItem
from utils.recycle_bin import RecycleResult


class TestRecordingLibraryService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.library_path = self.base_path / "QuickRec" / "recordings.json"
        self.service = RecordingLibraryService(self.library_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_deduplicates_normalized_file_path(self):
        video = self.base_path / "QuickRec_demo.mp4"
        video.write_bytes(b"video")
        older = self._item(video, "older", "2026-07-10T14:00:00+08:00")
        newer = self._item(video, "newer", "2026-07-10T15:00:00+08:00")

        self.assertTrue(self.service.add(older).ok)
        result = self.service.add(newer)

        self.assertTrue(result.ok)
        self.assertEqual([item.id for item in result.items], ["newer"])

    @patch("services.recording_library.probe_media")
    def test_add_recording_uses_session_metadata_without_ffprobe(self, probe):
        video = self.base_path / "QuickRec_20260710_160000.mp4"
        video.write_bytes(b"video")

        result = self.service.add_recording(
            video,
            metadata={
                "duration_sec": 3.25,
                "width": 1920,
                "height": 1080,
                "fps": 60.0,
                "mode": "fullscreen",
                "audio_source": "both",
            },
            diagnostic_dir=str(self.base_path / "diagnostics"),
        )

        self.assertTrue(result.ok)
        item = result.items[0]
        self.assertEqual(item.duration_sec, 3.25)
        self.assertEqual((item.width, item.height, item.fps), (1920, 1080, 60.0))
        self.assertEqual((item.mode, item.audio_source), ("fullscreen", "both"))
        probe.assert_not_called()

    def test_list_items_supports_incremental_pages(self):
        items = [
            self._item(
                self.base_path / f"QuickRec_{index:03d}.mp4",
                f"item-{index:03d}",
                f"2026-07-10T{index // 60:02d}:{index % 60:02d}:00+08:00",
            )
            for index in range(120)
        ]
        self.assertTrue(self.service.replace(items).ok)

        first_page = self.service.list_items(offset=0, limit=50)
        second_page = self.service.list_items(offset=50, limit=50)

        self.assertEqual(len(first_page), 50)
        self.assertEqual(len(second_page), 50)
        self.assertEqual(first_page[0].id, "item-119")
        self.assertEqual(second_page[0].id, "item-069")

    def test_remove_only_updates_index_and_keeps_video(self):
        video = self.base_path / "QuickRec_keep.mp4"
        video.write_bytes(b"video")
        self.assertTrue(self.service.add(self._item(video, "keep", "2026-07-10T15:00:00+08:00")).ok)

        result = self.service.remove("keep")

        self.assertTrue(result.ok)
        self.assertEqual(result.items, [])
        self.assertTrue(video.exists())

    @patch(
        "services.recording_library.probe_media",
        return_value=MediaMetadataResult(True, duration_sec=8.0, width=1280, height=720, fps=30.0),
    )
    def test_relink_updates_path_and_preserves_identity(self, _probe):
        missing = self.base_path / "missing.mp4"
        moved = self.base_path / "QuickRec_moved.mp4"
        moved.write_bytes(b"video")
        original = self._item(missing, "stable-id", "2026-07-10T15:00:00+08:00")
        self.assertTrue(self.service.add(original).ok)

        result = self.service.relink("stable-id", moved)

        self.assertTrue(result.ok)
        self.assertEqual(result.items[0].id, "stable-id")
        self.assertEqual(result.items[0].created_at, "2026-07-10T15:00:00+08:00")
        self.assertEqual(result.items[0].file_path, str(moved))
        self.assertEqual((result.items[0].width, result.items[0].height), (1280, 720))

    def test_relink_rejects_path_already_used_by_another_item(self):
        existing = self.base_path / "QuickRec_existing.mp4"
        existing.write_bytes(b"video")
        missing = self.base_path / "missing.mp4"
        self.assertTrue(
            self.service.replace(
                [
                    self._item(existing, "existing", "2026-07-10T15:00:00+08:00"),
                    self._item(missing, "missing", "2026-07-10T14:00:00+08:00"),
                ]
            ).ok
        )

        result = self.service.relink("missing", existing)

        self.assertFalse(result.ok)
        self.assertIn("already", result.error.lower())
        self.assertEqual(len(self.service.load().items), 2)

    @patch(
        "services.recording_library.probe_media",
        return_value=MediaMetadataResult(False, error="invalid media"),
    )
    def test_relink_rejects_unparseable_mp4_without_changing_index(self, _probe):
        missing = self.base_path / "missing.mp4"
        broken = self.base_path / "损坏 candidate.mp4"
        broken.write_bytes(b"not a video")
        self.assertTrue(self.service.add(self._item(missing, "missing", "2026-07-10T15:00:00+08:00")).ok)
        before = self.library_path.read_bytes()

        result = self.service.relink("missing", broken)

        self.assertFalse(result.ok)
        self.assertIn("invalid media", result.error)
        self.assertEqual(self.library_path.read_bytes(), before)
        item = self.service.load().items[0]
        self.assertEqual(item.file_path, str(missing))
        self.assertEqual(item.status, "missing")

    def test_relink_save_failure_keeps_persisted_original_record(self):
        missing = self.base_path / "missing.mp4"
        candidate = self.base_path / "中文 空格.mp4"
        candidate.write_bytes(b"video")
        self.assertTrue(self.service.add(self._item(missing, "missing", "2026-07-10T15:00:00+08:00")).ok)
        before = self.library_path.read_bytes()

        with patch(
            "services.recording_library.probe_media",
            return_value=MediaMetadataResult(True, duration_sec=2.0, width=640, height=360, fps=30.0),
        ), patch(
            "services.recording_library.save_library",
            return_value=LibraryWriteResult(False, self.library_path, error="write failed"),
        ):
            result = self.service.relink("missing", candidate)

        self.assertFalse(result.ok)
        self.assertEqual(self.library_path.read_bytes(), before)

    @patch("services.recording_library.recycle_file")
    def test_recycle_success_removes_index(self, recycle):
        video = self.base_path / "QuickRec_delete.mp4"
        video.write_bytes(b"video")
        self.assertTrue(self.service.add(self._item(video, "delete", "2026-07-10T15:00:00+08:00")).ok)
        recycle.return_value = RecycleResult(True, video)

        result = self.service.recycle("delete")

        self.assertTrue(result.ok)
        self.assertEqual(result.items, [])
        recycle.assert_called_once_with(video)

    @patch("services.recording_library.recycle_file")
    def test_recycle_failure_keeps_index(self, recycle):
        video = self.base_path / "QuickRec_keep.mp4"
        video.write_bytes(b"video")
        self.assertTrue(self.service.add(self._item(video, "keep", "2026-07-10T15:00:00+08:00")).ok)
        recycle.return_value = RecycleResult(False, video, "recycle failed")

        result = self.service.recycle("keep")

        self.assertFalse(result.ok)
        self.assertIn("recycle failed", result.error)
        self.assertEqual([item.id for item in self.service.load().items], ["keep"])

    @staticmethod
    def _item(path: Path, item_id: str, created_at: str) -> MaterialItem:
        return MaterialItem(
            id=item_id,
            file_path=str(path),
            file_name=path.name,
            directory=str(path.parent),
            mode="fullscreen",
            audio_source="none",
            created_at=created_at,
        )


if __name__ == "__main__":
    unittest.main()
