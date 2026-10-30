# AirPods Sync

🇪🇸 [Leer en español](README.es.md)

Educational project to bring AirPods auto-switching as close as possible to Windows:
put your AirPods on, play something on the PC, and they connect to it on their own.
Double-tap the back of your iPhone and they go back to it.

## Daily use

| You want | You do | What happens |
|---|---|---|
| **PC** | Nothing: wear the AirPods and play sound on the PC | After 2 s of sound they connect in ~1.5–4 s |
| **iPhone** | Double-tap the back of the iPhone ([shortcut](#iphone-shortcut)) | They go back to the iPhone and the PC **does not take them back** |
| **Manual control** | Tray icon next to the clock, or **Ctrl+Alt+A** | See status, switch by hand, pause auto-switch |

Tray icon colors: **green** = on this PC · **blue** = connecting (one attempt at a
time: extra clicks are ignored, since each request restarts the handshake) · **gray** = not on this PC ·
**amber** = auto-switch paused or holding off · **red** = error (hover for details).

Tray menu: *Use on PC* (also a left click) · *Release* · *Auto-switch* ·
*Pause media on disconnect* · *Notifications* · *Start with Windows* ·
*Nearby AirPods…* · *Open log folder* · version · *Quit*.

**Nearby AirPods…** opens a live card for every set of AirPods around you, with an
illustration of the model, batteries, in-ear and signal, and whether auto-switch
counts it as you (green border). Sony and other brands don't appear: only AirPods
broadcast this message. There you can:

- **Tune the minimum signal** with a slider while watching your own AirPods' signal
  and everyone else's. At the office, raise it until a colleague's AirPods say
  *weaker than* while yours still say *Counts as you*.
- **Choose the model to follow** (*Follow this model*), or go back to the
  model of the paired AirPods (*Follow paired model*, the default).

Both are saved and survive restarts; `--min-rssi` on the command line overrides
the saved signal.

With *Pause media on disconnect* (on by default), whatever the PC is playing
(Spotify, a browser video...) is paused when the AirPods leave the PC, however
they leave, so it doesn't carry on through the speakers. It is a real pause, not
the Play/Pause key, so nothing starts playing if nothing was.

**Ctrl+Alt+A** works from any app: it does *Use on PC* when the AirPods are
elsewhere and *Release* when they are on this PC. If another app already uses
that combination, the menu doesn't show the hint and the log says so.

Windows notifications tell you when the AirPods connect, leave the PC, or fail
to connect. Turn them off with *Notifications*; the choice is saved in
`%LOCALAPPDATA%\AirPodsSync\preferences.json`.

### Starting

The tray app starts **inactive** (amber icon): launching it, or turning on the
PC, never takes the AirPods. Auto-switch starts after your first *Use on PC*.
Hover the icon to see what it is waiting for and any countdown.

If Bluetooth is off or not ready yet (common right after Windows starts), or the
AirPods aren't paired, the icon stays gray and says so, and the app retries on its
own after 2, 5 and 10 s, then every 30 s. After 3 failed tries it turns red, and
keeps retrying.

### The hold-off rule

If the AirPods leave the PC without the PC asking (the iPhone took them back,
you chose *Release*, or you put them in the case), auto-switch **holds off** so it
doesn't steal them back while the PC keeps playing. It resumes once the PC has been
**silent for 15 s**, once you **haven't worn the AirPods for 60 s** (putting them on
again is a fresh start), or right away when you choose *Use on PC*.

If a connection doesn't complete in 20 s, the icon turns red and says why
(usually the AirPods are in a closed case or out of range).

### iPhone shortcut

1. **Shortcuts** app → **+** → **Add Action** → **Set Playback Destination**.
2. Tap **iPhone** in the action and pick your **AirPods**. Name it "AirPods to iPhone".
3. **Settings → Accessibility → Touch → Back Tap → Double Tap** → pick the shortcut.

It can also go on the Action button, a home screen widget, or Siri.

## How it works

1. **Reading the AirPods (BLE).** AirPods constantly broadcast Bluetooth Low Energy
   advertisements with their battery, in-ear state and case status. Any nearby
   device can read them **without connecting**.
2. **Detecting PC audio.** The Windows Core Audio peak meter tells whether the
   default output device is producing sound.
3. **Connecting.** Every Bluetooth audio endpoint is backed by a filter from the
   Windows Bluetooth audio driver that accepts a one-shot *reconnect* / *disconnect*
   request (`KSPROPSETID_BtAudio`), the same approach used by ToothTray.
4. **Auto-switch rule.** If you are wearing the AirPods (in-ear and close to the PC),
   the PC has been playing sound for 2 seconds, they are not connected yet, and
   auto-switch is not holding off, ask Windows to connect them.

The PC cannot hand the AirPods to the iPhone: after a disconnect they just stay
free. Going back always starts on the iPhone.

## Setup

Requires Windows 10/11 and Python 3.10+.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
airpods-sync startup on     # start the tray app with Windows
```

### Standalone .exe

To use it on another PC without Python:

```powershell
pip install -e ".[build]"
python packaging\build_exe.py
```

This creates `dist\AirPodsSync.exe`, a single file with no console window that
opens the tray app. On any PC, open it from wherever it is (Downloads, a USB
stick) and check *Start with Windows* in the tray menu: the .exe copies itself to
`%LOCALAPPDATA%\Programs\AirPodsSync` and registers that copy, so you can delete
the original. To update, open the new .exe and check the option again (uncheck
it first if it is checked); it replaces the installed copy.

### PCs with App Control (WDAC) or AppLocker

Managed PCs may block the unsigned native libraries inside the app (`winrt` for
Bluetooth and media control, Pillow for images) with *"An Application Control
policy has blocked this file"*. Don't work around the policy; allow the app in it:

```powershell
python packaging\build_exe.py --onedir                        # dist\AirPodsSync\
python packaging\build_exe.py --onedir --sign-thumbprint <TP> # also sign it
```

`--onedir` builds a folder whose files never change between runs (the single
.exe unpacks to a new temp folder each time, which is hard to allow). Copy it to
`C:\Program Files\AirPodsSync`; *Start with Windows* then registers the .exe in
place. To allow it:

- **Signer rule (recommended):** `--sign-thumbprint` signs every unsigned
  `.exe/.dll/.pyd` with a code-signing certificate from the Windows store that your
  policy trusts. New builds stay allowed.
- **Hash rules:** `SHA256SUMS.txt` in the folder lists every binary. With WDAC, a
  supplemental policy: `New-CIPolicy -ScanPath "C:\Program Files\AirPodsSync" -Level Hash -UserPEs -MultiplePolicyFormat -FilePath AirPodsSync.xml`,
  then `Set-CIPolicyIdInfo -SupplementsBasePolicyID <base policy GUID>` and
  `ConvertFrom-CIPolicy`. Hashes change with every build.

The CodeIntegrity event log (event 3077) names the policy that blocked a file. If
it is Smart App Control instead of a managed policy, it has no exceptions.

## Commands

```powershell
airpods-sync tray           # tray icon with auto-switch (what starts with Windows)
airpods-sync auto           # same auto-switch in the terminal (Ctrl+C to stop)
airpods-sync connect        # connect the AirPods to the PC now and time it
airpods-sync disconnect     # disconnect them from the PC
airpods-sync devices        # list paired Bluetooth audio devices
airpods-sync startup on|off|status
airpods-sync scan           # live table of nearby AirPods
airpods-sync scan --raw     # every packet's bytes by field, to study the protocol
pytest                      # run the tests
```

`connect`, `disconnect`, `auto` and `tray` take `--device <part of the name>`
(default: `AirPods`). `auto` and `tray` take `--min-rssi` (default `-55`) to ignore
AirPods that are farther away, such as other people's. They also only count
broadcasts from the same model as your paired AirPods, read from Windows.

Log file: `%LOCALAPPDATA%\AirPodsSync\logs\airpods-sync.log` (tray menu: *Open log folder*). It rotates at 1 MB and keeps 3 old files.

### Experiments with `scan --raw`

Watch which bytes change when you:
- open or close the case → `lid`
- take a pod out or put it in → bits of `status(bin)`
- charge the case → high nibble of `charge/case`

If your model shows up as `Unknown (0x....)`, add that ID to
`MODEL_NAMES` in `src/airpods_sync/domain/airpods.py`.

## Architecture

```
src/airpods_sync/
├── domain/                 Pure logic, no I/O
│   ├── airpods.py                  AirPodsStatus, PodStatus, CaseStatus, model names
│   └── proximity_pairing.py        Parser for Apple's 0x07 BLE message
├── application/            Use cases, depend only on domain + ports
│   ├── ports.py                    Interfaces: AdvertisementSource, AudioActivityMonitor, HeadsetController
│   ├── tracker.py                  AirPodsTracker: latest status per device, expiry
│   ├── headsets.py                 find_headset, wait_until_connected
│   ├── auto_switch.py              AutoSwitcher: auto-connect and hold-off rules, manual commands
│   └── runner.py                   SwitcherRunner: scan + tick loop, thread-safe commands
├── infrastructure/         Adapters for concrete libraries and Windows APIs
│   ├── bleak_source.py             BLE scanning with bleak (active, else passive)
│   ├── ble_diagnostics.py          Why Windows refuses to scan, for the log
│   ├── core_audio_interfaces.py    COM declarations missing from pycaw
│   ├── windows_audio.py            Audio meter and Bluetooth connect/disconnect
│   ├── windows_startup.py          Start with Windows (HKCU Run key, self-install)
│   ├── windows_hotkey.py           Global hotkey (RegisterHotKey)
│   ├── windows_media.py            Pause media apps (system media controls)
│   ├── preferences.py              Saved tray preferences (JSON)
│   └── single_instance.py          Named mutex so only one tray app runs
├── cli/                    Terminal presentation
│   ├── main.py                     Entry point and composition root
│   ├── scan.py                     Scan loop
│   └── render.py                   Pure text rendering
└── tray/                   System tray presentation
    ├── app.py                      TrayApp: icon, menu, status, hotkey
    ├── notifications.py            Which changes deserve a notification
    ├── nearby.py                   Cards of the Nearby AirPods window (pods grouped by set)
    ├── nearby_window.py            Nearby AirPods window (CustomTkinter)
    ├── illustrations.py            Headphone drawings per model family
    └── icons.py                    Icons drawn at runtime
```

Dependencies only point inward (`cli/tray → infrastructure → application → domain`).
The application never imports `bleak`, `pycaw`, `comtypes` or `pystray`, so the
rules are tested with fakes and the adapters can be swapped.

## Limitations

- The BLE message layout comes from community reverse engineering, not from Apple.
  Verified with AirPods Pro 3: model `0x2027` (little-endian), in-ear bits
  `0x02` = left and `0x08` = right regardless of the broadcasting pod.
- Part of the packet is encrypted and cannot be read without Apple's keys, so
  the BLE broadcast cannot be tied to a specific paired AirPods. The model and
  signal strength (`--min-rssi`) are used instead: someone with the same model
  sitting right next to you can still count as you. Color does not help: the
  Pro 3 is only sold in white (color byte `00`).
- Connecting must target both of the headset's driver filters (stereo and
  hands-free): asking only the stereo one took 8–11 s, both together 1.5–4 s,
  like Windows' own Connect button.
- If Windows' own "Connect" button stops working too, the pairing is broken:
  remove the AirPods from Windows and pair them again.
