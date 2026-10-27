"""Builds dist/AirPodsSync.exe with PyInstaller: one file, no console window.

Run from the project root: .venv\\Scripts\\python.exe packaging\\build_exe.py
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib
import subprocess
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AirPodsSync.exe with PyInstaller.")
    parser.add_argument(
        "--onedir", action="store_true",
        help="build a folder (dist/AirPodsSync/) instead of a single .exe: its files never "
             "change between runs, so App Control/AppLocker can allow them by signature, "
             "hash or path, e.g. once deployed to Program Files",
    )
    parser.add_argument(
        "--sign-thumbprint",
        help="sign every .exe/.dll/.pyd with this code-signing certificate from "
             "Cert:\\CurrentUser\\My or Cert:\\LocalMachine\\My (needs --onedir: a single "
             ".exe unpacks unsigned libraries at run time)",
    )
    parser.add_argument("--timestamp-url", default="http://timestamp.digicert.com",
                        help="RFC 3161 timestamp server for --sign-thumbprint")
    args = parser.parse_args()
    if args.sign_thumbprint and not args.onedir:
        parser.error("--sign-thumbprint needs --onedir")
    return args


def _binaries(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in (".exe", ".dll", ".pyd"))


def _sign(folder: Path, thumbprint: str, timestamp_url: str) -> None:
    """Authenticode-sign the folder's binaries; already signed ones (Python's own,
    signed by the PSF) keep their signature."""
    script = f"""
$ErrorActionPreference = 'Stop'
$cert = Get-ChildItem Cert:\\CurrentUser\\My, Cert:\\LocalMachine\\My -CodeSigningCert |
    Where-Object Thumbprint -eq '{thumbprint}' | Select-Object -First 1
if (-not $cert) {{ throw 'Code-signing certificate {thumbprint} not found' }}
Get-ChildItem -LiteralPath '{folder}' -Recurse -Include *.exe, *.dll, *.pyd |
    Where-Object {{ (Get-AuthenticodeSignature $_.FullName).Status -ne 'Valid' }} |
    ForEach-Object {{
        $result = Set-AuthenticodeSignature -FilePath $_.FullName -Certificate $cert `
            -HashAlgorithm SHA256 -TimestampServer '{timestamp_url}'
        if ($result.Status -ne 'Valid') {{ throw "Signing failed for $($_.Name): $($result.StatusMessage)" }}
    }}
"""
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], check=True)


def _write_hash_manifest(folder: Path) -> Path:
    """SHA-256 of every binary, for App Control/AppLocker hash rules."""
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest().upper()}  {p.relative_to(folder)}" for p in _binaries(folder)]
    manifest = folder / "SHA256SUMS.txt"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    args = _parse_args()
    # PyInstaller silently leaves out a module that fails to import, and the .exe
    # then dies at start-up; fail the build instead
    importlib.import_module("airpods_sync.cli.main")
    importlib.import_module("airpods_sync.tray.app")
    PyInstaller.__main__.run([
        str(_ROOT / "packaging" / "launcher.py"),
        "--name", _EXE_NAME,
        "--onedir" if args.onedir else "--onefile",
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
    if args.onedir:
        folder = _ROOT / "dist" / _EXE_NAME
        if args.sign_thumbprint:
            _sign(folder, args.sign_thumbprint, args.timestamp_url)
        print(f"Hash manifest: {_write_hash_manifest(folder)}")


if __name__ == "__main__":
    main()
