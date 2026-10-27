from airpods_sync.application.auto_switch import AutoSwitchStatus
from airpods_sync.tray.notifications import notification_for


def status(**overrides) -> AutoSwitchStatus:
    defaults = dict(wearing=True, pc_playing=False, connected=False)
    return AutoSwitchStatus(**{**defaults, **overrides})


def test_start_up_never_notifies():
    assert notification_for(None, status(connected=True)) is None


def test_connecting_notifies():
    assert notification_for(status(), status(connected=True)).title == "AirPods on this PC"


def test_leaving_the_pc_notifies():
    assert notification_for(status(connected=True), status(holding_off=True)).title == "AirPods left this PC"


def test_a_new_error_notifies_once():
    failed = status(error="Couldn't connect in 20 s.")

    assert notification_for(status(), failed).message == "Couldn't connect in 20 s."
    assert notification_for(failed, failed) is None


def test_countdowns_alone_do_not_notify():
    assert notification_for(status(connect_in=2.0), status(connect_in=1.0)) is None
