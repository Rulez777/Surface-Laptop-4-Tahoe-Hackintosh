<p align="center"><img src="assets/hero.svg" alt="Surface Laptop 4 running macOS Tahoe" width="100%"></p>

# Surface Laptop 4 — macOS Tahoe

OpenCore configuration and drivers for the **Microsoft Surface Laptop 4 Intel (13.5-inch)**. Tested on **macOS Tahoe 26.7.1**, with **Metal 2** acceleration and **Windows 11 dual boot** from the internal SSD.

## Hardware

| Component | Tested configuration |
| --- | --- |
| CPU | Intel Core i7-1185G7 (Tiger Lake) |
| GPU | Intel Iris Xe 96 EU (`8086:9A49`) |
| RAM | 16 GB |
| SSD | Samsung PM991 |
| Wi-Fi / Bluetooth | Intel AX201 |
| Audio | Intel HDA `8086:A0C8`, Realtek ALC274 |
| Display | 2496 × 1664, HiDPI |
| Bootloader | OpenCore 1.0.8 |

## Hardware support

| Feature | Status |
| --- | --- |
| macOS Tahoe / internal SSD boot | **Working** |
| Windows 11 dual boot | **Working** |
| Intel Iris Xe / Metal 2 | **Working** |
| Internal HiDPI and external DisplayPort displays | **Working** |
| Intel AX201 Wi-Fi / Bluetooth | **Working** |
| Built-in speakers | **Working** |
| Built-in microphone | **Working** |
| Keyboard, trackpad and multitouch | **Working** |
| Battery percentage | **Working** |
| CPU temperature / automatic fan / performance profiles | **Working** |
| Surface Dock | **Working** |
| Internal display brightness controls | In progress |
| Sleep / wake | In progress |

All working results are based on the tested Surface Laptop 4 Intel. Untested audio jacks and other hardware variants are not implied.

## Installation

**Requirements:** Surface Laptop 4 Intel, bootable macOS Tahoe, internal OpenCore EFI, Windows 11 administrator access for GPU setup, and Python 3. No USB drive is required for the existing-install workflow. For initial installation, see [first boot](docs/LEGACY-FIRST-BOOT.md) and [internal dual boot](docs/INTERNAL-BOOT.md).

### Graphics: Metal 2

In **Windows PowerShell (Administrator)**, clone the repository and mount the internal EFI:

```powershell
git clone https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh.git "$HOME\Downloads\SL4-Tahoe-Git"
mountvol S: /S
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\prepare_full_driver_pack.py" --source "S:\EFI" --out "$HOME\Downloads\SL4-FULL-DRIVERS" --cache "$HOME\Downloads\SL4-KEXT-CACHE"
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode prepare --dvmt-60 --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
mountvol S: /D
```

Copy `SL4-FULL-DRIVERS/macOS-Installers/WhateverXe-Graphics-0.4.4.pkg` to macOS Downloads using the Windows partition. Install in **macOS Terminal**:

```bash
sudo installer -pkg "$HOME/Downloads/WhateverXe-Graphics-0.4.4.pkg" -target /
```

Back in **Windows PowerShell (Administrator)**, enable hardware acceleration:

```powershell
mountvol S: /S
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode enable --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
mountvol S: /D
```

The tested GPU configuration uses 60 MB DVMT (`WhateverXePhysicalGGC=0xFEC1`), WhateverXe 0.8.3 and [WhateverXe Graphics 0.4.4](https://github.com/b00t0x/WhateverXe-Graphics/releases/tag/v0.4.4). See [validated graphics configuration](docs/VALIDATED-METAL-SL4.md).

### Audio: speakers and microphone

The tested audio stack is **Lilu 1.7.2 → AppleALC 1.9.8 → SimpleHDA 1.0.2**, with **ALC274 layout 35**. SimpleHDA restores the AppleHDA functionality removed from macOS Tahoe.

In **macOS Terminal**, clone the repository if needed and install audio:

```bash
git clone https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh.git "$HOME/Downloads/SL4-Tahoe-Git"
sudo python3 "$HOME/Downloads/SL4-Tahoe-Git/scripts/install_audio_macos.py" apply --esp disk0s1
```

Verify the EFI device identifier with `diskutil list` and change `--esp` if necessary. The installer verifies the `8086:A0C8` controller, downloads **SimpleHDA 1.0.2** with a pinned SHA-256 checksum, backs up the current `EFI/OC`, installs the kext and updates `config.plist`. It preserves `EFI/Microsoft`, boot order and all existing partitions. Restart macOS to activate the driver.

Verify both devices with:

```bash
system_profiler SPAudioDataType
```

Rollback to the backed-up OpenCore configuration:

```bash
sudo python3 "$HOME/Downloads/SL4-Tahoe-Git/scripts/install_audio_macos.py" rollback --esp disk0s1
```

Backups are saved under `~/Downloads/SL4-AUDIO-BACKUPS` and, when space permits, as a separate `EFI/OC-SL4-AUDIO-BACKUP-*` directory for Windows-only recovery. The script refuses to overwrite an existing SimpleHDA installation.

### Keyboard, trackpad and battery

Use the tested **BigSurface Tiger Lake** driver stack. The generic optional-driver pack does not automatically enable it.

[Installation guide](docs/INPUT-KEYBOARD-TRACKPAD.md) · [SL4 input driver build](experiments/sl4-input/README.md)

For Apple-style trackpad preferences:

```bash
curl -fL "https://raw.githubusercontent.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/main/scripts/configure_surface_trackpad.sh" -o "$HOME/Downloads/configure_surface_trackpad.sh" && sh "$HOME/Downloads/configure_surface_trackpad.sh"
```

## Documentation

[Driver status](docs/DRIVERS.md) · [Graphics](docs/VALIDATED-METAL-SL4.md) · [Performance](docs/FULL-PERFORMANCE.md) · [Internal boot](docs/INTERNAL-BOOT.md) · [EFI safety](docs/SAFETY.md)

Never publish your personalized OpenCore `PlatformInfo` identifiers (serial number, MLB, SystemUUID or ROM). Back up the known-good EFI before changing drivers. This is a community project, not affiliated with Microsoft or Apple.
