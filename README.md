<p align="center"><img src="assets/hero.svg" alt="Surface Laptop 4 with macOS Tahoe" width="100%"></p>

# Surface Laptop 4 — macOS Tahoe

**Install macOS Tahoe using Windows.** Quick Start prepares your personal OpenCore EFI, Apple macOS Recovery, compatible Surface drivers and a bootable USB. After installation, finish the macOS hardware setup and keep Windows in dual boot.

## Quick Start

**Start on Windows. You do not need macOS installed.**

1. [**Download Quick Start for Windows**](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/releases/download/sl4-tahoe-v0.4.2-beta/SL4-Tahoe-Windows-QuickStart-v0.4.2-beta.zip) and click **Extract All**.
2. Open the extracted folder and double-click **`QuickStart.cmd`**.
3. Press **1 — Install Tahoe from Windows**. The assistant prepares OpenCore, downloads Apple Recovery and the driver bundle, then asks which **USB drive** to prepare.
4. On the Surface, disable **Secure Boot** in UEFI (keep your Windows BitLocker recovery key), plug in the USB, hold **Volume Down**, press **Power**. At the **OpenCore boot menu**, use the arrow keys and **Enter** to select **macOS Base System (External)** (sometimes shown as **Recovery**). This is Apple's Recovery installer, **not** Windows Boot Manager or your existing macOS volume. New USBs show Recovery immediately, with 15 seconds to choose; on an older USB press **Space** to reveal hidden auxiliary entries.
5. Install Tahoe into **free space for macOS** (leave Windows partitions untouched). After installation, open **`QuickStart-Mac.command`** from the USB's `SL4DATA` partition to finish graphics and drivers.

**[Detailed Quick Start — click-by-click Windows → Tahoe installation](docs/QUICKSTART.md)**

Want to keep the existing USB-free dual boot after installation? Follow [internal OpenCore setup](docs/INTERNAL-BOOT.md).

### Tahoe is already installed

Select **2 — Tahoe already installed** in Windows Quick Start to download the driver recovery package. In macOS, use [Hardware and driver setup](docs/DRIVERS.md) or [the ready-made S0ix/DMC driver installer](docs/QUICKSTART-S0IX.md).

### All-in-one graphics stability and speaker tuning — v0.4.2 beta

**Critical sleep correction in v0.4.2:** the standard installer now **never writes macOS `pmset` power-policy settings**. It preserves existing sleep timers and the working DMC/S0ix manual sleep + eDP Keep/Softsleep screen wake. v0.4.1 should not be used for a new install because it inadvertently disabled automatic sleep. Recheck physical screen/lid wake on your own hardware.



**The normal Windows-first installer now includes the RCS graphics patch and original Surface Dolby speaker correction.** No separate graphics patch download, manual EFI edit or manual audio profile import.

Windows QuickStart includes the byte-pinned Surface RCS driver and Dolby FIR profile, fetches and verifies the original APOMac application, and stages everything on **SL4DATA**. On Tahoe use **option 1** in `QuickStart-Mac.command`: the first accelerated boot uses verified RCS single-port + DMC/eDP; APOMac is installed with **Clear Speech** (−3 dB preamp, +1.88 dB at 2.5 kHz, device-scoped) and login autostart.

Only **System Audio Recording consent** must be approved in macOS on first run. For already installed Tahoe, **option 2** checks and applies missing components. Original Windows boot data and personal EFI backups are preserved.

**[All-in-one technical guide, Dolby details and rollback](docs/AUDIO-ALL-IN-ONE.md).** Clean install of the newly integrated v0.4.2 USB build has not yet been confirmed on another machine. A successful individual RCS and audio installation on the reference Surface is not proof of a fully tested fresh install.

### Important Iris Xe graphics stability update (November 23, 2026)

**Previously released RCS Stability 0.1.0 beta** fixes the Tiger Lake Execlist context-switch/preemption hang observed in Spectator 3 and WindowServer on the reference Surface. After the patch, the machine booted with `SL4RCSSinglePortReady = Yes`, completed **400,000 Metal command buffers** without error and showed **no new GPU Reset reports after subsequent gameplay**. The owner reported FPS rising from approximately 14 to 30 after several minutes; the exact cause of that improvement has **not** been established.

[**RCS Stability download and safe macOS installation / rollback guide**](docs/QUICKSTART-RCS.md). The v0.4.1 all-in-one Quick Start **includes and automatically selects** this pinned RCS binary in its first graphics transition. Separate patch installation is now a legacy recovery option only; no previous macOS is required to prepare the Windows USB. No unsupported hardware receives this patch automatically. Your personal EFI and Windows installation are not included in the public package.

**Not yet certified:** indefinite gaming stability, all sleep/wake combinations, VP9/AV1 hardware decoding in Safari, other hardware models and other Tahoe builds.

### Different version or hardware

Select **3 — Advanced / Experiments** to select a different Apple Recovery version or board identity. Hardware profiles are selected from detected devices where available; unknown configurations are not silently treated as the SL4 i7 profile. Keep a separate recovery copy when experimenting.

## Hardware

| Device or feature | Surface Laptop 4 Intel |
| --- | --- |
| Tahoe on internal SSD | **Working** |
| Windows + macOS dual boot | **Working** |
| Intel Iris Xe / Metal 2 | **Working** |
| Built-in HiDPI display and brightness | **Working** |
| Keyboard / trackpad / multitouch | **Working** |
| Intel Wi-Fi / Bluetooth | **Working** |
| Speakers / microphone | **Working** |
| Battery status | **Working** |
| CPU temperature / thermal monitoring | **Working** |
| Surface Dock | **Working** |
| Display sleep / wake | **Working** |
| System S0ix sleep / wake | **Working** |

**Primary ready-made profile:** Surface Laptop 4 Intel 13.5-inch, Core i7-1185G7, Iris Xe 8086:9A49, macOS Tahoe 26.7.1, OpenCore 1.0.8. Windows Quick Start can prepare installation files on **any Windows computer**; hardware-specific EFI support on a different target must be selected explicitly.

## What Quick Start prepares

- **Personal OpenCore EFI:** fresh SMBIOS identity, Surface ACPI, bootloader, USB map and working keyboard/trackpad drivers.
- **Apple Tahoe Recovery:** downloaded directly from Apple through OpenCore's macrecovery.
- **Installation USB:** separate FAT32 boot and exFAT driver/data partitions with file-integrity checks.
- **Driver setup:** WhateverXe Graphics, custom Surface sleep/graphics package, audio, brightness and trackpad setup scripts.
- **Windows preservation:** no automatic modifications to the internal Windows disk, EFI, bootloader, BCD or partitions during USB preparation.

For an internal-SSD installation, create free space in Windows Disk Management and select **only that space** in macOS Recovery. A USB Ethernet adapter/dock may be necessary for Apple Recovery to download macOS.

## Project

[Quick Start](docs/QUICKSTART.md) · [Windows installer](scripts/QuickStart-Windows.ps1) · [macOS driver setup](scripts/QuickStart-Mac.command) · [Hardware drivers](docs/DRIVERS.md) · [Dual boot](docs/INTERNAL-BOOT.md) · [Existing Tahoe support](docs/QUICKSTART-S0IX.md) · [Advanced setup](docs/UNIVERSAL-SETUP.md)

Only original upstream recovery/installers and open-source drivers are downloaded. Your private serial/MLB/UUID and Windows data stay on your own computer. Not affiliated with Apple or Microsoft.
