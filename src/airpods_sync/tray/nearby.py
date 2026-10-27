"""Cards for the Nearby AirPods window: one per set of AirPods, and whether it counts as you."""

from __future__ import annotations

from dataclasses import dataclass

from airpods_sync.application.auto_switch import NearbySnapshot
from airpods_sync.application.tracker import TrackedAirPods
from airpods_sync.domain.airpods import MODEL_NAMES, AirPodsStatus


@dataclass(frozen=True)
class Battery:
    percent: int | None  # None = not reported (e.g. a closed case)
    charging: bool


@dataclass(frozen=True)
class NearbyCard:
    key: tuple  # stable while the set's state doesn't change, to update cards in place
    model_id: int
    model: str
    is_paired_model: bool
    is_followed_model: bool
    worn: str
    left: Battery
    right: Battery
    case: Battery
    rssi: int  # strongest pod
    verdict: str
    counts: bool  # this set makes the app believe you are wearing your AirPods


def model_label(model_id: int | None) -> str:
    if model_id is None:
        return "any model"
    return MODEL_NAMES.get(model_id, f"Unknown (0x{model_id:04X})")


def cards_for(snapshot: NearbySnapshot) -> list[NearbyCard]:
    """One card per set of AirPods, closest first.

    Each pod broadcasts its own packet from its own rotating address, so two pods
    that report the same model, batteries and in-ear state are taken as one set.
    Two different sets in exactly the same state would merge; that only hides a
    duplicate card.
    """
    groups: dict[tuple, list[TrackedAirPods]] = {}
    for device in snapshot.devices:  # closest first, so each group's first pod is its strongest
        groups.setdefault(_set_key(device.status), []).append(device)
    return [_card(key, pods[0], snapshot) for key, pods in groups.items()]


def strongest_of_followed_model(snapshot: NearbySnapshot) -> int | None:
    """Signal of the closest broadcast of the followed model, worn or not."""
    signals = [device.rssi for device in snapshot.devices if _model_matches(device, snapshot)]
    return max(signals, default=None)


def _set_key(status: AirPodsStatus) -> tuple:
    return (
        status.model_id,
        status.left.battery, status.right.battery, status.case.battery,
        status.left.in_ear, status.right.in_ear,
    )


def _card(key: tuple, strongest: TrackedAirPods, snapshot: NearbySnapshot) -> NearbyCard:
    status = strongest.status
    verdict, counts = _verdict(strongest, snapshot)
    return NearbyCard(
        key=key,
        model_id=status.model_id,
        model=model_label(status.model_id),
        is_paired_model=snapshot.paired_model_id is not None and status.model_id == snapshot.paired_model_id,
        is_followed_model=_model_matches(strongest, snapshot),
        worn=_worn(status),
        left=Battery(status.left.battery, status.left.charging),
        right=Battery(status.right.battery, status.right.charging),
        case=Battery(status.case.battery, status.case.charging),
        rssi=strongest.rssi,
        verdict=verdict,
        counts=counts,
    )


def _verdict(device: TrackedAirPods, snapshot: NearbySnapshot) -> tuple[str, bool]:
    # Same order as AutoSwitcher._worn_rssi
    if not _model_matches(device, snapshot):
        return "Other model · ignored", False
    if not device.status.in_ear:
        return "Not worn", False
    if device.rssi < snapshot.min_rssi:
        return "Too far · ignored", False
    return "Counts as you", True


def _model_matches(device: TrackedAirPods, snapshot: NearbySnapshot) -> bool:
    return snapshot.followed_model_id is None or device.status.model_id == snapshot.followed_model_id


def _worn(status: AirPodsStatus) -> str:
    if status.left.in_ear and status.right.in_ear:
        return "In both ears"
    if status.left.in_ear or status.right.in_ear:
        return "In the left ear" if status.left.in_ear else "In the right ear"
    if status.case.battery is not None:
        return "In or near the open case"
    return "Not in the ears"
