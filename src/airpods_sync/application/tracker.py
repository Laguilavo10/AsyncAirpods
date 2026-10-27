"""Keeps track of nearby AirPods from the advertisements they broadcast."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from airpods_sync.application.ports import Advertisement
from airpods_sync.domain import proximity_pairing
from airpods_sync.domain.airpods import AirPodsStatus


@dataclass(frozen=True)
class TrackedAirPods:
    address: str
    status: AirPodsStatus
    rssi: int
    last_seen: float


StatusChangedHandler = Callable[[TrackedAirPods], None]


class AirPodsTracker:
    """Latest status per BLE address.

    AirPods rotate their MAC address for privacy, so entries that stop
    broadcasting are forgotten after `expiry_seconds`.
    """

    def __init__(
        self,
        expiry_seconds: float = 10.0,
        clock: Callable[[], float] = time.monotonic,
        on_status_changed: StatusChangedHandler | None = None,
    ) -> None:
        self._expiry_seconds = expiry_seconds
        self._clock = clock
        self._on_status_changed = on_status_changed
        self._devices: dict[str, TrackedAirPods] = {}

    def handle(self, advertisement: Advertisement) -> None:
        data = advertisement.manufacturer_data.get(proximity_pairing.APPLE_COMPANY_ID)
        if data is None:
            return
        status = proximity_pairing.parse(data)
        if status is None:
            return

        previous = self._devices.get(advertisement.address)
        current = TrackedAirPods(advertisement.address, status, advertisement.rssi, self._clock())
        self._devices[advertisement.address] = current

        if self._on_status_changed and (previous is None or previous.status.raw != status.raw):
            self._on_status_changed(current)

    def active(self) -> list[TrackedAirPods]:
        """Non-expired devices, closest (highest RSSI) first."""
        now = self._clock()
        self._devices = {
            address: device
            for address, device in self._devices.items()
            if now - device.last_seen < self._expiry_seconds
        }
        return sorted(self._devices.values(), key=lambda device: device.rssi, reverse=True)
