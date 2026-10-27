from airpods_sync.application.ports import Advertisement
from airpods_sync.application.tracker import AirPodsTracker
from airpods_sync.domain.proximity_pairing import APPLE_COMPANY_ID

AIRPODS_MESSAGE = bytes([0x07, 0x19, 0x01, 0x14, 0x20,0x2B, 0x98, 0x45, 0x31, 0x00, 0x05]) + bytes(16)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def advertisement(address: str, rssi: int = -50, data: bytes = AIRPODS_MESSAGE) -> Advertisement:
    return Advertisement(address, rssi, {APPLE_COMPANY_ID: data})


def test_ignores_non_airpods_advertisements():
    tracker = AirPodsTracker()

    tracker.handle(Advertisement("A", -40, {}))
    tracker.handle(advertisement("B", data=bytes([0x10, 0x05, 0x01])))

    assert tracker.active() == []


def test_sorts_by_signal_strength():
    tracker = AirPodsTracker()

    tracker.handle(advertisement("far", rssi=-80))
    tracker.handle(advertisement("near", rssi=-40))

    assert [device.address for device in tracker.active()] == ["near", "far"]


def test_forgets_devices_that_stop_broadcasting():
    clock = FakeClock()
    tracker = AirPodsTracker(expiry_seconds=10, clock=clock)
    tracker.handle(advertisement("old"))

    clock.now = 11
    tracker.handle(advertisement("new"))

    assert [device.address for device in tracker.active()] == ["new"]


def test_notifies_only_when_status_changes():
    changes = []
    tracker = AirPodsTracker(on_status_changed=changes.append)

    tracker.handle(advertisement("A"))
    tracker.handle(advertisement("A"))
    changed = bytearray(AIRPODS_MESSAGE)
    changed[5] = 0x20  # pods taken out of the ears
    tracker.handle(advertisement("A", data=bytes(changed)))

    assert len(changes) == 2
    assert not changes[-1].status.in_ear
