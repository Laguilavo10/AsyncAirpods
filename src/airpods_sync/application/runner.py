"""Drives an AutoSwitcher: scans BLE, ticks once per interval, accepts commands from other threads."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace

from airpods_sync.application.auto_switch import AutoSwitcher, AutoSwitchStatus
from airpods_sync.application.ports import AdvertisementSource, HeadsetControlError
from airpods_sync.application.tracker import AirPodsTracker

StatusHandler = Callable[[AutoSwitchStatus], None]
SwitcherCommand = Callable[[AutoSwitcher], None]


class SwitcherRunner:
    def __init__(
        self,
        source: AdvertisementSource,
        tracker: AirPodsTracker,
        switcher: AutoSwitcher,
        on_status: StatusHandler,
        tick_seconds: float = 1.0,
    ) -> None:
        self._source = source
        self._tracker = tracker
        self._switcher = switcher
        self._on_status = on_status
        self._tick_seconds = tick_seconds
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stopped: asyncio.Event | None = None

    @property
    def device_name(self) -> str:
        return self._switcher.device_name

    async def run(self) -> None:
        """Run until stop() is called. Raises BluetoothUnavailableError if scanning cannot start."""
        self._loop = asyncio.get_running_loop()
        self._stopped = asyncio.Event()
        async with self._source.listen(self._tracker.handle):
            while not self._stopped.is_set():
                self._on_status(self._switcher.tick())
                try:
                    await asyncio.wait_for(self._stopped.wait(), self._tick_seconds)
                except asyncio.TimeoutError:
                    pass

    def submit(self, command: SwitcherCommand) -> None:
        """Thread-safe: run `command` on the switcher inside the runner's loop."""
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._execute, command)

    def stop(self) -> None:
        """Thread-safe."""
        if self._loop is not None and self._stopped is not None:
            self._loop.call_soon_threadsafe(self._stopped.set)

    def _execute(self, command: SwitcherCommand) -> None:
        try:
            command(self._switcher)
        except HeadsetControlError as error:
            self._on_status(replace(self._switcher.tick(), error=str(error)))
            return
        self._on_status(self._switcher.tick())
