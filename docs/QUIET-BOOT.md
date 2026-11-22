# Quiet OpenCore: macOS default, Windows available

This is the **post-install** profile for the Intel Surface Laptop 4 test machine after macOS Tahoe boots. The verified USB used verbose diagnostics while the boot problem was investigated. Those logs are not required for ordinary startup.

## What changes

| Setting | Quiet profile |
|---|---|
| OpenCore | Keep **OpenCore 1.0.8 RELEASE**, not DEBUG |
| `Misc -> Debug -> Target` | `0` — disable console/file debugging |
| `AppleDebug`, `ApplePanic` | `False` |
| `DisplayLevel` | `0` |
| `NVRAM -> boot-args` | Remove only `-v`, `keepsyms=1`, `debug=0x100` |
| `Misc -> Boot -> ShowPicker` | `True` |
| `PickerMode` | `Builtin` (no graphical boot driver needed) |
| `Timeout` | `4` seconds |
| `HideAuxiliary` | `True` — press **Space** to show Recovery/tools |
| `Misc -> Security -> AllowSetDefault` | `True` — **Ctrl+Enter** to save the macOS default |

Keep **all** Surface-specific ACPI, RTC0, kexts, NVMe, graphics, USB and `RequestBootVarRouting` settings unchanged. Keep `-wex-noaccel` until acceleration is independently validated. Do not reset NVRAM just to hide logging.

## Apply to the internal EFI without changing Kingston

After copying the known-good Kingston OpenCore with [Internal Boot](INTERNAL-BOOT.md), leave the USB as a backup. In **Windows PowerShell as Administrator**, from the cloned repository:

Mount the internal Windows EFI System Partition (ESP):

```powershell
mountvol S: /S
```

Inspect changes without writing:

```powershell
py -3 scripts/quiet_boot.py --mode inspect --efi S:\EFI
```

To apply the quiet profile **to internal `S:\EFI` only**, use the following command. Prefer supplying the **matching OpenCore 1.0.8** `ocvalidate.exe` with `--ocvalidate`, if installed:

```powershell
py -3 scripts/quiet_boot.py --mode apply --efi S:\EFI --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS"
```

Type `APPLY-SL4-QUIET` to confirm. The tool saves a verified backup of the **internal** `config.plist` on the C: drive, and changes only that plist. If a matching `ocvalidate.exe` is available, add `--ocvalidate "C:\path\to\ocvalidate.exe"` to the command; without it, the script still validates plist syntax but reports that OpenCore schema validation was skipped.

When done, unmount the internal ESP:

```powershell
mountvol S: /D
```

Never apply to the Kingston `MACOS-OC` volume unless deliberately updating the emergency recovery USB.

### Set macOS as the boot default

Boot the internal OpenCore picker **without Kingston attached** and with an external USB keyboard if the Surface built-in keyboard is not working. Select the installed **macOS Tahoe** volume, **hold Ctrl and press Enter once**. This sets the *default* boot entry in NVRAM. The picker then waits four seconds before launching macOS; Windows remains selectable.

**Note:** OpenCore enumerates entries and controls the menu order automatically. The selected macOS default often appears first, with Windows below. The script does not hard-code Windows as the second row; doing so can introduce duplicate entries or interfere with OS updates. Verify that Windows Boot Manager is visible before relying on this picker.

The internal copy has these settings independently of Kingston. Follow [Internal Boot](INTERNAL-BOOT.md) to create a separate OpenCore firmware entry while leaving Windows Boot Manager intact.

### Rollback

If a change causes a problem, boot Windows with the rescue USB or original boot entry and restore from the private backup:

```powershell
py -3 scripts/quiet_boot.py --mode restore --efi S:\EFI --backup "$HOME\Downloads\SL4-OC-BACKUPS\SL4-OC-before-quiet-YYYYMMDD-HHMMSS\config.plist"
```

Replace the example backup folder with the path printed by `apply`. **Never publish that backup:** it contains real SMBIOS serial/MLB/SystemUUID/ROM values.

## Notes

The builder `scripts/build_efi.py` now generates quiet settings **by default**. Add `--verbose-boot` when a fresh debugging EFI is needed. The proven boot sequence used a diagnostic configuration. Preserve Kingston unchanged so it remains a recovery path if the internal EFI needs to be reverted.

[OpenCore manual](https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/Configuration.pdf) · [OpenCore debugging](https://dortania.github.io/OpenCore-Install-Guide/troubleshooting/debug.html)
