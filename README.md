<p align="center"><img src="assets/hero.svg" alt="Illustration of a Surface Laptop 4 running a macOS-style desktop" width="100%"></p>

# Surface Laptop 4 (Intel) — macOS Tahoe with verified Metal 2

A community OpenCore project for **Microsoft Surface Laptop 4 Intel i7-1185G7 / Iris Xe 96 EU (`8086:9A49`)**, dual-booted with Windows 11 on the internal SSD.

![OpenCore](https://img.shields.io/badge/OpenCore-1.0.8-426ba4) ![macOS](https://img.shields.io/badge/Tahoe-26.7.1-665fae) ![GPU](https://img.shields.io/badge/Iris_Xe-Metal_2_verified-24866c)

> **Update: 2026-11-22.** After installing WhateverXe Graphics **0.4.4** and applying the upstream **fixed-60-MB DVMT** workaround, the test Surface boots Tahoe with **Metal 2, 1536 MB dynamic VRAM, a working internal 2496×1664 panel and an external 2560×1440 DisplayPort monitor**. Intel AX201 **Wi-Fi works**. The built-in keyboard and trackpad **do not yet work**, and overall performance is not certified as optimal. This is an observed result on one laptop, **not a universal ready-to-use EFI**.

Full evidence and precise settings: **[Validated Surface Laptop 4 Metal 2 configuration](docs/VALIDATED-METAL-SL4.md)**. The upstream WhateverXe maintainer has been notified in [hardware report #101 (Surface follow-up)](https://github.com/b00t0x/WhateverXe/issues/101#issuecomment-7082305989).

## Compatibility: tested, not assumed

| Feature | Status on the test Surface (2026-11-22) |
| --- | --- |
| Tahoe 26.7.1 on internal APFS + Windows 11 on NTFS | **Booted; Windows partition and Microsoft EFI preserved** |
| OpenCore 1.0.8 on internal ESP, four-second picker | **Booted from internal SSD** |
| Intel Iris Xe 96 EU, Metal | **Metal 2 verified; AppleIntelTGLGraphics actually loaded** |
| Internal eDP LCD 2496×1664 | **Working with acceleration; HiDPI 1248×832** |
| External MSI MPG271QX OLED | **Detected via Thunderbolt/DisplayPort at 2560×1440 59 Hz** |
| Intel AX201 Wi-Fi | **Working** |
| Surface Dock USB hub and Gigabit Ethernet adapter | Devices enumerate; actual full function **not verified** |
| Built-in keyboard and trackpad | **Not working** |
| Bluetooth, audio, battery reporting, touch, cameras | Drivers/devices detected in some tests; functionality **not validated** |
| Sleep/wake, high-refresh external display, endurance, peak speed | **Not yet validated** |

Do not describe this project as fully compatible. `ocvalidate` checks OpenCore configuration structure, **not** device support or boot success.

## Quick Start: reproduce the validated Metal 2 state (existing Tahoe, no removable media)

This **post-install** guide is for a Surface Laptop 4 whose **Tahoe is already bootable** from a known-good OpenCore EFI on the internal SSD. It does not install macOS from scratch; see the [historical first-boot procedure](docs/LEGACY-FIRST-BOOT.md) for the original experiment. Before writing EFI, back up Windows/macOS, record any disk-encryption recovery credentials, preserve your private no-acceleration config, and never overwrite `EFI/Microsoft`, `EFI/BOOT` or partition tables.

**Prerequisites:** confirmed installed Tahoe **26.7+**, Intel Iris Xe with *measured* `WhateverXePhysicalGGC = 0xFEC1` (**60 MB DVMT**) on this machine, OpenCore 1.0.8, Lilu/WhateverXe 0.8.3/AMFIAnchor and injector already in the boot EFI, working macOS input via an external device or on-screen keyboard, Git/Python 3 on Windows and an OpenCore 1.0.8 `ocvalidate.exe`. **Do not apply the 60 MB patch blindly on other hardware.**

**1. Update your local checkout from Windows** (PowerShell, one line):

```powershell
git -C "$HOME\Downloads\SL4-Tahoe-Git" pull --ff-only
```

Clone first if needed: `git clone https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh.git`.

**2. Mount the internal ESP read/write from elevated Windows PowerShell** (never target any external storage):

```powershell
if (!(Test-Path 'S:\EFI\OC\config.plist')) { mountvol S: /S }
```

If you do not already have the official Graphics 0.4.4 pkg and `ocvalidate.exe`, get them using the [full driver pack preparation workflow](docs/FULL-PERFORMANCE.md). The Graphics pkg is a **macOS installer**, not an EFI driver.

**3. Stage the fixed-60-MB DVMT profile while keeping safe framebuffer-only boot**. The script backs up the personalized `config.plist`, verifies required OpenCore dependencies, refuses conflicting iGPU properties and **preserves `-wex-noaccel`**:

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode prepare --dvmt-60 --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
```

Unmount the ESP:

```powershell
mountvol S: /D
```

**4. Boot installed Tahoe in no-acceleration mode; install the official Graphics pkg from your internal Windows partition**, which macOS can read when mounted at `/Volumes/Windows`. Replace `YOUR_WINDOWS_USER`:

```bash
cp "/Volumes/Windows/Users/YOUR_WINDOWS_USER/Downloads/SL4-FULL-DRIVERS/macOS-Installers/WhateverXe-Graphics-0.4.4.pkg" "$HOME/Downloads/"
```

```bash
shasum -a 256 "$HOME/Downloads/WhateverXe-Graphics-0.4.4.pkg"
```

**Expected SHA-256:** `f4c2d680a7c52c33a3f038ce6945da0aa2cc044e62b935a52ea046c7c473cfec`. Stop on any mismatch. Then:

```bash
sudo installer -pkg "$HOME/Downloads/WhateverXe-Graphics-0.4.4.pkg" -target /
```

Confirm **`The install was successful`**. This step is essential: merely adding WhateverXe kexts to OpenCore cannot supply Metal. Do not boot a changed acceleration profile until the installer succeeds.

**5. Return to Windows, remount the same internal ESP, enable Metal safely**. Updated `xe_acceleration.py` refuses to remove `-wex-noaccel` unless `-igfxdvmt` and both exact DVMT Data values are already present.

```powershell
if (!(Test-Path 'S:\EFI\OC\config.plist')) { mountvol S: /S }
```

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode enable --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
```

```powershell
mountvol S: /D
```

**6. Boot Tahoe and verify both the reported GPU and the loaded accelerator:**

```bash
nvram boot-args
```

```bash
system_profiler SPDisplaysDataType
```

```bash
kmutil showloaded 2>/dev/null | grep -Ei 'AppleIntelTGL|WhateverXe|AMFIAnchor'
```

On the tested machine the effective boot args are exactly `npci=0x2000 -allow3d -disablegfxfirmware -igfxdvmt`; the two iGPU Data properties are `01000000` and `0000C003`. `AppleIntelTGLGraphics 16.0.0` loaded; macOS reported **Metal 2 / 1536 MB**, and the external DisplayPort display appeared. Do not infer working hardware video decoding, full-speed UI, input devices or sleep from this alone.

**Rollback:** use your preserved **private** no-acceleration `config.plist` to restore `-wex-noaccel` through the independent Windows Boot Manager firmware entry. Do not reset NVRAM wholesale, format the ESP or alter Windows Boot Manager. See [validated result and rollback](docs/VALIDATED-METAL-SL4.md).

### Building a fresh personalized EFI

The EFI generator accepts the new **opt-in** `--dvmt-60` flag for hardware that actually reports 60 MB fixed DVMT:

```powershell
py -3 scripts/build_efi.py --serial YOUR_SERIAL --mlb YOUR_MLB --uuid YOUR_UUID --rom YOUR_12_HEX_DIGIT_ROM --dvmt-60 --out EFI-output
```

Generate **unique** SMBIOS values with [GenSMBIOS](https://github.com/corpnewt/GenSMBIOS) using `MacBookPro16,2`. `--dvmt-60` stages the correct properties and `-igfxdvmt` **but deliberately keeps `-wex-noaccel`** until the Graphics pkg is installed. The clean-build EFI is **not yet independently boot-validated**; the success above was measured on the test machine's existing EFI. Never publish your personal EFI/serial/MLB/ROM.

## Architecture and remaining work

The critical ACPI fix is `SSDT-RTC0-SL4.aml` at `\_SB.PC00.LPCB` (corrected from upstream's `PCI0` path). Keep it enabled. The tested package uses OpenCore **1.0.8**, Lilu **1.7.2**, WhateverXe **0.8.3**, WhateverXe Graphics **0.4.4**, AMFIAnchor **0.1.2** and USBToolBox **1.2.0** with the Surface USB map. The Graphics package is installed into macOS `/Library`, not `EFI/OC/Kexts`.

The extra Intel wireless/Bluetooth, AppleALC, SMCBatteryManager, VoodooPS2, VoodooI2C, BigSurface, NVMeFix and RestrictEvents downloads are **candidates**. Their presence or loading is not proof they work; **do not load conflicting BigSurface and VoodooI2C/battery stacks blindly**. Wi-Fi works on this device, but built-in Surface keyboard and trackpad require further SAM/ACPI investigation. The user still reports some lag despite Metal; `pmset -g therm` reported no thermal/performance limit at the time of observation, and an initial `top` sample did not identify a process-level bottleneck.

## Repository guide

- [Validated Metal 2 report and reproduction steps](docs/VALIDATED-METAL-SL4.md)
- [Full post-install performance and driver staging](docs/FULL-PERFORMANCE.md)
- [Graphics acceleration background](docs/GRAPHICS-ACCELERATION.md)
- [Driver versions and remaining hardware gaps](docs/DRIVERS.md)
- [Boot from internal SSD](docs/INTERNAL-BOOT.md)
- [Quiet OpenCore picker](docs/QUIET-BOOT.md)
- [Safety and Windows preservation](docs/SAFETY.md)
- [RTC0 case study](docs/RTC0-CASE-STUDY.md)
- [Historical first-boot notes](docs/LEGACY-FIRST-BOOT.md)
- [Updated protected Metal transition script](scripts/xe_acceleration.py) and [DVMT 60 MB helper](scripts/dvmt60.py)
- [EFI builder](scripts/build_efi.py), [driver pack downloader](scripts/prepare_full_driver_pack.py) and [DVMT regression tests](tests/test_dvmt60.py)

## Credits

[OpenCore](https://github.com/acidanthera/OpenCorePkg) · [Lilu](https://github.com/acidanthera/Lilu) · [VirtualSMC](https://github.com/acidanthera/VirtualSMC) · [WhateverXe](https://github.com/b00t0x/WhateverXe) · [WhateverXe Graphics](https://github.com/b00t0x/WhateverXe-Graphics) · [AMFIAnchor](https://github.com/b00t0x/AMFIAnchor) · [USBToolBox](https://github.com/USBToolBox/kext) · [Dortania](https://dortania.github.io/)

Independent community project; not affiliated with Apple or Microsoft. macOS on non-Apple hardware is unsupported by Apple. Back up all data before experimenting. The banner is illustrative art, not a test screenshot.
