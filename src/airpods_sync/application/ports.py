"""Interfaces the application needs from the outside world."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Advertisement:
    address: str
    rssi: int
    manufacturer_data: Mapping[int, bytes]


AdvertisementHandler = Callable[[Advertisement], None]


@dataclass(frozen=True)
class BluetoothAudioDevice:
    name: str
    connected: bool
    # Apple product ID (e.g. 0x2027 = AirPods Pro 3), the same value AirPods broadcast
    # over BLE; None for other brands or when the OS does not report it
    model_id: int | None = None


class BluetoothUnavailableError(RuntimeError):
    """The Bluetooth adapter is missing, off, or cannot scan."""


class DeviceNotFoundError(LookupError):
    """No paired Bluetooth audio device matches the requested name."""


class HeadsetControlError(RuntimeError):
    """The OS rejected a connect or disconnect request."""


class AdvertisementSource(Protocol):
    def listen(self, handler: AdvertisementHandler) -> AbstractAsyncContextManager[None]:
        """Deliver every received BLE advertisement to `handler` while the context is open.

        Raises BluetoothUnavailableError when scanning cannot start.
        """
        ...


class AudioActivityMonitor(Protocol):
    def is_playing(self) -> bool:
        """Whether the PC's default output device is producing sound right now."""
        ...


class MediaPlayback(Protocol):
    def pause_all(self) -> None:
        """Pause every app that is playing media. Returns at once; must not raise."""
        ...


class HeadsetController(Protocol):
    def list_devices(self) -> list[BluetoothAudioDevice]:
        """Paired Bluetooth audio devices and whether each is connected to this PC."""
        ...

    def connect(self, name: str) -> None:
        """Ask the OS to open the audio connection. Returns before it completes."""
        ...

    def disconnect(self, name: str) -> None:
        ...
