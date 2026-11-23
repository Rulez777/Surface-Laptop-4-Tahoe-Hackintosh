# Cross-platform hardware detection and safe offline EFI workflow

**Status:** experimental preparation workflow (2026-11-23). Successfully exercised on the tested macOS Surface Laptop 4 and with isolated fake EFI trees. It is **not a certified clean installer**, not an automatic live ESP updater, and not a system-sleep fix.

## What is included

- [`data/sl4_profiles.json`](../data/sl4_profiles.json) is the shared, non-secret hardware profile and pinned component checksum manifest.
- [`scripts/sl4_inventory.py`](../scripts/sl4_inventory.py) queries CPU, GPU PCI IDs, Surface ACPI IDs, SSD model, selected devices and disk partition types in read-only mode. It drops serial numbers, MAC addresses, SMBIOS values and system UUIDs.
- [`scripts/sl4_setup.py`](../scripts/sl4_setup.py) validates an **existing private EFI folder**, makes collision-safe copies *outside the EFI partition*, verifies their hashes and prepares an optional eDP add-on in an offline staging directory.
- [`scripts/Start-SL4.ps1`](../scripts/Start-SL4.ps1) and [`scripts/start_sl4_macos.sh`](../scripts/start_sl4_macos.sh) are Windows/macOS entry points into the **same** Python workflow.

**Hardware matching does not authorize modifying a live EFI.** The only profile included is the Microsoft Surface Laptop 4 Intel 13.5-inch, Core i7-1185G7, Iris Xe 8086:9A49 with the verified ACPI profile. The tested Samsung PM991 may identify as `SAMSUNG MZ9LQ256HBJQ-00000`. Different Surface variants, firmware revisions, SSDs and clean installs are not certified.

## Quick start — no USB

From an extracted ZIP or cloned repository, with Python 3 installed.

macOS (Terminal), from repo root:

```bash
sh scripts/start_sl4_macos.sh
python3 scripts/sl4_setup.py verify-pins
```

Windows (PowerShell), from repo root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Start-SL4.ps1 -Action Inventory
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Start-SL4.ps1 -Action VerifyPins
```

The first command produces a redacted local profile and an explicit `automatic_install_allowed: false`. The second verifies the bundled tested eDP package SHA-256.

The scanner does not mount ESP, alter BCD, change boot order, or install drivers. Unknown or incomplete hardware details produce `unsupported_or_insufficient_evidence`.

## Existing private EFI: inspect, backup, prepare

Provide an **already mounted or previously copied** directory named `EFI` containing `EFI/OC/config.plist`, `EFI/OC/OpenCore.efi`, `EFI/BOOT/BOOTx64.efi` and Windows Boot Manager `EFI/Microsoft/Boot/bootmgfw.efi`. Do not mount or write the ESP merely to run the scanner. The examples assume you already have a *private copied* EFI at `~/Downloads/SL4-PERSONAL/EFI` (macOS) or `C:\SL4-PERSONAL\EFI` (Windows). Replace these examples with your real private copy.

Read-only structure inspection:

```bash
python3 scripts/sl4_setup.py inspect --source-efi "$HOME/Downloads/SL4-PERSONAL/EFI"
```

Create a new, private local integrity-checked backup:

```bash
python3 scripts/sl4_setup.py backup --source-efi "$HOME/Downloads/SL4-PERSONAL/EFI" --out "$HOME/Downloads/SL4-PRIVATE-BACKUP" --ack BACKUP-PRIVATE-EFI
```

Create an isolated *staged* private copy, with verified optional eDP archive **not enabled**:

```bash
python3 scripts/sl4_setup.py prepare --source-efi "$HOME/Downloads/SL4-PERSONAL/EFI" --out "$HOME/Downloads/SL4-PRIVATE-STAGE" --ack PREPARE-OFFLINE-ONLY
```

Check the staged copy's hashes at any time:

```bash
python3 scripts/sl4_setup.py verify-backup --out "$HOME/Downloads/SL4-PRIVATE-STAGE"
```

To reproduce that backup into a **different ordinary local folder** (not the live ESP), verifying every copied hash again:

```bash
python3 scripts/sl4_setup.py restore-offline --backup-path "$HOME/Downloads/SL4-PRIVATE-STAGE" --out "$HOME/Downloads/SL4-PRIVATE-RECOVERED" --ack RESTORE-OFFLINE-COPY
```

The restored folder is private and not automatically installed. On Windows use `-Action RestoreOffline -BackupPath <private backup folder> -Out <new folder>`. Restoring to the active ESP and separately preserving Windows BCD still require a validated administrative process.

On Windows, the equivalent operations are `-Action Inspect|Backup|Prepare|VerifyBackup`, with `-SourceEfi` and `-Out` paths. The PowerShell wrapper passes the same explicit acknowledgments to the shared Python implementation.

**Private data warning:** staged/copied `EFI/OC/config.plist` still includes your personal SMBIOS identity. Never publish these output folders. Neither the tools nor GitHub releases include any personal EFI.

## Safety and recovery guarantees / limitations

- **No in-place live ESP write in this workflow.** Only ordinary new folders outside the provided source are created. Existing outputs are never overwritten.
- Source must be a real `EFI` directory; source `OC` and `BOOT` trees cannot contain symlinks. Windows Boot Manager must be present.
- All copied OC bytes and the Windows boot manager checksum are verified before success is reported.
- The live Windows BCD store is not copied because Windows can lock it. On Windows, export BCD separately using Windows backup procedures when authorized. A copy of bootmgfw.efi alone is *not* a full Windows recovery image.
- Any OpenCore configuration with enabled experimental `S0ixStandby.kext`, `SSDT-DEEPIDLE.aml`, conflicting VoodooI2C/SMCBatteryManager, missing drivers, or broken dependency order is **rejected for staging** until reviewed.
- `ocvalidate` 1.0.8 is optional for `inspect` when you provide a matching validator path. A syntax check **cannot prove an EFI boots**.
- Reinstalling all drivers on a clean, new Surface has **not** been tested. Some drivers require the existing machine's specific ACPI/graphics offsets, careful order, macOS package installation and actual reboot checks. Follow the [individual reversible installers](../README.md) only after exact hardware and backup verification.
- Full system S3/S0ix remains unresolved. Do not change `pmset sleep` or add experimental ACPI on the assumption that the eDP display-wake patch validates actual suspend-to-RAM.

## Produce a deterministic offline toolkit ZIP

The repository also includes `scripts/build_offline_kit.py`. It selects non-secret scripts, documents and the already pinned WEX eDP add-on. It never includes personal `config.plist`, EFI folders, Windows BCD or SMBIOS identifiers. From the repo root, create a new output filename:

`python3 scripts/build_offline_kit.py --out "$HOME/Downloads/SL4-UNIVERSAL-OFFLINE-20261123.zip"`

Check it later with `python3 scripts/build_offline_kit.py --out "$HOME/Downloads/SL4-UNIVERSAL-OFFLINE-20261123.zip" --verify-only`. The ZIP is a convenient existing-install *toolkit*; it does not create a universal bootable EFI and does not claim verified compatibility with other Intel Surface models. For missing upstream Graphics packages, `prepare_full_driver_pack.py` downloads them from pinned sources and verifies the known SHA-256.

## Validation and release checklist

Tests: `python3 -m unittest discover -s tests -v`.

Before calling an installation *verified*:

1. Compare hardware profile with the target machine (including ACPI, SSD variant, firmware).
2. Verify current live EFI/OC and Windows Boot Manager; preserve a private backup outside the ESP.
3. Confirm correct OpenCore 1.0.8 validator and SHA-256 manifest.
4. Use a separate offline stage for each proposed change, record hashes and rollback.
5. Apply changes to **one** test machine, with accessible Windows recovery, only once an installer has been independently audited.
6. Verify real macOS and Windows cold boots; test Metal, display, input, audio, network, battery and dock physically.
7. Repeat after recovery and document exact results. Automated tests and `ioreg` assertions do not substitute for these physical checks.

Until all steps are actually witnessed on supported hardware, this remains a preparatory workflow rather than a full one-click installer.
