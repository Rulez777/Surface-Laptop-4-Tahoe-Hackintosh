# Validated Surface Laptop 4 Tiger Lake-U Metal 2 configuration — 2026-11-22

This is an observed, reproducible **post-install** configuration for a *specific test laptop*, not a blanket compatibility claim or a distributable personalized EFI. It avoids external storage devices. The machine already had Tahoe on its internal APFS partition and an independent internal OpenCore UEFI entry beside Windows Boot Manager.

## Hardware and validated stack

| Item | Actual test result |
| --- | --- |
| Computer | Microsoft Surface Laptop 4 Intel, Core i7-1185G7 (Tiger Lake-U) |
| GPU | Intel Iris Xe 96 EU, PCI ID `8086:9A49`, revision 01 |
| RAM / SSD | 16 GB / Samsung PM991 256 GB (Windows 11 and Tahoe on same physical SSD, separate partitions) |
| OS | Installed macOS Tahoe **26.7.1**, confirmed with `sw_vers -productVersion` |
| Boot | **Internal** OpenCore 1.0.8; Windows Boot Manager's Microsoft EFI files preserved |
| GPU boot kext | Lilu 1.7.2, WhateverXe 0.8.3, AMFIAnchor 0.1.2 + injector |
| macOS GPU package | WhateverXe Graphics **0.4.4** (.pkg installed in Tahoe), AppleIntelTGLCompat 0.8.1 and AppleIntelTGLGraphics/Framebuffer 16.0.0 |
| Internal screen | LQ150P1JX51 eDP 2496×1664, online, HiDPI looks like 1248×832, 30-bit framebuffer |
| External screen | MSI MPG271QX OLED via Thunderbolt/DisplayPort, 2560×1440 at 59 Hz; higher refresh rates **not yet verified** |
| Graphics | `Metal Support: Metal 2`, dynamic VRAM max 1536 MB, **AppleIntelTGLGraphics loaded** |
| Wi-Fi | **Working**, Intel AX201 (AirportItlwm 2.4.0) |
| Surface Dock | USB2/USB3 hubs and Gigabit Ethernet device/interfaces enumerate; **full dock functionality unverified** |
| Input | **Built-in keyboard and trackpad not working**; touch not validated |
| Other | Audio/Bluetooth/battery kexts are present/loaded, but functional testing remains incomplete; sleep, wake and full-speed performance unverified |

Do **not** publish the test machine's SMBIOS serial, MLB, ROM, SystemUUID, Wi-Fi/Ethernet MAC addresses or a complete personalized EFI.

## Root cause observed on this machine: fixed 60 MB DVMT was unconfigured

With only `npci=0x2000 -allow3d -disablegfxfirmware -wex-noaccel` the system loaded in slow EFI framebuffer mode: **15 MB**, no Metal, and the external display was absent.

`ioreg` showed `WhateverXePhysicalGGC = 65217` (hex `0xFEC1`, fixed **60 MB DVMT pre-allocation**). The installed OpenCore had an empty `DeviceProperties -> Add` dictionary. The official Graphics 0.4.4 package was successfully installed in Tahoe, yet simply deleting `-wex-noaccel` resulted in a stalled graphical boot.

The successful boot followed the **upstream WhateverXe 60 MB DVMT instructions**, in addition to the already installed Graphics package:

| Location | Key | Value |
| --- | --- | --- |
| `DeviceProperties -> Add -> PciRoot(0x0)/Pci(0x2,0x0)` | `framebuffer-patch-enable` | **Data** `01000000` |
| Same | `framebuffer-stolenmem` | **Data** `0000C003` |
| `NVRAM -> Add -> 7C436110-AB2A-4BBB-A880-FE41995C9F82 -> boot-args` | args | `npci=0x2000 -allow3d -disablegfxfirmware -igfxdvmt` |

No device-ID spoofing, WhateverGreen or modified WhateverXe binary was needed. Do **not** copy the 60 MB workaround to a computer with different measured DVMT. The old CDCLK error `Unsupported CD clock decimal frequency 0x158` occurred even during successful no-acceleration boots; the evidence does not establish CDCLK as the reason for the stalled accelerated boot.

## Reproducing this result: Windows + existing Tahoe, without removable media

**Prerequisites:** a bootable installed Tahoe 26.7+ on a separate APFS container, an existing **known-bootable internal** OpenCore EFI, working access to Windows 11 and its internal EFI partition, Python 3 and Git on Windows, local admin permissions, and some usable mouse/keyboard path when running macOS. The repository's EFI builder is **not independently validated from a clean checkout**. Keep private backups of the Windows and macOS volumes before testing; do not modify `EFI/Microsoft`, `EFI/BOOT`, partitions or firmware entries as part of the graphics procedure.

1. In Windows, update the checked-out project. PowerShell (one line):

   ```powershell
   git -C "$HOME\Downloads\SL4-Tahoe-Git" pull --ff-only
   ```

2. Mount the existing internal ESP as Administrator if it is not already available:

   ```powershell
   if (!(Test-Path 'S:\EFI\OC\config.plist')) { mountvol S: /S }
   ```

3. If the official Graphics package and validator are not already cached, use the full driver pack downloader described in [Full performance setup](FULL-PERFORMANCE.md). **Do not enable all optional kexts simultaneously.** If you have already staged them, skip that step.

4. Verify that firmware truly has **60 MB DVMT / GGC 0xFEC1** on this machine. Then stage the exact 60 MB DeviceProperties and `-igfxdvmt`, **preserving `-wex-noaccel`** while installing Graphics. The updated script backs up `config.plist`, rejects conflicting binary values and checks OpenCore 1.0.8:

   ```powershell
   py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode prepare --dvmt-60 --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
   ```

5. Disconnect the ESP from Windows and boot installed Tahoe **still with** `-wex-noaccel`:

   ```powershell
   mountvol S: /D
   ```

6. In Tahoe, use the already mounted read-only Windows NTFS volume (in this test it was `/Volumes/Windows`) to copy the verified `.pkg` to the macOS home folder. Substitute your actual Windows username. **Do not use the ESP as a package-transfer volume.**

   ```bash
   cp "/Volumes/Windows/Users/YOUR_WINDOWS_USER/Downloads/SL4-FULL-DRIVERS/macOS-Installers/WhateverXe-Graphics-0.4.4.pkg" "$HOME/Downloads/"
   ```

   ```bash
   shasum -a 256 "$HOME/Downloads/WhateverXe-Graphics-0.4.4.pkg"
   ```

   The SHA-256 must match **`f4c2d680a7c52c33a3f038ce6945da0aa2cc044e62b935a52ea046c7c473cfec`**. Install only after verifying it:

   ```bash
   sudo installer -pkg "$HOME/Downloads/WhateverXe-Graphics-0.4.4.pkg" -target /
   ```

   Do not treat an unsuccessful installer exit as success. This installs the signed graphics components to `/Library` and updates the AuxKC. It does **not** enable the accelerator by itself.

7. Following **successful** package installation, return to Windows (without starting the accelerated Tahoe yet), mount the internal ESP, and enable Metal using the guarded script. It now **refuses to remove `-wex-noaccel` unless** the exact DVMT Data properties and `-igfxdvmt` are present:

   ```powershell
   if (!(Test-Path 'S:\EFI\OC\config.plist')) { mountvol S: /S }
   ```

   ```powershell
   py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode enable --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
   ```

   ```powershell
   mountvol S: /D
   ```

8. Boot Tahoe and verify **both** the Metal report and actual loaded GPU accelerator:

   ```bash
   nvram boot-args
   ```

   ```bash
   system_profiler SPDisplaysDataType
   ```

   ```bash
   kmutil showloaded 2>/dev/null | grep -Ei 'WhateverXe|AppleIntelTGL|AMFIAnchor'
   ```

   On the test machine, these commands confirmed the exact results in the first table.

### For builders using the repository EFI generator

`scripts/build_efi.py` now supports opt-in **`--dvmt-60`** for hardware *already verified* as fixed at 60 MB. It writes the two Data properties and `-igfxdvmt` but **deliberately keeps `-wex-noaccel`** for the first boot. Only remove `-wex-noaccel` after Tahoe boots, the official Graphics package installs successfully, and the enabling script verifies the DVMT settings. The generated EFI has **not** been independently proven to boot Tahoe on a new machine, even though the manually updated working test EFI has.

## Backups and rollback

- The working accelerated configuration was backed up on the test machine as **`~/Downloads/SL4-WORKING-METAL.plist`**. This is a **private file**, not a public downloadable EFI.
- An earlier no-acceleration config is privately stored at **`EFI/OC/config-before-DVMT.plist`** and in the macOS Downloads backup directory. Keep known-good Windows copies off the ESP as well.
- If the modified EFI fails to boot, select the independent Windows Boot Manager firmware entry and restore the saved **pre-acceleration** `config.plist` through Windows, returning to `-wex-noaccel`. Do not format the ESP or change the Windows boot loader.
- The exact macOS pkg, macOS version, kext version and non-default SIP configuration must be reviewed for other machines. Do not bypass SIP requirements blindly.

## Unresolved performance and peripherals

Despite working Metal and external DisplayPort, the user still reports some UI lag. The first `top -l 1` sample showed load averages 6.23/10.34/5.55 and 46.4% CPU idle; its per-process lines were all 0% and **cannot identify a bottleneck**. `pmset -g therm` showed no thermal/performance warning and 100% CPU scheduling/speed limits at the measurement time. Better sustained CPU/GPU/SSD sampling is needed; this is not a verified peak-performance result.

Built-in keyboard and trackpad did not work. The Surface SAM input stack may require device-specific ACPI and compatible drivers; BigSurface and VoodooI2C/SMCBatteryManager are potentially conflicting. Do not assume that loading every candidate fixes input. Wi-Fi **is** confirmed working; Bluetooth, audio, battery reporting, sleep/wake, high-refresh external output, dock networking and stability still require individual tests.

### Upstream references

- [WhateverXe README, including DVMT configuration](https://github.com/b00t0x/WhateverXe#dvmt)
- [WhateverXe Graphics 0.4.4](https://github.com/b00t0x/WhateverXe-Graphics/releases/tag/v0.4.4)
- [96 EU Tiger Lake upstream hardware report with Surface Laptop 4 follow-up](https://github.com/b00t0x/WhateverXe/issues/101#issuecomment-7082305989)
