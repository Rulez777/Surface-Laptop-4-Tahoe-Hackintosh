# Intel Iris Xe acceleration on macOS Tahoe

**Test machine:** Surface Laptop 4, Core i7-1185G7, Intel Iris Xe 96 EU (`8086:9A49`), macOS Tahoe 26.7.1. The currently proven EFI uses `-wex-noaccel`, meaning **framebuffer-only graphics without hardware acceleration**. This is the likely reason for slow window animations and UI rendering; disabling OpenCore logging alone does not provide Metal acceleration.

## What the full driver pack adds

The [full driver pack builder](../scripts/prepare_full_driver_pack.py) downloads the pinned **WhateverXe Graphics 0.4.4** `.pkg` (95,215,914 bytes) and validates its release SHA-256:

```text
f4c2d680a7c52c33a3f038ce6945da0aa2cc044e62b935a52ea046c7c473cfec
```

Upstream release: [WhateverXe Graphics v0.4.4](https://github.com/b00t0x/WhateverXe-Graphics/releases/tag/v0.4.4). **This package is installed into macOS `/Library`, not into the EFI directory.** Simply placing kexts in `EFI/OC/Kexts` cannot enable Iris Xe Metal acceleration.

## Required conditions before the acceleration attempt

1. Tahoe must be **26.7 or newer**; the test installer was 26.7.1.
2. OpenCore must load `Lilu 1.7.2+`, `WhateverXe 0.8.3`, `AMFIAnchor 0.1.2`, and the matching `AMFIAnchorInjector` in the required order. Do not enable WhateverGreen simultaneously.
3. Confirm `csr-active-config` is **Data `03080000`**. Review SIP implications before changing it.
4. Preserve `-allow3d -disablegfxfirmware` boot flags.
5. Preserve the recovery-capable Kingston EFI with `-wex-noaccel`; back up the internal EFI and the macOS volume before modifying either.
6. Keep an external USB keyboard/mouse available. The internal Surface Aggregator Module input is not yet verified.

**Do not simply remove `-wex-noaccel` now.** Doing so before the Graphics package and dependencies are in place may cause a black screen or boot failure.

## Recommended order on this machine

1. First confirm that the **internal OpenCore firmware entry** boots the installed Tahoe **without Kingston** in framebuffer-only mode. This does not mean accepting the slow mode as final; it establishes rollback.
2. With installed Tahoe running, open and install the **official WhateverXe Graphics 0.4.4 pkg** downloaded by the full driver pack builder. Do not ignore an installer failure.
3. Ensure the AMFIAnchor provider/injector, SIP and kext ordering meet upstream requirements. Then prepare a backup EFI with the same working ACPI and storage drivers but **remove only** `-wex-noaccel` from that test configuration.
4. Reboot to try hardware acceleration. If the screen fails, boot the original Kingston configuration and roll back the internal `config.plist`.
5. Once working, verify with `system_profiler SPDisplaysDataType`, `ioreg`, a Metal app and real UI response. **A GPU name or 1536 MB in About This Mac alone is not proof of Metal rendering**.

This repo **does not** claim that 96-EU Tiger Lake `9A49` was hardware-validated on this exact Surface. WhateverXe's own documentation lists Tiger Lake-U 96-EU as expected, not tested across all hardware. Panel timing and Surface firmware may still need tuning.

## If acceleration fails

Keep the checked-good internal or USB backup. Restore `-wex-noaccel`, confirm the Graphics package version and matched Lilu/WEX/AMFIAnchor settings, and inspect macOS installer logs. Do not randomly add AGDP patches or remove RTC0. Upstream provides an [uninstall script](https://github.com/b00t0x/WhateverXe-Graphics/blob/main/uninstall.sh) if Graphics must be uninstalled.

**Upstream documentation:** [WhateverXe installation](https://github.com/b00t0x/WhateverXe#installation), [WhateverXe Graphics installation](https://github.com/b00t0x/WhateverXe-Graphics#install), [AMFIAnchor setup](https://github.com/b00t0x/AMFIAnchor#install-with-opencore).

*Status: complete preparation path documented; full accelerated graphics on this Surface remains unverified.*
