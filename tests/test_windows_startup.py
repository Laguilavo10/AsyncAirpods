from pathlib import Path

from airpods_sync.infrastructure.windows_startup import InstalledExeStartup


class FakeRunKey:
    def __init__(self) -> None:
        self.enabled = False

    def is_enabled(self) -> bool:
        return self.enabled

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False


def make_exe(folder: Path, content: bytes = b"exe") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    exe = folder / "AirPodsSync.exe"
    exe.write_bytes(content)
    return exe


def test_enabling_copies_the_exe_to_the_install_folder(tmp_path):
    downloaded = make_exe(tmp_path / "Downloads")
    run_key = FakeRunKey()
    startup = InstalledExeStartup(downloaded, tmp_path / "Programs", run_key)

    startup.enable()

    assert (tmp_path / "Programs" / "AirPodsSync.exe").read_bytes() == b"exe"
    assert startup.is_enabled()


def test_enabling_replaces_an_older_installed_copy(tmp_path):
    make_exe(tmp_path / "Programs", b"old")
    startup = InstalledExeStartup(make_exe(tmp_path / "Downloads", b"new"), tmp_path / "Programs", FakeRunKey())

    startup.enable()

    assert (tmp_path / "Programs" / "AirPodsSync.exe").read_bytes() == b"new"


def test_running_the_installed_copy_does_not_copy_it_onto_itself(tmp_path):
    installed = make_exe(tmp_path / "Programs")
    startup = InstalledExeStartup(installed, tmp_path / "Programs", FakeRunKey())

    startup.enable()

    assert startup.is_enabled()


def test_disabled_when_the_installed_copy_is_gone(tmp_path):
    run_key = FakeRunKey()
    run_key.enabled = True
    startup = InstalledExeStartup(make_exe(tmp_path / "Downloads"), tmp_path / "Programs", run_key)

    assert not startup.is_enabled()


def test_disabling_keeps_the_installed_copy(tmp_path):
    startup = InstalledExeStartup(make_exe(tmp_path / "Downloads"), tmp_path / "Programs", FakeRunKey())
    startup.enable()

    startup.disable()

    assert not startup.is_enabled()
    assert (tmp_path / "Programs" / "AirPodsSync.exe").exists()


def test_registers_the_installed_copy():
    assert InstalledExeStartup.command_for(Path(r"C:\Apps\AirPodsSync.exe")) == r'"C:\Apps\AirPodsSync.exe" tray'
