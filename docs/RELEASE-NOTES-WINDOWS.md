# Surface Laptop 4 — Windows Quick Start v0.5.0 beta

Install macOS Tahoe from Windows with a guided **Quick Start**.

## How to use

1. Download and extract `SL4-Tahoe-Windows-QuickStart-v0.5.0-beta.zip`.
2. Double-click `QuickStart.cmd`.
3. Default Autopilot prepares OpenCore, Recovery, drivers and a suitable USB; it always requires exact disk-erase confirmation.
4. Boot the Surface from USB. In OpenCore select **macOS Base System (External)** (or **Recovery**) with arrow keys + Enter; do not select Windows or an existing macOS entry. New installer USBs show Recovery without pressing Space. Then install Tahoe into free space and run `QuickStart-Mac.command` to enable the full Surface hardware profile.
5. After accelerated macOS boots, the login agent validates the hardware. Run the same `QuickStart.cmd` in Windows with USB connected to automatically enter the validated internal EFI staging step (with user authorization).

Already running Tahoe? Open **QuickStart-Advanced.cmd** and choose **2** for repairs, **3** for advanced recovery options.

**Primary profile:** Surface Laptop 4 13.5-inch Intel Core i7-1185G7, Iris Xe 8086:9A49. Supported versions and components are selected by the setup; other hardware profiles require advanced customization.

[**Quick Start guide**](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/blob/main/docs/QUICKSTART.md) · [**Project README**](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh)

## v0.5.0 beta — automatic Windows-first installer orchestration

- `QuickStart.cmd` runs **Auto** by default; no Windows menu step. It prepares Recovery, personal EFI and pinned RCS + eDP/DMC/S0ix + Dolby as a single dependency-checked workflow; automatically selects a uniquely eligible USB disk, but requires explicit `ERASE USB N` plus administrator confirmation before any erase.
- The macOS helper now **autodetects first install / already-running accelerated Tahoe**, keeps advanced manual modes behind `--menu`, installs APOMac and Clear Speech without separate driver selections.
- A user-owned `com.sl4.autoverify` LaunchAgent checks actual accelerated RCS, DMC, eDP/Softsleep, S0ix, Metal 2, CoreMedia and the static Dolby speaker correction after the next reboot. It writes a ready marker to the USB **only when the real first boot passes**. Never runs as root or changes power settings.
- Starting the same Windows CMD again with the verified USB detects the stage, independently verifies EFI configuration and exact RCS binary SHA-256, and directs the existing internal OpenCore/BCD backup workflow. Privileged EFI work and new boot-entry selection still require explicit approval.
- Still mandatory: choose Surface UEFI USB boot; use Apple's Recovery GUI to safely choose the macOS target partition and set up a user; approve macOS administrator prompts and protected APOMac System Audio Recording. **This does not perform silent/unattended macOS installation or bypass Apple TCC.**
- Adds automated workflow tests and a new `docs/AUTOPILOT.md` guide. The accelerated driver and Dolby binary hashes remain unchanged, as does the default non-mutating macOS `pmset` behavior. Real fresh USB/Recovery-to-Tahoe installation not yet certified.

## v0.4.2 beta — preserve working sleep and screen wake (critical correction)

- **Removes the incorrect v0.4.1 `pmset -a sleep 0 displaysleep 0` call entirely.** Neither clean install nor existing-install repair overwrites the user's macOS power settings. The installer now displays the existing `pmset -g custom` values read-only.
- Keeps the same SHA-pinned WhateverXe RCS + DMC + eDP Keep/Softsleep binary, the S0ixStandby 0.5.8 driver and Deep Idle SSDT, with original flags for panel wake and manual system sleep. Does not overwrite an existing working EFI.
- Retains the previously verified macOS Tahoe YouTube H.264/HEVC CoreMedia compatibility check and original WhateverXe Graphics 0.4.4 postinstall, plus Dolby Clear Speech -3.0 dB profile and APOMac login support.
- Adds a regression test that **rejects any command that resets `pmset` sleep/displaysleep in core install scripts**. Improves clear documentation of the two short system sleep/wake cycles and observed lid/power-button wake. A user's working manual sleep may coexist with `pmset sleep=0`, which only disables automatic idle sleep; neither value is used as a benchmark of driver success.
- All-in-one clean install on independent devices still requires physical verification. A Windows CMD starts and prepares the full process but Apple Recovery installation, macOS driver transition and first-use TCC audio permission necessarily require user actions.

**Do not use the earlier v0.4.1 beta package for a new setup.** Its unintended power-policy write has been corrected in this release.

## v0.4.1 beta — superseded: mistaken automatic-sleep override

- Confirms the official WhateverXe Graphics 0.4.4 postinstall sets `/Library/Preferences/FeatureFlags/Domain/CoreMedia.plist` to `AllowOnePassMetalScaling.Enabled=false` for Tahoe. The first-boot setup now **asserts this value** immediately after package installation; it refuses to stage the new RCS driver if the H.264/HEVC compatibility prerequisite is missing.
- Preserves the working machine's conservative **automatic sleep disabled** policy (`pmset -a sleep 0 displaysleep 0`) during the initial macOS hardware setup. The previous `pmset -g custom` output is saved in Downloads before modification. Manual display-off and supervised sleep/wake remain available; full unattended sleep reliability is not established.
- Keeps the exact original composite RCS + DMC + eDP kext, S0ixStandby + Deep Idle SSDT, and Dolby Clear Speech. No new graphics binaries, no modified CoreMedia drivers.
- Updates first-install and download instructions and adds offline regression tests for both compatibility protections. Tested on one reference Surface; full v0.4.1 USB clean install not yet independently validated.

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
