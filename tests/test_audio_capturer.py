import sys
import tempfile
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

    def test_system_track_records_stream_start_time(self):
        class FakeRecorder:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

        loopback = SimpleNamespace(
            channels=2,
            recorder=lambda samplerate: FakeRecorder(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            capturer = AudioCapturer(AudioSource.SYSTEM, temp_dir)
            with patch.object(capturer, "_find_loopback_mic", return_value=(loopback, 48000)), \
                    patch.object(capturer, "_estimate_system_output_latency", return_value=0.055), \
                    patch("recorder.audio_capturer.time.perf_counter", return_value=12.5):
                self.assertTrue(capturer._start_system("audio"))

            timings = capturer.get_track_start_times()
            latencies = capturer.get_track_latency_seconds()
            self.assertEqual(timings[capturer._system_temp_path], 12.5)
            self.assertEqual(latencies[capturer._system_temp_path], 0.055)
            capturer._cleanup()

    def test_system_output_latency_uses_buffer_and_default_device_period(self):
        player = SimpleNamespace(
            buffersize=2238,
            deviceperiod=(0.01, 0.003),
        )
        soundcard = SimpleNamespace(
            default_speaker=lambda: SimpleNamespace(
                player=lambda samplerate: player,
            ),
        )

        with patch.dict(sys.modules, {"soundcard": soundcard}):
            latency = AudioCapturer._estimate_system_output_latency(48000)

        self.assertAlmostEqual(latency, 2238 / 48000 + 0.01)


if __name__ == "__main__":
    unittest.main()
