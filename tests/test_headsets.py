import pytest

from airpods_sync.application.headsets import find_headset, wait_until_connected
from airpods_sync.application.ports import BluetoothAudioDevice, DeviceNotFoundError


class FakeController:
    def __init__(self, *names: str) -> None:
        self._devices = [BluetoothAudioDevice(name, False) for name in names]

    def list_devices(self) -> list[BluetoothAudioDevice]:
        return self._devices

    def set_connected(self, name: str) -> None:
        self._devices = [BluetoothAudioDevice(d.name, d.connected or d.name == name) for d in self._devices]


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_wait_reports_seconds_until_connected():
    controller, fake_time = FakeController("AirPods"), FakeTime()
    original_sleep = fake_time.sleep

    def sleep_and_connect_at_3s(seconds: float) -> None:
        original_sleep(seconds)
        if fake_time.now >= 3:
            controller.set_connected("AirPods")

    elapsed = wait_until_connected(controller, "AirPods", clock=fake_time.clock, sleep=sleep_and_connect_at_3s)

    assert elapsed == 3.0


def test_wait_gives_up_after_timeout():
    fake_time = FakeTime()

    elapsed = wait_until_connected(
        FakeController("AirPods"), "AirPods", timeout_seconds=5, clock=fake_time.clock, sleep=fake_time.sleep
    )

    assert elapsed is None


def test_matches_part_of_the_name_ignoring_case():
    controller = FakeController("WH-CH720N", "AirPods Pro de Andrés")

    assert find_headset(controller, "airpods").name == "AirPods Pro de Andrés"


def test_no_match_lists_available_devices():
    with pytest.raises(DeviceNotFoundError, match="WH-CH720N"):
        find_headset(FakeController("WH-CH720N"), "AirPods")


def test_ambiguous_match_is_rejected():
    with pytest.raises(DeviceNotFoundError, match="several"):
        find_headset(FakeController("AirPods Pro", "AirPods Max"), "AirPods")
