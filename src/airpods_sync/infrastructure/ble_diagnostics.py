"""Why Windows refuses to scan for BLE advertisements.

bleak only reports "Failed to start scanner" when the WinRT watcher aborts; the
reason (BluetoothError) arrives later in the watcher's Stopped event, which bleak
drops. This probe starts a bare watcher to read it, plus the adapter's LE support.
"""

from __future__ import annotations

import asyncio

from winrt.windows.devices.bluetooth import BluetoothAdapter, BluetoothError
from winrt.windows.devices.bluetooth.advertisement import (
    BluetoothLEAdvertisementWatcher,
    BluetoothLEAdvertisementWatcherStatus,
    BluetoothLEScanningMode,
)


async def describe_scan_failure(timeout_seconds: float = 2.0) -> str:
    parts = [await _adapter_summary(timeout_seconds)]
    for mode in (BluetoothLEScanningMode.ACTIVE, BluetoothLEScanningMode.PASSIVE):
        parts.append(f"{mode.name.lower()} scan: {await _watcher_result(mode, timeout_seconds)}")
    return "; ".join(parts)


async def _adapter_summary(timeout_seconds: float) -> str:
    try:
        adapter = await asyncio.wait_for(BluetoothAdapter.get_default_async(), timeout_seconds)
    except Exception as error:  # noqa: BLE001 - diagnostics must not raise
        return f"adapter unreadable ({error!r})"
    if adapter is None:
        return "no Bluetooth adapter"
    return (
        f"adapter LE={adapter.is_low_energy_supported} "
        f"central={adapter.is_central_role_supported}"
    )


async def _watcher_result(mode: BluetoothLEScanningMode, timeout_seconds: float) -> str:
    loop = asyncio.get_running_loop()
    stopped: asyncio.Future[BluetoothError] = loop.create_future()

    def on_stopped(_sender, args) -> None:
        loop.call_soon_threadsafe(lambda: stopped.done() or stopped.set_result(args.error))

    try:
        watcher = BluetoothLEAdvertisementWatcher()
        watcher.scanning_mode = mode
        # Start() is an illegal call while no Received handler is attached.
        received_token = watcher.add_received(lambda _sender, _args: None)
        token = watcher.add_stopped(on_stopped)
        watcher.start()
    except Exception as error:  # noqa: BLE001
        return f"start raised {error!r}"
    try:
        error = await asyncio.wait_for(stopped, timeout_seconds)
        return f"aborted ({BluetoothError(error).name})"
    except TimeoutError:
        return "ok"
    finally:
        if watcher.status == BluetoothLEAdvertisementWatcherStatus.STARTED:
            watcher.stop()
        watcher.remove_stopped(token)
        watcher.remove_received(received_token)
