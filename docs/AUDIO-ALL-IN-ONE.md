# Surface Laptop 4 — integrated Iris Xe RCS graphics and Dolby Clear Speech

**Windows-first QuickStart v0.5.0 beta.** For the tested Surface Laptop 4 Intel 13.5", i7-1185G7, Iris Xe PCI 8086:9A49, ALC274 10EC:123E, Tahoe 26.7.1.

For the new Windows/Mac automatic mode and unavoidable Apple recovery/permission confirmations, read [Autopilot v0.5.0](AUTOPILOT.md).

## What happens without separate patches

1. On Windows, the QuickStart ZIP already contains the exact Surface-tested RCS single-port WhateverXe and the generated Dolby speaker-correction WAVs and APOMac profiles. The Windows preparer verifies their SHA-256, downloads the pinned official OpenCore/Apple Recovery/WhateverXe Graphics 0.4.4 and upstream APOMac v0.1.0, then stages all components together on the USB. No pre-existing macOS installation is needed.
2. Boot and install macOS Tahoe using the **MACOS-OC** Recovery USB while preserving Windows.
3. In Tahoe, run `QuickStart-Mac.command` from **SL4DATA**, choose **1**. It installs the verified graphics donor, replaces the first accelerated WhateverXe with the integrated RCS+eDP+DMC driver in the same transaction, enables original Surface input/Wi-Fi/Bluetooth/audio/brightness stages, backs up the user's personal OpenCore config, and installs the Dolby-derived `Clear Speech` correction and APOMac. No second separate RCS installer.
4. Reboot using the prepared OpenCore USB to activate hardware drivers and confirm macOS Metal, input, display and audio.
5. On first APOMac launch, **macOS requires user approval for System Audio Recording**. Click Allow. This TCC permission cannot be legally or reliably installed silently by a hardware utility. APOMac then processes audio and starts automatically at future logins.

The app download and all individual asset digests are pinned. **No personal EFI, serial, SMBIOS, BCD or original Dolby XML** is included in the public release.

## Previously verified sleep and YouTube compatibility are retained

The RCS kext is compiled from upstream WhateverXe 0.8.3 plus eDP Keep/Softsleep, DMC firmware and RCS mitigation patches **in this order**; it is not an RCS-only replacement. The installer also retains `S0ixStandby 0.5.8`, `SSDT-DEEPIDLE.aml` and the previously tested eDP/DMC/GPU-recovery flags.

Tahoe YouTube H.264/HEVC playback uses the original **WhateverXe Graphics 0.4.4** installer, including its Tahoe postinstall CoreMedia fix. The all-in-one verifies `AllowOnePassMetalScaling.Enabled=false` before activating the new graphics boot configuration. No promise of VP9/AV1 playback is made.

On the reference Surface, manual system sleep / Deep Idle wake works and the eDP Keep/Softsleep patch enables screen wake after lid/power-button action. The device currently reports `pmset sleep=0 displaysleep=0`, which **disables only timed automatic sleep/display idle**, not manual sleep. These values were a diagnostic choice on that one system, not a required driver configuration.

**Corrected in v0.4.2:** the all-in-one installation leaves `pmset` power policy **completely unchanged**, shows it read-only and preserves the tested eDP/DMC/S0ix/OpenCore patches. v0.4.1 mistakenly set both timers to zero; do not use that version for new installations. A new user's macOS sleep timers stay as they were. Verify real lid/power-button wake and monitor battery behavior on the actual device.


## Verified audio reference

The Intel Surface's genuine Windows Dolby DAX3 settings (`DEV_0274_SUBSYS_10EC123E_PCI_SUBSYS_72708086.xml`) were exported by `speaker-tuning-to-easyeffects`, converted to independent **left/right FIRs** at 48 kHz / 4096 taps, then mapped to APOMac's CoreAudio engine. The actual reference Surface was tested on macOS Tahoe 26.7.1 and the owner reported significantly clearer speech. Volume became noticeably quieter; the owner approved keeping it that way.

Default: **Surface Laptop 4 - Clear Speech**. FIR `980695d30da4e38...`, preamp **−3.0 dB**, bell **+1.88 dB / 2500 Hz / Q 0.70**. Device scope: `AppleHDAEngineOutput:1F,3,0,1,1:0` (built-in Surface speaker output only). No effect on unrelated output devices such as headphones/HDMI. Other preloaded profiles: Balanced, Detailed, Warm, Voice.

This recreates the **static speaker correction** and approximate speech boost, not the complete proprietary Dolby Atmos dynamic processing. It is not an AppleALC replacement and does not change the Windows audio driver.

Toggle APOMac bypass with **Cmd+B**. Quit APOMac to return to native audio. For complete permanent removal of the EQ, remove the user launch agent `~/Library/LaunchAgents/com.sl4.apomac.autostart.plist`, remove the APOMac profiles, and remove the app. Do not delete SimpleHDA if that is what provides native audio.

## Safety and recovery

- All new accelerated-kext installation is **qualified by exact Intel CPU, PCI ID, macOS 26.7.1 and donor SHA-256**. On other machines it stops without applying an unverified graphics driver.
- The original installer USB EFI is retained. An OpenCore config backup is written on USB and an entire OC copy in the user's Downloads.
- When repairing an already booting macOS, choose **2**. The installer checks whether `SL4RCSSinglePortReady` is active; if not, it finds exactly one internal Windows/macOS EFI and uses the reversible RCS installer with a full backup. It never blindly overwrites the Windows boot manager.
- Other systems, unsupported firmwares and versions of macOS are not automatically certified. This integration has been tested by offline package/unit checks, but **a newly assembled v0.4.1 USB full clean install remains to be tested**.
- Synthetic 400,000 Metal command buffers succeeded on the reference Surface with no new GPU resets in the subsequent session. Owner's FPS increase 14→30 after several minutes is anecdotal; the mechanism is unconfirmed.
- New audio permission may require user interaction and reapproval on fresh installations. Sound enhancement is tied to login; graphical driver is tied to OpenCore boot.

## Sources and licenses

- RCS source patch: `research/wex-sl4-rcs-singleport.patch` plus WhateverXe source and prior pinned DMC/eDP patches.
- Audio conversion method: <https://github.com/antoinecellerier/speaker-tuning-to-easyeffects> (MIT; generated assets originate in the reference Surface Dolby driver).
- APOMac: <https://github.com/mkroplewski/APOMac> (GPL-2.0, not bundled as a binary in the repo; installer downloads the official release for macOS and verifies SHA-256).
- The public ZIP contains speaker FIR / APOMac text presets only, not any raw Windows Dolby driver XML. Device-specific calibration may not be suitable for other hardware.

**Not an official Apple, Dolby, or Microsoft release.**
