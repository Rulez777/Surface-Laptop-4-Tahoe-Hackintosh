<p align="center"><img src="assets/hero.svg" alt="Surface Laptop 4 running macOS" width="100%"></p>

# Surface Laptop 4 — macOS Tahoe

OpenCore configuration and installation tools for **Microsoft Surface Laptop 4 (Intel)**, with Windows 11 dual boot on the internal SSD.

![macOS](https://img.shields.io/badge/macOS-Tahoe_26.7.1-665fae) ![OpenCore](https://img.shields.io/badge/OpenCore-1.0.8-426ba4) ![GPU](https://img.shields.io/badge/Iris_Xe-Metal_2-24866c)

**Hardware:** Core i7-1185G7 · Intel Iris Xe 96 EU (`8086:9A49`) · 16 GB RAM · Samsung PM991.

**Working:** Tahoe 26.7.1, Metal 2 (1536 MB VRAM), 2496×1664 HiDPI internal display, external 2560×1440 DisplayPort monitor, Intel AX201 Wi-Fi, internal SSD boot and Windows dual boot.

## Quick Start

For an **existing Tahoe installation booting through OpenCore**. Requires Windows PowerShell (Administrator), Python 3, Git and a working internal EFI. No USB drive is needed.

**1. Clone the project and mount the internal EFI.**

```powershell
git clone https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh.git "$HOME\Downloads\SL4-Tahoe-Git"
```

```powershell
mountvol S: /S
```

**2. Download the graphics installer and validator.**

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\prepare_full_driver_pack.py" --source "S:\EFI" --out "$HOME\Downloads\SL4-FULL-DRIVERS" --cache "$HOME\Downloads\SL4-KEXT-CACHE"
```

**3. Apply the 60 MB DVMT profile.** For Surface firmware reporting `WhateverXePhysicalGGC = 0xFEC1`. The tool backs up OpenCore and leaves `-wex-noaccel` enabled until the macOS graphics package is installed.

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode prepare --dvmt-60 --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
```

```powershell
mountvol S: /D
```

**4. Boot Tahoe and install [WhateverXe Graphics 0.4.4](https://github.com/b00t0x/WhateverXe-Graphics/releases/tag/v0.4.4).**

Copy `WhateverXe-Graphics-0.4.4.pkg` from `SL4-FULL-DRIVERS/macOS-Installers/` on the Windows partition into your macOS `~/Downloads` folder. Verify its SHA-256, then install:

```bash
shasum -a 256 "$HOME/Downloads/WhateverXe-Graphics-0.4.4.pkg"
```

Expected: `f4c2d680a7c52c33a3f038ce6945da0aa2cc044e62b935a52ea046c7c473cfec`.

```bash
sudo installer -pkg "$HOME/Downloads/WhateverXe-Graphics-0.4.4.pkg" -target /
```

**5. Return to Windows and enable Metal.**

```powershell
mountvol S: /S
```

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode enable --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
```

```powershell
mountvol S: /D
```

Boot Tahoe and verify acceleration:

```bash
system_profiler SPDisplaysDataType
```

Expected: **Intel Iris Xe · Metal 2 · 1536 MB VRAM**. The resulting boot arguments are `npci=0x2000 -allow3d -disablegfxfirmware -igfxdvmt`.

## Fresh installation

Generate a personal OpenCore EFI with [GenSMBIOS](https://github.com/corpnewt/GenSMBIOS) (`MacBookPro16,2`) and [`scripts/build_efi.py`](scripts/build_efi.py) using `--dvmt-60`. Follow the [installation procedure](docs/LEGACY-FIRST-BOOT.md), then complete the graphics steps above. Keep your serial, MLB, UUID and ROM private.

## Hardware support

| Feature | Status |
| --- | --- |
| Intel Iris Xe / Metal 2 / dual displays | Working |
| Intel AX201 Wi-Fi | Working |
| Built-in keyboard and trackpad | In progress |
| Audio, brightness control, browser video playback | In progress |
| Bluetooth, sleep/wake and full dock support | In progress |

## Documentation

[Full setup](docs/FULL-PERFORMANCE.md) · [Graphics configuration](docs/VALIDATED-METAL-SL4.md) · [Drivers](docs/DRIVERS.md) · [Internal boot](docs/INTERNAL-BOOT.md) · [RTC0 ACPI fix](docs/RTC0-CASE-STUDY.md) · [Windows safety](docs/SAFETY.md)

**Core components:** OpenCore 1.0.8 · Lilu 1.7.2 · WhateverXe 0.8.3 · WhateverXe Graphics 0.4.4 · AMFIAnchor 0.1.2. The Surface-specific `SSDT-RTC0-SL4.aml` is required.

Community project, not affiliated with Apple or Microsoft. Back up your existing EFI and Windows installation before making changes.
