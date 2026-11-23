# RCS Stability v0.1.0 beta — Surface Laptop 4 Intel

**Experimental graphics mitigation; recurrence confirmed after release** for macOS Tahoe 26.7.1 on Surface Laptop 4 Intel i7-1185G7 (Iris Xe `8086:9A49`).

## Why
Before the fix, rendering hardware RCS repeatedly hung and macOS reset the graphics engine. Two Spectator 3 resets were captured at 17:13:45 and 17:13:59 CET on 2026-11-23. The second involved `IPEHR=0x7a000204` and an Execlist semaphore/scanline wait.

## Change
- Opt-in `-wex-sl4-rcs-singleport` single-port RCS scheduling plus RCS preemption mitigation on the **exact** Tahoe AppleIntelTGLGraphics binary; five symbols and two unique machine-code signatures must match.
- Preserve the other working WhateverXe 0.8.3 changes: DMC, eDP, GPU recovery, stampfix, no-POSH and Metal.
- Reversible installer with preflight, SHA-256 manifest, full OpenCore backup, separate kext and offline rollback support. Windows partition and private EFI are **not** part of the distribution.

## New confirmed regression (2026-11-23 23:32 CET)

**RCS v0.1.0-beta is not a complete fix.** On the reference Surface with `SL4RCSSinglePortReady = Yes` and recovery/stampfix hooks loaded, macOS emitted another `GPU Reset` report at **23:32:09**. Affected application label was `WindowServer`; RCS was busy in a batch buffer, `IPEHR=0x7a000204`, and `LastContextSwitchReason=ELEMENT_SWITCH | WAIT_ON_SEMAPHORE | WAIT_ON_SCANLINE`. The previous two GPU resets were at 17:13 before the beta patch was confirmed active. Source and cause of the post-patch stall remain under investigation; no new kernel driver was deployed. See [RCS post-patch investigation](RCS-POSTPATCH-RESET-20261123.md).

## Observed results
- macOS successfully boots with `SL4RCSSinglePortReady = Yes`.
- Synthetic 400,000 Metal command buffers / three queues with no resets. No new GPU resets during the initial 18:36 CET observation **only**; a later `WindowServer` reset at 23:32 CET invalidates any implication of ongoing stability.
- User reported 14→30 FPS after five minutes; this is **not** claimed as a measured effect of the patch. Shader/pipeline cache warming or GPU clock state could also explain the time-dependent increase.

**Limitations:** Validated on only one Surface with one Tahoe build. Long-term game/wake stability not yet proven. Does not add hardware VP9/AV1 support to VideoToolbox/Safari. Requires *already working* macOS, not a Windows installer for blank storage.

Full safe installation and Windows recovery instructions: [docs/QUICKSTART-RCS.md](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/blob/main/docs/QUICKSTART-RCS.md).
