# Boot installed Tahoe and Windows from the internal SSD

**Tested on 2026-11-22:** Microsoft Surface Laptop 4 Intel (i7-1185G7), Windows 11 + Tahoe 26.7.1 on separate partitions of Samsung PM991 256 GB. The test machine **successfully booted installed Tahoe using OpenCore 1.0.8 on its internal EFI System Partition, with no external media attached**. The independent Windows Boot Manager files and UEFI entry were preserved. Do not equate that with exhaustive dual-boot/menu or disk-encryption validation.

This is a **post-install** procedure. You must already have installed Tahoe and an OpenCore EFI that **actually boots** your machine. Do not overwrite or delete `EFI/Microsoft`, `EFI/BOOT`, Windows BCD, any partitions or your backups. Preserve private no-accel and accelerated `config.plist` copies off the ESP.

## Working test-machine layout

- Internal physical SSD: EFI partition 1, Windows 11 on NTFS and Tahoe 26.7.1 on separate APFS.
- Internal ESP seen in Windows as `S:` using `mountvol S: /S`; in macOS as FAT32 `disk0s1` volume named `SYSTEM`.
- Internal OpenCore located at `\EFI\OC\OpenCore.efi`. `SSDT-RTC0-SL4.aml` and all working dependencies are inside the private `EFI/OC` directory.
- Windows Boot Manager remains `\EFI\Microsoft\Boot\bootmgfw.efi`; a **separate** OpenCore firmware entry was created, rather than changing Windows's boot path.
- Quiet picker is configured with `ShowPicker=True`, `Timeout=4` and optional `Ctrl+Enter` for default selection.
- The tested accelerated display path requires fixed-60-MB DVMT settings; see [validated Metal](VALIDATED-METAL-SL4.md).

## Safe read-only inspection from Windows

Open elevated PowerShell. Check the internal ESP location without changing the boot order:

```powershell
if (!(Test-Path 'S:\EFI\OC\config.plist')) { mountvol S: /S }
```

```powershell
Get-Item 'S:\EFI\OC\OpenCore.efi','S:\EFI\OC\ACPI\SSDT-RTC0-SL4.aml','S:\EFI\Microsoft\Boot\bootmgfw.efi'
```

```powershell
bcdedit.exe /enum firmware
```

Do not place a copied or newly built, **untested** EFI on the internal ESP just because `ocvalidate` accepts it. The repo's EFI builder is not independently boot-validated from a clean checkout. Use a *known-bootable private* OpenCore EFI as your baseline, saved outside the ESP. The historic original-staging procedure is preserved in [legacy first-boot notes](LEGACY-FIRST-BOOT.md); it is not required to reproduce the already installed test machine's current result.

## Independent firmware entry (only if not already present)

The test Surface already has an OpenCore entry: **do not duplicate it**. On a different machine, only after verified OpenCore files exist in its internal ESP, create a separate UEFI entry. Never edit the original `{bootmgr}` path.

```powershell
bcdedit.exe /copy "{bootmgr}" /d "OpenCore (Surface Laptop 4)"
```

Record the **new** GUID printed by this command. Use that returned GUID (not `{bootmgr}`) in:

```powershell
bcdedit.exe /set "{YOUR-NEW-GUID}" path "\EFI\OC\OpenCore.efi"
```

Inspect with:

```powershell
bcdedit.exe /enum firmware
```

Verify that Windows Boot Manager still targets `\EFI\Microsoft\Boot\bootmgfw.efi`, while your **different** entry targets `\EFI\OC\OpenCore.efi`. If firmware filters custom entries, stop and investigate; do **not** replace Windows Boot Manager to force OpenCore.

Test Tahoe from the OpenCore entry and Windows from its original entry before considering any permanent boot order change. The first OpenCore-only test can use the firmware's one-time boot choice. Changing boot order or firmware state may trigger BitLocker recovery; keep recovery credentials available.

To return to the Windows boot priority, use Surface UEFI. Only if necessary and after verifying its GUID, delete **the new independent OpenCore entry**, never `{bootmgr}`:

```powershell
bcdedit.exe /delete "{YOUR-NEW-GUID}"
```

The test machine's OpenCore entry was already created with a distinct GUID; keep it as-is.

## Graphics and rollback

The test laptop's **accelerated** configuration was successfully booted with:

- WhateverXe 0.8.3 + Graphics 0.4.4 installed inside Tahoe.
- 60 MB DVMT: `framebuffer-patch-enable` Data `01000000`; `framebuffer-stolenmem` Data `0000C003` under `PciRoot(0x0)/Pci(0x2,0x0)`.
- `boot-args = npci=0x2000 -allow3d -disablegfxfirmware -igfxdvmt`.
- Metal 2 / 1536 MB dynamic VRAM, with AppleIntelTGLGraphics actually loaded.

The owner saved a private working Metal `config.plist` in macOS Downloads and an earlier no-accel EFI backup. If a new change causes boot failure, select the preserved independent Windows Boot Manager entry and restore the known-good **no-acceleration** config (with `-wex-noaccel`) from the private backup. Do not reset NVRAM wholesale, repair the ESP blindly, alter Windows BCD or repartition.

See [Quick Start](../README.md#quick-start-reproduce-the-validated-metal-2-state-existing-tahoe-no-removable-media) for the end-to-end no-removable-media graphics path.

References: [Microsoft BCDEdit](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/bcdedit), [Dortania multiboot](https://dortania.github.io/OpenCore-Multiboot/oc/win.html).
