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
