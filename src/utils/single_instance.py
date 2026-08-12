"""基于 Windows 命名内核对象的产品级单实例守卫。"""

from __future__ import annotations

import ctypes
import os
import time
from typing import Any, Protocol


class InstanceKernel(Protocol):
    def create_mutex(self, name: str) -> tuple[object, bool]: ...

    def create_activation_event(self, name: str) -> object: ...

    def signal_activation_event(self, name: str) -> bool: ...

    def consume_activation_event(self, handle: object) -> bool: ...

    def close_handle(self, handle: object) -> None: ...


class WindowsInstanceKernel:
    _ERROR_FILE_NOT_FOUND = 2
    _ERROR_ALREADY_EXISTS = 183
    _EVENT_MODIFY_STATE = 0x0002
    _WAIT_OBJECT_0 = 0x00000000
    _WAIT_TIMEOUT = 0x00000102
    _WAIT_FAILED = 0xFFFFFFFF

    def __init__(
        self,
        *,
        signal_attempts: int = 10,
        signal_retry_seconds: float = 0.05,
    ) -> None:
        if os.name != "nt":
            raise OSError("QuickRec Lite single-instance protection requires Windows")
        win_dll = getattr(ctypes, "WinDLL")
        self._kernel32: Any = win_dll("kernel32", use_last_error=True)
        self._signal_attempts = max(1, signal_attempts)
        self._signal_retry_seconds = max(0.0, signal_retry_seconds)
        self._configure_signatures()

    def _configure_signatures(self) -> None:
        from ctypes import wintypes

        self._kernel32.CreateMutexW.argtypes = [
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        self._kernel32.CreateMutexW.restype = wintypes.HANDLE
        self._kernel32.CreateEventW.argtypes = [
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        self._kernel32.CreateEventW.restype = wintypes.HANDLE
        self._kernel32.OpenEventW.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        self._kernel32.OpenEventW.restype = wintypes.HANDLE
        self._kernel32.SetEvent.argtypes = [wintypes.HANDLE]
        self._kernel32.SetEvent.restype = wintypes.BOOL
        self._kernel32.WaitForSingleObject.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
        ]
        self._kernel32.WaitForSingleObject.restype = wintypes.DWORD
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL

    def create_mutex(self, name: str) -> tuple[object, bool]:
        self._clear_last_error()
        handle = self._kernel32.CreateMutexW(None, False, name)
        if not handle:
            self._raise_last_error("CreateMutexW")
        existed = self._last_error() == self._ERROR_ALREADY_EXISTS
        return handle, existed

    def create_activation_event(self, name: str) -> object:
        handle = self._kernel32.CreateEventW(None, False, False, name)
        if not handle:
            self._raise_last_error("CreateEventW")
        return handle

    def signal_activation_event(self, name: str) -> bool:
        for attempt in range(self._signal_attempts):
            handle = self._kernel32.OpenEventW(
                self._EVENT_MODIFY_STATE,
                False,
                name,
            )
            if handle:
                try:
                    return bool(self._kernel32.SetEvent(handle))
                finally:
                    self._kernel32.CloseHandle(handle)
            if self._last_error() != self._ERROR_FILE_NOT_FOUND:
                return False
            if attempt + 1 < self._signal_attempts:
                time.sleep(self._signal_retry_seconds)
        return False

    def consume_activation_event(self, handle: object) -> bool:
        result = int(self._kernel32.WaitForSingleObject(handle, 0))
        if result == self._WAIT_OBJECT_0:
            return True
        if result == self._WAIT_TIMEOUT:
            return False
        if result == self._WAIT_FAILED:
            self._raise_last_error("WaitForSingleObject")
        raise OSError(f"unexpected wait result: {result}")

    def close_handle(self, handle: object) -> None:
        self._kernel32.CloseHandle(handle)

    @staticmethod
    def _last_error() -> int:
        return int(getattr(ctypes, "get_last_error")())

    @staticmethod
    def _clear_last_error() -> None:
        getattr(ctypes, "set_last_error")(0)

    def _raise_last_error(self, operation: str) -> None:
        error_code = self._last_error()
        raise OSError(error_code, f"{operation} failed")


class SingleInstanceGuard:
    def __init__(
        self,
        product_id: str,
        *,
        kernel: InstanceKernel | None = None,
    ) -> None:
        normalized = product_id.strip()
        if not normalized or "\\" in normalized:
            raise ValueError("product_id must be non-empty and cannot contain backslashes")
        self._kernel = kernel or WindowsInstanceKernel()
        self._mutex_name = rf"Local\{normalized}.Instance"
        self._activation_event_name = rf"Local\{normalized}.Activate"
        self._mutex_handle: object | None = None
        self._activation_event_handle: object | None = None
        self._acquire_attempted = False
        self._activation_signal_sent = False

    @property
    def mutex_name(self) -> str:
        return self._mutex_name

    @property
    def activation_event_name(self) -> str:
        return self._activation_event_name

    @property
    def is_primary(self) -> bool:
        return self._mutex_handle is not None and self._activation_event_handle is not None

    @property
    def activation_signal_sent(self) -> bool:
        return self._activation_signal_sent

    def acquire(self) -> bool:
        if self._acquire_attempted:
            return self.is_primary
        self._acquire_attempted = True
        mutex_handle, already_exists = self._kernel.create_mutex(self._mutex_name)
        if already_exists:
            try:
                self._activation_signal_sent = self._kernel.signal_activation_event(
                    self._activation_event_name
                )
            finally:
                self._kernel.close_handle(mutex_handle)
            return False
        self._mutex_handle = mutex_handle
        try:
            self._activation_event_handle = self._kernel.create_activation_event(
                self._activation_event_name
            )
        except Exception:
            self._kernel.close_handle(mutex_handle)
            self._mutex_handle = None
            raise
        return True

    def consume_activation_request(self) -> bool:
        if self._activation_event_handle is None:
            return False
        return self._kernel.consume_activation_event(self._activation_event_handle)

    def close(self) -> None:
        if self._activation_event_handle is not None:
            self._kernel.close_handle(self._activation_event_handle)
            self._activation_event_handle = None
        if self._mutex_handle is not None:
            self._kernel.close_handle(self._mutex_handle)
            self._mutex_handle = None
