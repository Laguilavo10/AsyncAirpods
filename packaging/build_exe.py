"""Builds dist/AirPodsSync.exe with PyInstaller: one file, no console window.

Run from the project root: .venv\\Scripts\\python.exe packaging\\build_exe.py
"""

from __future__ import annotations

from pathlib import Path

import PyInstaller.__main__

from airpods_sync.tray.icons import IconState, draw

_ROOT = Path(__file__).resolve().parent.parent
_BUILD = _ROOT / "build"


def _write_icon() -> Path:
    icon_path = _BUILD / "airpods-sync.ico"
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    draw(IconState.ON_PC).save(icon_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    return icon_path


def main() -> None:
    PyInstaller.__main__.run([
        str(_ROOT / "packaging" / "launcher.py"),
        "--name", "AirPodsSync",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--icon", str(_write_icon()),
        "--paths", str(_ROOT / "src"),
        "--distpath", str(_ROOT / "dist"),
        "--workpath", str(_BUILD),
        "--specpath", str(_BUILD),
        # loaded dynamically, so PyInstaller's import scan misses them
        "--hidden-import", "pystray._win32",
        "--collect-submodules", "bleak.backends.winrt",
        "--collect-submodules", "winrt",
    ])


if __name__ == "__main__":
    main()
