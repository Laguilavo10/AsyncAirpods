"""Parser for Apple's "proximity pairing" BLE advertisement (message type 0x07).

AirPods continuously broadcast this message inside Apple's manufacturer data
(company ID 0x004C). Any nearby device can read it without connecting; it is
what drives the battery popup on an iPhone when the case is opened.

Byte layout (manufacturer data without the company ID):

  idx  content
  0    message type: 0x07
  1    remaining length (usually 0x19 = 25)
  2    prefix: 0x01 for AirPods status; other values carry a different layout
       (an Apple device near the PC sent prefix 0x06 with a changing "model")
  3-4  model ID, little-endian (bytes 27 20 = 0x2027 = AirPods Pro 3)
  5    status flags: 0x20 = left pod is broadcasting,
       0x02 = left in ear, 0x08 = right in ear (fixed sides, see below)
  6    pod batteries, one nibble each, ordered by broadcasting pod
  7    high nibble: charging flags, ordered by broadcasting pod
       · low nibble: case battery
  8    lid state / open counter
  9    color
  10   unknown
  11+  encrypted payload (needs keys from Apple's accessory protocol)

Battery nibbles go from 0 to 10 (x10 = percent); 15 means "unavailable".

The layout comes from community reverse engineering (OpenPods, AirPodsDesktop,
furiousMAC/continuity) and is not official; some bits may differ per model.
Community parsers treat the in-ear bits as relative to the broadcasting pod,
but captures from AirPods Pro 3 show them as fixed left/right: with the left
pod in the ear and the right one charging in the case, both pods broadcast
0x02 set and 0x08 clear.
"""

from __future__ import annotations

from airpods_sync.domain.airpods import AirPodsStatus, CaseStatus, PodStatus

APPLE_COMPANY_ID = 0x004C
MESSAGE_TYPE = 0x07
_STATUS_PREFIX = 0x01
_MIN_LENGTH = 11  # through byte 10; the encrypted payload is optional

_LEFT_BROADCASTING = 0x20
_LEFT_IN_EAR = 0x02
_RIGHT_IN_EAR = 0x08
_BATTERY_UNAVAILABLE = 0x0F

_FIELDS: tuple[tuple[str, slice], ...] = (
    ("type", slice(0, 1)),
    ("length", slice(1, 2)),
    ("prefix", slice(2, 3)),
    ("model", slice(3, 5)),
    ("status", slice(5, 6)),
    ("pods", slice(6, 7)),
    ("charge/case", slice(7, 8)),
    ("lid", slice(8, 9)),
    ("color", slice(9, 10)),
    ("unknown", slice(10, 11)),
    ("encrypted", slice(11, None)),
)


def parse(data: bytes) -> AirPodsStatus | None:
    """Return the decoded status, or None if `data` is not a proximity pairing
    message (e.g. it comes from an iPhone or a Mac)."""
    if len(data) < _MIN_LENGTH or data[0] != MESSAGE_TYPE or data[2] != _STATUS_PREFIX:
        return None

    flags = data[5]
    charge_flags = data[7] >> 4
    left_is_broadcasting = bool(flags & _LEFT_BROADCASTING)

    # Battery and charging nibbles are ordered by broadcasting pod
    broadcaster = (_battery_percent(data[6] & 0x0F), bool(charge_flags & 0x01))
    other = (_battery_percent(data[6] >> 4), bool(charge_flags & 0x02))
    (left_battery, left_charging), (right_battery, right_charging) = (
        (broadcaster, other) if left_is_broadcasting else (other, broadcaster)
    )

    return AirPodsStatus(
        model_id=data[3] | (data[4] << 8),
        left=PodStatus(left_battery, left_charging, in_ear=bool(flags & _LEFT_IN_EAR)),
        right=PodStatus(right_battery, right_charging, in_ear=bool(flags & _RIGHT_IN_EAR)),
        case=CaseStatus(
            battery=_battery_percent(data[7] & 0x0F),
            charging=bool(charge_flags & 0x04),
        ),
        left_is_broadcasting=left_is_broadcasting,
        status_flags=flags,
        lid=data[8],
        color=data[9],
        raw=bytes(data),
    )


def split_fields(data: bytes) -> list[tuple[str, bytes]]:
    """Split a raw message into named fields, for studying the protocol."""
    return [(name, data[span]) for name, span in _FIELDS if data[span]]


def _battery_percent(nibble: int) -> int | None:
    if nibble == _BATTERY_UNAVAILABLE:
        return None
    return min(nibble, 10) * 10
