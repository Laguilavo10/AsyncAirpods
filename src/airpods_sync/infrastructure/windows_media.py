"""Pausing media apps through Windows' system media transport controls.

These are the sessions behind the media keys and the volume flyout (Spotify,
browsers, the Media Player app...). Pausing a session is a real pause, unlike
the Play/Pause key, which would start playback if nothing was playing.
"""

from __future__ import annotations

import asyncio
import logging
import threading

from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as SessionManager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
)

log = logging.getLogger(__name__)


class WindowsMediaPlayback:
    def pause_all(self) -> None:
        # WinRT calls are async; run them off the caller's thread so the tick loop never waits
        threading.Thread(target=self._pause_all_blocking, name="pause-media", daemon=True).start()

    def _pause_all_blocking(self) -> None:
        try:
            paused = asyncio.run(self._pause_playing_sessions())
        except Exception:  # OSError from WinRT and the like; never let it escape a thread
            log.exception("Couldn't pause media")
            return
        log.info("Paused %s", ", ".join(paused) if paused else "nothing (no media was playing)")

    @staticmethod
    async def _pause_playing_sessions() -> list[str]:
        manager = await SessionManager.request_async()
        paused = []
        for session in manager.get_sessions():
            if session.get_playback_info().playback_status != PlaybackStatus.PLAYING:
                continue
            if await session.try_pause_async():
                paused.append(session.source_app_user_model_id)
        return paused
