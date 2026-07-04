import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recorder.timer_resolution import TimerResolution


class FakeWinmm:
    def __init__(self):
        self.begin_calls = []
        self.end_calls = []

    def timeBeginPeriod(self, milliseconds):
        self.begin_calls.append(milliseconds)

    def timeEndPeriod(self, milliseconds):
        self.end_calls.append(milliseconds)


class FakeWindll:
    def __init__(self):
        self.winmm = FakeWinmm()


class RaisingWinmm:
    def timeBeginPeriod(self, _milliseconds):
        raise RuntimeError("begin failed")

    def timeEndPeriod(self, _milliseconds):
        raise RuntimeError("end failed")


class TestTimerResolution(unittest.TestCase):
    def test_begin_and_end_are_idempotent(self):
        fake_windll = FakeWindll()
        with patch("recorder.timer_resolution.ctypes.windll", fake_windll, create=True):
            timer = TimerResolution(milliseconds=1)

            timer.begin()
            timer.begin()
            self.assertTrue(timer.is_active())
            timer.end()
            timer.end()

        self.assertEqual(fake_windll.winmm.begin_calls, [1])
        self.assertEqual(fake_windll.winmm.end_calls, [1])
        self.assertFalse(timer.is_active())

    def test_begin_failure_leaves_timer_inactive(self):
        fake_windll = type("Windll", (), {"winmm": RaisingWinmm()})()
        with patch("recorder.timer_resolution.ctypes.windll", fake_windll, create=True):
            timer = TimerResolution()

            timer.begin()
            timer.end()

        self.assertFalse(timer.is_active())

    def test_end_failure_still_marks_timer_inactive(self):
        fake_windll = type("Windll", (), {"winmm": RaisingWinmm()})()
        with patch("recorder.timer_resolution.ctypes.windll", fake_windll, create=True):
            timer = TimerResolution()
            timer._active = True

            timer.end()

        self.assertFalse(timer.is_active())


if __name__ == "__main__":
    unittest.main()
