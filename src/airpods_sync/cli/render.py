"""Pure text rendering for the CLI."""

from __future__ import annotations

import time

from airpods_sync import status_text
from airpods_sync.application.auto_switch import AutoSwitchStatus
from airpods_sync.application.tracker import TrackedAirPods
from airpods_sync.domain import proximity_pairing

_CLEAR_SCREEN = "\033[2J\033[H"
_STATUS_WIDTH = 120  # pads the \r-overwritten status line so shorter text clears longer text


def table(devices: list[TrackedAirPods]) -> str:
    lines = [
        "Nearby AirPods (Ctrl+C to quit) · '+' = charging",
        "",
        f"{'Model':<24}{'Left':<9}{'Right':<9}{'Case':<9}{'In ear':<9}{'RSSI':>5}",
        "-" * 65,
    ]
    for device in devices:
        status = device.status
        in_ear = ("L" if status.left.in_ear else "-") + " " + ("R" if status.right.in_ear else "-")
        lines.append(
            f"{status.model_name:<24}"
            f"{_battery(status.left.battery, status.left.charging):<9}"
            f"{_battery(status.right.battery, status.right.charging):<9}"
            f"{_battery(status.case.battery, status.case.charging):<9}"
            f"{in_ear:<9}"
            f"{device.rssi:>5}"
        )

    if devices:
        lines += ["", "The highest RSSI (closest to 0) is most likely yours."]
    else:
        lines.append("Searching... open the case near the PC.")
    return _CLEAR_SCREEN + "\n".join(lines)


def raw_line(device: TrackedAirPods) -> str:
    raw = device.status.raw
    fields = " ".join(f"{name}={value.hex()}" for name, value in proximity_pairing.split_fields(raw))
    return (
        f"{time.strftime('%H:%M:%S')} {device.address} rssi={device.rssi:>4}  "
        f"{fields}  status(bin)={device.status.status_flags:08b}"
    )


def auto_status(status: AutoSwitchStatus) -> str:
    parts = [
        f"Wearing: {'yes' if status.wearing else 'no '}",
        f"PC audio: {'playing' if status.pc_playing else 'silent '}",
        status_text.describe(status),
    ]
    return " · ".join(parts).ljust(_STATUS_WIDTH)


def _battery(percent: int | None, charging: bool) -> str:
    text = "--" if percent is None else f"{percent}%"
    return text + (" +" if charging else "")
