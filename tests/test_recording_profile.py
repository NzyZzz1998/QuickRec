from services.recording_profile import resolve_recording_profile


def test_fullscreen_120_uses_high_resolution_cap_and_120fps():
    profile = resolve_recording_profile(
        configured_fps=120,
        mode="fullscreen",
        source_size=(2560, 1440),
        quality="native",
    )

    assert profile.effective_fps == 120
    assert profile.output_size == (1920, 1080)
    assert profile.requires_120_capability is True
    assert profile.notice == "120 FPS 将以 1920×1080 输出"


def test_region_and_window_are_limited_to_60_without_mutating_config():
    region = resolve_recording_profile(
        configured_fps=120,
        mode="region",
        source_size=(1600, 900),
        quality="native",
    )
    window = resolve_recording_profile(
        configured_fps=120,
        mode="window",
        source_size=(1280, 720),
        quality="native",
    )

    assert region.effective_fps == 60
    assert window.effective_fps == 60
    assert region.notice == "区域录制本次将按 60 FPS 进行"
    assert window.notice == "窗口录制本次将按 60 FPS 进行"
    assert region.requires_120_capability is False
    assert window.requires_120_capability is False


def test_720p_and_480p_keep_120fps():
    medium = resolve_recording_profile(
        configured_fps=120,
        mode="fullscreen",
        source_size=(2560, 1440),
        quality="medium",
    )
    low = resolve_recording_profile(
        configured_fps=120,
        mode="fullscreen",
        source_size=(2560, 1440),
        quality="low",
    )

    assert medium.output_size == (1280, 720)
    assert low.output_size == (854, 480)
    assert medium.effective_fps == low.effective_fps == 120


def test_existing_30_and_60_profiles_remain_unchanged():
    profile = resolve_recording_profile(
        configured_fps=60,
        mode="fullscreen",
        source_size=(2560, 1440),
        quality="native",
    )

    assert profile.effective_fps == 60
    assert profile.output_size == (2560, 1440)
    assert profile.notice == ""
