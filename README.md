<p align="center"><img src="assets/hero.svg" alt="Surface Laptop 4 with macOS Tahoe" width="100%"></p>

# Surface Laptop 4 — macOS Tahoe

**Install macOS Tahoe using Windows.** Quick Start prepares your personal OpenCore EFI, Apple macOS Recovery, compatible Surface drivers and a bootable USB. After installation, finish the macOS hardware setup and keep Windows in dual boot.

## Quick Start

**Start on Windows. You do not need macOS installed.**

1. [**Download Quick Start for Windows**](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/archive/refs/tags/sl4-tahoe-v0.3.0-beta.zip) and click **Extract All**.
2. Open the extracted folder and double-click **`QuickStart.cmd`**.
3. Press **1 — Install Tahoe from Windows**. The assistant prepares OpenCore, downloads Apple Recovery and the driver bundle, then asks which **USB drive** to prepare.
4. On the Surface, disable **Secure Boot** in UEFI (keep your Windows BitLocker recovery key), plug in the USB, hold **Volume Down**, press **Power**, and select **macOS Base System** in OpenCore.
5. Install Tahoe into **free space for macOS** (leave Windows partitions untouched). After installation, open **`QuickStart-Mac.command`** from the USB's `SL4DATA` partition to finish graphics and drivers.

**[Detailed Quick Start — click-by-click Windows → Tahoe installation](docs/QUICKSTART.md)**

Want to keep the existing USB-free dual boot after installation? Follow [internal OpenCore setup](docs/INTERNAL-BOOT.md).

### Tahoe is already installed

Select **2 — Tahoe already installed** in Windows Quick Start to download the driver recovery package. In macOS, use [Hardware and driver setup](docs/DRIVERS.md) or [the ready-made S0ix/DMC driver installer](docs/QUICKSTART-S0IX.md).

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
