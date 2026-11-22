# Pinned boot drivers and hardware status

These versions were present in the EFI used for the successful Recovery boot. **Being present in EFI does not prove every device works after installation.**

| Component | Pinned version | Purpose | Initial boot |
|---|---:|---|---|
| [OpenCore](https://github.com/acidanthera/OpenCorePkg/releases/tag/1.0.8) | 1.0.8 | Bootloader and OpenRuntime | Enabled |
| [Lilu](https://github.com/acidanthera/Lilu/releases/tag/1.7.2) | 1.7.2 | Kernel patching framework | Enabled |
| [VirtualSMC](https://github.com/acidanthera/VirtualSMC/releases/tag/1.3.8) | 1.3.8 | SMC emulation | Enabled |
| [WhateverXe](https://github.com/b00t0x/WhateverXe/releases/tag/0.8.3) | 0.8.3 | Experimental Tiger Lake Iris Xe support | Enabled; no acceleration |
| [AMFIAnchor](https://github.com/b00t0x/AMFIAnchor/releases/tag/0.1.2) | 0.1.2 | AMFI compatibility components | Enabled with injector |
| [USBToolBox](https://github.com/USBToolBox/kext/releases/tag/1.2.0) | 1.2.0 | USB mapping layer | Enabled |
| UTBMap | device-specific | Surface USB port map | Enabled |
| SL4-XHCI-A0ED | custom | Matching Intel A0ED controller on Darwin 25 | Enabled |
| SSDT-RTC0-SL4 | custom | Expose legacy RTC for macOS under `PC00.LPCB` | **Essential in this tested boot path** |

The builder in `scripts/build_efi.py` is designed to retrieve upstream boot binaries and include the tested, device-specific codeless components. **Do not enable all optional drivers simultaneously.**

## Post-install is a separate phase

- **Metal/graphics:** the first boot uses `-wex-noaccel`. Test any [WhateverXe Graphics](https://github.com/b00t0x/WhateverXe-Graphics) system package after macOS is installed, with a backup and a rollback plan. Hardware acceleration is not yet verified on this Surface.
- **Keyboard/trackpad/touch:** Surface Aggregator Module (SAM) input may need a compatible, model-specific driver. BigSurface support for Laptop 4 is not established here. Keep an external USB keyboard and mouse ready.
- **Wi‑Fi/Bluetooth:** Intel firmware drivers were present in previous experiments but disabled in the proven initial configuration; functionality is unverified.
- **Audio:** AppleALC was not enabled in the initial working config; the codec layout and audio outputs still need testing.
- **Sleep, brightness, battery and camera:** unverified. Do not claim full compatibility.

Please report verified behavior in issues, specifying the exact model/CPU, Tahoe build, EFI changes, and whether the test was performed in Recovery or in the installed OS. Strip all SMBIOS identifiers from logs.
