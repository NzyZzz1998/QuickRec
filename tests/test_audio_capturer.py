import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recorder.audio_capturer import AudioCapturer, AudioSource


class TestAudioCapturer(unittest.TestCase):
    def test_find_loopback_prefers_default_speaker_device_id(self):
        default_speaker = SimpleNamespace(
            id="default-device-id",
            name="扬声器 (HECATE G1500 BAR)",
        )
        wrong_loopback = SimpleNamespace(
            id="other-device-id",
            name="扬声器 (HECATE GS03 GAMING SOUND CARD)",
            isloopback=True,
            channels=8,
        )
        expected_loopback = SimpleNamespace(
            id="default-device-id",
            name="扬声器 (HECATE G1500 BAR)",
            isloopback=True,
            channels=2,
        )
        soundcard = SimpleNamespace(
            default_speaker=lambda: default_speaker,
            all_microphones=lambda include_loopback: [wrong_loopback, expected_loopback],
        )
        capturer = AudioCapturer(AudioSource.SYSTEM, ".")

        with patch.dict(sys.modules, {"soundcard": soundcard}):
            microphone, sample_rate = capturer._find_loopback_mic()

        self.assertIs(microphone, expected_loopback)
        self.assertEqual(sample_rate, 48000)


if __name__ == "__main__":
    unittest.main()
