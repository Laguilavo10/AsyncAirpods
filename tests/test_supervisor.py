import threading

from airpods_sync.application.ports import BluetoothUnavailableError
from airpods_sync.application.supervisor import RetryPolicy, run_with_retry

FAST = RetryPolicy(delays=(0.0, 0.0, 0.0), reset_after_seconds=100)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_retries_until_start_succeeds():
    attempts, failures = [], []

    def start() -> None:
        attempts.append(1)
        if len(attempts) < 3:
            raise BluetoothUnavailableError("not ready")

    run_with_retry(start, lambda error, count, delay: failures.append(count), threading.Event(), FAST)

    assert len(attempts) == 3
    assert failures == [1, 2]


def test_delays_grow_and_the_last_one_repeats():
    delays, stopped = [], threading.Event()

    def on_failure(error, count, delay) -> None:
        delays.append(delay)
        if count == 5:
            stopped.set()

    policy = RetryPolicy(delays=(0.001, 0.002, 0.003))
    run_with_retry(lambda: (_ for _ in ()).throw(OSError("boom")), on_failure, stopped, policy)

    assert delays == [0.001, 0.002, 0.003, 0.003, 0.003]


def test_quit_while_waiting_stops_retrying():
    stopped, attempts = threading.Event(), []

    def start() -> None:
        attempts.append(1)
        raise BluetoothUnavailableError("off")

    policy = RetryPolicy(delays=(30.0,))
    threading.Timer(0.05, stopped.set).start()
    run_with_retry(start, lambda *args: None, stopped, policy)

    assert len(attempts) == 1


def test_a_long_healthy_run_starts_the_delays_over():
    clock, delays, stopped, runs = Clock(), [], threading.Event(), []

    def start() -> None:
        runs.append(1)
        if len(runs) == 3:
            clock.now += 500  # this run was healthy for a while before failing
        if len(runs) == 4:
            stopped.set()
        raise OSError("lost")

    policy = RetryPolicy(delays=(0.0, 0.001, 0.002), reset_after_seconds=100)
    run_with_retry(start, lambda error, count, delay: delays.append(count), stopped, policy, clock)

    assert delays == [1, 2, 1, 2]
