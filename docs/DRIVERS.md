# Surface Laptop 4 Intel — driver status

Tested on Surface Laptop 4 Intel (i7-1185G7, macOS Tahoe 26.7.1, OpenCore 1.0.8). A driver loading is not, by itself, proof of a working device. The statuses below reflect actual hardware checks.

## Validated

| Component | Driver / configuration | Result |
| --- | --- | --- |
| Graphics | WhateverXe 0.8.3 + Graphics 0.4.4; DVMT 60 MB | Intel Iris Xe Metal 2; internal HiDPI and external DisplayPort |
| Wi-Fi | AirportItlwm 2.4.0 | Intel AX201 wireless |
| Bluetooth | Intel Bluetooth stack | Working |
| Keyboard / trackpad | BigSurface 1.2.0, BigSurfaceHIDDriver 1.0.0, VoodooGPIO 1.2.0, VoodooSerial 1.2, VoodooInput 1.1.3 | Keyboard, taps, clicks and multitouch |
| Battery | BigSurface | Battery percentage |
| Audio output | Lilu 1.7.2, AppleALC 1.9.8, SimpleHDA 1.0.2; ALC274 layout 35 | **Built-in speakers working** |
| Audio input | Same audio stack | **Built-in microphone working** |
| Brightness | WhateverXe 0.8.3 + AppleBacklight + SSDT-PNLF UID 19 | **Built-in backlight controls working after reboot** |
| Temperature | SMCProcessor 1.3.8 | CPU die temperature |
| Cooling | Surface performance profile | Fan operation and profiles |

## Audio installation

The built-in audio controller is Intel `8086:A0C8`; the codec is Realtek **ALC274**. macOS Tahoe no longer includes AppleHDA. The working configuration restores it with [SimpleHDA 1.0.2](https://github.com/laobamac/SimpleHDA/releases/tag/v1.0.2), loaded after Lilu and AppleALC. Set `DeviceProperties → PciRoot(0x0)/Pci(0x1F,0x3) → layout-id` to Data `23000000` (35) and `Kernel → Quirks → DisableLinkeditJettison` to `true`.

The installation script performs these changes, verifies the official SimpleHDA archive checksum, preserves Microsoft EFI and creates an OpenCore backup:

```bash
sudo python3 scripts/install_audio_macos.py apply --esp disk0s1
```

Restart macOS. To restore the original config and remove the audio kext:

```bash
sudo python3 scripts/install_audio_macos.py rollback --esp disk0s1
```

The ESP identifier may differ; check `diskutil list`. Do not install competing AppleHDA restoration drivers or enable VoodooHDA simultaneously.

## Brightness installation

The tested panel has `AppleBacklightDisplay` and `AppleIntelPanelA` attached. The tested earlier `SSDT-PNLF.aml` exposes `_UID=14`, which does not activate the WhateverXe brightness curve; a fresh EFI may not include the PNLF table at all. Changing it to `_UID=19` enables native `brightness` and `linear-brightness` parameters.

Use [the brightness installer](../scripts/install_brightness_macos.py), which adds the verified 126-byte SSDT if absent from a freshly generated EFI, or patches an existing UID 14 table. It fixes the ACPI checksum, registers or enables the OpenCore entry, and creates complete EFI backups before writing:

```bash
sudo python3 scripts/install_brightness_macos.py apply --esp disk0s1
```

Restart macOS and verify **System Settings → Displays → Brightness**. Roll back if necessary:

```bash
sudo python3 scripts/install_brightness_macos.py rollback --esp disk0s1
```

Do not combine this tested WhateverXe/PNLF fix with unrelated panel patches or other hardware configurations.

## Other hardware

Reliable sleep/wake remains in progress. The headphone jack and additional hardware variants have not been validated.

See [installation and verified hardware](../README.md), [graphics](VALIDATED-METAL-SL4.md) and [keyboard/trackpad](INPUT-KEYBOARD-TRACKPAD.md).
