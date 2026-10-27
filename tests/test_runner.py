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


def test_query_reads_the_switcher_from_another_thread():
    source, statuses, answers = FakeSource(), [], []
    tracker = AirPodsTracker()
    runner = SwitcherRunner(
        source, tracker, AutoSwitcher(tracker, FakeAudio(), FakeHeadset(), NAME), statuses.append, tick_seconds=0.01
    )

    def drive() -> None:
        while not source.listening:
            pass
        answers.append(runner.query(lambda switcher: switcher.device_name).result(timeout=5))
        runner.stop()

    threading.Thread(target=drive).start()
    asyncio.run(asyncio.wait_for(runner.run(), timeout=5))

    assert answers == [NAME]


def test_query_before_running_fails_instead_of_hanging():
    tracker = AirPodsTracker()
    runner = SwitcherRunner(FakeSource(), tracker, AutoSwitcher(tracker, FakeAudio(), FakeHeadset(), NAME), print)

    assert runner.query(lambda switcher: switcher.device_name).exception() is not None


def test_commands_submitted_before_start_run_once_it_starts():
    source, headset, statuses = FakeSource(), FakeHeadset(), []
    tracker = AirPodsTracker()
    runner = SwitcherRunner(
        source, tracker, AutoSwitcher(tracker, FakeAudio(), headset, NAME), statuses.append, tick_seconds=0.01
    )
    runner.submit(lambda switcher: switcher.set_enabled(False))
    runner.stop()  # also accepted before the start

    asyncio.run(asyncio.wait_for(runner.run(), timeout=5))

    assert not statuses[-1].enabled


def test_commands_after_the_runner_ended_are_dropped():
    tracker = AirPodsTracker()
    runner = SwitcherRunner(FakeSource(), tracker, AutoSwitcher(tracker, FakeAudio(), FakeHeadset(), NAME), print)
    runner.stop()
    asyncio.run(asyncio.wait_for(runner.run(), timeout=5))

    runner.submit(lambda switcher: switcher.release())  # must not raise on the closed loop
    assert runner.query(lambda switcher: switcher.device_name).exception() is not None
