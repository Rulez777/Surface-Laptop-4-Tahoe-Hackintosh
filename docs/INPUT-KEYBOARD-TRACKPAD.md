# Surface Laptop 4 Intel — built-in keyboard and trackpad on macOS Tahoe

**Status (2026-11-22): Confirmed working on the project owner's Surface Laptop 4 Intel** (i7-1185G7, Tahoe 26.7.1). The owner confirmed the built-in keyboard and touchpad function, and then confirmed the touchpad became substantially better after applying the macOS tap/gesture preferences below. The driver stack enumerates in `kmutil showloaded` and Surface HID devices attach in `ioreg`. This is one-machine user verification, **not** a universal hardware certification.

**Terminology:** Microsoft's built-in pointing device is a **trackpad / touchpad** (тачпад), not an Apple **Touch Bar**. The procedure provides input and gestures, not a Touch Bar screen.

## Exact input stack verified in the owner's live system

| Kext | Version observed loaded | Role |
| --- | --- | --- |
| `VoodooGPIO.kext` | 1.2.0 | Tiger Lake-LP GPIO / interrupt support |
| `VoodooSerial.kext` | 1.2 | Intel Tiger Lake UART0, `8086:A0A8` |
| `BigSurface.kext` | 1.2.0 | Surface Aggregator Module (SAM) |
| `BigSurfaceHIDDriver.kext` | 1.0.0 | Built-in Surface HID input |
| `VoodooInput.kext` | 1.1.3 | Multitouch events and gestures |

Live system also showed `SurfaceSerialHubDriver`, `VoodooUARTController`, `VoodooGPIOTigerLakeLP`, `SurfaceHIDNub`, `SurfaceHIDDriver`, `SurfaceHIDDevice`, and Apple multitouch HID matching in IORegistry.

Hardware ACPI: `\_SB.SSH` = `MSHW0084`; UART `\_SB.PC00.UA00` 4 Mbps; GPIO `\_SB.GPI0`, pin `0x012A`. Original Surface Laptop 4 Intel ACPI: [linux-surface](https://github.com/linux-surface/acpidumps/blob/master/surface_laptop_4_intel/ssdt9.dsl). **Do not use the SL5 SSDT-SAM: the existing SL4 ACPI hub must be retained.**

## Install BigSurface stack on an existing macOS Tahoe / Metal 2 EFI

**Prerequisites:** Surface Laptop 4 **Intel Tiger Lake** with UART `8086:A0A8`, current working **OpenCore 1.0.8 + Tahoe + Metal 2**, installed Xcode Command Line Tools (`xcode-select --install`, follow graphical installation), an **external keyboard/mouse**, and **independent Windows Boot Manager access** for recovery. Never copy another owner's serialized `config.plist` or SMBIOS IDs.

The tested-laptop kexts were operational, but the fresh clean-checkout builder and both staging scripts have not been verified end-to-end on a second computer. The builder downloads pinned third-party sources and outputs five experimental kexts; the guarded stager operates **only** on a matching internal ESP. Check the [experimental code](../experiments/sl4-input/README.md) and [macOS procedure](../experiments/sl4-input/INSTALL-MACOS-RU.md) before applying.

**Run each command as one physical line. Stop at any error.**

1. Check tools: `xcode-select -p && python3 --version && git --version`
2. Clone public project if not present: `git clone https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh.git "$HOME/Downloads/SL4-Tahoe-Git"`
3. Build the five-kext stack (only writes under Downloads): `python3 "$HOME/Downloads/SL4-Tahoe-Git/experiments/sl4-input/build-bigsurface-sl4.py"`
4. After a confirmed successful build, package them: `cd "$HOME/Downloads/bigsurface-sl4" && /usr/bin/zip -qyr "$HOME/Downloads/SL4-BigSurface-EXPERIMENTAL.zip" out`
5. Get OpenCore **1.0.8** validator: `curl -fL --retry 3 "https://github.com/acidanthera/OpenCorePkg/releases/download/1.0.8/OpenCore-1.0.8-RELEASE.zip" -o "$HOME/Downloads/OpenCore-1.0.8-RELEASE.zip" && mkdir -p "$HOME/Downloads/OC108-validate" && ditto -xk "$HOME/Downloads/OpenCore-1.0.8-RELEASE.zip" "$HOME/Downloads/OC108-validate"`
6. Mount ESP read-only and **inspect, without writing**: `sudo diskutil mount readOnly disk0s1; python3 "$HOME/Downloads/SL4-Tahoe-Git/experiments/sl4-input/stage-surface-input-macos.py" --mode inspect --efi /Volumes/SYSTEM/EFI --artifact "$HOME/Downloads/SL4-BigSurface-EXPERIMENTAL.zip"`
7. **Only if inspect succeeds** and Windows recovery is confirmed, mount ESP read/write: `sudo diskutil unmount disk0s1 && sudo diskutil mount disk0s1`
8. Stage with complete OC backup and validation: `sudo python3 "$HOME/Downloads/SL4-Tahoe-Git/experiments/sl4-input/stage-surface-input-macos.py" --mode apply --efi /Volumes/SYSTEM/EFI --artifact "$HOME/Downloads/SL4-BigSurface-EXPERIMENTAL.zip" --backup-dir "$HOME/Downloads/SL4-INPUT-BACKUPS" --ocvalidate "$HOME/Downloads/OC108-validate/Utilities/ocvalidate/ocvalidate" --ack STAGE-SL4-INPUT`
9. If and **only if** you see `STAGED AND VALIDATED`: `sync && sudo diskutil unmount disk0s1`. Reboot macOS and test built-in keyboard, trackpad and existing Metal/Wi-Fi.

The stager disables the conflicting `VoodooI2C*`, duplicate `VoodooInput`, `SMCBatteryManager` and `SMCLightSensor` paths in OpenCore, inserts the five kexts in dependency order, **preserves the graphics / NVRAM configuration**, and keeps a complete `EFI/OC` backup. It rejects non-matching hardware and invalid binaries. **Never hand-edit Microsoft EFI or Windows BCD.**

**Windows alternative** (without Xcode on the Mac): [Windows installation guide](../experiments/sl4-input/INSTALL-RU.md). That method requires a previously successful five-kext macOS CI build artifact.

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

The macOS stager saves the complete original `EFI/OC` in `~/Downloads/SL4-INPUT-BACKUPS/SL4-INPUT-*/OC` **and** saves an original `config.plist` snapshot as `EFI/SL4-INPUT-ROLLBACK-*.plist`, visible from Windows. If macOS fails to start after applying the new kexts, independently boot Windows Boot Manager and restore this pre-input `config.plist` (on the mounted internal ESP), then reboot. See [macOS rollback instructions](../experiments/sl4-input/INSTALL-MACOS-RU.md).

**Scope:** verified on one SL4 Intel, not SL4 AMD, SL3/SL5, Surface Pro or every firmware revision. Installer must refuse an unsupported device rather than assume compatibility.
