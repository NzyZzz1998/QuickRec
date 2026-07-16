import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.pending_recordings import PendingRecordingService
from utils.media_metadata import MediaMetadataResult
from utils.pending_recording_store import PendingRecordingItem, load_pending, save_fallback_marker


class TestPendingRecordingService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.pending_path = self.root / "appdata" / "QuickRec" / "pending-recordings.json"
        self.service = PendingRecordingService(self.pending_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_discovers_only_current_save_directory_markers(self):
        current = self.root / "current"
        other = self.root / "other"
        current.mkdir()
        other.mkdir()
        current_video = self._video(current / "QuickRec_current.mp4")
        other_video = self._video(other / "QuickRec_other.mp4")
        self.assertTrue(save_fallback_marker(self._item(current_video, "current", "material-current")).ok)
        self.assertTrue(save_fallback_marker(self._item(other_video, "other", "material-other")).ok)

        loaded = self.service.load(current)

        self.assertTrue(loaded.ok)
        self.assertEqual([item.pending_id for item in loaded.items], ["current"])

    def test_load_directory_explicitly_discovers_selected_directory(self):
        selected = self.root / "历史 目录"
        selected.mkdir()
        video = self._video(selected / "QuickRec_history.mp4")
        self.assertTrue(save_fallback_marker(self._item(video, "history", "material-history")).ok)

        loaded = self.service.load_directory(selected)

        self.assertTrue(loaded.ok)
        self.assertEqual([item.pending_id for item in loaded.items], ["history"])

    def test_discover_directory_merges_markers_into_primary_queue(self):
        selected = self.root / "历史 目录"
        video = self._video(selected / "QuickRec_history.mp4")
        self.assertTrue(save_fallback_marker(self._item(video, "history", "material-history")).ok)

        result = self.service.discover_directory(selected)

        self.assertTrue(result.ok)
        self.assertEqual([item.pending_id for item in load_pending(self.pending_path).items], ["history"])
        self.assertTrue((selected / "QuickRecMetadata" / "Pending" / "history.json").exists())

    def test_primary_and_marker_duplicate_merge_to_one_newest_item(self):
        directory = self.root / "save"
        directory.mkdir()
        video = self._video(directory / "QuickRec_demo.mp4")
        primary = self._item(video, "same", "material-same", attempt_count=2)
        marker = self._item(video, "same", "material-same", attempt_count=4)
        marker.updated_at = "2026-07-15T11:00:00+08:00"
        marker.status = "retry_failed"
        self.assertTrue(self.service.persist(primary).ok)
        self.assertTrue(save_fallback_marker(marker).ok)

        loaded = self.service.load(directory)

        self.assertTrue(loaded.ok)
        self.assertEqual(len(loaded.items), 1)
        self.assertEqual(loaded.items[0].attempt_count, 4)
        self.assertEqual(loaded.items[0].status, "retry_failed")
        self.assertEqual(loaded.items[0].material_id, "material-same")

    def test_missing_video_is_reported_without_discarding_item(self):
        missing = self.root / "missing.mp4"
        self.assertTrue(self.service.persist(self._item(missing, "missing", "material-missing")).ok)

        loaded = self.service.load()

        self.assertTrue(loaded.ok)
        self.assertEqual(loaded.items[0].status, "missing")

    def test_relink_valid_video_updates_path_and_metadata(self):
        original = self.root / "missing.mp4"
        replacement = self._video(self.root / "中文 空格" / "QuickRec_replacement.mp4")
        replacement.parent.mkdir(exist_ok=True)
        self.assertTrue(self.service.persist(self._item(original, "pending", "material-pending")).ok)

        with patch(
            "services.pending_recordings.probe_media",
            return_value=MediaMetadataResult(True, duration_sec=3.5, width=1920, height=1080, fps=60),
        ):
            result = self.service.relink("pending", replacement)

        self.assertTrue(result.ok)
        loaded = self.service.load()
        self.assertEqual(loaded.items[0].file_path, str(replacement))
        self.assertEqual(loaded.items[0].status, "pending")
        self.assertEqual(loaded.items[0].duration_seconds, 3.5)
        self.assertEqual(loaded.items[0].width, 1920)
        self.assertEqual(loaded.items[0].fps, 60)

    def test_relink_invalid_video_does_not_change_persisted_item(self):
        original = self.root / "missing.mp4"
        broken = self._video(self.root / "broken.mp4")
        self.assertTrue(self.service.persist(self._item(original, "pending", "material-pending")).ok)
        before = self.pending_path.read_bytes()

        with patch(
            "services.pending_recordings.probe_media",
            return_value=MediaMetadataResult(False, error="invalid video"),
        ):
            result = self.service.relink("pending", broken)

        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "VIDEO_INVALID")
        self.assertEqual(self.pending_path.read_bytes(), before)

    def test_relink_fallback_only_item_promotes_it_to_primary_queue(self):
        save_dir = self.root / "save"
        original = save_dir / "missing.mp4"
        replacement = self._video(save_dir / "中文 空格 replacement.mp4")
        item = self._item(original, "fallback", "material-fallback")
        self.assertTrue(save_fallback_marker(item).ok)

        with patch(
            "services.pending_recordings.probe_media",
            return_value=MediaMetadataResult(True, duration_sec=4, width=1280, height=720, fps=30),
        ):
            result = self.service.relink(
                "fallback",
                replacement,
                current_save_dir=save_dir,
            )

        self.assertTrue(result.ok)
        loaded = self.service.load(save_dir)
        self.assertEqual(len(loaded.items), 1)
        self.assertEqual(loaded.items[0].file_path, str(replacement))
        self.assertTrue(self.pending_path.exists())
        self.assertFalse((save_dir / "QuickRecMetadata" / "Pending" / "fallback.json").exists())

    def test_remove_deletes_pending_metadata_but_keeps_video(self):
        video = self._video(self.root / "QuickRec_keep.mp4")
        item = self._item(video, "pending", "material-pending")
        self.assertTrue(self.service.persist(item).ok)
        self.assertTrue(save_fallback_marker(item).ok)

        result = self.service.remove("pending", current_save_dir=video.parent)

        self.assertTrue(result.ok)
        self.assertTrue(video.exists())
        self.assertEqual(load_pending(self.pending_path).items, [])
        self.assertFalse((video.parent / "QuickRecMetadata" / "Pending" / "pending.json").exists())

    def test_primary_write_failure_falls_back_to_video_marker(self):
        video = self._video(self.root / "QuickRec_fallback.mp4")
        item = self._item(video, "fallback", "material-fallback")

        with patch("services.pending_recordings.save_pending") as save_primary:
            save_primary.return_value.ok = False
            save_primary.return_value.error = "denied"
            result = self.service.persist_with_fallback(item)

        self.assertTrue(result.ok)
        self.assertEqual(result.storage, "fallback")
        self.assertTrue((video.parent / "QuickRecMetadata" / "Pending" / "fallback.json").exists())

    def _video(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"video")
        return path

    @staticmethod
    def _item(
        path: Path,
        pending_id: str,
        material_id: str,
        *,
        attempt_count: int = 1,
    ) -> PendingRecordingItem:
        return PendingRecordingItem(
            pending_id=pending_id,
            material_id=material_id,
            file_path=str(path),
            file_name=path.name,
            created_at="2026-07-15T10:00:00+08:00",
            queued_at="2026-07-15T10:00:00+08:00",
            updated_at="2026-07-15T10:00:00+08:00",
            status="pending",
            attempt_count=attempt_count,
            capture_mode="fullscreen",
            audio_source="none",
        )


if __name__ == "__main__":
    unittest.main()
