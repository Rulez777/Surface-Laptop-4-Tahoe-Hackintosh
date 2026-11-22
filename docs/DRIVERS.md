# Surface Laptop 4 Intel — tested and candidate drivers

**Last update: 2026-11-22.** Tahoe **26.7.1** boots on the test i7-1185G7 / Iris Xe 96 EU machine from **internal** OpenCore. **Metal 2 is confirmed** following the fixed-60-MB DVMT configuration and the WhateverXe Graphics 0.4.4 macOS package. **Intel AX201 Wi-Fi works.** Built-in keyboard and trackpad are **working on the tested SL4 Intel**, using five Tiger Lake BigSurface input kexts. The owner also confirmed improved touchpad clicks and gestures after the [post-install preference script](../scripts/configure_surface_trackpad.sh). See [validated configuration](VALIDATED-METAL-SL4.md).

A `kext` appearing in `kmutil showloaded` means it is loaded, **not** that a physical device works. Do not present this as a complete ready-to-use peripheral stack.

## Actual validated results

| Function | Observation on test machine |
| --- | --- |
| Installed Tahoe boot | **Yes**, Tahoe 26.7.1 on internal APFS |
| Internal OpenCore 1.0.8 | **Yes**, separate from original Windows Boot Manager |
| GPU hardware acceleration | **Yes**, Metal 2, 1536 MB dynamic VRAM, AppleIntelTGLGraphics 16.0.0 **loaded** |
| Built-in 2496×1664 LCD | **Yes**, HiDPI 1248×832 |
| External display over Type-C/DP | **Yes**, MSI MPG271QX OLED, 2560×1440 **59 Hz** |
| Intel AX201 Wi-Fi | **Yes** (user confirmed; AirportItlwm 2.4.0 loaded) |
| Surface Dock | USB2/USB3 hubs and GigE USB device/port enumerate; complete dock functions **not** confirmed |
| Surface keyboard and trackpad | **Yes, owner-confirmed** on one SL4 Intel with VoodooGPIO 1.2.0, VoodooSerial 1.2, BigSurface 1.2.0, BigSurfaceHIDDriver 1.0.0, VoodooInput 1.1.3; [setup](INPUT-KEYBOARD-TRACKPAD.md) |
| Sound, Bluetooth, battery display, touch and cameras | Kext/device detection in some cases, **function not confirmed** |
| Sleep/wake, brightness control, persistent SSD reliability, high-refresh external, full-speed performance | **Not tested to completion** |

## Owner-verified Surface keyboard and trackpad (2026-11-22)

The user reported **working physical keyboard and pointing device** after loading the following driver IDs:

```text
org.coolstar.VoodooGPIO                  1.2.0
com.xavier.VoodooSerial                 1.2
com.xavier.BigSurface                   1.2.0
com.xavier.BigSurfaceHIDDriver          1.0.0
me.kishorprins.VoodooInput              1.1.3
```

IORegistry contained `SurfaceSerialHubDriver`, `VoodooUARTController`, `VoodooGPIOTigerLakeLP`, `SurfaceHIDNub`, `SurfaceHIDDriver`, `AppleMultitouchTrackpadHIDEventDriver`. Hardware `MSHW0084` was exposed by the firmware; no extra SL5-style SSDT is needed. The owner later confirmed the preferences in `scripts/configure_surface_trackpad.sh` made the touchpad work to their satisfaction, including tap-to-click / Look Up behavior. These findings are **one device's observed result**, not a blanket compatibility guarantee.

See [installation, staged backups, rollback and optional trackpad tuning](INPUT-KEYBOARD-TRACKPAD.md). Keep an external USB keyboard/mouse for recovery; **do not enable both BigSurface and the generic VoodooI2C/SMCBatteryManager combination**.

## Known-boot / observed loaded graphics components

| Driver or component | Version | What was actually established |
| --- | --- | --- |
| [OpenCore](https://github.com/acidanthera/OpenCorePkg) | 1.0.8 | Booted from internal SSD |
| [Lilu](https://github.com/acidanthera/Lilu) | 1.7.2 | Loaded |
| [VirtualSMC](https://github.com/acidanthera/VirtualSMC) | 1.3.8 | Boot baseline |
| [WhateverXe](https://github.com/b00t0x/WhateverXe) | 0.8.3 | Loaded; hardware acceleration confirmed with DVMT 60 MB fix |
| [WhateverXe Graphics](https://github.com/b00t0x/WhateverXe-Graphics) | 0.4.4 | Official pkg successfully installed into Tahoe `/Library` |
| AppleIntelTGLCompat | 0.8.1 | Loaded |
| AppleIntelTGLGraphics + AppleIntelTGLGraphicsFramebuffer | 16.0.0 | Both loaded **after** Metal fix |
| [AMFIAnchor](https://github.com/b00t0x/AMFIAnchor) + injector | 0.1.2 | Loaded; `InstallStatus = 1`, anchor present |
| [USBToolBox](https://github.com/USBToolBox/kext) + UTBMap | 1.2.0 + custom map | Loaded / used; no comprehensive port matrix yet |
| Custom SL4-XHCI-A0ED injector | Device-specific | Existing boot baseline |
| `SSDT-RTC0-SL4.aml` | Device-specific | **Required**; ACPI path `\_SB.PC00.LPCB` |
| HfsPlus.efi + OpenRuntime.efi | OpenCore boot components | Boot baseline |

**Graphics configuration, critical:** GGC `0xFEC1` (60 MB DVMT), `DeviceProperties -> Add -> PciRoot(0x0)/Pci(0x2,0x0)` with Data `framebuffer-patch-enable=01000000` and `framebuffer-stolenmem=0000C003`; boot args `npci=0x2000 -allow3d -disablegfxfirmware -igfxdvmt`, **without** `-wex-noaccel`. Hardware Metal does **not** work by installing the pkg alone. See [DVMT case details](GRAPHICS-ACCELERATION.md).

## Additional candidate drivers / actual evidence

These versions are **pinned download candidates** in the repository, not a guaranteed mutually compatible stack.

| Driver | Pinned candidate source/version | Test-system observation or warning |
| --- | --- | --- |
| [AppleALC](https://github.com/acidanthera/AppleALC) | 1.9.8 | Loaded; internal speakers/microphone not yet functionally verified; codec layout may be needed |
| [Tahoe AirportItlwm](https://github.com/laobamac/itlwm/releases/tag/v2.4.0-alpha) | 2.4.0-alpha | **Wi-Fi confirmed working** using AirportItlwm 2.4.0 |
| [IntelBluetoothFirmware](https://github.com/OpenIntelWireless/IntelBluetoothFirmware) | Pinned downloader has 2.4.0 | **Actual loaded kext was 2.5.3** in the test log; candidate/pinned archive was not used to overwrite it; Bluetooth functionality unverified |
| [IntelBTPatcher](https://github.com/OpenIntelWireless/IntelBluetoothFirmware) | 2.4.0 | Not confirmed loaded or functionally working |
| [BlueToolFixup](https://github.com/acidanthera/BrcmPatchRAM) | 2.7.2 | Loaded; Bluetooth working state not yet verified |
| [SMCBatteryManager](https://github.com/acidanthera/VirtualSMC) | 1.3.8 | Loaded; battery readings/wake not verified; conflict risk with BigSurface |
| [VoodooPS2Controller](https://github.com/acidanthera/VoodooPS2) | 2.3.7 | File staged; Surface input is not necessarily PS/2 |
| [VoodooI2C + VoodooI2CHID](https://github.com/VoodooI2C/VoodooI2C) | 2.9.1 | VoodooI2CServices appeared loaded; built-in trackpad **still not working** |
| [BigSurface](https://github.com/Xiashangning/BigSurface) + [SL4 Tiger Lake port](../experiments/sl4-input/README.md) | Loaded as 1.2.0 with 4 supporting kexts | **Working on the owner’s SL4 Intel / Tahoe**. See [full input setup](INPUT-KEYBOARD-TRACKPAD.md). The legacy standalone 6.5 release is not the validated SL4 stack. |
| [NVMeFix](https://github.com/acidanthera/NVMeFix) | 1.1.3 | Avoid enabling for Samsung PM991 without stability testing |
| [RestrictEvents](https://github.com/acidanthera/RestrictEvents) | 1.1.6 | Optional; not needed to prove Metal |
| [IPTSDaemon](https://github.com/Xiashangning/IPTSDaemon) | 1.4 | ZIP downloaded as candidate, not a tested SL4/Tahoe daemon |
| BigSurfaceHIDDriver | 1.0.0 | **Loaded and physical trackpad/keyboard confirmed** as part of SL4-specific five-kext build. No universal prebuilt binary guaranteed. |

**Do not enable all kexts simultaneously.** In particular, BigSurface and VoodooI2C/SMCBatteryManager may be incompatible without changing the Surface ACPI map and input stack. `ocvalidate` tests plist consistency, not these runtime conflicts.

## Driver package and activation

The pinned archives and verified official Graphics pkg can be downloaded on Windows without any external media:

```powershell
py -3 scripts/prepare_full_driver_pack.py --source "S:\EFI" --out "$HOME\Downloads\SL4-FULL-DRIVERS" --cache "$HOME\Downloads\SL4-KEXT-CACHE"
```

The `scripts/stage_full_kext_pack.py` tool stages **missing** optional candidates **disabled** by default. For keyboard and trackpad use the separately validated [Tiger Lake BigSurface input instructions](INPUT-KEYBOARD-TRACKPAD.md); do not simply enable old BigSurface 6.5 in the generic candidate pack. It does not independently turn on Wi-Fi, keyboard or trackpad. For controlled audio/Wi-Fi/Bluetooth *copy profiles*, `scripts/add_optional_drivers.py` exposes `--enable audio,wifi,bluetooth`; these are still unqualified on other machines. The test-machine Wi-Fi result is from a runtime user observation, not from a blanket successful download.

For the proven graphics path see [root Quick Start](../README.md#quick-start-reproduce-the-validated-metal-2-state-existing-tahoe-no-removable-media) and [validated steps](VALIDATED-METAL-SL4.md). The updated `scripts/xe_acceleration.py --mode prepare --dvmt-60` stages the official iGPU Data properties and retains `-wex-noaccel`; `--mode enable` refuses to remove the safe flag until these values and `-igfxdvmt` exist.

## Priority for future validation

Test actual sustained Metal workloads and CPU power management; debug remaining lag without guessing from one `top` sample; validate dock Ethernet, USB ports and monitor modes; keyboard and trackpad have now been demonstrated on the test laptop; next validate the BigSurface build on additional SL4 Intel firmware revisions, then investigate audio, Bluetooth, battery, brightness and sleep. Keep the **working private Metal `config.plist`** and a separate private no-accel rollback backup. Do not publish SMBIOS identifiers or complete personalized EFI.
