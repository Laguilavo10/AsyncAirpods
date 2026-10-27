"""AdvertisementSource backed by bleak (WinRT on Windows)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakError

from airpods_sync.application.ports import (
    Advertisement,
    AdvertisementHandler,
    BluetoothUnavailableError,
)


class BleakAdvertisementSource:
    @asynccontextmanager
    async def listen(self, handler: AdvertisementHandler) -> AsyncIterator[None]:
        def on_detection(device: BLEDevice, data: AdvertisementData) -> None:
            handler(Advertisement(device.address, data.rssi, data.manufacturer_data))

        scanner = BleakScanner(detection_callback=on_detection)
        try:
            await scanner.start()
        except (BleakError, OSError) as error:
            raise BluetoothUnavailableError(str(error)) from error

        try:
            yield
        finally:
            await scanner.stop()
