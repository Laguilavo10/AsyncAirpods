"""Builds dist/AirPodsSync.exe with PyInstaller: one file, no console window.

Run from the project root: .venv\\Scripts\\python.exe packaging\\build_exe.py
"""

from __future__ import annotations

import datetime
from pathlib import Path

import PyInstaller.__main__

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

from airpods_sync import __version__
from airpods_sync.tray.icons import IconState, draw

_ROOT = Path(__file__).resolve().parent.parent
_BUILD = _ROOT / "build"

# Shown in the .exe's Properties > Details
_PRODUCT = "AirPods Sync"
_DESCRIPTION = "AirPods Sync - AirPods auto-switching for Windows"
_AUTHOR = "Andres Laguilavo"
_COPYRIGHT = f"Copyright (c) {datetime.date.today().year} {_AUTHOR}"
_URL = "https://github.com/Laguilavo10/AsyncAirpods"
_EXE_NAME = "AirPodsSync"


def _write_icon() -> Path:
    icon_path = _BUILD / "airpods-sync.ico"
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    draw(IconState.ON_PC).save(icon_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    return icon_path


def _write_version_info() -> Path:
    """Windows version resource, generated from airpods_sync.__version__."""
    numbers = tuple(int(part) for part in __version__.split("."))
    numbers = (numbers + (0, 0, 0, 0))[:4]  # Windows wants exactly four numbers
    info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
        kids=[
            StringFileInfo([
                StringTable("040904B0", [  # U.S. English, Unicode
                    StringStruct("CompanyName", _AUTHOR),
                    StringStruct("FileDescription", _DESCRIPTION),
                    StringStruct("FileVersion", __version__),
                    StringStruct("InternalName", _EXE_NAME),
                    StringStruct("LegalCopyright", _COPYRIGHT),
                    StringStruct("OriginalFilename", f"{_EXE_NAME}.exe"),
                    StringStruct("ProductName", _PRODUCT),
                    StringStruct("ProductVersion", __version__),
                    StringStruct("Comments", _URL),
                ]),
            ]),
            VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
        ],
    )
    path = _BUILD / "version_info.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(info), encoding="utf-8")
    return path


def main() -> None:
    PyInstaller.__main__.run([
        str(_ROOT / "packaging" / "launcher.py"),
        "--name", _EXE_NAME,
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--icon", str(_write_icon()),
        "--version-file", str(_write_version_info()),
        "--paths", str(_ROOT / "src"),
        "--distpath", str(_ROOT / "dist"),
        "--workpath", str(_BUILD),
        "--specpath", str(_BUILD),
        # loaded dynamically, so PyInstaller's import scan misses them
        "--hidden-import", "pystray._win32",
        "--collect-submodules", "bleak.backends.winrt",
        "--collect-submodules", "winrt",
        # CustomTkinter reads its themes from JSON files inside the package
        "--collect-data", "customtkinter",
    ])


if __name__ == "__main__":
    main()
