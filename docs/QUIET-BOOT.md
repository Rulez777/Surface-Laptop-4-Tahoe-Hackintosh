# Quiet OpenCore picker: 4-second internal SSD boot

**Test status (2026-11-22):** The Surface Laptop 4 Intel test machine now boots Tahoe 26.7.1 with Metal 2 via **internal OpenCore 1.0.8** beside Windows 11. Its quiet picker was configured earlier and should **not** be reapplied if already working.

## Current known-good settings

| Key | Test-machine value |
| --- | --- |
| OpenCore | 1.0.8 RELEASE |
| `Misc -> Boot -> ShowPicker` | `True` |
| `PickerMode` | `Builtin` |
| `Timeout` | `4` seconds |
| `HideAuxiliary` | `True` (Space shows hidden Recovery tools) |
| `Misc -> Security -> AllowSetDefault` | `True` (Ctrl+Enter can set the preferred OS) |
| `Misc -> Debug -> Target` | `0` |
| `AppleDebug`, `ApplePanic` | `False` |
| `DisplayLevel` | `0` |
| `NVRAM -> boot-args` | **`npci=0x2000 -allow3d -disablegfxfirmware -igfxdvmt`** with validated DVMT 60 MB iGPU Data properties |

The last line reflects **working accelerated graphics on this measured-60-MB-DVMT Surface**, not a default for every system. The old framebuffer-only `-wex-noaccel` configuration is kept only as a **private rollback backup**. See [validated Metal settings](VALIDATED-METAL-SL4.md).

## Inspect or (only if necessary) apply quiet settings

Open PowerShell **as Administrator** on Windows. Use the internal ESP, not an external disk:

```powershell
if (!(Test-Path 'S:\EFI\OC\config.plist')) { mountvol S: /S }
```

First inspect (read-only):

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\quiet_boot.py" --mode inspect --efi "S:\EFI"
```

If the four-second picker and quiet flags are already present, **stop here**. If they are missing, and only after saving the known-good EFI and Windows backups, apply the tool with matching OpenCore 1.0.8 validator:

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\quiet_boot.py" --mode apply --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
```

The tool changes only `config.plist`, removes old debug flags (`-v`, `keepsyms=1`, `debug=0x100`) and preserves **all graphics, DVMT, storage and USB arguments**. It verifies and saves the old plist in a private backup. Do not edit `EFI/Microsoft`, partitions or firmware order.

Unmount when finished:

```powershell
mountvol S: /D
```

### Default boot and rollback

From the independent internal OpenCore picker, you may select installed Tahoe and press **Ctrl+Enter** to set it as default; **this default-selection action has not been separately verified on the test machine**. Keep Windows Boot Manager as an independent firmware entry, and test its boot path before changing boot order. Surface built-in keyboard is currently not functioning in Tahoe, so access to a usable input device is necessary.

If the quiet profile itself introduces a problem, use the original Windows Boot Manager firmware entry and the private previous `config.plist` backup. The tool supports `--mode restore` with `--backup` and `--backup-dir`. Never publish backup files with SMBIOS values.

[Internal boot](INTERNAL-BOOT.md) · [Validated Metal 2](VALIDATED-METAL-SL4.md) · [OpenCore manual](https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/Configuration.pdf).
