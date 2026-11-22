# Boot Tahoe and Windows without a USB drive

**Tested target:** Surface Laptop 4 (Intel i7-1185G7), Windows 11 + an existing Tahoe installation. This is the **post-install** step. It does not create a macOS partition or reinstall Tahoe.

The goal is a separate **OpenCore** firmware entry next to **Windows Boot Manager**. Both operating systems should then appear in the OpenCore picker, without keeping the Kingston installer plugged in.

> **Before changing firmware:** back up Windows, record your BitLocker recovery key, and keep the already-working Kingston OpenCore USB for rescue. A firmware change or failed boot may trigger BitLocker recovery. Run commands in **elevated Windows PowerShell**, not macOS Recovery. Do not try this while an installation/reboot sequence is still in progress.

**Before staging**, [switch the known-working Kingston EFI to the quiet picker profile](QUIET-BOOT.md) and test it once from USB. That profile uses OpenCore release-style logging, a four-second timer and `AllowSetDefault=True`. After the internal OpenCore entry is working, select installed **macOS Tahoe** and use **Ctrl+Enter** once to make it the persistent default. Windows will remain selectable. Exact visual order depends on boot enumeration, so don't hardcode Windows as the second entry.

## 1. Stage the known-working EFI on the internal ESP

Use the EFI that actually booted Tahoe, **not** an untested new build. The script copies only `EFI\OC` to the internal Windows EFI System Partition. It never replaces `EFI\Microsoft` or `EFI\BOOT`, and does not change any boot entries.

Confirm Windows is on disk 0 and Kingston is present:

```powershell
Get-Disk | Format-Table Number,FriendlyName,BusType,IsSystem,IsBoot,Size
```

Run a read-only check:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\stage_internal_efi.ps1" -Mode Inspect -InternalDiskNumber 0
```

After `INSPECT OK`, stage OpenCore:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\stage_internal_efi.ps1" -Mode Stage -InternalDiskNumber 0
```

Type `STAGE-OPENCORE-INTERNAL` when prompted. The script stores a Windows EFI and BCD backup in `Downloads\SL4-ESP-BACKUP-...`, then hashes **every** copied file. Do not continue unless it reports `STAGE SUCCESS`.

Disconnect and reconnect the USB if desired, then verify the internal EFI **without** requiring Kingston:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\stage_internal_efi.ps1" -Mode Verify -InternalDiskNumber 0
```

## 2. Create a *new* firmware entry — keep the original Windows entry

Create a copy of the firmware's Windows boot entry, **without modifying the original**:

```powershell
bcdedit.exe /copy "{bootmgr}" /d "OpenCore (Surface Laptop 4)"
```

The command returns a **new GUID**. Substitute that new GUID into the following command; **never substitute `{bootmgr}`**:

```powershell
bcdedit.exe /set "{YOUR-NEW-GUID}" path "\EFI\OC\OpenCore.efi"
```

Check the result. You should see one entry called `Windows Boot Manager` with `\EFI\Microsoft\Boot\bootmgfw.efi` and a **separate** entry called `OpenCore (Surface Laptop 4)` with `\EFI\OC\OpenCore.efi`:

```powershell
bcdedit.exe /enum firmware
```

**Stop** if the Windows entry was changed or the new entry was not created correctly. Do **not** run `bcdedit /set "{bootmgr}" path ...`: that replaces the boot path associated with Windows.

## 3. Test from firmware with the USB removed

Power down fully, remove the USB, enter Surface UEFI (Volume Up + Power), and choose the newly created **OpenCore** boot entry if the firmware exposes it. Check that both Tahoe and Windows can be selected from the OpenCore picker; test **both** before changing the boot order. Surface firmware may filter or reorder custom entries; in that case, do not remove the Windows entry or overwrite its bootloader to force OpenCore.

After a successful test, you may put the new entry first in firmware order:

```powershell
bcdedit.exe /set "{fwbootmgr}" displayorder "{YOUR-NEW-GUID}" /addfirst
```

OpenCore `Misc -> Boot -> ShowPicker = True` and `Timeout = 10` are already present in the test configuration. `UEFI -> Quirks -> RequestBootVarRouting = True` is also set. Do not enable `LauncherOption = Full` on the USB and internal EFI simultaneously, as it may create a boot entry for the wrong device.

If Windows doesn't appear in OpenCore, **do not change partitions**: use the UEFI's existing Windows Boot Manager entry, confirm that `EFI\Microsoft\Boot\bootmgfw.efi` still exists and investigate picker scanning.

## Roll back

Return Windows Boot Manager to the top of the firmware boot order via Surface UEFI, then delete **only the newly created GUID**:

```powershell
bcdedit.exe /delete "{YOUR-NEW-GUID}"
```

Verify with `bcdedit /enum firmware`. Leaving the staged `EFI\OC` directory in place is harmless; do not delete or rename `EFI\Microsoft` or `EFI\BOOT`. If Windows does not start, use its recovery media and the saved BCD/EFI backup.

**References:** [Dortania: dual boot](https://dortania.github.io/OpenCore-Multiboot/oc/win.html), [Microsoft: BCDEdit](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/bcdedit), [OpenCore LauncherOption](https://dortania.github.io/OpenCore-Post-Install/multiboot/bootstrap.html).

This is a documented, reversible path; the **internal firmware-entry boot has not yet been verified on the test Surface**. The confirmed macOS boot used the Kingston USB.
