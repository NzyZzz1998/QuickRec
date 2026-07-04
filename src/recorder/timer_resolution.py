import ctypes
import logging

logger = logging.getLogger("QuickRec")


class TimerResolution:
    def __init__(self, milliseconds: int = 1):
        self._milliseconds = milliseconds
        self._active = False

    def begin(self) -> None:
        if self._active:
            return
        try:
            ctypes.windll.winmm.timeBeginPeriod(self._milliseconds)
            self._active = True
        except Exception as e:
            logger.warning(f"timeBeginPeriod failed: {e}")

    def end(self) -> None:
        if not self._active:
            return
        try:
            ctypes.windll.winmm.timeEndPeriod(self._milliseconds)
        except Exception as e:
            logger.warning(f"timeEndPeriod failed: {e}")
        finally:
            self._active = False

    def is_active(self) -> bool:
        return self._active
