from airpods_sync.infrastructure.windows_audio import _EndpointInfo, headset_name

# Filter IDs read from the user's PC
AIRPODS_STEREO = (
    r"{2}.\\?\bthenum#{0000110b-0000-1000-8000-00805f9b34fb}_vid&0001004c_pid&2027"
    r"#8&85fac88&0&70ae2a550e3c_c00000000#{6994ad04-93ef-11d0-a3cc-00a0c9223196}\src"
)
SONY_STEREO = (
    r"{2}.\\?\bthenum#{0000110b-0000-1000-8000-00805f9b34fb}_vid&0002054c_pid&0eaf"
    r"#8&85fac88&0&00a41c055864_c00000000#{6994ad04-93ef-11d0-a3cc-00a0c9223196}\src"
)
HANDS_FREE = r"{2}.\\?\bthhfenum#bthhfpaudio#9&1de3ddc&1&97#{6994ad04-93ef-11d0-a3cc-00a0c9223196}\wave"


def test_reads_the_apple_model_from_the_stereo_filter():
    assert _EndpointInfo("AirPods", AIRPODS_STEREO).model_id == 0x2027


def test_no_model_for_other_vendors_or_hands_free():
    assert _EndpointInfo("WH-CH720N", SONY_STEREO).model_id is None
    assert _EndpointInfo("AirPods", HANDS_FREE).model_id is None


def test_both_profiles_get_the_same_name_with_or_without_find_my():
    # Seen 2026-10-27: one endpoint had the suffix and the other didn't, and the
    # tray reported "'AirPods' matches several devices"
    assert headset_name("AirPods Pro de Andrés  - Find My") == "AirPods Pro de Andrés"
    assert headset_name("AirPods Pro de Andrés ") == "AirPods Pro de Andrés"


def test_other_names_are_only_trimmed():
    assert headset_name(" WH-CH720N Hands-Free ") == "WH-CH720N Hands-Free"
