# Surface Laptop 4 — Windows Quick Start v0.3.2 beta

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

## v0.3.1 beta fix

- Fixed an incomplete Windows release archive: `scripts/xe_acceleration.py` was missing from the distributable ZIP even though `windows_prepare_tahoe.py` requires it when staging post-install drivers. Previously, option 1 could fail late after Apple Recovery and OpenCore had already downloaded.
- Added a distribution regression test asserting that this helper is present in the ZIP.
- Exercised `QuickStart.cmd` option 4 on an Intel Surface Laptop 4 using a 29.3 GiB USB disk, and verified that OpenCore and Apple Recovery were written to `MACOS-OC` while driver files were copied to `SL4DATA`. This tests USB creation, not the physical Recovery boot; boot validation is pending.

## v0.3.2 beta - confirmed USB Recovery boot and visible installer entry

- On 2026-11-23, the user confirmed a real USB OpenCore boot into Apple macOS Recovery on the Surface Laptop 4 Intel, prepared entirely from Windows Quick Start. The previous v0.3.1 installer had hidden Recovery as an auxiliary picker entry; it was manually revealed for the successful boot. This does **not** certify a clean macOS installation or a newly rebuilt v0.3.2 USB boot.
- New installer EFI explicitly sets `Misc/Boot/HideAuxiliary=false`, `ShowPicker=true`, `Timeout=15`, without changing the quiet picker policy for existing installed-system EFI configurations.
- Added an automated regression test for quiet and verbose installer profiles, and updated the Windows CLI, README and Russian step-by-step guide with the exact entry to boot. Older USBs can expose hidden Recovery by pressing **Space** in OpenCore.
