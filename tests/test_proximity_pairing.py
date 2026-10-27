from airpods_sync.domain import proximity_pairing


def make_message(status: int, pods: int, charge_case: int, model: int = 0x2014) -> bytes:
    header = [0x07, 0x19, 0x01, model & 0xFF, model >> 8, status, pods, charge_case, 0x31, 0x00, 0x05]
    return bytes(header) + bytes(16)


def test_left_broadcasting_reads_low_nibble_as_left():
    status = proximity_pairing.parse(make_message(status=0x2B, pods=0x98, charge_case=0x45))

    assert status.model_name == "AirPods Pro 2"
    assert status.left_is_broadcasting
    assert (status.left.battery, status.right.battery, status.case.battery) == (80, 90, 50)
    assert status.left.in_ear and status.right.in_ear
    assert (status.left.charging, status.right.charging, status.case.charging) == (False, False, True)


def test_right_broadcasting_swaps_battery_and_charging_sides():
    status = proximity_pairing.parse(make_message(status=0x02, pods=0x98, charge_case=0x15))

    assert not status.left_is_broadcasting
    assert (status.left.battery, status.right.battery) == (90, 80)
    assert (status.left.charging, status.right.charging) == (False, True)


# Captured from AirPods Pro 3: left pod in the ear, right pod charging in the case.
# Each pod broadcasts its own packet; the encrypted payload is zeroed out.
PRO3_LEFT_PACKET = bytes.fromhex("0719012720" "33aaa8110000") + bytes(16)
PRO3_RIGHT_PACKET = bytes.fromhex("0719012720" "53aa98310000") + bytes(16)


def test_pro3_packets_from_both_pods_agree():
    for packet in (PRO3_LEFT_PACKET, PRO3_RIGHT_PACKET):
        status = proximity_pairing.parse(packet)

        assert status.model_name == "AirPods Pro 3"
        assert (status.left.in_ear, status.right.in_ear) == (True, False)
        assert (status.left.charging, status.right.charging) == (False, True)
        assert (status.left.battery, status.right.battery, status.case.battery) == (100, 100, 80)


def test_pro3_both_in_ear_with_case_out_of_range():
    status = proximity_pairing.parse(bytes.fromhex("0719012720" "2baa8f110000") + bytes(16))

    assert status.left.in_ear and status.right.in_ear
    assert status.case.battery is None


def test_unavailable_battery_is_none():
    status = proximity_pairing.parse(make_message(status=0x20, pods=0xF7, charge_case=0x0F))

    assert (status.left.battery, status.right.battery, status.case.battery) == (70, None, None)


def test_unknown_model_shows_its_id():
    status = proximity_pairing.parse(make_message(status=0x20, pods=0x00, charge_case=0x00, model=0x2099))

    assert status.model_name == "Unknown (0x2099)"


def test_ignores_other_apple_messages():
    assert proximity_pairing.parse(bytes([0x10, 0x05, 0x01, 0x18, 0x00, 0x00, 0x00])) is None
    assert proximity_pairing.parse(bytes([0x07, 0x19, 0x01])) is None


def test_ignores_type_07_messages_with_another_prefix():
    # Captured from an Apple device next to the PC; its "model" bytes changed between packets
    assert proximity_pairing.parse(bytes.fromhex("070b06548bc46f8dcef64c")) is None


def test_split_fields_names_each_byte_group():
    fields = dict(proximity_pairing.split_fields(make_message(status=0x2B, pods=0x98, charge_case=0x45)))

    assert fields["model"] == bytes([0x14, 0x20])
    assert fields["status"] == bytes([0x2B])
    assert len(fields["encrypted"]) == 16
