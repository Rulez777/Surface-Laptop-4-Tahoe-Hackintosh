> **Current release v0.4.0 beta:** RCS and Dolby Clear Speech are now integrated into the standard Windows-first QuickStart. [See one-step install and recovery](AUDIO-ALL-IN-ONE.md). Earlier separate RCS/S0ix procedures below remain for advanced troubleshooting only.

# Intel Iris Xe acceleration on macOS Tahoe: Surface Laptop 4 Intel

**Verified on 2026-11-22:** Core i7-1185G7, Iris Xe **96 EU** (`8086:9A49`, rev 01), macOS Tahoe **26.7.1**, OpenCore 1.0.8, WhateverXe 0.8.3, WhateverXe Graphics 0.4.4, AMFIAnchor 0.1.2, Lilu 1.7.2. **Metal 2 / 1536 MB dynamic VRAM / AppleIntelTGLGraphics loaded** were all observed, along with the built-in 2496×1664 eDP panel and external 2560×1440 Thunderbolt/DisplayPort monitor.

For the tested command-by-command procedure, evidence and safe rollback, see **[Validated Surface Laptop 4 Metal 2](VALIDATED-METAL-SL4.md)** and the new [root Quick Start](../README.md#quick-start-reproduce-the-validated-metal-2-state-existing-tahoe-no-removable-media).

## The essential discovery: GGC 0xFEC1 / 60 MB DVMT

With only `npci=0x2000 -allow3d -disablegfxfirmware -wex-noaccel` Tahoe booted but showed only **15 MB / no Metal**. The `DeviceProperties -> Add` dictionary was empty. Installing the official Graphics pkg and then *only* deleting `-wex-noaccel` caused the system to stall at the Apple boot screen.

`ioreg` reported **`WhateverXePhysicalGGC = 65217`**, which is hex **`0xFEC1`**: firmware-fixed **60 MB DVMT pre-allocation**. The [upstream WhateverXe DVMT instructions](https://github.com/b00t0x/WhateverXe#dvmt) prescribe:

| Setting | Exact required value on this machine |
| --- | --- |
| `DeviceProperties -> Add -> PciRoot(0x0)/Pci(0x2,0x0) -> framebuffer-patch-enable` | **Data** `01000000` |
| Same path, `framebuffer-stolenmem` | **Data** `0000C003` |
| `boot-args` | `npci=0x2000 -allow3d -disablegfxfirmware -igfxdvmt` (remove `-wex-noaccel` **only after** pkg installation) |

After applying these changes to the existing, known-bootable internal OpenCore EFI, macOS booted with **Metal 2, 1536 MB dynamic VRAM**, the accelerated TGL driver actually loaded, and an external monitor was detected. These are direct observations, not inferred compatibility.

These parameters are **for measured fixed-60-MB DVMT**, not a universal Tiger Lake profile. They do not increase physical firmware-allocated memory. The repo's `scripts/xe_acceleration.py` now requires the explicit `--dvmt-60` option during preparation and **refuses to enable** accelerated boot without those binary values and `-igfxdvmt`. `scripts/build_efi.py --dvmt-60` stages the profile but retains safe `-wex-noaccel` for first boot.

## Graphics installation and dependencies

The separate **WhateverXe Graphics 0.4.4** pkg is essential, installed **inside Tahoe** into `/Library` and the AuxKC, not into EFI. It was verified by SHA-256 before installation:

```text
f4c2d680a7c52c33a3f038ce6945da0aa2cc044e62b935a52ea046c7c473cfec
```

The installed test system used `sudo installer -pkg ... -target /` and reported `The install was successful`. `kmutil inspect` listed `AppleIntelTGLGraphics`, `AppleIntelTGLGraphicsFramebuffer` and `AppleIntelTGLCompat`. After the corrected accelerated boot, `kmutil showloaded` reported the actual loaded TGL accelerator.

Keep `-allow3d` and `-disablegfxfirmware`, preserve WhateverXe/Lilu/AMFIAnchor and injector order, and ensure the nondefault SIP data required for this package (`03080000` in this test). SIP is deliberately weakened; review the security implications. Never enable WhateverGreen alongside WhateverXe.

## CDCLK diagnostics are not the demonstrated blocker

The earlier framebuffer-only logs repeatedly reported `Unsupported CD clock decimal frequency 0x158`, `Wrong CD clock frequency 0x0 set by EFI`, and backlight/cursor-memory messages. **Those messages also appeared on successful no-acceleration boots.** They deserve investigation but should not be described as the proven root cause of the original boot stall. The decisive observed fix on this test machine was the **60 MB DVMT profile**. A custom CDCLK kext was **not** needed for the successful Metal result.

## Remaining limitations

Metal support does not prove peak performance or video encode/decode stability. User still observed some UI lag. External MSI MPG271QX OLED was detected at **2560×1440 59 Hz**, not verified at higher refresh. Wi-Fi (Intel AX201) is reported working. Built-in keyboard and trackpad do **not** work. Sleep/wake, brightness controls, docking stability, video acceleration and sustained GPU load remain unverified.

### Recovery

Preserve a **private** known-good no-acceleration `config.plist` and Windows boot entry. The test machine's accelerated config was also saved as `~/Downloads/SL4-WORKING-METAL.plist` (not distributed). If a subsequent change breaks the graphics boot, restore the earlier private config from Windows and reboot with `-wex-noaccel`; do not erase the ESP or edit `EFI/Microsoft`. If `diskutil mount disk0s1` fails in Tahoe, a read-only mount worked during diagnosis, but **never repair the Windows ESP blindly**.

**Upstream:** [WhateverXe DVMT](https://github.com/b00t0x/WhateverXe#dvmt) · [WhateverXe Graphics v0.4.4](https://github.com/b00t0x/WhateverXe-Graphics/releases/tag/v0.4.4) · [our Surface hardware report to the developer](https://github.com/b00t0x/WhateverXe/issues/101#issuecomment-7082305989).

## RCS Stability update (2026-11-23)

For Intel Surface Laptop 4 i7-1185G7 / Iris Xe 9A49 on **Tahoe 26.7.1**, see [RCS Stability 0.1.0 beta](QUICKSTART-RCS.md). The addon fixes a tested render-queue / preemption hang, and is installed **after** the graphics package and working Tahoe/DMC. Windows QuickStart 0.3.3 downloads and stages it for the Mac-side optional installer. It is not a fix for AV1/VP9 decoding; its preflight and private OpenCore rollback are mandatory. Do not install this kext on an unknown donor or the Windows installer USB.
