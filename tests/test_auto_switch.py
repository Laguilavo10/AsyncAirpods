import pytest

from airpods_sync.application.auto_switch import AutoSwitcher, AutoSwitchSettings
from airpods_sync.application.ports import Advertisement, BluetoothAudioDevice, HeadsetControlError
from airpods_sync.application.tracker import AirPodsTracker
from airpods_sync.domain.proximity_pairing import APPLE_COMPANY_ID

NAME = "AirPods Pro"
IN_EAR = bytes.fromhex("0719012720" "2baa8f110000") + bytes(16)
IN_CASE = bytes.fromhex("0719012720" "25aab8310000") + bytes(16)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeAudio:
    def __init__(self) -> None:
        self.playing = False

    def is_playing(self) -> bool:
        return self.playing


class FakeHeadset:
    def __init__(self) -> None:
        self.connected = False
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.fail = False

    def list_devices(self) -> list[BluetoothAudioDevice]:
        return [BluetoothAudioDevice(NAME, self.connected)]

    def connect(self, name: str) -> None:
        self.connect_calls += 1
        if self.fail:
            raise HeadsetControlError("rejected")

    def disconnect(self, name: str) -> None:
        self.disconnect_calls += 1
        self.connected = False


class FakeMedia:
    def __init__(self) -> None:
        self.pause_calls = 0

    def pause_all(self) -> None:
        self.pause_calls += 1


class Env:
    def __init__(self, settings: AutoSwitchSettings = AutoSwitchSettings(), model_id: int | None = None) -> None:
        self.clock, self.audio, self.headset, self.media = FakeClock(), FakeAudio(), FakeHeadset(), FakeMedia()
        self.tracker = AirPodsTracker(clock=self.clock)
        self.switcher = AutoSwitcher(
            self.tracker, self.audio, self.headset, NAME, settings, self.clock, model_id=model_id, media=self.media
        )

    def wear(self, rssi: int = -40) -> None:
        self.see(IN_EAR, rssi)

    def see(self, data: bytes, rssi: int = -40) -> None:
        self.tracker.handle(Advertisement("AA", rssi, {APPLE_COMPANY_ID: data}))

    def advance(self, seconds: float):
        """Move time forward one second per tick, re-seeing the AirPods so they don't expire."""
        status = None
        for _ in range(int(seconds)):
            self.clock.now += 1
            self.wear()
            status = self.switcher.tick()
        return status

    def play(self, seconds: float):
        self.audio.playing = True
        self.switcher.tick()
        return self.advance(seconds)

    def silence(self, seconds: float):
        self.audio.playing = False
        self.switcher.tick()
        return self.advance(seconds)


@pytest.fixture
def env() -> Env:
    return Env()


def test_connects_when_wearing_and_audio_is_sustained(env):
    env.wear()

    status = env.play(2)

    assert status.connect_requested and status.wearing and status.pc_playing
    assert env.headset.connect_calls == 1


def test_short_sounds_do_not_connect(env):
    env.wear()

    env.play(1)
    env.silence(1)
    env.play(1)

    assert env.headset.connect_calls == 0


def test_does_not_connect_when_not_wearing(env):
    env.see(IN_CASE)
    env.audio.playing = True
    env.switcher.tick()
    env.clock.now += 5
    env.see(IN_CASE)

    assert not env.switcher.tick().wearing
    assert env.headset.connect_calls == 0


def test_ignores_distant_airpods(env):
    env.wear(rssi=-90)
    env.audio.playing = True
    env.switcher.tick()
    env.clock.now += 5

    assert not env.switcher.tick().wearing
    assert env.headset.connect_calls == 0


def test_default_signal_threshold_rejects_someone_a_couple_of_meters_away(env):
    env.wear(rssi=-60)

    assert not env.switcher.tick().wearing


PRO2_IN_EAR = bytes.fromhex("0719011420" "2baa8f110000") + bytes(16)


def test_only_the_paired_model_counts_as_wearing():
    env = Env(model_id=0x2027)
    env.see(PRO2_IN_EAR)
    assert not env.switcher.tick().wearing

    env.see(IN_EAR)  # AirPods Pro 3
    assert env.switcher.tick().wearing


def test_following_another_model_and_back_to_the_paired_one():
    env = Env(model_id=0x2027)
    env.see(PRO2_IN_EAR)

    env.switcher.follow_model(0x2014)
    assert env.switcher.tick().wearing
    assert env.switcher.nearby().followed_model_id == 0x2014

    env.switcher.follow_model(None)
    assert not env.switcher.tick().wearing
    assert env.switcher.nearby().followed_model_id == 0x2027


def test_signal_threshold_changes_at_runtime(env):
    env.wear(rssi=-50)
    assert env.switcher.tick().wearing

    env.switcher.set_min_rssi(-45)
    assert not env.switcher.tick().wearing
    assert env.switcher.nearby().min_rssi == -45


def test_any_model_counts_when_the_paired_model_is_unknown(env):
    env.see(PRO2_IN_EAR)

    assert env.switcher.tick().wearing


def test_does_nothing_when_already_connected(env):
    env.wear()
    env.headset.connected = True

    status = env.play(5)

    assert status.connected
    assert env.headset.connect_calls == 0


def test_does_not_resend_while_connecting_then_retries_after_timeout(env):
    env.wear()
    assert env.play(2).connecting
    assert env.headset.connect_calls == 1

    env.advance(19)
    assert env.headset.connect_calls == 1

    env.advance(1)
    assert env.headset.connect_calls == 2


def test_repeated_use_pc_sends_a_single_request(env):
    env.switcher.use_pc()
    env.switcher.use_pc()
    env.switcher.use_pc()

    assert env.headset.connect_calls == 1
    assert env.switcher.tick().connecting


def test_connecting_ends_when_connected(env):
    env.switcher.use_pc()
    env.headset.connected = True

    status = env.switcher.tick()

    assert status.connected and not status.connecting


def test_explains_a_connection_that_times_out(env):
    env.switcher.use_pc()

    status = env.advance(20)

    assert not status.connecting
    assert "closed case" in status.error


def test_failure_message_clears_once_connected(env):
    env.switcher.use_pc()
    env.advance(20)

    env.headset.connected = True

    assert env.switcher.tick().error is None


def test_resumes_after_not_wearing_for_a_while(env):
    env.wear()
    env.headset.connected = True
    env.play(1)
    env.headset.connected = False  # put back in the case while the PC keeps playing
    env.switcher.tick()

    # No advertisements: the last one expires after 10 s, then 60 s of not wearing
    for _ in range(70):
        env.clock.now += 1
        status = env.switcher.tick()
    assert not status.holding_off

    env.play(2)
    assert env.headset.connect_calls == 1


def test_hold_stays_while_still_wearing_on_the_iphone(env):
    env.wear()
    env.headset.connected = True
    env.play(1)
    env.headset.connected = False

    assert env.advance(120).holding_off


def test_failed_request_is_not_left_in_progress(env):
    env.headset.fail = True

    with pytest.raises(HeadsetControlError):
        env.switcher.use_pc()

    assert not env.switcher.tick().connecting


def test_reports_connection_errors(env):
    env.wear()
    env.headset.fail = True

    status = env.play(2)

    assert status.error == "rejected"
    assert not status.connect_requested


def test_disabled_never_connects(env):
    env.wear()
    env.switcher.set_enabled(False)

    status = env.play(5)

    assert not status.enabled
    assert env.headset.connect_calls == 0


def test_holds_off_when_airpods_leave_while_pc_plays(env):
    env.wear()
    env.headset.connected = True
    env.play(1)

    env.headset.connected = False  # the iPhone took them back
    status = env.advance(60)

    assert status.holding_off
    assert env.headset.connect_calls == 0


def test_resumes_after_pc_silence(env):
    env.wear()
    env.headset.connected = True
    env.play(1)
    env.headset.connected = False
    env.advance(1)

    assert not env.silence(15).holding_off
    env.play(2)
    assert env.headset.connect_calls == 1


def test_reports_countdowns(env):
    env.wear()
    env.switcher.release()

    assert env.silence(10).resume_in == 5
    assert env.play(1).connect_in == 1  # still on hold, but the audio timer runs


def test_reports_connect_countdown_and_elapsed_connecting_time(env):
    env.wear()

    assert env.play(1).connect_in == 1
    env.advance(1)
    assert env.advance(3).connecting_for == 3


def test_toggle_connects_when_away_and_releases_when_on_pc(env):
    env.switcher.toggle_pc()
    assert env.headset.connect_calls == 1

    env.headset.connected = True
    env.switcher.toggle_pc()
    assert env.headset.disconnect_calls == 1
    assert env.advance(1).holding_off


def test_pauses_media_when_the_airpods_leave_the_pc(env):
    env.headset.connected = True
    env.play(1)
    assert env.media.pause_calls == 0

    env.headset.connected = False  # the iPhone took them
    env.advance(3)
    assert env.media.pause_calls == 1  # once per disconnection


def test_release_pauses_media_too(env):
    env.headset.connected = True
    env.advance(1)

    env.switcher.release()
    env.advance(1)

    assert env.media.pause_calls == 1


def test_media_keeps_playing_when_pausing_is_off(env):
    env.switcher.set_pause_media(False)
    env.headset.connected = True
    env.advance(1)
    env.headset.connected = False
    env.advance(1)

    assert env.media.pause_calls == 0


def test_already_disconnected_at_start_does_not_pause(env):
    env.advance(3)

    assert env.media.pause_calls == 0


def test_release_after_a_long_silence_still_holds_off(env):
    env.wear()
    env.headset.connected = True
    env.silence(60)

    env.switcher.release()
    assert env.advance(1).holding_off  # the earlier silence does not count
    assert env.silence(10).resume_in == 4
    env.play(2)
    assert env.headset.connect_calls == 0

    env.silence(15)
    env.play(2)
    assert env.headset.connect_calls == 1


def test_release_disconnects_and_holds_off(env):
    env.wear()
    env.headset.connected = True

    env.switcher.release()
    status = env.play(10)

    assert env.headset.disconnect_calls == 1
    assert status.holding_off
    assert env.headset.connect_calls == 0


def test_waits_for_first_use_before_switching_automatically():
    env = Env(AutoSwitchSettings(wait_for_first_use=True))
    env.wear()

    status = env.play(10)
    assert not status.started
    assert env.headset.connect_calls == 0

    env.switcher.use_pc()
    env.headset.connected = True
    env.advance(1)
    env.headset.connected = False  # back to the iPhone
    env.silence(15)
    env.play(2)

    assert env.headset.connect_calls == 2  # the manual one, then an automatic one


def test_use_pc_connects_and_clears_hold(env):
    env.wear()
    env.switcher.release()

    env.switcher.use_pc()

    assert env.headset.connect_calls == 1
    assert not env.switcher.tick().holding_off
