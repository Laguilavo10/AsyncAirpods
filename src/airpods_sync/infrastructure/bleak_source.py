"""AdvertisementSource backed by bleak (WinRT on Windows)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData, AdvertisementDataCallback
from bleak.exc import BleakError

from airpods_sync.application.ports import (
    Advertisement,
    AdvertisementHandler,
    BluetoothUnavailableError,
)
from airpods_sync.infrastructure.ble_diagnostics import describe_scan_failure

log = logging.getLogger(__name__)

# Active first, as before. Some adapters or policies abort active scanning; the
# AirPods' status is in the advertisement itself, so passive scanning is enough.
_SCANNING_MODES = ("active", "passive")


class BleakAdvertisementSource:
    def __init__(self) -> None:
        self._logged_mode: str | None = None

    @asynccontextmanager
    async def listen(self, handler: AdvertisementHandler) -> AsyncIterator[None]:
        def on_detection(device: BLEDevice, data: AdvertisementData) -> None:
            handler(Advertisement(device.address, data.rssi, data.manufacturer_data))

        scanner = await self._start(on_detection)
        try:
            yield
        finally:
            await scanner.stop()

    async def _start(self, callback: AdvertisementDataCallback) -> BleakScanner:
        failures = []
        for mode in _SCANNING_MODES:
            scanner = BleakScanner(detection_callback=callback, scanning_mode=mode)
            try:
                await scanner.start()
            except (BleakError, OSError) as error:
                failures.append(f"{mode}: {error}")
                continue
            if mode != self._logged_mode:
                log.info("Scanning for BLE advertisements (%s)", mode)
                self._logged_mode = mode
            return scanner

        diagnosis = await describe_scan_failure()
        log.warning("BLE scanning unavailable: %s", diagnosis)
        raise BluetoothUnavailableError(f"{failures[0]} ({diagnosis})")
