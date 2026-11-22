# Surface Laptop 4 Intel: complete candidate driver pack and verified Metal 2

**Updated 2026-11-22.** The previous no-acceleration-only status is obsolete. On the test laptop (i7-1185G7, Iris Xe 96 EU `8086:9A49`), **Tahoe 26.7.1 + stock WhateverXe 0.8.3 + Graphics 0.4.4 + fixed 60 MB DVMT profile booted with Metal 2** and 1536 MB dynamic VRAM. The built-in 2496×1664 display and external 2560×1440 DisplayPort monitor worked. Intel AX201 Wi-Fi also works. **Built-in keyboard and trackpad still do not work, and full peak performance is not established.** See the [full validated report](VALIDATED-METAL-SL4.md).

This is an **already-installed Tahoe** workflow using only the **internal SSD** and Windows 11. The scripts never need a removable transfer drive. Keep the Windows Boot Manager, EFI/Microsoft, EFI/BOOT and existing partitions unchanged.

## Windows: current repository, verified candidates, known-good EFI backup

Run PowerShell as Administrator. All commands are one line.

Update the repo:

```powershell
git -C "$HOME\Downloads\SL4-Tahoe-Git" pull --ff-only
```

Mount the internal Windows ESP *if not already mounted*:

```powershell
if (!(Test-Path 'S:\EFI\OC\config.plist')) { mountvol S: /S }
```

Inspect existing core graphics kexts, SIP, boot flags and 60 MB DVMT readiness (read-only):

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode inspect --efi "S:\EFI"
```

If needed, download the official Graphics 0.4.4 pkg, **OpenCore 1.0.8** validator and optional driver candidates. The downloader uses pinned release URLs and checks the pkg hash. The output is on Windows C:, not in the ESP:

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\prepare_full_driver_pack.py" --source "S:\EFI" --out "$HOME\Downloads\SL4-FULL-DRIVERS" --cache "$HOME\Downloads\SL4-KEXT-CACHE"
```

It prepares AppleALC, Tahoe AirportItlwm, IntelBluetoothFirmware/Patcher, BlueToolFixup, SMCBatteryManager, VoodooPS2, VoodooI2C/HID, BigSurface, NVMeFix, RestrictEvents and IPTSDaemon candidates; the unproven kexts remain **disabled**. The package is at `SL4-FULL-DRIVERS/macOS-Installers/WhateverXe-Graphics-0.4.4.pkg`. `ocvalidate.exe` is at `SL4-FULL-DRIVERS/tools/ocvalidate.exe`.

If this driver set is **not already staged** on the ESP, these commands inspect and apply only the missing disabled entries, with a private verified OC backup on C:. Do **not** repeat the staging command on a machine whose pack has already been applied and tested:

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\stage_full_kext_pack.py" --mode inspect --internal-efi "S:\EFI" --pack-efi "$HOME\Downloads\SL4-FULL-DRIVERS\optional-EFI\EFI" --backup-dir "$HOME\Downloads\SL4-KEXT-BACKUPS"
```

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\stage_full_kext_pack.py" --mode apply --internal-efi "S:\EFI" --pack-efi "$HOME\Downloads\SL4-FULL-DRIVERS\optional-EFI\EFI" --backup-dir "$HOME\Downloads\SL4-KEXT-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
```

The additional drivers are candidates, **not** a universal mutually-compatible stack. Do not enable BigSurface and VoodooI2C/SMCBatteryManager indiscriminately: Surface SAM/ACPI and Tahoe compatibility are not proven. Merely staging them does not make devices work.

## Windows: prepare the *verified fixed-60-MB* graphics settings

On the test machine `ioreg` reported **`WhateverXePhysicalGGC = 65217` (0xFEC1)**. That means **60 MB fixed DVMT**. The original empty `DeviceProperties -> Add` prevented successful accelerated boot even after Graphics 0.4.4 was installed: simply removing `-wex-noaccel` stalled at the Apple logo.

For **measured 60 MB DVMT** only, run:

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode prepare --dvmt-60 --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
```

The protected script stages the official WhateverXe DVMT entries (`framebuffer-patch-enable=01000000` and `framebuffer-stolenmem=0000C003`, both **Data**, under `PciRoot(0x0)/Pci(0x2,0x0)`) plus `-igfxdvmt`. It leaves `-wex-noaccel` intact until the macOS pkg succeeds. It also checks Lilu/WEX/AMFIAnchor dependencies, custom RTC0 and SIP; it backs up `config.plist` before writing and validates the new plist.

```powershell
mountvol S: /D
```

## Installed macOS: install Graphics 0.4.4 from internal Windows NTFS

Boot installed Tahoe in no-acceleration mode. If internet in macOS is unavailable, **use the internal Windows NTFS partition** as the data source. On this test it was already mounted read-only as `/Volumes/Windows`. Substitute the actual Windows username:

```bash
cp "/Volumes/Windows/Users/YOUR_WINDOWS_USER/Downloads/SL4-FULL-DRIVERS/macOS-Installers/WhateverXe-Graphics-0.4.4.pkg" "$HOME/Downloads/"
```

Check SHA-256 (do **not** skip):

```bash
shasum -a 256 "$HOME/Downloads/WhateverXe-Graphics-0.4.4.pkg"
```

Expected `f4c2d680a7c52c33a3f038ce6945da0aa2cc044e62b935a52ea046c7c473cfec`. Also verify `sw_vers -productVersion` is **26.7+**. Then install:

```bash
sudo installer -pkg "$HOME/Downloads/WhateverXe-Graphics-0.4.4.pkg" -target /
```

The successful test output included `installer: The install was successful.` and `installer: The install requires restarting now.` This installs graphics components into macOS `/Library` and its AuxKC; it is **not** accomplished by copying kexts into EFI. If the installer fails, do not remove `-wex-noaccel`.

## Windows: safely enable Metal after successful pkg installation

Return to Windows via the existing independent Windows Boot Manager entry and mount the internal ESP:

```powershell
if (!(Test-Path 'S:\EFI\OC\config.plist')) { mountvol S: /S }
```

Run guarded enable:

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode enable --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
```

The updated script now **requires** `-igfxdvmt` and the two exact 60 MB Data properties, *and* explicitly asks you to confirm successful Graphics package installation before removing only `-wex-noaccel`. It makes a separate private backup. Then:

```powershell
mountvol S: /D
```

Boot Tahoe and verify:

```bash
nvram boot-args
```

```bash
system_profiler SPDisplaysDataType
```

```bash
kmutil showloaded 2>/dev/null | grep -Ei 'AppleIntelTGL|WhateverXe|AMFIAnchor'
```

The **actual observed** test boot used `npci=0x2000 -allow3d -disablegfxfirmware -igfxdvmt` and showed **Metal 2, 1536 MB VRAM, loaded AppleIntelTGLGraphics 16.0.0** and an external monitor. Wi-Fi worked.

## Current non-graphics driver limitations

- Intel AX201 Wi-Fi: **user-confirmed working**. AirportItlwm 2.4.0 loaded.
- Microsoft Surface Dock: USB2/USB3 hubs and GigE adapter enumerate; external monitor appeared over DisplayPort with Metal, but **all** dock functions and sustained reliability were not fully tested.
- Built-in keyboard and trackpad: **nonfunctional**; require further Surface SAM/ACPI investigation. VoodooPS2/VoodooI2C alone cannot be assumed sufficient.
- Bluetooth/audio/battery: some kexts loaded; functional results are not yet confirmed.
- Samsung PM991 NVMe stability, sleep/wake, high-refresh external output, CPU power management, sustained performance: **unverified**.
- Metal fixed a major graphics bottleneck, **not** every source of lag.

Keep a private **known-bootable no-accel config** on Windows and macOS. If GPU init fails, select Windows Boot Manager and restore it, reintroducing `-wex-noaccel`. Never erase the ESP, alter Windows BCD or repartition the SSD to test graphics.

Upstream: [WhateverXe DVMT](https://github.com/b00t0x/WhateverXe#dvmt) · [Graphics 0.4.4](https://github.com/b00t0x/WhateverXe-Graphics/releases/tag/v0.4.4) · [Surface success report](https://github.com/b00t0x/WhateverXe/issues/101#issuecomment-7082305989).
