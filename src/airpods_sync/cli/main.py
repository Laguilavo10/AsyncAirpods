"""`airpods-sync` entry point and composition root: the only place that picks adapters."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from airpods_sync.application.auto_switch import AutoSwitcher, AutoSwitchSettings, AutoSwitchStatus
from airpods_sync.application.headsets import find_headset, wait_until_connected
from airpods_sync.application.ports import BluetoothUnavailableError, DeviceNotFoundError, HeadsetControlError
from airpods_sync.application.runner import StatusHandler, SwitcherRunner
from airpods_sync.application.tracker import AirPodsTracker
from airpods_sync.cli import render
from airpods_sync.cli.scan import run_scan
from airpods_sync.domain.airpods import MODEL_NAMES
from airpods_sync.infrastructure.bleak_source import BleakAdvertisementSource
from airpods_sync.infrastructure.preferences import JsonPreferences
from airpods_sync.infrastructure.single_instance import SingleInstance
from airpods_sync.infrastructure.windows_media import WindowsMediaPlayback
from airpods_sync.infrastructure.windows_hotkey import MOD_ALT, MOD_CONTROL, GlobalHotkey
from airpods_sync.infrastructure.windows_audio import CoreAudioActivityMonitor, CoreAudioHeadsetController
from airpods_sync.infrastructure.windows_startup import InstalledExeStartup, RunKeyStartup, default_install_dir

_DEFAULT_DEVICE_QUERY = "AirPods"
_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AirPodsSync"
_LOG_DIR = _DATA_DIR / "logs"
_LOG_FILE = _LOG_DIR / "airpods-sync.log"
# Rotated so the log never grows without bound: about 4 MB at most
_LOG_MAX_BYTES = 1_000_000
_LOG_BACKUPS = 3
_PREFERENCES_FILE = _DATA_DIR / "preferences.json"


def _build_runner(device_query: str, settings: AutoSwitchSettings, on_status: StatusHandler) -> SwitcherRunner:
    controller = CoreAudioHeadsetController()
    device = find_headset(controller, device_query)
    tracker = AirPodsTracker()
    logging.info(
        "Tracking %s (model %s), min RSSI %d", device.name,
        "any" if device.model_id is None else MODEL_NAMES.get(device.model_id, f"0x{device.model_id:04X}"),
        settings.min_rssi,
    )
    switcher = AutoSwitcher(
        tracker, CoreAudioActivityMonitor(), controller, device.name, settings,
        model_id=device.model_id, media=WindowsMediaPlayback(),
    )
    return SwitcherRunner(BleakAdvertisementSource(), tracker, switcher, on_status)


def _startup_registration() -> RunKeyStartup | InstalledExeStartup:
    if getattr(sys, "frozen", False):  # packaged .exe (PyInstaller)
        return InstalledExeStartup(Path(sys.executable), default_install_dir())
    # pythonw.exe runs without a console window
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return RunKeyStartup(f'"{pythonw}" -m airpods_sync tray')


def _scan(args: argparse.Namespace) -> None:
    asyncio.run(run_scan(BleakAdvertisementSource(), args.raw, args.duration))


def _devices(args: argparse.Namespace) -> None:
    for device in CoreAudioHeadsetController().list_devices():
        print(f"{'connected   ' if device.connected else 'disconnected'}  {device.name}")


def _connect(args: argparse.Namespace) -> None:
    controller = CoreAudioHeadsetController()
    device = find_headset(controller, args.device)
    if device.connected:
        print(f"'{device.name}' is already connected.")
        return
    controller.connect(device.name)
    print(f"Asked Windows to connect '{device.name}'...", flush=True)
    elapsed = wait_until_connected(controller, device.name)
    if elapsed is None:
        sys.exit("Still not connected after 30 s.")
    print(f"Connected in {elapsed:.1f} s.")


def _disconnect(args: argparse.Namespace) -> None:
    controller = CoreAudioHeadsetController()
    device = find_headset(controller, args.device)
    controller.disconnect(device.name)
    print(f"Asked Windows to disconnect '{device.name}'.")


def _auto(args: argparse.Namespace) -> None:
    def print_status(status: AutoSwitchStatus) -> None:
        if status.connect_requested or status.error:
            event = "Connecting..." if status.connect_requested else status.error
            print(f"\n{time.strftime('%H:%M:%S')} {event}", flush=True)
        print(render.auto_status(status), end="\r", flush=True)

    runner = _build_runner(args.device, AutoSwitchSettings(min_rssi=args.min_rssi), print_status)
    print(f"Auto-switching '{runner.device_name}' to this PC (Ctrl+C to quit)", flush=True)
    asyncio.run(runner.run())


def _tray(args: argparse.Namespace) -> None:
    from airpods_sync.tray.app import PAUSE_MEDIA, HotkeyBinding, TrayApp  # pystray is only needed here

    instance = SingleInstance("AirPodsSyncTray")
    if not instance.acquire():
        logging.info("Tray already running; exiting")
        return
    preferences = JsonPreferences(_PREFERENCES_FILE)
    settings = AutoSwitchSettings(
        min_rssi=args.min_rssi,
        wait_for_first_use=True,
        pause_media_on_disconnect=preferences.get_bool(PAUSE_MEDIA, True),
    )
    hotkey = HotkeyBinding("Ctrl+Alt+A", lambda on_press: GlobalHotkey(MOD_CONTROL | MOD_ALT, "A", on_press))
    TrayApp(
        lambda on_status: _build_runner(args.device, settings, on_status),
        _startup_registration(),
        preferences,
        _LOG_DIR,
        hotkey,
    ).run()


def _startup(args: argparse.Namespace) -> None:
    startup = _startup_registration()
    if args.action == "on":
        startup.enable()
    elif args.action == "off":
        startup.disable()
    print(f"Start with Windows: {'on' if startup.is_enabled() else 'off'}")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="airpods-sync", description="AirPods tools for Windows.")
    commands = parser.add_subparsers(dest="command", required=True)

    scan = commands.add_parser("scan", help="show nearby AirPods status from their BLE broadcasts")
    scan.add_argument("--raw", action="store_true", help="print each packet's bytes by field")
    scan.add_argument("--duration", type=float, help="seconds to scan (default: until Ctrl+C)")
    scan.set_defaults(handler=_scan)

    devices = commands.add_parser("devices", help="list paired Bluetooth audio devices")
    devices.set_defaults(handler=_devices)

    for name, handler, help_text in (
        ("connect", _connect, "connect the AirPods to this PC"),
        ("disconnect", _disconnect, "disconnect the AirPods from this PC"),
        ("auto", _auto, "connect automatically when you wear the AirPods and the PC plays sound"),
        ("tray", _tray, "run auto-switch with a system tray icon"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument(
            "--device", default=_DEFAULT_DEVICE_QUERY,
            help=f"part of the paired device name (default: {_DEFAULT_DEVICE_QUERY})",
        )
        command.set_defaults(handler=handler)
        if name in ("auto", "tray"):
            command.add_argument(
                "--min-rssi", type=int, default=AutoSwitchSettings.min_rssi,
                help="ignore AirPods with a weaker signal (default: %(default)s)",
            )

    startup = commands.add_parser("startup", help="start the tray app with Windows")
    startup.add_argument("action", choices=("on", "off", "status"))
    startup.set_defaults(handler=_startup)

    return parser.parse_args(argv)


def _configure_logging() -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(_LOG_FILE, maxBytes=_LOG_MAX_BYTES, backupCount=_LOG_BACKUPS, encoding="utf-8")
    logging.basicConfig(
        handlers=[handler],
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    _configure_logging()
    if sys.stdout is not None:  # None under pythonw.exe
        sys.stdout.reconfigure(encoding="utf-8")
        os.system("")  # enables ANSI escape codes on the legacy Windows console

    try:
        args.handler(args)
    except KeyboardInterrupt:
        pass
    except BluetoothUnavailableError as error:
        logging.error("Bluetooth error: %s", error)
        sys.exit(f"Bluetooth error: {error}\nIs Bluetooth turned on?")
    except (DeviceNotFoundError, HeadsetControlError) as error:
        logging.error("%s", error)
        sys.exit(str(error))
