<p align="center"><img src="assets/hero.svg" alt="Surface Laptop 4 with macOS Tahoe" width="100%"></p>

# Surface Laptop 4 — macOS Tahoe

**Install macOS Tahoe using Windows.** Quick Start prepares your personal OpenCore EFI, Apple macOS Recovery, compatible Surface drivers and a bootable USB. After installation, finish the macOS hardware setup and keep Windows in dual boot.

## Graphics performance v0.1.7 beta

[Integrated beta and GPU test results](docs/GRAPHICS-PERFORMANCE-V017.md). The Windows-first build includes the exact Surface-tested v0.1.7 graphics payload and local compute-hint fix. It corrects missing Unity compute pipelines and stale MTLHeap depth sampling. The RCS single-port/native-queue trial flags are deliberately disabled in the default profile; they remain opt-in because the user-approved reference EFI has them disabled. The v0.5.0 download below is the historical recovery build; use the v0.5.2 sleep/wake beta distribution for the updated All-in-One after CI publishes it. Until then use the graphics-fixes-v017 branch snapshot and QuickStart.cmd. Long-term stability and clean-install validation remain open.

## Surface input and lid-wake profile

The Windows-first All-in-One now stages the pinned Surface Laptop 4 Intel keyboard/trackpad and lid-wake profile (VoodooGPIO 1.2.5, BigSurface 1.2.1, and SSDT-SL4-LIDWAKE.aml). Temporary GPIO probe telemetry and the eDP diagnostic trace flag are excluded. Package and EFI integration tests pass; the clean GPIO rebuild and SAM keyboard/trackpad wake still require physical regression on the reference Surface. See docs/INPUT-KEYBOARD-TRACKPAD.md.

## Quick Start

**Start on Windows. You do not need macOS installed.**

1. [**Download Quick Start for Windows**](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/releases/download/sl4-tahoe-v0.5.2-sleepwake-beta/SL4-Tahoe-Windows-QuickStart-v0.5.2-sleepwake-beta.zip) and click **Extract All**.
2. Open the extracted folder and double-click **`QuickStart.cmd`**.
3. The automatic assistant builds OpenCore, downloads Apple Recovery and all verified drivers, then detects the eligible **USB drive**; erasing it still requires confirmation.
4. On the Surface, disable **Secure Boot** in UEFI (keep your Windows BitLocker recovery key), plug in the USB, hold **Volume Down**, press **Power**. At the **OpenCore boot menu**, use the arrow keys and **Enter** to select **macOS Base System (External)** (sometimes shown as **Recovery**). This is Apple's Recovery installer, **not** Windows Boot Manager or your existing macOS volume. New USBs show Recovery immediately, with 15 seconds to choose; on an older USB press **Space** to reveal hidden auxiliary entries.
5. Install Tahoe into **free space for macOS** (leave Windows partitions untouched). After installation, open **`QuickStart-Mac.command`** from the USB's `SL4DATA` partition to finish graphics and drivers.

**[Detailed Quick Start — click-by-click Windows → Tahoe installation](docs/QUICKSTART.md)**

Want to keep the existing USB-free dual boot after installation? Follow [internal OpenCore setup](docs/INTERNAL-BOOT.md).

### Tahoe is already installed

If Tahoe is already installed, open **QuickStart-Advanced.cmd** and select **2 — Tahoe already installed** to prepare a repair package. In macOS, use [Hardware and driver setup](docs/DRIVERS.md) or [the ready-made S0ix/DMC driver installer](docs/QUICKSTART-S0IX.md).

### Autopilot v0.5.0 beta — fewer steps, no manual driver selection

Start from Windows by double-clicking **`QuickStart.cmd`**. The default route now automatically prepares the complete installer and selects the only eligible USB disk (with **explicit disk erase confirmation**). After Apple's Recovery and Setup Assistant, opening `SL4DATA/QuickStart-Mac.command` **automatically chooses fresh install versus repair**. The next macOS login validates Metal 2, DMC/S0ix, eDP wake, heap-depth, video and Dolby, then records readiness on USB. RCS trial hooks are not required and remain opt-in. Open the same `QuickStart.cmd` in Windows again to automatically enter the existing safe internal-boot stage; the Microsoft bootloader remains backed up and the user still approves firmware changes.

**UEFI keys, selecting a safe macOS partition, installing macOS via Apple's GUI, administrator approval and APOMac audio privacy consent cannot be bypassed.** This is automated coordination, **not** an unattended one-click macOS installation. [Exact automatic flow and recovery](docs/AUTOPILOT.md).

### Integrated RCS graphics and speaker tuning (v0.4.2 base)

**Critical sleep correction in v0.4.2:** the standard installer now **never writes macOS `pmset` power-policy settings**. It preserves existing sleep timers and the working DMC/S0ix manual sleep + eDP Keep/Softsleep screen wake. v0.4.1 should not be used for a new install because it inadvertently disabled automatic sleep. Recheck physical screen/lid wake on your own hardware.



**The normal Windows-first installer includes the pinned RCS graphics payload and original Surface Dolby speaker correction. The RCS single-port/native-queue trial flags are not enabled by default; the tested heap-depth, DMC and eDP profile is retained.** No separate graphics patch download, manual EFI edit or manual audio profile import.

Windows QuickStart includes the byte-pinned Surface RCS driver and Dolby FIR profile, fetches and verifies the original APOMac application, and stages everything on **SL4DATA**. On Tahoe run `QuickStart-Mac.command` (automatic mode): the first accelerated boot uses the reference DMC/eDP + heap-depth profile, while RCS trial hooks remain disabled; APOMac is installed with **Clear Speech** (−3 dB preamp, +1.88 dB at 2.5 kHz, device-scoped) and login autostart.

Only **System Audio Recording consent** must be approved in macOS on first run. For already installed Tahoe, automatic mode checks and applies missing components. Original Windows boot data and personal EFI backups are preserved.

**[All-in-one technical guide, Dolby details and rollback](docs/AUDIO-ALL-IN-ONE.md).** Clean install of the newly integrated v0.5.0 USB build has not yet been confirmed on another machine. A successful individual RCS and audio installation on the reference Surface is not proof of a fully tested fresh install.

### Important Iris Xe graphics stability update (November 23, 2026)

**Previously released RCS Stability 0.1.0 beta** mitigates some Tiger Lake Execlist context-switch/preemption hangs, but **does not fully prevent RCS GPU resets** on the reference Surface. A later reset on November 23 at 23:32 CET was confirmed with `SL4RCSSinglePortReady = Yes`; see [RCS v0.1.0 regression analysis](docs/RCS-POSTPATCH-RESET-20261123.md). After the patch, the machine booted with `SL4RCSSinglePortReady = Yes`, completed **400,000 Metal command buffers** without error and initially showed **no GPU Reset reports during a limited post-install observation** (later superseded by the 23:32 reset). The owner reported FPS rising from approximately 14 to 30 after several minutes; the exact cause of that improvement has **not** been established.

[**RCS Stability download and safe macOS installation / rollback guide**](docs/QUICKSTART-RCS.md). For an immediate read-only diagnostic on an installed Mac use `zsh scripts/QuickStart-Mac.command --rcs-audit` (or advanced menu 7). This reports the current boot recovery counters separately from recorded GPU resets. The v0.5.2 Autopilot includes this pinned RCS payload in its first graphics transition, but the single-port/native-queue trial flags remain disabled by default. The separate RCS installer remains an explicit opt-in; no previous macOS is required to prepare the Windows USB. No unsupported hardware receives this patch automatically. Your personal EFI and Windows installation are not included in the public package.

**Not yet certified:** RCS stability under ordinary desktop use or prolonged gaming, all sleep/wake combinations, VP9/AV1 hardware decoding in Safari, other hardware models and other Tahoe builds.

### Different version or hardware

Open **QuickStart-Advanced.cmd** and select **3 — Advanced / Experiments** to choose a different Apple Recovery version or board identity. Hardware profiles are selected from detected devices where available; unknown configurations are not silently treated as the SL4 i7 profile. Keep a separate recovery copy when experimenting.

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
