"""System-wide keyboard shortcut through Win32 RegisterHotKey.

RegisterHotKey without a window posts WM_HOTKEY to the registering thread's
message queue, so the hotkey lives on its own thread with its own message loop.
"""

from __future__ import annotations

import ctypes
import logging
import threading
from collections.abc import Callable
from ctypes import wintypes

log = logging.getLogger(__name__)

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
_MOD_NOREPEAT = 0x4000  # holding the keys down fires once
_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012
_HOTKEY_ID = 1

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
_user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
_user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_kernel32 = ctypes.WinDLL("kernel32")


class GlobalHotkey:
    def __init__(self, modifiers: int, key: str, on_press: Callable[[], None]) -> None:
        self._modifiers = modifiers | _MOD_NOREPEAT
        self._virtual_key = ord(key.upper())  # letters and digits share their ASCII code
        self._on_press = on_press
        self._thread_id: int | None = None

    def start(self) -> bool:
        """Register the hotkey; False if another app already owns this combination."""
        registered = threading.Event()
        outcome: list[bool] = []

        def loop() -> None:
            self._thread_id = _kernel32.GetCurrentThreadId()
            ok = bool(_user32.RegisterHotKey(None, _HOTKEY_ID, self._modifiers, self._virtual_key))
            outcome.append(ok)
            registered.set()
            if not ok:
                return
            message = wintypes.MSG()
            while _user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == _WM_HOTKEY:
                    try:
                        self._on_press()
                    except Exception:  # a failing handler must not kill the hotkey
                        log.exception("Hotkey handler failed")
            _user32.UnregisterHotKey(None, _HOTKEY_ID)

        threading.Thread(target=loop, name="hotkey", daemon=True).start()
        registered.wait()
        return outcome[0]

    def stop(self) -> None:
        if self._thread_id is not None:
            _user32.PostThreadMessageW(self._thread_id, _WM_QUIT, 0, 0)
