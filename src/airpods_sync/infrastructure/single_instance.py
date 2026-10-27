"""Prevents two tray instances from fighting over the AirPods, using a named mutex."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

_ERROR_ALREADY_EXISTS = 183

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


class SingleInstance:
    """Holds the mutex for the lifetime of the process once acquired."""

    def __init__(self, name: str) -> None:
        self._name = f"Local\\{name}"
        self._handle: int | None = None

    def acquire(self) -> bool:
        handle = _kernel32.CreateMutexW(None, False, self._name)
        if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
            _kernel32.CloseHandle(handle)
            return False
        self._handle = handle
        return True
