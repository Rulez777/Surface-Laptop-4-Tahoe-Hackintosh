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

## Other hardware

Display brightness control and reliable sleep/wake are not yet confirmed. Direct fan RPM control is unavailable through the documented Surface interface. Headphone jack and additional hardware variants have not been validated.

See [installation and verified hardware](../README.md), [graphics](VALIDATED-METAL-SL4.md) and [keyboard/trackpad](INPUT-KEYBOARD-TRACKPAD.md).
