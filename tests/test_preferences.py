from airpods_sync.infrastructure.preferences import JsonPreferences


def test_missing_file_gives_defaults(tmp_path):
    assert JsonPreferences(tmp_path / "missing.json").get_bool("notifications", True)


def test_values_survive_a_new_instance(tmp_path):
    path = tmp_path / "AirPodsSync" / "preferences.json"
    JsonPreferences(path).set_bool("notifications", False)

    assert not JsonPreferences(path).get_bool("notifications", True)


def test_corrupt_file_gives_defaults(tmp_path):
    path = tmp_path / "preferences.json"
    path.write_text("{not json", encoding="utf-8")

    assert JsonPreferences(path).get_bool("notifications", True)
