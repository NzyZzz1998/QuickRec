import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.material_ingestion import MaterialIngestionCoordinator
from services.pending_recordings import PendingActionResult, PendingRecordingService
from services.recording_library import RecordingLibraryService
from utils.pending_recording_store import PendingRecordingItem, load_pending
from utils.recording_library_store import LibraryWriteResult


class TestMaterialIngestionCoordinator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.library = RecordingLibraryService(self.root / "appdata" / "QuickRec" / "recordings.json")
        self.pending = PendingRecordingService(self.root / "appdata" / "QuickRec" / "pending-recordings.json")
        self.coordinator = MaterialIngestionCoordinator(self.library, self.pending)
        self.video = self.root / "视频 目录" / "QuickRec_20260715_100000.mp4"
        self.video.parent.mkdir()
        self.video.write_bytes(b"video")
        self.metadata = {
            "mode": "fullscreen",
            "audio_source": "none",
            "duration_sec": 2.0,
            "width": 1920,
            "height": 1080,
            "fps": 60,
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_formal_index_success_does_not_create_pending_record(self):
        result = self.coordinator.ingest_saved_recording(
            self.video,
            metadata=self.metadata,
            diagnostic_dir=None,
            pending_id="pending-1",
            material_id="material-1",
        )

        self.assertTrue(result.video_saved)
        self.assertTrue(result.formal_indexed)
        self.assertFalse(result.pending_persisted)
        self.assertEqual(self.library.load().items[0].id, "material-1")
        self.assertFalse(self.pending.pending_path.exists())

    def test_formal_index_failure_persists_pending_without_changing_video_success(self):
        failure = LibraryWriteResult(False, self.library.library_path, error="denied")
        with patch.object(self.library, "add_recording", return_value=failure):
            result = self.coordinator.ingest_saved_recording(
                self.video,
                metadata=self.metadata,
                diagnostic_dir=None,
                pending_id="pending-1",
                material_id="material-1",
            )

        self.assertTrue(result.video_saved)
        self.assertFalse(result.formal_indexed)
        self.assertTrue(result.pending_persisted)
        self.assertEqual(result.error_code, "FORMAL_INDEX_WRITE_FAILED")
        self.assertEqual(load_pending(self.pending.pending_path).items[0].material_id, "material-1")
        self.assertTrue(self.video.exists())

    def test_dual_pending_persistence_failure_still_reports_video_saved(self):
        formal_failure = LibraryWriteResult(False, self.library.library_path, error="index denied")
        pending_failure = PendingActionResult(
            False,
            error="both denied",
            error_code="PENDING_FALLBACK_WRITE_FAILED",
        )
        with (
            patch.object(self.library, "add_recording", return_value=formal_failure),
            patch.object(self.pending, "persist_with_fallback", return_value=pending_failure),
        ):
            result = self.coordinator.ingest_saved_recording(
                self.video,
                metadata=self.metadata,
                diagnostic_dir=None,
                pending_id="pending-1",
                material_id="material-1",
            )

        self.assertTrue(result.video_saved)
        self.assertFalse(result.formal_indexed)
        self.assertFalse(result.pending_persisted)
        self.assertEqual(result.error_code, "PENDING_FALLBACK_WRITE_FAILED")
        self.assertTrue(self.video.exists())

    def test_manual_retry_succeeds_once_and_clears_pending(self):
        formal_failure = LibraryWriteResult(False, self.library.library_path, error="denied")
        with patch.object(self.library, "add_recording", return_value=formal_failure):
            first = self.coordinator.ingest_saved_recording(
                self.video,
                metadata=self.metadata,
                diagnostic_dir=None,
                pending_id="pending-1",
                material_id="material-1",
            )
        self.assertTrue(first.pending_persisted)

        retried = self.coordinator.retry("pending-1", current_save_dir=self.video.parent)
        repeated = self.coordinator.retry("pending-1", current_save_dir=self.video.parent)

        self.assertTrue(retried.formal_indexed)
        self.assertEqual(len(self.library.load().items), 1)
        self.assertEqual(self.library.load().items[0].id, "material-1")
        self.assertEqual(load_pending(self.pending.pending_path).items, [])
        self.assertTrue(repeated.already_indexed)

    def test_startup_retry_runs_only_once_per_coordinator(self):
        self.assertTrue(self.pending.persist(self._pending_item()).ok)

        first = self.coordinator.retry_startup(self.video.parent)
        second = self.coordinator.retry_startup(self.video.parent)

        self.assertEqual(first.scanned_count, 1)
        self.assertEqual(first.succeeded_count, 1)
        self.assertFalse(first.already_ran)
        self.assertTrue(second.already_ran)
        self.assertEqual(len(self.library.load().items), 1)

    def test_retry_missing_file_keeps_pending_record(self):
        missing = self.root / "missing.mp4"
        item = self._pending_item(path=missing)
        self.assertTrue(self.pending.persist(item).ok)

        result = self.coordinator.retry(item.pending_id)

        self.assertFalse(result.formal_indexed)
        self.assertEqual(result.error_code, "VIDEO_MISSING")
        self.assertEqual(load_pending(self.pending.pending_path).items[0].status, "missing")

    def test_retry_failure_updates_attempt_and_error_for_later_retry(self):
        item = self._pending_item()
        self.assertTrue(self.pending.persist(item).ok)
        failure = LibraryWriteResult(False, self.library.library_path, error="still denied")

        with patch.object(self.library, "add_recording", return_value=failure):
            result = self.coordinator.retry(item.pending_id)

        saved = load_pending(self.pending.pending_path).items[0]
        self.assertFalse(result.formal_indexed)
        self.assertEqual(result.error_code, "FORMAL_INDEX_WRITE_FAILED")
        self.assertEqual(saved.status, "retry_failed")
        self.assertEqual(saved.attempt_count, 2)
        self.assertEqual(saved.last_error_summary, "still denied")

    def test_existing_formal_item_is_idempotent_and_cleans_pending(self):
        first = self.coordinator.ingest_saved_recording(
            self.video,
            metadata=self.metadata,
            diagnostic_dir=None,
            pending_id="first-pending",
            material_id="material-1",
        )
        self.assertTrue(first.formal_indexed)
        self.assertTrue(self.pending.persist(self._pending_item()).ok)

        result = self.coordinator.retry("pending-1", current_save_dir=self.video.parent)

        self.assertTrue(result.formal_indexed)
        self.assertTrue(result.already_indexed)
        self.assertEqual(len(self.library.load().items), 1)
        self.assertEqual(load_pending(self.pending.pending_path).items, [])

    def test_cleanup_failure_keeps_formal_success_without_duplicate(self):
        item = self._pending_item()
        self.assertTrue(self.pending.persist(item).ok)
        cleanup_failure = PendingActionResult(False, item, error="cleanup denied")

        with patch.object(self.pending, "remove", return_value=cleanup_failure):
            first = self.coordinator.retry(item.pending_id)
            second = self.coordinator.retry(item.pending_id)

        self.assertTrue(first.formal_indexed)
        self.assertEqual(first.error_code, "PENDING_CLEANUP_FAILED")
        self.assertTrue(second.already_indexed)
        self.assertEqual(len(self.library.load().items), 1)

    def _pending_item(self, *, path: Path | None = None) -> PendingRecordingItem:
        target = path or self.video
        return PendingRecordingItem(
            pending_id="pending-1",
            material_id="material-1",
            file_path=str(target),
            file_name=target.name,
            created_at="2026-07-15T10:00:00+08:00",
            queued_at="2026-07-15T10:01:00+08:00",
            updated_at="2026-07-15T10:01:00+08:00",
            status="pending",
            attempt_count=1,
            capture_mode="fullscreen",
            audio_source="none",
            duration_seconds=2.0,
            width=1920,
            height=1080,
            fps=60,
            file_size_bytes=target.stat().st_size if target.exists() else None,
        )


if __name__ == "__main__":
    unittest.main()
