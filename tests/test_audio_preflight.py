import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recorder.audio_capturer import AudioSource
from recorder.audio_preflight import plan_audio_source


class TestAudioPreflight(unittest.TestCase):
    def test_none_source_stays_none_without_degradation(self):
        result = plan_audio_source(
            AudioSource.NONE,
            system_available=False,
            microphone_available=False,
        )

        self.assertEqual(result.requested_source, AudioSource.NONE)
        self.assertEqual(result.final_source, AudioSource.NONE)
        self.assertFalse(result.degraded)
        self.assertEqual(result.reason, "")

    def test_both_degrades_to_microphone_when_system_unavailable(self):
        result = plan_audio_source(
            AudioSource.BOTH,
            system_available=False,
            microphone_available=True,
        )

        self.assertEqual(result.requested_source, AudioSource.BOTH)
        self.assertEqual(result.final_source, AudioSource.MICROPHONE)
        self.assertTrue(result.degraded)
        self.assertEqual(result.reason, "system_unavailable")

    def test_both_degrades_to_system_when_microphone_unavailable(self):
        result = plan_audio_source(
            AudioSource.BOTH,
            system_available=True,
            microphone_available=False,
        )

        self.assertEqual(result.final_source, AudioSource.SYSTEM)
        self.assertTrue(result.degraded)
        self.assertEqual(result.reason, "microphone_unavailable")

    def test_both_degrades_to_none_when_no_devices_available(self):
        result = plan_audio_source(
            AudioSource.BOTH,
            system_available=False,
            microphone_available=False,
        )

        self.assertEqual(result.final_source, AudioSource.NONE)
        self.assertTrue(result.degraded)
        self.assertEqual(result.reason, "no_audio_devices")

    def test_single_unavailable_source_degrades_to_none(self):
        result = plan_audio_source(
            AudioSource.SYSTEM,
            system_available=False,
            microphone_available=True,
        )

        self.assertEqual(result.final_source, AudioSource.NONE)
        self.assertTrue(result.degraded)
        self.assertEqual(result.reason, "system_unavailable")


if __name__ == "__main__":
    unittest.main()
