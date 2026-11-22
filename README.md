<p align="center"><img src="assets/hero.svg" alt="Surface Laptop 4 running macOS Tahoe" width="100%"></p>

# Surface Laptop 4 — macOS Tahoe

A tested OpenCore configuration for the **Microsoft Surface Laptop 4 Intel (13.5-inch)**. macOS Tahoe 26.7.1 runs from the internal SSD alongside Windows 11, with Metal 2 graphics, built-in input, audio and screen brightness.

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
| Internal HiDPI and external DisplayPort | **Working** |
| **Internal display brightness controls** | **Working** |
| Intel AX201 Wi-Fi / Bluetooth | **Working** |
| Built-in speakers / microphone | **Working** |
| Keyboard / trackpad / multitouch | **Working** |
| Battery percentage | **Working** |
| CPU temperature / automatic fan / performance profiles | **Working** |
| Surface Dock | **Working** |
| Sleep / wake | In progress |

Verified on one Surface Laptop 4 Intel. Other models, headphone jack and untested hardware are not certified.

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

Restart into macOS and verify `system_profiler SPDisplaysDataType` reports **Metal 2**. The tested profile uses WhateverXe 0.8.3, WhateverXe Graphics 0.4.4 and **60 MB DVMT**. [Technical details](docs/VALIDATED-METAL-SL4.md).

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

[Drivers](docs/DRIVERS.md) · [Graphics](docs/VALIDATED-METAL-SL4.md) · [Keyboard/trackpad](docs/INPUT-KEYBOARD-TRACKPAD.md) · [Full-performance setup](docs/FULL-PERFORMANCE.md) · [EFI safety](docs/SAFETY.md)

Keep private SMBIOS serial, MLB, SystemUUID and ROM values out of public repositories. Community project; not affiliated with Microsoft or Apple.
