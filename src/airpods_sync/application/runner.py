"""Drives an AutoSwitcher: scans BLE, ticks once per interval, accepts commands from other threads."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import replace
from typing import TypeVar

from airpods_sync.application.auto_switch import AutoSwitcher, AutoSwitchStatus
from airpods_sync.application.ports import AdvertisementSource, HeadsetControlError
from airpods_sync.application.tracker import AirPodsTracker

StatusHandler = Callable[[AutoSwitchStatus], None]
SwitcherCommand = Callable[[AutoSwitcher], None]
T = TypeVar("T")


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
        # Guards the hand-over between other threads and the loop's lifetime
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stopped: asyncio.Event | None = None
        self._queued: list[SwitcherCommand] = []  # submitted before the loop started
        self._stop_requested = False

    @property
    def device_name(self) -> str:
        return self._switcher.device_name

    async def run(self) -> None:
        """Run until stop() is called. Raises BluetoothUnavailableError if scanning cannot start."""
        stopped = asyncio.Event()
        with self._lock:
            self._loop = asyncio.get_running_loop()
            self._stopped = stopped
            queued, self._queued = self._queued, []
            if self._stop_requested:
                stopped.set()
        try:
            async with self._source.listen(self._tracker.handle):
                for command in queued:
                    self._execute(command)
                while not stopped.is_set():
                    self._on_status(self._switcher.tick())
                    try:
                        await asyncio.wait_for(stopped.wait(), self._tick_seconds)
                    except asyncio.TimeoutError:
                        pass
        finally:
            with self._lock:
                self._loop = None  # later commands are dropped instead of hitting a closed loop

    def submit(self, command: SwitcherCommand) -> None:
        """Thread-safe: run `command` on the switcher inside the runner's loop.

        Commands submitted before run() starts are kept and run as soon as it does.
        """
        with self._lock:
            if self._loop is None:
                if self._stopped is None:  # not started yet
                    self._queued.append(command)
                return
            self._loop.call_soon_threadsafe(self._execute, command)

    def query(self, read: Callable[[AutoSwitcher], T]) -> Future[T]:
        """Thread-safe: run `read` on the switcher inside the runner's loop, without a tick.

        For reading state from other threads (the tracker is only touched by the loop).
        """
        future: Future[T] = Future()

        def execute() -> None:
            try:
                future.set_result(read(self._switcher))
            except Exception as error:
                future.set_exception(error)

        with self._lock:
            if self._loop is None:
                future.set_exception(RuntimeError("Auto-switch is not running"))
            else:
                self._loop.call_soon_threadsafe(execute)
        return future

    def stop(self) -> None:
        """Thread-safe; also works before run() starts."""
        with self._lock:
            self._stop_requested = True
            if self._loop is not None and self._stopped is not None:
                self._loop.call_soon_threadsafe(self._stopped.set)

    def _execute(self, command: SwitcherCommand) -> None:
        try:
            command(self._switcher)
        except HeadsetControlError as error:
            self._on_status(replace(self._switcher.tick(), error=str(error)))
            return
        self._on_status(self._switcher.tick())
