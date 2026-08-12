from recorder.frame_schedule import due_frame_count


def test_schedule_does_not_oversubmit_when_capture_polling_is_faster():
    assert due_frame_count(
        elapsed_seconds=0.004,
        target_fps=60,
        submitted_frames=1,
    ) == 0
    assert due_frame_count(
        elapsed_seconds=0.017,
        target_fps=60,
        submitted_frames=1,
    ) == 1


def test_schedule_catches_up_after_a_short_delay():
    assert due_frame_count(
        elapsed_seconds=0.100,
        target_fps=60,
        submitted_frames=2,
    ) == 5


def test_schedule_rejects_invalid_inputs():
    import pytest

    with pytest.raises(ValueError):
        due_frame_count(elapsed_seconds=-0.001, target_fps=60, submitted_frames=0)
    with pytest.raises(ValueError):
        due_frame_count(elapsed_seconds=0.0, target_fps=0, submitted_frames=0)
