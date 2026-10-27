"""System tray app: status icon plus a menu to switch the AirPods by hand."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pystray

from airpods_sync import __version__, status_text
from airpods_sync.application.auto_switch import AutoSwitchStatus
from airpods_sync.application.runner import StatusHandler, SwitcherRunner
from airpods_sync.tray.icons import IconState, draw
from airpods_sync.tray.notifications import notification_for

log = logging.getLogger(__name__)

RunnerFactory = Callable[[StatusHandler], SwitcherRunner]


class StartupRegistration(Protocol):
    def is_enabled(self) -> bool: ...
    def enable(self) -> None: ...
    def disable(self) -> None: ...


class Preferences(Protocol):
    def get_bool(self, name: str, default: bool) -> bool: ...
    def set_bool(self, name: str, value: bool) -> None: ...


class Hotkey(Protocol):
    def start(self) -> bool: ...
    def stop(self) -> None: ...


@dataclass(frozen=True)
class HotkeyBinding:
    label: str  # shown in the menu, e.g. "Ctrl+Alt+A"
    create: Callable[[Callable[[], None]], Hotkey]


NOTIFICATIONS = "notifications"
PAUSE_MEDIA = "pause_media_on_disconnect"


class TrayApp:
    def __init__(
        self,
        build_runner: RunnerFactory,
        startup: StartupRegistration,
        preferences: Preferences,
        log_dir: Path,
        hotkey: HotkeyBinding | None = None,
    ) -> None:
        self._log_dir = log_dir
        self._build_runner = build_runner
        self._startup = startup
        self._preferences = preferences
        self._hotkey_binding = hotkey
        self._hotkey: Hotkey | None = None
        self._runner: SwitcherRunner | None = None
        self._status: AutoSwitchStatus | None = None
        self._fatal_error: str | None = None
        self._logged_error: str | None = None
        self._auto_enabled = True
        self._icon_state = IconState.AWAY
        self._icon = pystray.Icon("airpods-sync", draw(self._icon_state), "AirPods Sync", self._menu())

    def run(self) -> None:
        """Blocks until Quit. The switcher runs on pystray's setup thread."""
        self._start_hotkey()
        try:
            self._icon.run(setup=self._run_switcher)
        finally:
            if self._hotkey:
                self._hotkey.stop()

    def _start_hotkey(self) -> None:
        binding = self._hotkey_binding
        if binding is None:
            return
        hotkey = binding.create(self._toggle_pc)
        if hotkey.start():
            self._hotkey = hotkey
            log.info("Hotkey %s toggles the AirPods", binding.label)
        else:
            log.warning("Hotkey %s is taken by another app", binding.label)
            self._hotkey_binding = None  # don't advertise it in the menu

    def _run_switcher(self, icon: pystray.Icon) -> None:
        icon.visible = True
        try:
            self._runner = self._build_runner(self._on_status)
            asyncio.run(self._runner.run())
        except Exception as error:  # thread boundary: surface it in the tray instead of dying silently
            log.exception("Auto-switch stopped")
            self._fatal_error = str(error)
            self._refresh()

    def _menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(lambda _: self._status_text(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Use on PC", self._use_pc, default=True),
            pystray.MenuItem("Release", self._release),
            pystray.MenuItem(lambda _: self._hotkey_hint(), None, enabled=False, visible=lambda _: bool(self._hotkey)),
            pystray.MenuItem("Auto-switch", self._toggle_auto, checked=lambda _: self._auto_enabled),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Pause media on disconnect", self._toggle_pause_media, checked=lambda _: self._pause_media_on()
            ),
            pystray.MenuItem("Notifications", self._toggle_notifications, checked=lambda _: self._notifications_on()),
            pystray.MenuItem("Start with Windows", self._toggle_startup, checked=lambda _: self._startup.is_enabled()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open log folder", self._open_log_folder),
            pystray.MenuItem(f"AirPods Sync {__version__}", None, enabled=False),
            pystray.MenuItem("Quit", self._quit),
        )

    def _use_pc(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        if self._runner:
            self._runner.submit(lambda switcher: switcher.use_pc())

    def _release(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        if self._runner:
            self._runner.submit(lambda switcher: switcher.release())

    def _toggle_pc(self) -> None:
        if self._runner:
            self._runner.submit(lambda switcher: switcher.toggle_pc())

    def _hotkey_hint(self) -> str:
        return f"{self._hotkey_binding.label}: use on PC / release" if self._hotkey_binding else ""

    def _notifications_on(self) -> bool:
        return self._preferences.get_bool(NOTIFICATIONS, True)

    def _toggle_notifications(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        try:
            self._preferences.set_bool(NOTIFICATIONS, not self._notifications_on())
        except OSError:
            log.exception("Couldn't save the notifications preference")

    def _pause_media_on(self) -> bool:
        return self._preferences.get_bool(PAUSE_MEDIA, True)

    def _toggle_pause_media(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        enabled = not self._pause_media_on()
        try:
            self._preferences.set_bool(PAUSE_MEDIA, enabled)
        except OSError:
            log.exception("Couldn't save the pause media preference")
            return
        if self._runner:
            self._runner.submit(lambda switcher: switcher.set_pause_media(enabled))

    def _toggle_auto(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._auto_enabled = not self._auto_enabled
        enabled = self._auto_enabled
        if self._runner:
            self._runner.submit(lambda switcher: switcher.set_enabled(enabled))

    def _toggle_startup(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        try:
            if self._startup.is_enabled():
                self._startup.disable()
                log.info("Start with Windows disabled")
            else:
                self._startup.enable()
                log.info("Start with Windows enabled")
        except OSError:  # the menu item stays unchecked; the log has the reason
            log.exception("Couldn't change Start with Windows")

    def _open_log_folder(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        try:
            os.startfile(self._log_dir)
        except OSError:
            log.exception("Couldn't open the log folder")

    def _quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        if self._runner:
            self._runner.stop()
        icon.stop()

    def _on_status(self, status: AutoSwitchStatus) -> None:
        changed = status != self._status
        notification = notification_for(self._status, status)
        if notification and self._notifications_on():
            self._icon.notify(notification.message, notification.title)
        self._status = status
        if status.error and status.error != self._logged_error:
            log.warning(status.error)
        self._logged_error = status.error
        if changed:
            self._refresh()

    def _refresh(self) -> None:
        state = self._current_icon_state()
        if state != self._icon_state:
            self._icon_state = state
            self._icon.icon = draw(state)
        self._icon.title = f"AirPods Sync\n{self._status_text()}"[:127]  # Windows tooltip limit
        self._icon.update_menu()

    def _current_icon_state(self) -> IconState:
        status = self._status
        if self._fatal_error or (status and status.error):
            return IconState.ERROR
        if status and status.connected:
            return IconState.ON_PC
        if status and status.connecting:
            return IconState.CONNECTING
        if status and (not status.enabled or not status.started or status.holding_off):
            return IconState.PAUSED
        return IconState.AWAY

    def _status_text(self) -> str:
        if self._fatal_error:
            return f"Error: {self._fatal_error}"
        if self._status is None:
            return "Starting..."
        return status_text.describe(self._status)
