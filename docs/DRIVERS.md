# Drivers and hardware testing

The **boot EFI** and the **peripheral-test EFI** serve different purposes. Tahoe booted on the test Surface with the minimal kernel stack plus the custom RTC0 ACPI fix. The additional drivers below are **available for testing**, not confirmation that each feature works.

**Full driver download:** `py -3 scripts/prepare_full_driver_pack.py --source C:/path/to/personal/EFI --out SL4-Driver-Pack` downloads all optional EFI candidates **plus the verified 95 MB WhateverXe Graphics 0.4.4 macOS installer** and the optional Surface IPTSDaemon. Keep the source EFI private and unchanged. See [graphics acceleration](GRAPHICS-ACCELERATION.md). The package contents are candidates; no single working all-drivers EFI for Surface Laptop 4 + Tahoe has yet been demonstrated.

## Known-boot components

| Component | Version | Status |
|---|---|---|
| [OpenCore](https://github.com/acidanthera/OpenCorePkg/releases/tag/1.0.8) | 1.0.8 | Test-machine bootloader |
| [Lilu](https://github.com/acidanthera/Lilu/releases/tag/1.7.2) | 1.7.2 | Enabled |
| [VirtualSMC](https://github.com/acidanthera/VirtualSMC/releases/tag/1.3.8) | 1.3.8 | Enabled |
| [WhateverXe](https://github.com/b00t0x/WhateverXe/releases/tag/0.8.3) | 0.8.3 | Enabled, with `-wex-noaccel` |
| [AMFIAnchor](https://github.com/b00t0x/AMFIAnchor/releases/tag/0.1.2) and injector | 0.1.2 | Enabled |
| [USBToolBox](https://github.com/USBToolBox/kext/releases/tag/1.2.0) + custom UTBMap | 1.2.0 + custom | Enabled; actual USB behavior still needs tests |
| Surface `SL4-XHCI-A0ED.kext` | Custom | Enabled for Tahoe |
| Surface `SSDT-RTC0-SL4.aml` | Custom | **Enabled — pivotal last change before successful Recovery** |
| `HfsPlus.efi`, `OpenRuntime.efi` | OpenCore dependencies | Enabled |

## Extra drivers — staged for testing

Run the optional driver fetcher **against a personal EFI copy**, preferably only after a full backup:

```powershell
py -3 scripts/add_optional_drivers.py --source EFI-output/EFI --out EFI-peripherals
```

The following are copied to `EFI-peripherals/EFI/OC/Kexts`, with matching **disabled** OpenCore entries. The original `EFI-output/EFI` stays untouched.

| Component | Pinned source/version | Intended hardware | Notes |
|---|---|---|---|
| [AppleALC](https://github.com/acidanthera/AppleALC) | 1.9.8 | Realtek audio | Needs correct ALC layout; not tested |
| [AirportItlwm Tahoe fork](https://github.com/laobamac/itlwm/releases/tag/v2.4.0-alpha) | 2.4.0-alpha | Intel AX201 Wi-Fi | Experimental Tahoe build; hardware test pending |
| [IntelBluetoothFirmware](https://github.com/OpenIntelWireless/IntelBluetoothFirmware/releases/tag/v2.4.0) | 2.4.0 | Intel Bluetooth | Upstream stable may not work on Tahoe; test only |
| [IntelBTPatcher](https://github.com/OpenIntelWireless/IntelBluetoothFirmware/releases/tag/v2.4.0) | 2.4.0 | Intel BT feature patches | Staged **disabled**; do not enable alongside incompatible alternative patches |
| [BlueToolFixup](https://github.com/acidanthera/BrcmPatchRAM/releases/tag/2.7.2) | 2.7.2 | Bluetooth macOS integration | Requires firmware/support testing |
| [SMCBatteryManager](https://github.com/acidanthera/VirtualSMC/releases/tag/1.3.8) | 1.3.8 | Battery | Staged; **do not pair with BigSurface** if following BigSurface's own installation instructions |
| [VoodooPS2Controller](https://github.com/acidanthera/VoodooPS2/releases/tag/2.3.7) | 2.3.7 | PS/2 keyboard/trackpad | Surface Laptop 4 uses a different input architecture; no support proven |
| [VoodooI2C / VoodooI2CHID](https://github.com/VoodooI2C/VoodooI2C/releases/tag/v2.9.1) | 2.9.1 | I²C input | Only suitable if hardware ACPI matches; may conflict with BigSurface |
| [BigSurface](https://github.com/Xiashangning/BigSurface/releases/tag/v6.5) | 6.5 | Surface SAM input, touch, battery | **Not verified for Laptop 4 or Tahoe**. Requires matching Surface SSDT and possible daemon. Not safe to enable blindly |
| [NVMeFix](https://github.com/acidanthera/NVMeFix/releases/tag/1.1.3) | 1.1.3 | NVMe power behavior | Candidate only; **do not enable on Samsung PM991 without a measured compatibility test** |
| [RestrictEvents](https://github.com/acidanthera/RestrictEvents/releases/tag/1.1.6) | 1.1.6 | Optional macOS compatibility patches | Not necessary for proven boot; staged disabled |
| [IPTSDaemon](https://github.com/Xiashangning/IPTSDaemon/releases/tag/v1.4) | 1.4 | Surface touchscreen/stylus user-space helper | Downloaded as a separate ZIP; requires compatible SAM and touch drivers, unqualified for Tahoe |

The [BigSurfaceHIDDriver source](https://github.com/Xiashangning/BigSurfaceHIDDriver) is also available, but it has **no published prebuilt release**. It cannot honestly be presented as a ready-made tested Laptop 4/Tahoe driver. Compiling and adapting the Surface SAM/HID stack may be necessary.\n\nThe official BigSurface README specifically lists earlier Surface models and instructs users to remove VoodooI2C and SMCBatteryManager before using BigSurface. **Do not enable BigSurface and VoodooI2C simultaneously.** Do not assume the 2023 BigSurface release loads on Tahoe 26.

Optional test profiles supported by the builder (each in a **new output directory**):

```powershell
py -3 scripts/add_optional_drivers.py --source EFI-output/EFI --out EFI-audio-test --enable audio
```

```powershell
py -3 scripts/add_optional_drivers.py --source EFI-output/EFI --out EFI-wifi-test --enable wifi
```

```powershell
py -3 scripts/add_optional_drivers.py --source EFI-output/EFI --out EFI-bluetooth-test --enable bluetooth
```

**These are experimental, not guaranteed Tahoe-ready.** After creating each test EFI, run matching OpenCore 1.0.8 `ocvalidate` and confirm every required dependency, then test **one profile at a time from a recovery-capable USB**. Keep a separately backed-up known-good EFI. Do not apply all unverified drivers to the internal ESP at once.

## Graphics and input status

- **Iris Xe 96 EU:** boots to GUI with WhateverXe and `-wex-noaccel`; this is **not** Metal acceleration and is a likely reason for slow UI rendering. The complete pack fetches [WhateverXe Graphics 0.4.4](https://github.com/b00t0x/WhateverXe-Graphics/releases/tag/v0.4.4), a **macOS /Library installer** that cannot be enabled simply by adding EFI kexts. Read the [safe acceleration plan](GRAPHICS-ACCELERATION.md). Acceleration remains unverified on this Surface.
- **Built-in keyboard / trackpad / touchscreen:** unverified. The Surface Laptop 4 uses Surface Aggregator Module (SAM) devices, and an off-the-shelf VoodooPS2/VoodooI2C kext is unlikely to make all input devices functional. Test with **external USB keyboard and mouse**; request or develop a Laptop 4-specific SAM/ACPI solution if BigSurface fails.
- **Wi-Fi / Bluetooth:** unverified in installed Tahoe; the optional archive includes experiment candidates. Avoid treating third-party alpha release notes as hardware confirmation.
- **Battery, brightness, sleep, cameras, audio:** unverified.
- **NVMe:** early kernel initialization confirmed but the internal Samsung PM991 is a known macOS reliability risk; keep backups.

Report exact Surface model, BIOS, Tahoe build, which additional driver was enabled, and test outcome. Remove SMBIOS serial/MLB/SystemUUID/ROM before sharing logs.
