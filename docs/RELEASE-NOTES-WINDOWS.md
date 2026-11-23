# Surface Laptop 4 — Windows Quick Start v0.4.0 beta

Install macOS Tahoe from Windows with a guided **Quick Start**.

## How to use

1. Download and extract `SL4-Tahoe-Windows-QuickStart-v0.3.2-beta.zip`.
2. Double-click `QuickStart.cmd`.
3. Press `1` to prepare the Tahoe installer, personal OpenCore EFI, Apple Recovery, drivers and installation USB.
4. Boot the Surface from USB. In OpenCore select **macOS Base System (External)** (or **Recovery**) with arrow keys + Enter; do not select Windows or an existing macOS entry. New installer USBs show Recovery without pressing Space. Then install Tahoe into free space and run `QuickStart-Mac.command` to enable the full Surface hardware profile.
5. Press `5` in Windows Quick Start to complete internal-SSD OpenCore dual boot, preserving Windows.

Already running Tahoe? Press **2** to prepare the driver repair kit. For other recovery variants use **3 — Advanced / Experiments**.

**Primary profile:** Surface Laptop 4 13.5-inch Intel Core i7-1185G7, Iris Xe 8086:9A49. Supported versions and components are selected by the setup; other hardware profiles require advanced customization.

[**Quick Start guide**](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/blob/main/docs/QUICKSTART.md) · [**Project README**](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh)

## v0.4.0 beta — integrated RCS graphics and Dolby Clear Speech

- The **Windows-first ZIP itself includes** the verified Intel Iris Xe `SL4-RCS-Stability-0.1.0-beta.zip` and the Surface ALC274 Dolby speaker FIR/presets. No external manual patch download or audio conversion.
- Windows wizard obtains the official APOMac 0.1.0 DMG pinned to SHA-256 and stages it alongside the official Graphics donor, original DMC/S0ix release and RCS-verified binary.
- **QuickStart-Mac option 1** stages the RCS single-port WhateverXe (rather than the old DMC-only kext) into the first Metal-accelerated USB EFI with validated donor and hardware ID; applies the `-wex-sl4-rcs-singleport` flag and stores full OC backups.
- The **same option 1** installs APOMac, binds the exact Windows Dolby derived Clear Speech profile to the built-in Surface output, leaves its reported preferred −3 dB preamp unchanged and registers a login item.
- **QuickStart-Mac option 2** repairs an already installed system: check active RCS first, otherwise use the guarded existing installer and full backup, then install the sound profile. All assets are SHA-256-checked; wrong hardware/OS fails closed.
- The user must manually approve the first **System Audio Recording** macOS privacy prompt. No automated TCC circumvention.
- Windows and macOS recovery environments are still independent; private SMBIOS, Windows EFI, Steam and boot order are never shipped as public assets.
- Tested individual Intel RCS fix and audio profile on one reference Surface; a fresh complete v0.4.0 installation has not yet been verified, so release remains **beta**. Full guide: [AUDIO-ALL-IN-ONE.md](AUDIO-ALL-IN-ONE.md).

## v0.3.3 beta — stable RCS driver available from Windows

- Pins the verified `SL4-RCS-Stability-0.1.0-beta.zip` public release by archive SHA-256 and by the SHA-256 of its Intel WhateverXe executable. The Windows preparer validates its signed-off manifest **before copying** it to the SL4DATA partition.
- Both the fresh Windows-to-Tahoe USB and the **Tahoe already installed** repair path stage this optional postinstall package. Users do not need macOS already installed to download and prepare the drivers on Windows.
- Adds **option 4** to the *macOS* `QuickStart-Mac.command` to install the RCS fix only after exact Surface CPU, GPU, Tahoe donor, existing Metal/DMC profile and internal EFI pass preflight. Installer creates full private OC backup and preserves Windows Boot Manager and original WhateverXe.
- Patches the RCS Execlist single-port/preemption issue found in two Spectator 3 GPU Reset reports. Owner observed no new reset after gameplay and a reported warm-up from 14 to approximately 30 FPS. **Causality of the FPS improvement remains unproven**.
- Adds archive, source-patch and fail-closed regression checks; publishes a new independent v0.3.3 release without overwriting v0.3.2.

## v0.3.1 beta fix

- Fixed an incomplete Windows release archive: `scripts/xe_acceleration.py` was missing from the distributable ZIP even though `windows_prepare_tahoe.py` requires it when staging post-install drivers. Previously, option 1 could fail late after Apple Recovery and OpenCore had already downloaded.
- Added a distribution regression test asserting that this helper is present in the ZIP.
- Exercised `QuickStart.cmd` option 4 on an Intel Surface Laptop 4 using a 29.3 GiB USB disk, and verified that OpenCore and Apple Recovery were written to `MACOS-OC` while driver files were copied to `SL4DATA`. This tests USB creation, not the physical Recovery boot; boot validation is pending.

## v0.3.2 beta - confirmed USB Recovery boot and visible installer entry

- On 2026-11-23, the user confirmed a real USB OpenCore boot into Apple macOS Recovery on the Surface Laptop 4 Intel, prepared entirely from Windows Quick Start. The previous v0.3.1 installer had hidden Recovery as an auxiliary picker entry; it was manually revealed for the successful boot. This does **not** certify a clean macOS installation or a newly rebuilt v0.3.2 USB boot.
- New installer EFI explicitly sets `Misc/Boot/HideAuxiliary=false`, `ShowPicker=true`, `Timeout=15`, without changing the quiet picker policy for existing installed-system EFI configurations.
- Added an automated regression test for quiet and verbose installer profiles, and updated the Windows CLI, README and Russian step-by-step guide with the exact entry to boot. Older USBs can expose hidden Recovery by pressing **Space** in OpenCore.
