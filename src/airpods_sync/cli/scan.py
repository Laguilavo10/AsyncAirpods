"""`airpods-sync scan`: live view of nearby AirPods from their BLE broadcasts."""

from __future__ import annotations

import asyncio
import time

from airpods_sync.application.ports import AdvertisementSource
from airpods_sync.application.tracker import AirPodsTracker, TrackedAirPods
from airpods_sync.cli import render

_REFRESH_SECONDS = 1.0


async def run_scan(source: AdvertisementSource, raw: bool, duration: float | None) -> None:
    def print_raw(device: TrackedAirPods) -> None:
        print(render.raw_line(device), flush=True)

    tracker = AirPodsTracker(on_status_changed=print_raw if raw else None)
    deadline = time.monotonic() + duration if duration else None

    async with source.listen(tracker.handle):
        if raw:
            print("Printing AirPods packets when they change (Ctrl+C to quit)...", flush=True)
        while deadline is None or time.monotonic() < deadline:
            await asyncio.sleep(_REFRESH_SECONDS)
            if not raw:
                print(render.table(tracker.active()), flush=True)
