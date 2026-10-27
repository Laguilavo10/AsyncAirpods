# CLAUDE.md

Guidance for Claude when working on this repository. User-facing docs are
`README.md` (English) and `README.es.md` (Spanish); this file records the
decisions, measurements and gotchas behind them.

## Project

Educational project: bring AirPods auto-switching as close as possible to Windows.
The user owns AirPods Pro 3 and an iPhone. Apple's real auto-switching needs iCloud
and Apple's protocol, so this app reads the AirPods' BLE broadcasts, watches PC
audio, and asks the Windows Bluetooth driver to connect or disconnect.

## Working with the user

- Talk to the user in **Spanish**; write all code, identifiers, comments and
  docstrings in **English**.
- Keep the layered architecture (see below) and add tests for new rules.
- Keep **both READMEs** in sync when behavior or commands change.
- The user tests on real hardware; ask them to say "listo" before any step that
  needs the AirPods in a given state, and give precise step-by-step instructions.
- Git: commits are authored by the user only. **Never add `Co-Authored-By: Claude`**
  or any Claude attribution to commits or PRs. The remote is
  `git@github.com:Laguilavo10/AsyncAirpods.git`. The SSH key has a passphrase; the
  user loads it into a Git Bash agent at `~/.ssh/agent.sock` and the global
  `core.sshCommand` points to it, so Claude can push. After a reboot the agent is
  gone: `Permission denied (publickey)` means the user must rerun `ssh-agent -a`
  and `ssh-add`. Don't set a repo-local `core.sshCommand` (it overrides that).
- Never claim a hardware behavior works until it was observed on the device.
  Several early assumptions were wrong (see "Findings").

## Environment

- Windows 11, PowerShell 5.1. Python 3.13 installed per-user with
  `winget install Python.Python.3.13 --scope user`, at
  `%LOCALAPPDATA%\Programs\Python\Python313`.
- Virtual env in `.venv`; install with `pip install -e ".[dev]"`; run tests with
  `.venv\Scripts\python.exe -m pytest -q`.
- **Don't write files with PowerShell `Set-Content -Encoding utf8`**: it adds a BOM
  and `pyproject.toml` stops parsing. Use the Write/Edit tools.
- The tray app runs as `pythonw.exe -m airpods_sync tray`. A venv `pythonw.exe`
  spawns a child process, so stop it by command line, not by one PID:
  ```powershell
  Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
    Where-Object { $_.CommandLine -like "*airpods_sync tray*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  ```
  Restart it after code changes, and **stop it during hardware experiments** so its
  auto-switch doesn't interfere.
- Log: `%LOCALAPPDATA%\AirPodsSync\logs\airpods-sync.log` (UTF-8, rotates at 1 MB, 3 backups; before 0.2.0 it was one level up, cp1252). Read it first when the user
  reports a problem: it has connection timings and every decision.
- Start with Windows uses the `HKCU\...\Run` value `AirPodsSync`. Writing it was
  blocked by the session's permission classifier; the user enables it from the
  tray menu (*Start with Windows*) or with `airpods-sync startup on`. On
  2026-10-27 the value was found missing (never enabled), not broken.
- Packaged build: `packaging/build_exe.py` (PyInstaller, onefile, windowed) →
  `dist/AirPodsSync.exe`; `packaging/launcher.py` defaults to `tray`. When frozen,
  *Start with Windows* uses `InstalledExeStartup`: it copies the running .exe to
  `%LOCALAPPDATA%\Programs\AirPodsSync` and registers `"<that copy>" tray`, so it
  works on any PC wherever the .exe was opened from (the user wants it on an
  office PC too). Stop it with `Stop-Process -Name AirPodsSync`. Onefile runs as
  two processes (bootloader + child); that is normal.
- **0.3.1 shipped broken** (`ModuleNotFoundError: airpods_sync.cli.main` on the
  office PC): a `
` written through a heredoc became a real newline, a syntax
  error PyInstaller silently dropped. Now `tests/test_imports.py` imports every
  module and `build_exe.py` imports the entry modules before building. After a
  build, launch the .exe and check the log has a "Tracking" line before handing it
  over. Same-second edits of a same-size file (e.g. via `git stash pop`) can leave
  a stale `.pyc`; delete `__pycache__` if the version looks wrong.
- Office PC (Intel CPU): the headset wasn't found although Bluetooth was on and the
  AirPods connected. Suspected Intel Bluetooth audio offload (endpoints behind an
  Intel SST filter, not `bthenum`). 0.3.2 logs every audio endpoint with its filter
  ID once when the headset isn't found; waiting for that log.
- The .exe's Properties > Details (version, description, author, copyright, repo
  URL) come from a version resource that `build_exe.py` generates from
  `airpods_sync.__version__`, the single source of the version (pyproject reads it
  too). Bump it before giving the user a new build.

## Architecture

`src/airpods_sync/`, dependencies only point inward:
`cli/`, `tray/` → `infrastructure/` → `application/` → `domain/`.

- `domain/`: pure parsing of Apple's proximity pairing message and the status model.
- `application/`: `ports.py` (Protocols), `tracker.py`, `headsets.py`,
  `auto_switch.py` (all rules), `runner.py` (scan + tick loop with thread-safe
  commands). Never imports bleak, pycaw, comtypes or pystray.
- `infrastructure/`: bleak scanner, Core Audio meter and Bluetooth control
  (`windows_audio.py` + `core_audio_interfaces.py`), Run-key startup, named-mutex
  single instance. `infrastructure/__init__.py` sets `sys.coinit_flags = 0` (MTA)
  before any comtypes import; bleak's WinRT callbacks don't fire on an STA thread.
- `cli/main.py` is the composition root (the only place that picks adapters).
- `status_text.py` is the user-facing status line shared by CLI and tray.

## Findings from the hardware (verified)

### BLE proximity pairing message (Apple company ID 0x004C, type 0x07)

- Model ID is **little-endian**: bytes `27 20` = `0x2027` = AirPods Pro 3, the same
  value Windows shows as `pid&2027`.
- **Each pod broadcasts its own packet** with its own rotating address; status bit
  `0x20` set = the left pod is the broadcaster. Once both pods are out of the case,
  usually only one keeps broadcasting.
- **In-ear bits are fixed sides**: `0x02` = left, `0x08` = right, whichever pod
  broadcasts. Community parsers (OpenPods, AirPodsDesktop) treat them as relative
  to the broadcaster; that was wrong for the Pro 3.
- Battery nibbles (byte 6) and charging flags (high nibble of byte 7) **are**
  ordered by broadcaster. Case battery nibble `0xF` = unavailable (case closed or
  out of range). Bit `0x04` of the status byte seems to mean "both pods in case"
  (not used).
- Real captured headers, used as test fixtures:
  `0719012720 2baa8f110000` (both in ear) and `0719012720 25aab8310000` (in case).
- AirPods advertise less often while connected and in ear (gaps of ~6 s seen;
  once only 1 packet in 20 s); the tracker expires entries after 10 s.
- Only prefix (byte 2) `0x01` is the AirPods status layout. An Apple device next
  to the PC (likely the iPhone) sends type 0x07 with prefix `0x06`, length 11 and
  "model" bytes that change per packet; the parser rejects it.
- Color byte is `00` (white) for the Pro 3, the only color sold: useless for
  telling the user's Pro 3 from a colleague's.
- RSSI measured 2026-10-27: case open next to the PC -18; worn, seated at the
  desk -40 (single packet). Default `min_rssi` is now -55.
- Windows' stereo filter ID carries `_vid&0001004c_pid&2027`: the paired model,
  the same ID the AirPods broadcast. `BluetoothAudioDevice.model_id` reads it and
  `AutoSwitcher` only counts broadcasts of that model (None = any).

### Connecting from Windows

- Method (same as ToothTray): endpoint → `IDeviceTopology` → connector →
  `GetDeviceIdConnectedTo()` gives the KS filter ID → `IMMDeviceEnumerator.GetDevice`
  → `Activate(IKsControl)` → `KsProperty(KSPROPSETID_BtAudio, ONESHOT_RECONNECT /
  ONESHOT_DISCONNECT, KSPROPERTY_TYPE_GET)`. `IPart.Activate(IKsControl)` fails
  with E_NOINTERFACE; use the enumerator route.
- **Send the request to both filters**: stereo (`bthenum`, render endpoint) and
  hands-free (`bthhfenum`, reachable from the microphone/capture endpoint, hence
  `EDataFlow.eAll`). Stereo alone took **8.4–11.1 s**; both took **1.5–4.3 s**, in
  line with Windows' own Connect button.
- **Each new request appears to restart the handshake**: double clicks sent 5
  requests in 25 s and nothing connected. Only one attempt runs at a time
  (`connect_timeout_seconds = 20`).
- Windows answers `S_OK` even when nothing happens; confirm by polling the endpoint
  state (`ACTIVE` vs `UNPLUGGED`).
- Once, neither our request nor Windows' Connect button worked: the pairing was
  stale. Removing the AirPods in Windows and pairing again fixed it. Pairing mode
  only works with the iPhone's Bluetooth off (Settings, not Control Center).
- The Windows device name after re-pairing is `AirPods Pro de Andrés  - Find My`
  (two spaces); names are matched by substring (`--device`, default `AirPods`).
- **Bluetooth off hides every Bluetooth audio endpoint** (paired ones included), so
  `find_headset` treats an empty list as `BluetoothUnavailableError`. Seen
  2026-10-27: with the radio off the tray retried, and recovered on the next retry
  after turning it on. After that the Windows name showed as
  `AirPods Pro de Andrés` (no " - Find My"): don't rely on the exact name.
- The user's other headset: Sony WH-CH720N (stereo and "Hands-Free" show up as two
  names). Connect/disconnect is generic; auto-switch needs the AirPods' in-ear signal.

### What is not possible

- The PC cannot hand the AirPods to the iPhone: after a disconnect they stay free.
  Going back starts on the iPhone, with a Shortcuts action
  "Set Playback Destination → AirPods" on Back Tap (double tap).
- The PC cannot know when the iPhone is playing, nor tie a BLE broadcast to a
  specific paired AirPods (the identifying part is encrypted). Model filter plus
  `min_rssi = -55` is the stand-in for "these are mine"; the user wants this at
  the office, where colleagues wear AirPods. Both are tunable live from the
  tray's *Nearby AirPods…* window.

## Auto-switch rules (agreed with the user)

All in `application/auto_switch.py`, defaults in `AutoSwitchSettings`:

| Rule | Value |
|---|---|
| Connect when wearing (in ear, paired model, RSSI ≥ -55), PC playing, not connected | after 2 s of sustained sound |
| PC "playing" | default output peak > 0.01 |
| One attempt at a time; then report failure in the tray (red) | 20 s |
| AirPods leave the PC without the PC asking → hold off | until 15 s of PC silence (was 30 s; the user lowered it on 2026-10-27; after *Release* the silence counts from the release), or 60 s not worn, or *Use on PC* |
| Tray starts inactive (`wait_for_first_use=True`); CLI `auto` starts active | first *Use on PC* starts it |
| Can't start or fails (Bluetooth not ready at boot, AirPods not paired) → retry (`application/supervisor.py`) | after 2, 5, 10 s, then every 30 s; gray, red from the 3rd failure; a run of 120 s resets the delays |

The tray shows what it waits for plus countdowns (`status_text.describe`).
Icon colors: green on PC, blue connecting, amber paused/on hold, gray away, red error.

## Related

- Interactive step-by-step explainer of the whole flow (private artifact):
  https://claude.ai/artifact/6UcT8ukuzsw1FrtCWJXoUa. Republish it if behavior changes.
- Hotkey **Ctrl+Alt+A** (`infrastructure/windows_hotkey.py`, RegisterHotKey on its
  own message-loop thread) calls `AutoSwitcher.toggle_pc()`: release if on the PC,
  else use_pc. Notifications use pystray's `notify` and `tray/notifications.py`
  (connected, left the PC, new error; never for the first status). The
  *Notifications* toggle is saved in `%LOCALAPPDATA%\AirPodsSync\preferences.json`.
- *Pause media on disconnect* (default on, saved in the same file): on any
  connected → disconnected change (iPhone, Release, case) `AutoSwitcher` calls
  `MediaPlayback.pause_all()`. `infrastructure/windows_media.py` pauses every
  *playing* GlobalSystemMediaTransportControls session on its own thread
  (`winrt-Windows.Media.Control`); never the Play/Pause key, which would start
  playback. Detection runs on the 1 s tick, so up to ~1 s may leak to the speakers.
- **Nearby AirPods…** window (`tray/nearby_window.py`, CustomTkinter on its own
  thread; one card per set from `tray/nearby.py`, which groups both pods by model +
  batteries + in-ear; drawings from `tray/illustrations.py`; the user rejected the
  plain table as ugly and chose original drawings over copyrighted product photos): live list from `AutoSwitcher.nearby()` read through
  `SwitcherRunner.query()` (a Future, so the tracker is only touched on the loop),
  a min-signal slider (`set_min_rssi`) and *Follow this / paired model*
  (`follow_model`). Saved as `min_rssi` / `followed_model_id` in preferences.json;
  `--min-rssi` overrides. Agreed with the user: it can't remember *which* AirPods
  are theirs (encrypted, rotating addresses), so it tunes model + signal instead.
  First real capture in the window: own Pro 3 worn at the desk, -34 dBm.
