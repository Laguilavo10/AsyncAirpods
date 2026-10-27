"""Keeps auto-switch alive: restarts it, with growing delays, when it can't start or stops with an error.

Starting with Windows is the usual case: Bluetooth and the audio devices may not
be ready yet when the app starts, and they appear a few seconds later.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

log = logging.getLogger(__name__)

FailureHandler = Callable[[Exception, int, float], None]  # error, consecutive failures, seconds until retry


@dataclass(frozen=True)
class RetryPolicy:
    delays: tuple[float, ...] = (2.0, 5.0, 10.0, 30.0)  # the last one repeats
    # A run that lasted this long was healthy: the next failure starts the delays over
    reset_after_seconds: float = 120.0


def run_with_retry(
    start: Callable[[], None],
    on_failure: FailureHandler,
    stopped: threading.Event,
    policy: RetryPolicy = RetryPolicy(),
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Call `start` (which blocks while running) until it returns normally or `stopped` is set."""
    failures = 0
    while not stopped.is_set():
        began = clock()
        try:
            start()
            return
        except Exception as error:  # at start-up the failures come from WinRT, COM and device lookup alike
            if clock() - began >= policy.reset_after_seconds:
                failures = 0
            delay = policy.delays[min(failures, len(policy.delays) - 1)]
            failures += 1
            log.warning("Auto-switch failed (%s: %s); retry %d in %.0f s",
                        type(error).__name__, error, failures, delay)
            on_failure(error, failures, delay)
            if stopped.wait(delay):
                return
