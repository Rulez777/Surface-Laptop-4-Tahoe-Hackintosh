<p align="center"><img src="assets/hero.svg" alt="Surface Laptop 4 running macOS Tahoe" width="100%"></p>

# Surface Laptop 4 — macOS Tahoe

A tested OpenCore configuration for the **Microsoft Surface Laptop 4 Intel (13.5-inch)**. macOS Tahoe 26.7.1 runs from the internal SSD alongside Windows 11, with Metal 2 graphics, built-in input, audio and screen brightness.

## Fast start — reproducible S0ix sleep (beta)

**Already booting Tahoe with Metal 2 and working eDP Keep + Softsleep?** Download [the complete S0ix DMC beta release](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/releases/tag/sl4-s0ix-v0.2.0-beta). The ZIP contains the tested byte-verified WhateverXe/DMC driver, S0ixStandby, Deep Idle ACPI, a checksum manifest, installer and rollback. **No Xcode build, USB flash drive or copied personal EFI is needed.**

Use the [**quick start (macOS installation, verification and Windows recovery)**](docs/QUICKSTART-S0IX.md). On the tested SL4 it is three steps: extract ZIP, run installer `check`, run installer `apply`, then restart.

The installer **requires Tahoe 26.7.1, i7-1185G7/9A49, OpenCore 1.0.8 and existing working custom eDP graphics**. It rejects other builds and preserves the original WEX and Windows Boot Manager. Two macOS Deep Idle / RTC wakes (8 and 71 seconds) succeeded, and the owner confirms sleep works. **A delayed RCS GPU Reset was observed afterward**, and measured hardware S0ix residency remains unproven. Long lid/battery/overnight reliability is not certified; **automatic idle sleep stays off by default**. See [GPU diagnostics](docs/POST-S0IX-GPU-RCS-RESET-20261123.md).

## Tested hardware

| Component | Configuration |
| --- | --- |
| Model | Surface Laptop 4 Intel, 13.5-inch |
| CPU / GPU | Core i7-1185G7 / Intel Iris Xe 96 EU (`8086:9A49`) |
| RAM / SSD | 16 GB / Samsung PM991 |
| Wireless | Intel AX201 |
| Audio | Intel HDA `8086:A0C8`, Realtek ALC274 |
| Display | 2496 × 1664, HiDPI |
| Bootloader / macOS | OpenCore 1.0.8 / Tahoe 26.7.1 |

## Hardware support

| Feature | Status |
| --- | --- |
| macOS Tahoe / internal SSD boot | **Working** |
| Windows 11 dual boot | **Working** |
| Intel Iris Xe / Metal 2 | **Working** |
| Browser / online video playback | **Working on the tested SL4**; details in [media notes](docs/MEDIA.md) |
| Internal HiDPI and external DisplayPort | **Working** |
| **Internal display brightness controls** | **Working** |
| Intel AX201 Wi-Fi / Bluetooth | **Working** |
| Built-in speakers / microphone | **Working** |
| Keyboard / trackpad / multitouch | **Working** |
| Battery percentage | **Working** |
| CPU temperature / optional TMP=3 startup request | **Working** |
| Surface Dock | **Working** |
| Display-only sleep / screen wake with eDP Keep + Softsleep | **Working** |
| Full system sleep (S3 / S0ix) | **Working** |

Verified on one Surface Laptop 4 Intel. Other models, headphone jack and untested hardware are not certified.

**Wake distinction:** The eDP Keep + Softsleep fix previously verified **display-only wake**. On 2026-11-23 the same Surface also completed **two separate real S0ix / Deep Idle RTC wakes (8 and 71 seconds)** with experimental WhateverXe DMC, S0ixStandby and SSDT-DEEPIDLE. This does **not** establish reliable lid/power-button wake, battery efficiency or overnight sleep. **Automatic sleep remains disabled** (`pmset sleep 0`) and this experimental stack is not included in the default installer. **A delayed render-engine GPU Restart was observed at 13:08:40, after the successful cycles; an earlier matching hang predates these tests, so the cause is unresolved.** See [S0ix RTC evidence](docs/S0IX-INITIAL-RTC-WAKE-20261123.md), [GPU hang follow-up](docs/POST-S0IX-GPU-RCS-RESET-20261123.md), and [sleep limitations](docs/SLEEP.md).

## Installation — reproduce the tested setup

This is the **existing-install workflow**: macOS Tahoe and OpenCore must already boot. Windows 11 is retained; no USB drive is used. For a new installation, follow [first boot](docs/LEGACY-FIRST-BOOT.md) and [internal SSD dual boot](docs/INTERNAL-BOOT.md) first.

**Before starting:** confirm access to Windows Boot Manager, back up your working `EFI/OC`, and have an external keyboard/mouse available until the Surface input drivers work. Check the EFI partition identifier with `diskutil list` on macOS; below it is `disk0s1`. Stop if a command reports an error.

### 1. Graphics — Metal 2

In **Windows PowerShell (Administrator)**:

```powershell
git clone https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh.git "$HOME\Downloads\SL4-Tahoe-Git"
mountvol S: /S
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\prepare_full_driver_pack.py" --source "S:\EFI" --out "$HOME\Downloads\SL4-FULL-DRIVERS" --cache "$HOME\Downloads\SL4-KEXT-CACHE"
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode prepare --dvmt-60 --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
mountvol S: /D
```

Copy `SL4-FULL-DRIVERS/macOS-Installers/WhateverXe-Graphics-0.4.4.pkg` from Windows to macOS Downloads using the internal Windows partition. In **macOS Terminal**:

```bash
sudo installer -pkg "$HOME/Downloads/WhateverXe-Graphics-0.4.4.pkg" -target /
```

Return to **Windows PowerShell (Administrator)**:

```powershell
mountvol S: /S
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode enable --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
mountvol S: /D
```

Restart into macOS and verify `system_profiler SPDisplaysDataType` reports **Metal 2**. The tested profile uses WhateverXe 0.8.3, WhateverXe Graphics 0.4.4 and **60 MB DVMT**. Graphics 0.4.4 also configures Tahoe's CoreMedia scaling compatibility flag. [Technical details](docs/VALIDATED-METAL-SL4.md).

### 1b. Internal display sleep / wake — persistent eDP fix

The tested Surface now recovers the **physical internal screen** when using the sleep/power button and closing/reopening the lid. The fix is part of a versioned, offline **WhateverXe 0.8.3** add-on and keeps existing Metal 2 graphics and GPU recovery. It updates the existing internal OpenCore configuration; it is **not** a complete EFI or a generic patch for other hardware.

Download the [eDP fix package](packages/SL4-WEX-0.8.3-EDP-KeepSoftSleep.zip), or use it directly from this cloned repository. In **macOS Terminal** with your existing Tahoe installation already accelerated:

```bash
diskutil list
sudo python3 "$HOME/Downloads/SL4-Tahoe-Git/scripts/install_edp_keep_macos.py" check --esp disk0s1
sudo python3 "$HOME/Downloads/SL4-Tahoe-Git/scripts/install_edp_keep_macos.py" apply --esp disk0s1
```

**Replace `disk0s1` with the actual internal EFI partition identifier.** The script verifies your CPU/GPU, graphics donor, WhateverXe version and OpenCore 1.0.8 compatibility, backs up the entire private `EFI/OC`, keeps the previous kext, and never edits `EFI/Microsoft`. Restart macOS after installation and check that your display works. For a standalone ZIP download, extract it and run the included `install_edp_keep_macos.py` from its folder.

**Rollback** (then restart):

```bash
sudo python3 "$HOME/Downloads/SL4-Tahoe-Git/scripts/install_edp_keep_macos.py" rollback --esp disk0s1
```

**This eDP add-on** only fixes **display-off / screen wake**. A separate [optional S0ix beta release](docs/QUICKSTART-S0IX.md) now bundles a byte-verified DMC/WhateverXe driver with S0ixStandby and SSDT-DEEPIDLE. Two short genuine Deep Idle RTC wakes (8 and 71 seconds) succeeded. Longer-duration system sleep, lid/button wake and battery drain require independent validation; automatic idle sleep remains disabled.

### Browser video

Video playback has been tested successfully in Safari on this Surface. The full results and optional diagnostic checker are in [media notes](docs/MEDIA.md); the main README does not maintain a codec-compatibility list.

### 2. Built-in keyboard, trackpad and battery

Follow the [tested Tiger Lake BigSurface installation](docs/INPUT-KEYBOARD-TRACKPAD.md). It builds and installs five drivers: VoodooGPIO, VoodooSerial, VoodooInput, BigSurface and BigSurfaceHIDDriver. **Do not enable the generic conflicting VoodooI2C/SMCBatteryManager candidates.**

After the input drivers work, set Apple-style trackpad preferences in macOS Terminal:

```bash
curl -fL "https://raw.githubusercontent.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/main/scripts/configure_surface_trackpad.sh" -o "$HOME/Downloads/configure_surface_trackpad.sh" && sh "$HOME/Downloads/configure_surface_trackpad.sh"
```

### 3. Speakers, microphone and brightness

In **macOS Terminal**, download the current repository (skip the clone if it already exists):

```bash
git clone https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh.git "$HOME/Downloads/SL4-Tahoe-Git"
```

If previously cloned, use `git -C "$HOME/Downloads/SL4-Tahoe-Git" pull --ff-only` instead.

Install **audio** and **brightness**, one command at a time:

```bash
sudo python3 "$HOME/Downloads/SL4-Tahoe-Git/scripts/install_audio_macos.py" apply --esp disk0s1
sudo python3 "$HOME/Downloads/SL4-Tahoe-Git/scripts/install_brightness_macos.py" apply --esp disk0s1
```

Restart macOS. Both changes are stored in OpenCore and persist across reboots; no startup service is needed.

The audio installer pins **SimpleHDA 1.0.2**, works with Lilu 1.7.2 and AppleALC 1.9.8, and selects **ALC274 layout 35**. The brightness installer **adds `SSDT-PNLF` if absent** (including fresh EFI builds), or patches an existing table from **UID 14 to UID 19**, the tested WhateverXe backlight profile. It changes only the PNLF ACPI table and, when needed, its OpenCore enable entry. Both installers verify prerequisites and create full `EFI/OC` backups, including a Windows-accessible copy on the EFI partition. They do not edit `EFI/Microsoft`.

### 4. Verify

In macOS Terminal:

```bash
system_profiler SPDisplaysDataType
system_profiler SPAudioDataType
ioreg -p IOACPIPlane -r -n PNLF -l -w0
```

Check **System Settings → Displays → Brightness**, play sound, record from the built-in microphone and test keyboard/trackpad gestures.

**Rollback** individual post-install changes (then restart):

```bash
sudo python3 "$HOME/Downloads/SL4-Tahoe-Git/scripts/install_brightness_macos.py" rollback --esp disk0s1
sudo python3 "$HOME/Downloads/SL4-Tahoe-Git/scripts/install_audio_macos.py" rollback --esp disk0s1
```

Backups are saved in `~/Downloads/SL4-BRIGHTNESS-BACKUPS` and `~/Downloads/SL4-AUDIO-BACKUPS`. If macOS no longer boots, use Windows Boot Manager to restore the pre-change `EFI/OC` copy from the internal EFI; do not format the ESP.

## Documentation

[**S0ix quick start**](docs/QUICKSTART-S0IX.md) · [S0ix v0.2.0 beta release notes](docs/RELEASE-NOTES-S0IX.md) · [Drivers](docs/DRIVERS.md) · [Graphics](docs/VALIDATED-METAL-SL4.md) · [eDP screen wake](docs/EDP-WAKE.md) · [System sleep limits](docs/SLEEP.md) · [Deep sleep research](docs/SYSTEM-SLEEP-RESEARCH.md) · [Experimental TGL DMC candidate](docs/DMC-SLEEP-TRIAL.md) · [First confirmed RTC wake](docs/S0IX-INITIAL-RTC-WAKE-20261123.md) · [Battery charging notes](docs/BATTERY.md) · [Low-battery CPU throttle investigation and safe AC retry](docs/POWER-RECOVERY.md) · [Keyboard/trackpad](docs/INPUT-KEYBOARD-TRACKPAD.md) · [Full-performance setup](docs/FULL-PERFORMANCE.md) · [EFI safety](docs/SAFETY.md)

**Cross-platform preparation (experimental):** [hardware detection, private EFI backups, checksum-verified staging and offline toolkit](docs/UNIVERSAL-SETUP.md). Run the redacted scanner before selecting a hardware profile; this is not a certified one-click clean installer. For a read-only current-macOS compatibility and crash summary, run `python3 scripts/sl4_stability_audit_macos.py`.

Keep private SMBIOS serial, MLB, SystemUUID and ROM values out of public repositories. Community project; not affiliated with Microsoft or Apple.
