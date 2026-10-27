"""Connects the AirPods to the PC when you are wearing them and the PC plays sound.

When the AirPods leave the PC without the PC asking for it (the iPhone took them
back, you released them, or you put them in the case), auto-switching holds off
so the PC does not steal them right back. It resumes once the PC has been silent
for a while, once you haven't worn the AirPods for a while (putting them on again
is a fresh start), or as soon as you choose the PC by hand.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, replace

from airpods_sync.application.ports import AudioActivityMonitor, HeadsetControlError, HeadsetController
from airpods_sync.application.tracker import AirPodsTracker

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AutoSwitchSettings:
    # Ignore AirPods weaker than this, so other people's nearby AirPods don't count.
    # Worn AirPods at the desk measured -40; this leaves ~15 dB of margin
    min_rssi: int = -55
    # Sound must last this long, so notification beeps don't steal the AirPods from the phone
    sustained_audio_seconds: float = 2.0
    # A connection attempt counts as in progress for this long; new requests are not
    # sent meanwhile, because each one could restart the handshake (1.5-4 s measured)
    connect_timeout_seconds: float = 20.0
    # After the AirPods leave the PC, stay away until the PC has been silent this long...
    resume_after_silence_seconds: float = 15.0
    # ...or until the AirPods have not been worn this long
    resume_after_not_wearing_seconds: float = 60.0
    # Stay inactive until the first use_pc(), so starting the app never takes the AirPods
    wait_for_first_use: bool = False


@dataclass(frozen=True)
class AutoSwitchStatus:
    wearing: bool
    pc_playing: bool
    connected: bool
    enabled: bool = True
    started: bool = True  # False until the first use_pc() when wait_for_first_use is set
    holding_off: bool = False
    connecting: bool = False
    connect_requested: bool = False
    error: str | None = None
    # Countdowns in seconds, None when not running
    resume_in: float | None = None  # until holding off ends
    connect_in: float | None = None  # until the PC has played sound long enough
    connecting_for: float | None = None  # since the current connection request


class AutoSwitcher:
    def __init__(
        self,
        tracker: AirPodsTracker,
        audio: AudioActivityMonitor,
        headset: HeadsetController,
        device_name: str,
        settings: AutoSwitchSettings = AutoSwitchSettings(),
        clock: Callable[[], float] = time.monotonic,
        model_id: int | None = None,
    ) -> None:
        self._tracker = tracker
        self._audio = audio
        self._headset = headset
        self._device_name = device_name
        # Only broadcasts of this model count as "wearing"; None accepts any model
        self._model_id = model_id
        self._settings = settings
        self._clock = clock
        self._enabled = True
        self._started = not settings.wait_for_first_use
        self._holding_off = False
        self._was_connected: bool | None = None
        self._playing_since: float | None = None
        self._silent_since: float | None = None
        self._not_wearing_since: float | None = None
        self._connecting_since: float | None = None
        self._failure: str | None = None

    @property
    def device_name(self) -> str:
        return self._device_name

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        log.info("Auto-switch %s", "enabled" if enabled else "disabled")

    def use_pc(self) -> None:
        """Connect now, regardless of the rules. Raises HeadsetControlError."""
        if not self._started:
            self._started = True
            log.info("Auto-switch started by the first 'Use on PC'")
        self._holding_off = False
        if self._is_connecting(self._clock()):
            log.info("Already connecting; ignoring repeated request")
            return
        log.info("Connecting %s on request", self._device_name)
        self._request_connection()

    def release(self) -> None:
        """Disconnect from the PC and keep auto-switch from reconnecting. Raises HeadsetControlError."""
        self._holding_off = True
        self._connecting_since = None
        if self._silent_since is not None:
            # Silence before the release must not count, or the hold would end at once
            self._silent_since = self._clock()
        log.info("Releasing %s on request", self._device_name)
        self._headset.disconnect(self._device_name)

    def tick(self) -> AutoSwitchStatus:
        """Evaluate the current state once and connect if needed. Call it periodically."""
        now = self._clock()
        playing = self._audio.is_playing()
        wearing = self._is_wearing()
        connected = self._is_connected()
        self._track_audio(playing, now)
        self._track_wearing(wearing, now)
        self._track_connection(connected, now)
        self._update_hold(connected, now)

        status = AutoSwitchStatus(
            wearing=wearing,
            pc_playing=playing,
            connected=connected,
            enabled=self._enabled,
            started=self._started,
            holding_off=self._holding_off,
            connecting=self._is_connecting(now),
            error=self._failure,
            **self._countdowns(now),
        )
        if not self._should_connect(status, now):
            return status

        log.info(
            "Wearing AirPods (RSSI %d) and PC is playing: connecting %s",
            self._worn_rssi(), self._device_name,
        )
        try:
            self._request_connection()
        except HeadsetControlError as error:
            log.warning("Connection failed: %s", error)
            return replace(status, error=str(error))
        return replace(
            status, connecting=True, connect_requested=True, error=None, connect_in=None, connecting_for=0.0
        )

    def _request_connection(self) -> None:
        self._failure = None
        self._connecting_since = self._clock()
        try:
            self._headset.connect(self._device_name)
        except HeadsetControlError:
            self._connecting_since = None
            raise

    def _is_connecting(self, now: float) -> bool:
        return (
            self._connecting_since is not None
            and now - self._connecting_since < self._settings.connect_timeout_seconds
        )

    def _track_audio(self, playing: bool, now: float) -> None:
        if playing:
            self._silent_since = None
            if self._playing_since is None:
                self._playing_since = now
        else:
            self._playing_since = None
            if self._silent_since is None:
                self._silent_since = now

    def _track_wearing(self, wearing: bool, now: float) -> None:
        if wearing:
            self._not_wearing_since = None
        elif self._not_wearing_since is None:
            self._not_wearing_since = now

    def _track_connection(self, connected: bool, now: float) -> None:
        if connected:
            self._failure = None
            if self._connecting_since is not None:
                log.info("Connected %.1f s after the request", now - self._connecting_since)
            elif self._was_connected is False:
                log.info("Connected (not requested by this app)")
            self._connecting_since = None
        elif self._connecting_since is not None and not self._is_connecting(now):
            timeout = self._settings.connect_timeout_seconds
            self._failure = f"Couldn't connect in {timeout:.0f} s. Are the AirPods in a closed case or out of range?"
            log.warning("Not connected %.0f s after the request; giving up", timeout)
            self._connecting_since = None

    def _update_hold(self, connected: bool, now: float) -> None:
        if self._was_connected and not connected and not self._holding_off:
            self._holding_off = True
            log.info("%s left the PC; holding off", self._device_name)
        self._was_connected = connected

        if not self._holding_off:
            return
        if self._elapsed(self._silent_since, now) >= self._settings.resume_after_silence_seconds:
            self._holding_off = False
            log.info("PC has been silent; auto-switch resumed")
        elif self._elapsed(self._not_wearing_since, now) >= self._settings.resume_after_not_wearing_seconds:
            self._holding_off = False
            log.info("AirPods have not been worn for a while; auto-switch resumed")

    def _countdowns(self, now: float) -> dict[str, float | None]:
        settings = self._settings
        resume_in = connect_in = connecting_for = None
        if self._holding_off:
            remaining = [
                limit - self._elapsed(since, now)
                for since, limit in (
                    (self._silent_since, settings.resume_after_silence_seconds),
                    (self._not_wearing_since, settings.resume_after_not_wearing_seconds),
                )
                if since is not None
            ]
            resume_in = max(0.0, min(remaining)) if remaining else None
        if self._playing_since is not None:
            connect_in = max(0.0, settings.sustained_audio_seconds - (now - self._playing_since))
        if self._is_connecting(now):
            connecting_for = now - self._connecting_since
        return {"resume_in": resume_in, "connect_in": connect_in, "connecting_for": connecting_for}

    @staticmethod
    def _elapsed(since: float | None, now: float) -> float:
        return 0.0 if since is None else now - since

    def _should_connect(self, status: AutoSwitchStatus, now: float) -> bool:
        if not (status.enabled and status.started) or status.holding_off:
            return False
        if status.connected or status.connecting:
            return False
        if not status.wearing or self._playing_since is None:
            return False
        return now - self._playing_since >= self._settings.sustained_audio_seconds

    def _is_wearing(self) -> bool:
        return self._worn_rssi() is not None

    def _worn_rssi(self) -> int | None:
        """Signal of the closest worn AirPods that pass the filters, or None."""
        for device in self._tracker.active():  # closest first
            if self._model_id is not None and device.status.model_id != self._model_id:
                continue
            if device.status.in_ear and device.rssi >= self._settings.min_rssi:
                return device.rssi
        return None

    def _is_connected(self) -> bool:
        return any(
            device.name == self._device_name and device.connected
            for device in self._headset.list_devices()
        )
