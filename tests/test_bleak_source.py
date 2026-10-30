import asyncio

import pytest
from bleak.exc import BleakError

from airpods_sync.application.ports import BluetoothUnavailableError
from airpods_sync.infrastructure import bleak_source


class FakeScanner:
    failing_modes: set[str] = set()
    started: list[str] = []

    def __init__(self, detection_callback, scanning_mode):
        self.mode = scanning_mode

    async def start(self):
        if self.mode in self.failing_modes:
            raise BleakError("Failed to start scanner. Is Bluetooth turned on?")
        self.started.append(self.mode)

    async def stop(self):
        pass


@pytest.fixture
def fake_scanner(monkeypatch):
    FakeScanner.started = []
    monkeypatch.setattr(bleak_source, "BleakScanner", FakeScanner)

    async def diagnosis():
        return "active scan: aborted (DISABLED_BY_POLICY)"

    monkeypatch.setattr(bleak_source, "describe_scan_failure", diagnosis)
    return FakeScanner


async def _listen_once(source):
    async with source.listen(lambda advertisement: None):
        pass


def test_scans_actively_when_possible(fake_scanner):
    fake_scanner.failing_modes = set()
    asyncio.run(_listen_once(bleak_source.BleakAdvertisementSource()))
    assert fake_scanner.started == ["active"]


def test_falls_back_to_passive_scanning(fake_scanner):
    fake_scanner.failing_modes = {"active"}
    asyncio.run(_listen_once(bleak_source.BleakAdvertisementSource()))
    assert fake_scanner.started == ["passive"]


def test_reports_the_windows_reason_when_no_mode_works(fake_scanner):
    fake_scanner.failing_modes = {"active", "passive"}
    with pytest.raises(BluetoothUnavailableError, match="DISABLED_BY_POLICY"):
        asyncio.run(_listen_once(bleak_source.BleakAdvertisementSource()))
