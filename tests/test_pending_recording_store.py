import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import utils.pending_recording_store as store


class TestPendingRecordingStore(unittest.TestCase):
    def test_resolve_pending_file_uses_appdata_quickrec_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = store.resolve_pending_file(Path(temp_dir))

        self.assertEqual(path, Path(temp_dir) / "QuickRec" / "pending-recordings.json")

    def test_save_and_load_round_trip_preserves_item(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "含 空格" / "QuickRec_demo.mp4"
            video.parent.mkdir()
            video.write_bytes(b"video")
            path = root / "pending-recordings.json"
            item = self._item(video)

            written = store.save_pending(path, [item])
            loaded = store.load_pending(path)

        self.assertTrue(written.ok)
        self.assertTrue(loaded.ok)
        self.assertEqual(len(loaded.items), 1)
        self.assertEqual(loaded.items[0].pending_id, "pending-1")
        self.assertEqual(loaded.items[0].material_id, "material-1")
        self.assertEqual(loaded.items[0].file_path, str(video))

    def test_corrupt_pending_file_is_preserved_and_not_treated_as_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pending-recordings.json"
            path.write_text("{broken", encoding="utf-8")

            loaded = store.load_pending(path)
            self.assertFalse(loaded.ok)
            self.assertEqual(path.read_text(encoding="utf-8"), "{broken")
            self.assertIsNotNone(loaded.corrupt_path)
            self.assertTrue(loaded.corrupt_path.exists())

    def test_atomic_write_failure_keeps_previous_pending_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "pending-recordings.json"
            first = self._item(root / "first.mp4")
            second = self._item(root / "second.mp4", pending_id="pending-2", material_id="material-2")
            self.assertTrue(store.save_pending(path, [first]).ok)
            before = path.read_bytes()

            with patch("utils.pending_recording_store._atomic_write_json", side_effect=OSError("denied")):
                result = store.save_pending(path, [second])

            self.assertFalse(result.ok)
            self.assertEqual(path.read_bytes(), before)

    def test_fallback_marker_round_trip_uses_video_metadata_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "视频 目录" / "QuickRec_demo.mp4"
            video.parent.mkdir()
            video.write_bytes(b"video")
            item = self._item(video)

            written = store.save_fallback_marker(item)
            markers = store.load_fallback_markers(video.parent)

        expected = video.parent / "QuickRecMetadata" / "Pending" / "pending-1.json"
        self.assertTrue(written.ok)
        self.assertEqual(written.path, expected)
        self.assertEqual([candidate.pending_id for candidate in markers.items], ["pending-1"])

    def test_corrupt_marker_is_skipped_without_hiding_valid_marker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            video = directory / "QuickRec_demo.mp4"
            video.write_bytes(b"video")
            self.assertTrue(store.save_fallback_marker(self._item(video)).ok)
            marker_dir = directory / "QuickRecMetadata" / "Pending"
            (marker_dir / "broken.json").write_text("{broken", encoding="utf-8")

            loaded = store.load_fallback_markers(directory)

        self.assertTrue(loaded.ok)
        self.assertEqual([item.pending_id for item in loaded.items], ["pending-1"])
        self.assertEqual(loaded.skipped_items, 1)

    def test_adding_201st_item_evicts_oldest_metadata_without_deleting_video(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "pending-recordings.json"
            items = []
            for index in range(201):
                video = root / f"QuickRec_{index:03d}.mp4"
                video.write_bytes(b"video")
                items.append(
                    self._item(
                        video,
                        pending_id=f"pending-{index:03d}",
                        material_id=f"material-{index:03d}",
                        queued_at=f"2026-07-15T10:{index // 60:02d}:{index % 60:02d}+08:00",
                    )
                )

            result = store.save_pending(path, items)

            self.assertTrue(result.ok)
            self.assertEqual(len(result.items), 200)
            self.assertEqual(result.evicted_ids, ("pending-000",))
            self.assertTrue((root / "QuickRec_000.mp4").exists())

    def test_saved_document_uses_schema_one_and_utf8_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "pending-recordings.json"
            video = root / "中文.mp4"
            video.write_bytes(b"video")

            self.assertTrue(store.save_pending(path, [self._item(video)]).ok)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["max_items"], 200)
        self.assertEqual(payload["items"][0]["file_name"], "中文.mp4")

    @staticmethod
    def _item(
        path: Path,
        *,
        pending_id: str = "pending-1",
        material_id: str = "material-1",
        queued_at: str = "2026-07-15T10:00:00+08:00",
    ):
        return store.PendingRecordingItem(
            pending_id=pending_id,
            material_id=material_id,
            file_path=str(path),
            file_name=path.name,
            created_at="2026-07-15T09:59:00+08:00",
            queued_at=queued_at,
            updated_at=queued_at,
            status="pending",
            attempt_count=1,
            capture_mode="fullscreen",
            audio_source="none",
            file_size_bytes=path.stat().st_size if path.exists() else None,
        )


if __name__ == "__main__":
    unittest.main()
