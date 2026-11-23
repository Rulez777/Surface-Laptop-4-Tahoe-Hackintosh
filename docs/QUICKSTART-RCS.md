# Surface Laptop 4 Intel — WhateverXe RCS Stability 0.1.0 beta

**Post-install add-on only.** Windows-first installation remains available through the project's Windows QuickStart. Do not try to install this kext in Windows or before Tahoe and the tested graphics drivers are running.

## Hardware and software qualified
- Surface Laptop 4 Intel 13.5-inch, i7-1185G7, Iris Xe `8086:9A49`.
- macOS Tahoe **26.7.1**, exact WhateverXe Graphics donor `AppleIntelTGLGraphics` SHA-256 `6c8ab6cce50b9529679ee4fdf5b1c37d091677d945076f41cb4b7f8196c51449`.
- Working WhateverXe 0.8.3 with Metal 2, DMC trial, `-wex-tgl-gpurec`, `-wex-tgl-stampfix` and `-allow3d`.
- Original Windows Boot Manager and a recovery boot path must remain available.

This release addresses the **RCS Execlist context-switch/preemption hang**, not the unrelated VP9/AV1 VideoToolbox decoding or all possible graphics bugs.

## Download from GitHub Releases
[SL4 RCS Stability 0.1.0 beta](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/releases/tag/sl4-rcs-v0.1.0-beta)

Download and extract `SL4-RCS-Stability-0.1.0-beta.zip` into your Mac's `~/Downloads`. The archive includes a source patch, compiled version-checked kext, OpenCore 1.0.8 validator, manifest and standalone rollback-capable installer.

Verify your internal EFI partition with `diskutil list` (on tested Surface it is `disk0s1`). **Do not assume that identifier on another computer.**

Read-only check:

`sudo python3 "$HOME/Downloads/SL4-RCS-Stability-0.1.0-beta/install.py" check --esp disk0s1`

If it reports `READY_FOR_RCS_INSTALL`, install:

`sudo python3 "$HOME/Downloads/SL4-RCS-Stability-0.1.0-beta/install.py" apply --esp disk0s1`

Restart macOS. Confirm that the patch was loaded:

`ioreg -p IOService -l -w0 | grep SL4RCSSinglePortReady`

Expected: `"SL4RCSSinglePortReady" = Yes`. Check that Metal acceleration still works:

`system_profiler SPDisplaysDataType`

The installer creates a complete backup of the existing **OC directory** under `~/Documents/SL4-RCS-BACKUPS`, writes an independent backup of the original OpenCore config on the EFI partition, and copies the new kext under a **different filename**. It does **not** delete the previous WhateverXe, edit Windows EFI, alter NVRAM directly, or change sleep policy.

### Rollback
If macOS still boots and your EFI configuration has not since been edited:

`sudo python3 "$HOME/Downloads/SL4-RCS-Stability-0.1.0-beta/install.py" rollback --esp disk0s1`

Restart. If macOS does not boot, use Windows or Recovery to restore `EFI/OC/config.plist` from the latest `EFI/OC/config-SL4-RCS-before-*.plist` file. Preserve `EFI/Microsoft` and do not format the EFI partition.

## Verification on reference Surface (2026-11-23)
- Before fix: repeated GPU Restart reports, including two in **Spectator 3** at 17:13:45 and 17:13:59 CET. RCS hardware context 355; last IPEHR `0x7a000204` (PIPE_CONTROL) and `WAIT_ON_SEMAPHORE | WAIT_ON_SCANLINE`.
- After fix: `SL4RCSSinglePortReady = Yes`, **400,000 Metal command buffers** over 3 command queues, 200,000 compute/3D iterations in 57.7 seconds without GPU Reset.
- After owner played Spectator 3: as of 18:36 CET, no new GPU restart logs, graphics fix still active, no thermal/CPU throttling.
- Owner reports game improved from around **14 FPS to 30 FPS after approximately five minutes**, with the improvement persisting after scene changes. This is **a user report, not benchmark proof of cause**. Shader compilation/caches and GPU power management are plausible, not confirmed.
- Long-term gaming stability across hardware, other macOS versions, reboot, battery and sleep remains unverified. A passed synthetic stress test does not guarantee zero future hangs.

## Build source and attribution
Patch: [research/wex-sl4-rcs-singleport.patch](../research/wex-sl4-rcs-singleport.patch), applied **after** [wex-sl4-edp-base.patch](../research/wex-sl4-edp-base.patch) and [wex-tgl-dmc-supervised.patch](../research/wex-tgl-dmc-supervised.patch) to upstream WhateverXe commit `f26a36880c49ea1063393d943527808c0f38feca`.

The single-port Execlist and RCS preemption research was informed by the [HP Elite Dragonfly G2 Tiger Lake investigation](https://github.com/yankedi/HP-Elite-Dragonfly-G2-Hackintosh). This project adds exact donor/PCI/boot-argument guards and fail-closed behavior. See source files for detailed provenance. Do not assume this patch is safe on other graphics donors.
