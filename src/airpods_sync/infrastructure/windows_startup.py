"""Start-with-Windows registration through the current user's Run registry key."""

from __future__ import annotations

import logging
import os
import shutil
import winreg
from pathlib import Path

log = logging.getLogger(__name__)

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "AirPodsSync"


class RunKeyStartup:
    def __init__(self, command: str) -> None:
        self._command = command

    def is_enabled(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
                value, _ = winreg.QueryValueEx(key, _VALUE_NAME)
        except FileNotFoundError:
            return False
        return value == self._command

    def enable(self) -> None:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, self._command)

    def disable(self) -> None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, _VALUE_NAME)
        except FileNotFoundError:
            pass


def default_install_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / "AirPodsSync"


class InstalledExeStartup:
    """Startup for the packaged .exe that works wherever the .exe was opened from.

    Enabling copies the running .exe into a fixed per-user folder and registers that
    copy, so startup keeps working after the original is moved or deleted (Downloads,
    a USB stick, another PC).
    """

    def __init__(self, running_exe: Path, install_dir: Path, run_key: RunKeyStartup | None = None) -> None:
        self._running_exe = running_exe
        self._installed_exe = install_dir / running_exe.name
        self._run_key = run_key or RunKeyStartup(self.command_for(self._installed_exe))

    @staticmethod
    def command_for(exe: Path) -> str:
        return f'"{exe}" tray'

    def is_enabled(self) -> bool:
        return self._installed_exe.exists() and self._run_key.is_enabled()

    def enable(self) -> None:
        if self._running_exe.resolve() != self._installed_exe.resolve():
            self._installed_exe.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self._running_exe, self._installed_exe)  # also updates an older copy
            log.info("Installed %s to %s", self._running_exe.name, self._installed_exe.parent)
        self._run_key.enable()

    def disable(self) -> None:
        self._run_key.disable()
