"""Finding the user's headset among the paired Bluetooth audio devices."""

from __future__ import annotations

import time
from collections.abc import Callable

from airpods_sync.application.ports import BluetoothAudioDevice, DeviceNotFoundError, HeadsetController


def find_headset(controller: HeadsetController, query: str) -> BluetoothAudioDevice:
    """The single paired device whose name contains `query` (case-insensitive)."""
    devices = controller.list_devices()
    matches = [device for device in devices if query.casefold() in device.name.casefold()]

    if len(matches) == 1:
        return matches[0]
    if not matches:
        available = ", ".join(device.name for device in devices) or "none"
        raise DeviceNotFoundError(f"No paired Bluetooth audio device matches '{query}'. Available: {available}")
    names = ", ".join(device.name for device in matches)
    raise DeviceNotFoundError(f"'{query}' matches several devices ({names}). Use a more specific name.")


def wait_until_connected(
    controller: HeadsetController,
    name: str,
    timeout_seconds: float = 30.0,
    poll_seconds: float = 0.5,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> float | None:
    """Seconds until `name` shows up as connected, or None if `timeout_seconds` passes first."""
    start = clock()
    while clock() - start < timeout_seconds:
        if any(device.name == name and device.connected for device in controller.list_devices()):
            return clock() - start
        sleep(poll_seconds)
    return None
