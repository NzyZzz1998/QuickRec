from dataclasses import dataclass
from enum import Enum


class WindowFailureReason(Enum):
    NONE = "none"
    UNSUPPORTED_WINDOW = "unsupported_window"
    RECT_UNAVAILABLE = "rect_unavailable"
    FOREGROUND_DENIED = "foreground_denied"
    CAPTURE_BACKEND_FAILED = "capture_backend_failed"


@dataclass(frozen=True)
class WindowRecordingDiagnostic:
    reason: WindowFailureReason = WindowFailureReason.NONE
    hwnd: int = 0
    title: str = ""
    mode: str = ""
    stage: str = ""
    rect: tuple[int, int, int, int] | None = None
    foreground_result: str = ""
