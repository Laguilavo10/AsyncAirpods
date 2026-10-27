"""Domain model for the status AirPods broadcast over BLE."""

from __future__ import annotations

from dataclasses import dataclass

# Apple USB/Bluetooth product IDs; Windows shows the same value as `pid&XXXX`
MODEL_NAMES: dict[int, str] = {
    0x2002: "AirPods (1st gen)",
    0x200F: "AirPods (2nd gen)",
    0x2013: "AirPods (3rd gen)",
    0x200E: "AirPods Pro",
    0x2014: "AirPods Pro 2",
    0x2024: "AirPods Pro 2 (USB-C)",
    0x2027: "AirPods Pro 3",
    0x200A: "AirPods Max",
}


@dataclass(frozen=True)
class PodStatus:
    battery: int | None  # percent; None when the pod does not report it
    charging: bool
    in_ear: bool


@dataclass(frozen=True)
class CaseStatus:
    battery: int | None
    charging: bool


@dataclass(frozen=True)
class AirPodsStatus:
    model_id: int
    left: PodStatus
    right: PodStatus
    case: CaseStatus
    left_is_broadcasting: bool
    status_flags: int
    lid: int
    color: int
    raw: bytes

    @property
    def model_name(self) -> str:
        return MODEL_NAMES.get(self.model_id, f"Unknown (0x{self.model_id:04X})")

    @property
    def in_ear(self) -> bool:
        return self.left.in_ear or self.right.in_ear
