"""Which status changes deserve a Windows notification."""

from __future__ import annotations

from dataclasses import dataclass

from airpods_sync.application.auto_switch import AutoSwitchStatus


@dataclass(frozen=True)
class Notification:
    title: str
    message: str


def notification_for(previous: AutoSwitchStatus | None, current: AutoSwitchStatus) -> Notification | None:
    """A notification for the change from `previous` to `current`, if it is worth one.

    The first status after start-up never notifies: it describes how things already
    were, not something that just happened.
    """
    if previous is None:
        return None
    if current.connected and not previous.connected:
        return Notification("AirPods on this PC", "Connected.")
    if previous.connected and not current.connected:
        return Notification("AirPods left this PC", "Auto-switch waits until the PC is silent for a while.")
    if current.error and current.error != previous.error:
        return Notification("Couldn't connect the AirPods", current.error)
    return None
