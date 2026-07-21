import time
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from services.material_query import MaterialQueryCriteria, MaterialQueryEngine
from utils.pending_recording_store import PendingRecordingItem
from utils.recording_library_store import MaterialItem


class TestMaterialQueryEngine(unittest.TestCase):
    def setUp(self):
        self.engine = MaterialQueryEngine()
        self.now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone(timedelta(hours=8)))

    def test_search_matches_file_name_or_full_path_case_insensitively_without_duplicates(self):
        name_match = self._material("name", file_name="Demo Clip.mp4", file_path=r"E:\videos\plain.mp4")
        path_match = self._material("path", file_name="plain.mp4", file_path=r"E:\Demo Folder\plain.mp4")
        both_match = self._material("both", file_name="demo.mp4", file_path=r"E:\Demo\demo.mp4")
        miss = self._material("miss", file_name="other.mp4", file_path=r"E:\videos\other.mp4")

        result = self.engine.execute(
            [name_match, path_match, both_match, miss],
            [],
            MaterialQueryCriteria(keyword="  dEmO  "),
            now=self.now,
        )

        self.assertEqual({item.id for item in result.formal_items}, {"name", "path", "both"})
        self.assertEqual(result.formal_matched, 3)
        self.assertEqual(result.matched_total, 3)

    def test_search_supports_chinese_and_cross_category_filters_use_and(self):
        wanted = self._material(
            "wanted",
            file_name="课程演示.mp4",
            file_path=r"E:\中文 目录\课程演示.mp4",
            status="available",
            mode="window",
            audio_source="both",
        )
        wrong_mode = self._material(
            "wrong-mode",
            file_name="课程演示-区域.mp4",
            file_path=r"E:\中文 目录\课程演示-区域.mp4",
            status="available",
            mode="region",
            audio_source="both",
        )

        result = self.engine.execute(
            [wanted, wrong_mode],
            [],
            MaterialQueryCriteria(
                keyword="中文 目录",
                status="available",
                mode="window",
                audio="both",
            ),
            now=self.now,
        )

        self.assertEqual([item.id for item in result.formal_items], ["wanted"])

    def test_status_mode_and_audio_mapping_cover_pending_and_unknown_values(self):
        pending = self._pending("pending", status="retrying", capture_mode="unexpected", audio_source="mystery")
        failed = self._pending("failed", status="retry_failed")
        incomplete = self._pending("incomplete", status="pending", duration_seconds=None, width=None, height=None, fps=None)

        pending_result = self.engine.execute(
            [], [pending, failed, incomplete], MaterialQueryCriteria(status="pending"), now=self.now
        )
        failed_result = self.engine.execute(
            [], [pending, failed, incomplete], MaterialQueryCriteria(status="retry_failed"), now=self.now
        )
        unknown_result = self.engine.execute(
            [],
            [pending, failed, incomplete],
            MaterialQueryCriteria(status="pending", mode="unknown", audio="unknown"),
            now=self.now,
        )
        incomplete_result = self.engine.execute(
            [], [pending, failed, incomplete], MaterialQueryCriteria(status="metadata_incomplete"), now=self.now
        )

        self.assertEqual([item.pending_id for item in pending_result.pending_items], ["pending"])
        self.assertEqual([item.pending_id for item in failed_result.pending_items], ["failed"])
        self.assertEqual([item.pending_id for item in unknown_result.pending_items], ["pending"])
        self.assertEqual([item.pending_id for item in incomplete_result.pending_items], ["incomplete"])

    def test_time_ranges_use_local_timezone_and_invalid_time_only_matches_all(self):
        today = self._material("today", created_at="2026-07-18T00:00:00+08:00")
        six_days = self._material("six-days", created_at="2026-07-12T12:00:00+08:00")
        eight_days = self._material("eight-days", created_at="2026-07-10T11:59:59+08:00")
        invalid = self._material("invalid", created_at="not-a-time")

        today_result = self.engine.execute(
            [today, six_days, eight_days, invalid], [], MaterialQueryCriteria(time_range="today"), now=self.now
        )
        seven_day_result = self.engine.execute(
            [today, six_days, eight_days, invalid], [], MaterialQueryCriteria(time_range="last_7_days"), now=self.now
        )
        all_result = self.engine.execute(
            [today, six_days, eight_days, invalid], [], MaterialQueryCriteria(), now=self.now
        )

        self.assertEqual([item.id for item in today_result.formal_items], ["today"])
        self.assertEqual({item.id for item in seven_day_result.formal_items}, {"today", "six-days"})
        self.assertIn("invalid", [item.id for item in all_result.formal_items])

    def test_all_six_sort_orders_keep_missing_values_last(self):
        newest = self._material(
            "newest", created_at="2026-07-18T10:00:00+08:00", duration_sec=20, file_size_bytes=300
        )
        middle = self._material(
            "middle", created_at="2026-07-17T10:00:00+08:00", duration_sec=10, file_size_bytes=200
        )
        oldest = self._material(
            "oldest", created_at="2026-07-16T10:00:00+08:00", duration_sec=30, file_size_bytes=100
        )
        empty = self._material(
            "empty", created_at="not-a-time", duration_sec=None, file_size_bytes=None
        )
        items = [middle, empty, oldest, newest]

        expected = {
            "created_desc": ["newest", "middle", "oldest", "empty"],
            "created_asc": ["oldest", "middle", "newest", "empty"],
            "duration_desc": ["oldest", "newest", "middle", "empty"],
            "duration_asc": ["middle", "newest", "oldest", "empty"],
            "size_desc": ["newest", "middle", "oldest", "empty"],
            "size_asc": ["oldest", "middle", "newest", "empty"],
        }
        for sort_order, expected_ids in expected.items():
            with self.subTest(sort_order=sort_order):
                result = self.engine.execute(
                    items, [], MaterialQueryCriteria(sort_order=sort_order), now=self.now
                )
                self.assertEqual([item.id for item in result.formal_items], expected_ids)

    def test_equal_primary_values_use_created_desc_then_stable_id(self):
        older = self._material(
            "z-id", created_at="2026-07-17T10:00:00+08:00", duration_sec=10, file_size_bytes=100
        )
        newer_b = self._material(
            "b-id", created_at="2026-07-18T10:00:00+08:00", duration_sec=10, file_size_bytes=100
        )
        newer_a = self._material(
            "a-id", created_at="2026-07-18T10:00:00+08:00", duration_sec=10, file_size_bytes=100
        )

        result = self.engine.execute(
            [older, newer_b, newer_a], [], MaterialQueryCriteria(sort_order="duration_desc"), now=self.now
        )

        self.assertEqual([item.id for item in result.formal_items], ["a-id", "b-id", "z-id"])

    def test_pending_and_formal_are_separate_and_only_formal_is_paginated(self):
        formal = [self._material(f"formal-{index:03d}") for index in range(70)]
        pending = [self._pending(f"pending-{index:03d}") for index in range(3)]

        result = self.engine.execute(formal, pending, MaterialQueryCriteria(), visible_count=50, now=self.now)

        self.assertEqual(len(result.pending_items), 3)
        self.assertEqual(len(result.formal_items), 70)
        self.assertEqual(len(result.visible_formal_items), 50)
        self.assertEqual((result.pending_matched, result.pending_total), (3, 3))
        self.assertEqual((result.formal_matched, result.formal_total), (70, 70))
        self.assertEqual(result.matched_total, 73)
        self.assertEqual(result.source_total, 73)
        self.assertTrue(result.has_more)

    def test_execute_does_not_mutate_inputs(self):
        formal = [self._material("formal")]
        pending = [self._pending("pending")]
        formal_before = deepcopy(formal)
        pending_before = deepcopy(pending)

        self.engine.execute(formal, pending, MaterialQueryCriteria(keyword="quickrec"), now=self.now)

        self.assertEqual(formal, formal_before)
        self.assertEqual(pending, pending_before)

    def test_200_formal_and_200_pending_complete_under_100_ms(self):
        formal = [self._material(f"formal-{index:03d}", file_name=f"Demo {index:03d}.mp4") for index in range(200)]
        pending = [self._pending(f"pending-{index:03d}", file_name=f"Demo pending {index:03d}.mp4") for index in range(200)]

        started = time.perf_counter()
        result = self.engine.execute(formal, pending, MaterialQueryCriteria(keyword="demo"), now=self.now)
        elapsed_ms = (time.perf_counter() - started) * 1000

        self.assertEqual(result.matched_total, 400)
        self.assertLess(elapsed_ms, 100)

    @staticmethod
    def _material(
        item_id: str,
        *,
        file_name: str | None = None,
        file_path: str | None = None,
        status: str = "available",
        mode: str = "fullscreen",
        audio_source: str = "none",
        created_at: str = "2026-07-18T10:00:00+08:00",
        duration_sec: float | None = 10.0,
        file_size_bytes: int | None = 1024,
    ) -> MaterialItem:
        path = file_path or rf"E:\videos\QuickRec_{item_id}.mp4"
        return MaterialItem(
            id=item_id,
            file_path=path,
            file_name=file_name or path.rsplit("\\", 1)[-1],
            directory=path.rsplit("\\", 1)[0],
            mode=mode,
            audio_source=audio_source,
            created_at=created_at,
            duration_sec=duration_sec,
            width=1920,
            height=1080,
            fps=60,
            file_size_bytes=file_size_bytes,
            status=status,
        )

    @staticmethod
    def _pending(
        pending_id: str,
        *,
        file_name: str | None = None,
        status: str = "pending",
        capture_mode: str = "fullscreen",
        audio_source: str = "none",
        created_at: str = "2026-07-18T10:00:00+08:00",
        duration_seconds: float | None = 10.0,
        width: int | None = 1920,
        height: int | None = 1080,
        fps: float | None = 60,
        file_size_bytes: int | None = 1024,
    ) -> PendingRecordingItem:
        path = rf"E:\videos\QuickRec_{pending_id}.mp4"
        return PendingRecordingItem(
            pending_id=pending_id,
            material_id=f"material-{pending_id}",
            file_path=path,
            file_name=file_name or path.rsplit("\\", 1)[-1],
            created_at=created_at,
            queued_at=created_at,
            updated_at=created_at,
            status=status,
            attempt_count=1,
            capture_mode=capture_mode,
            audio_source=audio_source,
            duration_seconds=duration_seconds,
            width=width,
            height=height,
            fps=fps,
            file_size_bytes=file_size_bytes,
        )


if __name__ == "__main__":
    unittest.main()
