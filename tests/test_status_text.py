from airpods_sync.application.auto_switch import AutoSwitchStatus
from airpods_sync.status_text import describe


def status(**overrides) -> AutoSwitchStatus:
    defaults = dict(wearing=True, pc_playing=False, connected=False)
    return AutoSwitchStatus(**{**defaults, **overrides})


def test_hold_counts_down():
    assert describe(status(holding_off=True, resume_in=17.2)) == "On hold · auto-switch resumes in 18 s"


def test_hold_explains_how_to_resume_when_no_countdown_runs():
    assert describe(status(holding_off=True, pc_playing=True)) == (
        "On hold · resumes after 15 s of PC silence or 60 s without the AirPods on"
    )


def test_ready_states_say_what_is_missing():
    assert describe(status(wearing=False)) == "Ready · put the AirPods on"
    assert describe(status()) == "Ready · connects when the PC plays sound"
    assert describe(status(pc_playing=True, connect_in=0.4)) == "Connecting in 1 s"


def test_not_started_waits_for_first_use():
    assert describe(status(started=False, pc_playing=True, connect_in=1)) == (
        "Auto-switch starts after your first 'Use on PC'"
    )


def test_connecting_shows_elapsed_time():
    assert describe(status(connecting=True, connecting_for=4.0)).startswith("Connecting... 4 s")


def test_connected_and_errors_take_priority():
    assert describe(status(connected=True, holding_off=True)) == "AirPods on this PC"
    assert describe(status(error="rejected", connected=True)) == "Error: rejected"


def test_start_failures_are_short_enough_for_the_tooltip():
    from airpods_sync.application.ports import BluetoothUnavailableError, DeviceNotFoundError
    from airpods_sync.status_text import describe_start_failure

    assert describe_start_failure(BluetoothUnavailableError("radio off")) == "Bluetooth is off or not ready"
    assert describe_start_failure(DeviceNotFoundError("long list")) == "AirPods not found among the paired devices"
    assert describe_start_failure(OSError()) == "OSError"


def test_tooltip_text_has_no_countdowns():
    # Windows hides the tooltip whenever its text changes, so it must stay put
    assert describe(status(holding_off=True, resume_in=17.2), live=False) == describe(
        status(holding_off=True, resume_in=3.0), live=False
    ) == describe(status(holding_off=True, pc_playing=True), live=False)
    assert describe(status(connecting=True, connecting_for=4.0), live=False) == "Connecting..."
    assert describe(status(pc_playing=True, connect_in=0.4), live=False) == "PC is playing · about to connect"
