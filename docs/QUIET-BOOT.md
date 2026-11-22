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

## Apply to the proven Kingston EFI from Windows

Boot Windows, plug in the *working* Kingston USB, and open PowerShell as administrator. Run from a fresh clone of this repo.

**Inspect only** (change the drive letter if necessary):

```powershell
py -3 scripts/quiet_boot.py --mode inspect --efi D:\EFI
```

**Apply** (keeps a private, verified `config.plist` backup on C:):

```powershell
py -3 scripts/quiet_boot.py --mode apply --efi D:\EFI --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\OC108\Utilities\ocvalidate\ocvalidate.exe"
```

Type `APPLY-SL4-QUIET` only after checking the planned changes. The utility validates the proposed plist before replacing the old one. If your `ocvalidate.exe` is at a different path, find it in the extracted **OpenCore 1.0.8** release, then pass that exact path.

### Set macOS as the boot default

Boot the USB OpenCore picker **with an external USB keyboard attached if the Surface built-in keyboard is not working**. Select the installed **macOS Tahoe** volume, **hold Ctrl and press Enter once**. This sets the *default* boot entry in NVRAM. The picker then waits four seconds before launching macOS; Windows remains selectable.

**Note:** OpenCore enumerates entries and controls the menu order automatically. The selected macOS default often appears first, with Windows below. The script does not hard-code Windows as the second row; doing so can introduce duplicate entries or interfere with OS updates. Verify that Windows Boot Manager is visible before relying on this picker.

To keep the same settings **without USB**, stage the tuned known-good USB EFI on the internal ESP using [INTERNAL-BOOT.md](INTERNAL-BOOT.md). This only copies `EFI/OC` and creates a separate OpenCore firmware entry: Windows Boot Manager remains independent.

### Rollback

If a change causes a problem, boot Windows with the rescue USB or original boot entry and restore from the private backup:

```powershell
py -3 scripts/quiet_boot.py --mode restore --efi D:\EFI --backup "$HOME\Downloads\SL4-OC-BACKUPS\SL4-OC-before-quiet-YYYYMMDD-HHMMSS\config.plist"
```

Replace the example backup folder with the path printed by `apply`. **Never publish that backup:** it contains real SMBIOS serial/MLB/SystemUUID/ROM values.

## Notes

The builder `scripts/build_efi.py` now generates quiet settings **by default**. Add `--verbose-boot` when a fresh debugging EFI is needed. The proven boot sequence used a diagnostic configuration; the quiet profile is a post-install convenience change and should be tested with a recoverable USB copy before updating the internal EFI.

[OpenCore manual](https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/Configuration.pdf) · [OpenCore debugging](https://dortania.github.io/OpenCore-Install-Guide/troubleshooting/debug.html)
