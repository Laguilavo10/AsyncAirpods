"""One-line, user-facing description of what auto-switch is doing or waiting for.

Shared by the terminal and tray presentations.
"""

from __future__ import annotations

import math

from airpods_sync.application.auto_switch import AutoSwitchSettings, AutoSwitchStatus
from airpods_sync.application.ports import BluetoothUnavailableError, DeviceNotFoundError


def describe_start_failure(error: Exception) -> str:
    """Why auto-switch couldn't start, short enough for the tray tooltip."""
    if isinstance(error, BluetoothUnavailableError):
        return "Bluetooth is off or not ready"
    if isinstance(error, DeviceNotFoundError):
        return "AirPods not found among the paired devices"
    return str(error) or type(error).__name__


def describe(status: AutoSwitchStatus, settings: AutoSwitchSettings = AutoSwitchSettings()) -> str:
    if status.error:
        return f"Error: {status.error}"
    if status.connected:
        return "AirPods on this PC"
    if status.connecting:
        return f"Connecting... {_seconds(status.connecting_for or 0)}"
    if not status.enabled:
        return "Auto-switch off · use 'Use on PC' to connect"
    if not status.started:
        return "Auto-switch starts after your first 'Use on PC'"
    if status.holding_off:
        if status.resume_in is None:
            silence = _seconds(settings.resume_after_silence_seconds)
            off = _seconds(settings.resume_after_not_wearing_seconds)
            return f"On hold · resumes after {silence} of PC silence or {off} without the AirPods on"
        return f"On hold · auto-switch resumes in {_seconds(status.resume_in)}"
    if not status.wearing:
        return "Ready · put the AirPods on"
    if status.connect_in is None:
        return "Ready · connects when the PC plays sound"
    return f"Connecting in {_seconds(status.connect_in)}"


def _seconds(value: float) -> str:
    return f"{math.ceil(value)} s"
