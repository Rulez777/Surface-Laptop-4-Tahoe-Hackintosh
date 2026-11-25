# Surface Laptop 4 Intel — built-in keyboard, trackpad and sleep/wake profile

**Reference hardware:** Surface Laptop 4 Intel i7-1185G7, Tahoe 26.7.1. The existing keyboard and trackpad worked with the BigSurface stack; the project now carries a clean production rebuild that adds guarded lid-GPE recovery and optional SAM GPIO wake.

## Production profile assembled 2026-11-25

| Component | Pinned version | Role |
| --- | --- | --- |
| VoodooGPIO.kext | **1.2.5** | Tiger Lake-LP GPIO, F11 lid GPE watchdog/re-arm, RXINV preservation |
| VoodooSerial.kext | 1.2 | Surface UART 8086:A0A8 |
| VoodooInput.kext | 1.1.3 | Multitouch input and gestures |
| BigSurface.kext | **1.2.1** | Surface Aggregator Module; guarded SAM GPIO 0x12A wake |
| BigSurfaceHIDDriver.kext | 1.0.0 | Built-in Surface HID input |

The profile also installs SSDT-SL4-LIDWAKE.aml for the Surface Laptop 4 Intel lid GPE 0x4B. The VoodooGPIO watchdog is bounded, hardware-fingerprint-gated to the observed Tiger Lake-LP mapping, and retained because the firmware disables the lid GPE after repeated resume cycles. RXINV is preserved from the live OEM ACPI state across GPIO resume. SAM keyboard/trackpad wake on GPIO 0x12A is enabled in the profile but **has not yet passed physical wake regression**.

The production package excludes the temporary lid GPIO probe timer, IORegistry diagnostic properties, probe sample counters, and per-event GPIO wake log. OpenCore Misc.Debug.SysReport is disabled. The temporary -wex-edp-wake-trace boot argument is removed while preserving all other boot arguments.

**Important validation boundary:** the package and all-in-one staging paths pass archive, checksum, configuration, and OpenCore integration tests. The clean VoodooGPIO 1.2.5 rebuild has not yet completed its own physical sleep/wake regression on the reference Surface. The currently running macOS session was still using VoodooGPIO 1.2.4 at the last read-only audit. Do not describe the 1.2.5 profile or SAM wake as physically verified until the machine is rebooted and tested.

## Install on an existing Tahoe EFI

The Windows-first All-in-One now includes the exact pinned package and guarded macOS installer:

- Package: packages/SL4-TGL-Input-SleepWake-v2-beta.zip
- Installer: scripts/install_sl4_sleepwake_macos.py
- Reproducible build: experiments/sl4-input/build-bigsurface-sl4-sleepwake.py
- Production source patch: experiments/sl4-input/patches/sl4-sleepwake-production.patch

First mount the internal EFI read-only and inspect:

    sudo diskutil mount readOnly disk0s1
    python3 scripts/install_sl4_sleepwake_macos.py --mode inspect --efi /Volumes/SYSTEM/EFI --artifact packages/SL4-TGL-Input-SleepWake-v2-beta.zip

Only after confirming Windows Boot Manager recovery, remount the internal EFI read/write and stage with a complete EFI/OC backup, Windows-visible rollback plist, and mandatory OpenCore 1.0.8 validation:

    sudo diskutil unmount disk0s1
    sudo diskutil mount disk0s1
    sudo python3 scripts/install_sl4_sleepwake_macos.py --mode apply --efi /Volumes/SYSTEM/EFI --artifact packages/SL4-TGL-Input-SleepWake-v2-beta.zip --backup-dir "$HOME/Downloads/SL4-SLEEPWAKE-BACKUPS" --ocvalidate "$HOME/Downloads/OC108-validate/Utilities/ocvalidate/ocvalidate" --ack STAGE-SL4-SLEEPWAKE
    sync
    sudo diskutil unmount disk0s1

The installer refuses a non-SL4 Intel machine, a different internal ESP, missing Microsoft Boot Manager, mismatched DVMT/Metal boot arguments, unrecognized kext binaries, or invalid SSDT. It replaces the five input bundles, disables conflicting VoodooI2C/duplicate input paths, enables the lid-wake SSDT, disables OpenCore SysReport, removes only the temporary eDP trace argument, and preserves all other boot arguments and graphics settings. A full OC backup is stored on APFS; a separate original config.plist rollback snapshot is written at the EFI root for recovery from Windows. The installer never modifies EFI/Microsoft, partitions, BCD, APFS, firmware boot order, or SMBIOS identity.

The Windows-created new-install EFI is assembled with the same package by scripts/build_efi.py; it also strips the temporary eDP trace and the two RCS trial flags so the new-install profile matches the reference EFI. The Mac postinstall checks the exact versions and SSDT before proceeding. Existing-system repair removes only the eDP diagnostic flag and preserves any user-enabled RCS trial settings.

## Apple-like trackpad controls, tap-to-click, disable accidental Look Up

After macOS boots with the five working kexts, run the following in Terminal **as the normal macOS user; do not use sudo**:

```bash
sh "$HOME/Downloads/SL4-Tahoe-Git/scripts/configure_surface_trackpad.sh"
```

Or download just the standalone script and run it in a single shell line:

```bash
curl -fL --retry 3 "https://raw.githubusercontent.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/main/scripts/configure_surface_trackpad.sh" -o "$HOME/Downloads/configure_surface_trackpad.sh" && sh "$HOME/Downloads/configure_surface_trackpad.sh"
```

It sets current-user Apple trackpad preferences (no EFI/kext changes):
- tap-to-click (`Clicking=true`);
- two-finger secondary click (`TrackpadRightClick=true`);
- disables the accidental three-finger **Look Up** (`TrackpadThreeFingerTapGesture=0`);
- suppresses Apple Force Click behavior; preserves regular trackpad movement and scrolling.

The owner reported this exact group of preferences made the touchpad behave ideally for them. Some settings may need sign-out/sign-in, and real behavior depends on the active HID driver. Apple Force Touch haptics are not available in Surface hardware.

## Verification

Use: `kmutil showloaded 2>/dev/null | grep -Ei 'BigSurface|VoodooSerial|VoodooGPIO|VoodooInput'`

Inspect input matching without dumping megabytes of `IOKitDiagnostics`: `ioreg -l -w0 | grep -E 'SurfaceHIDDriver|SurfaceSerialHubDriver|VoodooGPIOTigerLakeLP|AppleMultitouchTrackpadHIDEventDriver' | cut -c 1-260 | head -20`

Verify physical keyboard, one-finger tap, two-finger secondary click, two-finger scroll, and physical left/right click in a harmless app such as Finder. A loaded kext alone does not mean a working input device.

## Recovery

The macOS stager saves the complete original `EFI/OC` in `~/Downloads/SL4-SLEEPWAKE-BACKUPS/SL4-SLEEPWAKE-*/OC` **and** saves an original `config.plist` snapshot as `EFI/SL4-SLEEPWAKE-ROLLBACK-*.plist`, visible from Windows. If macOS fails to start after applying the new kexts, independently boot Windows Boot Manager and restore this pre-input `config.plist` (on the mounted internal ESP), then reboot. See [macOS rollback instructions](../experiments/sl4-input/INSTALL-MACOS-RU.md).

**Scope:** verified on one SL4 Intel, not SL4 AMD, SL3/SL5, Surface Pro or every firmware revision. Installer must refuse an unsupported device rather than assume compatibility.
