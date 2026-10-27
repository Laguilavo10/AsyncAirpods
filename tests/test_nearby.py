from airpods_sync.application.auto_switch import NearbySnapshot
from airpods_sync.application.tracker import TrackedAirPods
from airpods_sync.domain import proximity_pairing
from airpods_sync.tray.nearby import Battery, cards_for, strongest_of_followed_model


def packet(header: str):
    return proximity_pairing.parse(bytes.fromhex(header) + bytes(16))


PRO3_IN_EAR = packet("0719012720" "2baa8f110000")
PRO3_IN_CASE = packet("0719012720" "25aab8310000")
PRO2_IN_EAR = packet("0719011420" "2baa8f110000")
# The same set seen from each pod (captured): left pod in the ear, right pod charging in the case
PRO3_LEFT_POD = packet("0719012720" "33aaa8110000")
PRO3_RIGHT_POD = packet("0719012720" "53aa98310000")


def snapshot(*devices: TrackedAirPods, min_rssi: int = -55) -> NearbySnapshot:
    return NearbySnapshot(devices, followed_model_id=0x2027, paired_model_id=0x2027, min_rssi=min_rssi)


def seen(address: str, status, rssi: int) -> TrackedAirPods:
    return TrackedAirPods(address, status, rssi, last_seen=0.0)


def test_verdicts_follow_the_auto_switch_filters():
    cards = cards_for(snapshot(
        seen("mine", PRO3_IN_EAR, -42),
        seen("other-model", PRO2_IN_EAR, -40),
        seen("in-case", PRO3_IN_CASE, -30),
    ))

    assert [(card.model, card.verdict, card.counts) for card in cards] == [
        ("AirPods Pro 3", "Counts as you", True),
        ("AirPods Pro 2", "Other model · ignored", False),
        ("AirPods Pro 3", "Not worn", False),
    ]


def test_a_colleague_too_far_away_is_ignored():
    card = cards_for(snapshot(seen("colleague", PRO3_IN_EAR, -62)))[0]

    assert (card.verdict, card.counts) == ("Too far · ignored", False)


def test_both_pods_of_one_set_make_one_card_with_the_strongest_signal():
    cards = cards_for(snapshot(seen("left-pod", PRO3_LEFT_POD, -40), seen("right-pod", PRO3_RIGHT_POD, -48)))

    assert len(cards) == 1
    assert cards[0].rssi == -40
    assert cards[0].worn == "In the left ear"


def test_card_shows_batteries_and_marks_the_paired_model():
    card = cards_for(snapshot(seen("mine", PRO3_IN_EAR, -42)))[0]

    assert card.is_paired_model and card.is_followed_model
    assert (card.left, card.right, card.case) == (Battery(100, False), Battery(100, False), Battery(None, False))
    assert card.worn == "In both ears"


def test_strongest_signal_ignores_other_models():
    assert strongest_of_followed_model(snapshot(seen("a", PRO2_IN_EAR, -30), seen("b", PRO3_IN_CASE, -50))) == -50
    assert strongest_of_followed_model(snapshot(seen("a", PRO2_IN_EAR, -30))) is None
