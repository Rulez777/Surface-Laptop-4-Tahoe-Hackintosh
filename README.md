<p align="center"><img src="assets/hero.svg" alt="Surface Laptop 4 running macOS Tahoe" width="100%"></p>

# Surface Laptop 4 — macOS Tahoe

**Microsoft Surface Laptop 4 Intel · macOS Tahoe 26.7.1 · OpenCore 1.0.8 · Metal 2 · Windows 11 dual boot**

OpenCore configuration, driver stack and installation tools for macOS Tahoe on the Intel Surface Laptop 4. Internal SSD boot and dual boot without removable media.

## Hardware

| Component | Configuration |
| --- | --- |
| Model | Surface Laptop 4 Intel, 13.5-inch |
| CPU | Intel Core i7-1185G7, Tiger Lake-U |
| GPU | Intel Iris Xe 96 EU, PCI `8086:9A49` |
| RAM | 16 GB |
| SSD | Samsung PM991 |
| Wireless | Intel AX201 |
| Internal screen | 2496 × 1664, HiDPI |
| Surface Serial Hub | ACPI `MSHW0084`, UART `8086:A0A8` |
| Operating systems | macOS Tahoe 26.7.1 / Windows 11 |

## Hardware support

| Feature | Status |
| --- | --- |
| macOS Tahoe / internal SSD boot | **Working** |
| Windows 11 dual boot | **Working** |
| Intel Iris Xe / Metal 2 acceleration | **Working** |
| Internal HiDPI display | **Working** |
| External DisplayPort monitor, 2560 × 1440 | **Working** |
| Intel AX201 Wi-Fi | **Working** |
| Built-in keyboard | **Working** |
| Built-in trackpad, tap-to-click and multitouch | **Working** |
| Battery percentage | **Working** |
| Fan operation / Surface performance profiles | **Working** |
| Audio and microphone | In progress |
| Bluetooth | In progress |
| Brightness controls | In progress |
| Sleep / wake | In progress |
| Complete Surface Dock functionality | In progress |
| CPU temperature telemetry / custom fan curve | In progress |

## Driver stack

| Component | Version | Function |
| --- | --- | --- |
| [OpenCore](https://github.com/acidanthera/OpenCorePkg) | 1.0.8 | UEFI boot |
| [Lilu](https://github.com/acidanthera/Lilu) | 1.7.2 | Kernel patching |
| [VirtualSMC](https://github.com/acidanthera/VirtualSMC) | 1.3.8 | SMC emulation |
| [WhateverXe](https://github.com/b00t0x/WhateverXe) | 0.8.3 | Intel Iris Xe support |
| [WhateverXe Graphics](https://github.com/b00t0x/WhateverXe-Graphics/releases/tag/v0.4.4) | 0.4.4 | Tahoe graphics package |
| [AMFIAnchor](https://github.com/b00t0x/AMFIAnchor) | 0.1.2 | Graphics compatibility |
| [AirportItlwm](https://github.com/OpenIntelWireless/itlwm) | 2.4.0 | Intel AX201 Wi-Fi |
| VoodooGPIO | 1.2.0 | Tiger Lake GPIO |
| VoodooSerial | 1.2 | Tiger Lake UART |
| [BigSurface](https://github.com/Xiashangning/BigSurface) | 1.2.0 | Surface Serial Hub / battery / HID |
| BigSurfaceHIDDriver | 1.0.0 | Keyboard and trackpad |
| VoodooInput | 1.1.3 | Multitouch |

### Surface keyboard and trackpad

**Working:** integrated keyboard, trackpad, tap-to-click, two-finger secondary click and multitouch.

Surface serial-hub configuration:

- ACPI: `\_SB.SSH` / `MSHW0084`
- UART: `\_SB.PC00.UA00` / `8086:A0A8` / 4 Mbps
- GPIO: `\_SB.GPI0` / interrupt pin `0x012A`
- Native Surface Laptop 4 ACPI; no Surface Laptop 5 `SSDT-SAM` injection
- BigSurface input stack; conflicting VoodooI2C / SMCBatteryManager entries disabled

[Keyboard and trackpad installation](docs/INPUT-KEYBOARD-TRACKPAD.md) · [Driver builder and EFI staging](experiments/sl4-input/README.md)

### Trackpad gestures

Apple-style tap-to-click, two-finger secondary click, multitouch preferences and disabled three-finger Look Up gesture:

~~~bash
curl -fL --retry 3 "https://raw.githubusercontent.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/main/scripts/configure_surface_trackpad.sh" -o "$HOME/Downloads/configure_surface_trackpad.sh" && sh "$HOME/Downloads/configure_surface_trackpad.sh"
~~~

Execution: macOS Terminal, regular account, **without `sudo`**.

### Battery and cooling

- Battery percentage: **Working** via BigSurface.
- Surface performance profiles: **Working** via Surface Serial Hub / `PerformanceMode`.
- Automatic fan operation: **Working**.
- Direct fan RPM control and custom 80 °C fan-speed curve: In progress.
- CPU die temperature key `TC0D`: unavailable without an appropriate SMC temperature provider.
- Additional thermal software: experimental; not included in the standard install.

[Cooling source research](https://github.com/torvalds/linux/blob/master/drivers/platform/surface/surface_platform_profile.c)

## Installation — existing macOS Tahoe

**Requirements:** installed bootable macOS Tahoe, internal OpenCore EFI, Windows 11 administrator access, Python 3, Git. No USB drive required.

### 1. Repository and internal EFI

Windows PowerShell (Administrator):

~~~powershell
git clone https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh.git "$HOME\Downloads\SL4-Tahoe-Git"
~~~

~~~powershell
mountvol S: /S
~~~

### 2. Graphics package and OpenCore validator

~~~powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\prepare_full_driver_pack.py" --source "S:\EFI" --out "$HOME\Downloads\SL4-FULL-DRIVERS" --cache "$HOME\Downloads\SL4-KEXT-CACHE"
~~~

### 3. 60 MB DVMT configuration

Required Surface firmware profile: `WhateverXePhysicalGGC = 0xFEC1`, fixed 60 MB DVMT.

~~~powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode prepare --dvmt-60 --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
~~~

~~~powershell
mountvol S: /D
~~~

`-wex-noaccel` remains enabled until the macOS graphics package installation finishes.

### 4. WhateverXe Graphics 0.4.4

Package path on Windows: `SL4-FULL-DRIVERS/macOS-Installers/WhateverXe-Graphics-0.4.4.pkg`.

Copy the package to macOS `~/Downloads` using the internal Windows partition.

macOS Terminal:

~~~bash
shasum -a 256 "$HOME/Downloads/WhateverXe-Graphics-0.4.4.pkg"
~~~

Required SHA-256: `f4c2d680a7c52c33a3f038ce6945da0aa2cc044e62b935a52ea046c7c473cfec`.

~~~bash
sudo installer -pkg "$HOME/Downloads/WhateverXe-Graphics-0.4.4.pkg" -target /
~~~

### 5. Enable Metal 2

Windows PowerShell (Administrator), after graphics package installation:

~~~powershell
mountvol S: /S
~~~

~~~powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode enable --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
~~~

~~~powershell
mountvol S: /D
~~~

macOS graphics verification:

~~~bash
system_profiler SPDisplaysDataType
~~~

Expected graphics: Intel Iris Xe; **Metal 2**; up to **1536 MB VRAM**.

Boot arguments: `npci=0x2000 -allow3d -disablegfxfirmware -igfxdvmt`.

### 6. Keyboard, trackpad and battery

BigSurface input-driver installation is a separate OpenCore EFI stage, with driver dependency checks, backups and rollback.

[Keyboard and trackpad guide](docs/INPUT-KEYBOARD-TRACKPAD.md) · [Windows driver installation](experiments/sl4-input/INSTALL-RU.md) · [macOS driver installation](experiments/sl4-input/INSTALL-MACOS-RU.md)

The generic fresh-EFI builder does not automatically enable the BigSurface input stack.

## Fresh installation

- [GenSMBIOS](https://github.com/corpnewt/GenSMBIOS): `MacBookPro16,2`
- [EFI generator](scripts/build_efi.py): device-specific OpenCore EFI; `--dvmt-60` for matching DVMT configuration
- [Initial macOS installation](docs/LEGACY-FIRST-BOOT.md)
- [Internal SSD boot and dual boot](docs/INTERNAL-BOOT.md)

**Private data:** SMBIOS serial, MLB, SystemUUID and ROM. Independent boot verification and EFI backup required before replacing an existing bootable EFI.

## Documentation

[Full configuration](docs/FULL-PERFORMANCE.md) · [Graphics and DVMT](docs/VALIDATED-METAL-SL4.md) · [All drivers](docs/DRIVERS.md) · [Keyboard and trackpad](docs/INPUT-KEYBOARD-TRACKPAD.md) · [Internal boot](docs/INTERNAL-BOOT.md) · [RTC0 ACPI fix](docs/RTC0-CASE-STUDY.md) · [Windows protection](docs/SAFETY.md)

## EFI and Windows safety

- Windows Boot Manager and `EFI/Microsoft` preserved.
- `EFI/OC` backup before OpenCore and kext changes.
- Separate Windows boot entry and rollback configuration.
- Surface-specific `SSDT-RTC0-SL4.aml` required.
- No default installation of experimental thermal-control software.

Community project; not affiliated with Microsoft or Apple.
