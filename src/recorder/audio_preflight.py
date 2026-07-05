from dataclasses import dataclass

from recorder.audio_capturer import AudioSource


@dataclass(frozen=True)
class AudioPreflightResult:
    requested_source: str
    final_source: str
    system_available: bool
    microphone_available: bool
    degraded: bool = False
    reason: str = ""


def plan_audio_source(
    requested_source: str,
    system_available: bool,
    microphone_available: bool,
) -> AudioPreflightResult:
    if requested_source == AudioSource.NONE:
        return AudioPreflightResult(
            requested_source=requested_source,
            final_source=AudioSource.NONE,
            system_available=system_available,
            microphone_available=microphone_available,
        )

    if requested_source == AudioSource.SYSTEM:
        if system_available:
            return AudioPreflightResult(requested_source, AudioSource.SYSTEM, True, microphone_available)
        return AudioPreflightResult(
            requested_source,
            AudioSource.NONE,
            False,
            microphone_available,
            degraded=True,
            reason="system_unavailable",
        )

    if requested_source == AudioSource.MICROPHONE:
        if microphone_available:
            return AudioPreflightResult(requested_source, AudioSource.MICROPHONE, system_available, True)
        return AudioPreflightResult(
            requested_source,
            AudioSource.NONE,
            system_available,
            False,
            degraded=True,
            reason="microphone_unavailable",
        )

    if requested_source == AudioSource.BOTH:
        if system_available and microphone_available:
            return AudioPreflightResult(requested_source, AudioSource.BOTH, True, True)
        if microphone_available:
            return AudioPreflightResult(
                requested_source,
                AudioSource.MICROPHONE,
                False,
                True,
                degraded=True,
                reason="system_unavailable",
            )
        if system_available:
            return AudioPreflightResult(
                requested_source,
                AudioSource.SYSTEM,
                True,
                False,
                degraded=True,
                reason="microphone_unavailable",
            )
        return AudioPreflightResult(
            requested_source,
            AudioSource.NONE,
            False,
            False,
            degraded=True,
            reason="no_audio_devices",
        )

    return AudioPreflightResult(
        requested_source=requested_source,
        final_source=AudioSource.NONE,
        system_available=system_available,
        microphone_available=microphone_available,
        degraded=True,
        reason="unknown_audio_source",
    )
