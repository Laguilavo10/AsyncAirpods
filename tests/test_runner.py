import asyncio
import threading
from contextlib import asynccontextmanager

from airpods_sync.application.auto_switch import AutoSwitcher
from airpods_sync.application.runner import SwitcherRunner
from airpods_sync.application.tracker import AirPodsTracker
from tests.test_auto_switch import NAME, FakeAudio, FakeHeadset


class FakeSource:
    def __init__(self) -> None:
        self.listening = False

    @asynccontextmanager
    async def listen(self, handler):
        self.listening = True
        try:
            yield
        finally:
            self.listening = False


def test_runs_commands_from_other_threads_and_stops():
    source, headset, statuses = FakeSource(), FakeHeadset(), []
    tracker = AirPodsTracker()
    runner = SwitcherRunner(
        source, tracker, AutoSwitcher(tracker, FakeAudio(), headset, NAME), statuses.append, tick_seconds=0.01
    )

    def drive() -> None:
        while not source.listening:
            pass
        runner.submit(lambda switcher: switcher.release())
        runner.stop()

    threading.Thread(target=drive).start()
    asyncio.run(asyncio.wait_for(runner.run(), timeout=5))

    assert headset.disconnect_calls == 1
    assert statuses[-1].holding_off
    assert not source.listening
