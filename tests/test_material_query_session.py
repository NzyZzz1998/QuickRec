import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from services.material_query import MaterialQueryCriteria, MaterialQueryEngine
from services.material_query_session import MaterialQuerySession
from utils.recording_library_store import MaterialItem


class TestMaterialQuerySession(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
        self.items = [self._item(index) for index in range(120)]
        self.session = MaterialQuerySession(page_size=50)

    def test_default_state_and_load_more_only_change_visible_count(self):
        first = self.session.execute(self.items, [], now=self.now)
        self.session.load_more(first.result.formal_matched)
        second = self.session.execute(self.items, [], now=self.now)

        self.assertEqual(first.result.visible_formal_count, 50)
        self.assertEqual(second.result.visible_formal_count, 100)
        self.assertEqual(self.session.criteria, MaterialQueryCriteria())

    def test_formal_pagination_boundaries(self):
        for count, expected_visible, expected_more in (
            (0, 0, False),
            (1, 1, False),
            (49, 49, False),
            (50, 50, False),
            (51, 50, True),
            (199, 50, True),
            (200, 50, True),
        ):
            with self.subTest(count=count):
                session = MaterialQuerySession(page_size=50)
                items = [self._item(index) for index in range(count)]
                result = session.execute(items, [], now=self.now).result
                self.assertEqual(result.visible_formal_count, expected_visible)
                self.assertEqual(result.has_more, expected_more)

    def test_any_condition_change_resets_formal_page(self):
        first = self.session.execute(self.items, [], now=self.now)
        self.session.load_more(first.result.formal_matched)

        self.session.update(keyword="quickrec")
        result = self.session.execute(self.items, [], now=self.now)

        self.assertEqual(self.session.visible_count, 50)
        self.assertEqual(result.result.visible_formal_count, 50)
        self.assertEqual(self.session.criteria.keyword, "quickrec")

    def test_each_condition_category_resets_formal_page(self):
        for field_name, value in (
            ("status", "available"),
            ("mode", "fullscreen"),
            ("audio", "none"),
            ("time_range", "last_7_days"),
            ("sort_order", "size_desc"),
        ):
            with self.subTest(field_name=field_name):
                session = MaterialQuerySession(page_size=50)
                first = session.execute(self.items, [], now=self.now)
                session.load_more(first.result.formal_matched)
                session.update(**{field_name: value})
                self.assertEqual(session.visible_count, 50)

    def test_reset_restores_default_criteria_and_page_size(self):
        self.session.update(status="available", sort_order="size_desc", keyword="demo")
        self.session.load_more(120)

        self.session.reset()

        self.assertEqual(self.session.criteria, MaterialQueryCriteria())
        self.assertEqual(self.session.visible_count, 50)

    def test_query_failure_keeps_last_successful_result_without_logging_private_values(self):
        success = self.session.execute(self.items, [], now=self.now)
        self.session.update(keyword="PRIVATE-KEYWORD")
        failing_engine = MaterialQueryEngine()
        self.session.engine = failing_engine

        with patch.object(failing_engine, "execute", side_effect=RuntimeError(r"PRIVATE C:\Secret\video.mp4")), \
                self.assertLogs("QuickRec", level="ERROR") as captured:
            failed = self.session.execute(self.items, [], now=self.now)

        self.assertFalse(failed.ok)
        self.assertIs(failed.result, success.result)
        combined = " ".join(captured.output)
        self.assertNotIn("PRIVATE-KEYWORD", combined)
        self.assertNotIn("Secret", combined)
        self.assertIn("MATERIAL_QUERY_FAILED", combined)

    def test_new_session_starts_with_defaults(self):
        self.session.update(mode="window", time_range="last_7_days")

        new_session = MaterialQuerySession(page_size=50)

        self.assertEqual(new_session.criteria, MaterialQueryCriteria())
        self.assertEqual(new_session.visible_count, 50)

    @staticmethod
    def _item(index: int) -> MaterialItem:
        path = rf"E:\videos\QuickRec_{index:03d}.mp4"
        return MaterialItem(
            id=f"item-{index:03d}",
            file_path=path,
            file_name=f"QuickRec_{index:03d}.mp4",
            directory=r"E:\videos",
            mode="fullscreen",
            audio_source="none",
            created_at=f"2026-07-18T10:{index % 60:02d}:00+00:00",
            duration_sec=float(index),
            file_size_bytes=index * 1024,
        )


if __name__ == "__main__":
    unittest.main()
