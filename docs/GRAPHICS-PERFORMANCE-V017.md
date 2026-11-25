# Surface graphics performance 0.1.7 beta — 2026-11-24

Physical reference: Surface Laptop 4 Intel i7-1185G7, Iris Xe 8086:9A49, Tahoe 26.7.1 (25G241), Graphics 0.4.4 donors. WhateverXe 0.8.3 upstream base f26a368; exact tested kext SHA-256 94669172f4c2a52937b587c5eb3fdb73ff030963397aa094e575d9c4b54863d3, UUID 1DAD98CE-CD44-3CA8-9BEE-CE65F3B47DBF.

- Unity compute hint: exact original adapter 11609123ce5b930aee500736f8bd504cd0280c37654f8e9f353fcc9fc876aff0, patched 50cc0fb84ffc8af995c35fe05e94e0543b8b8e7973edfd541710db93ff5e3b22. Accept only u32 maxTotalThreadsPerThreadgroup <=1024 at +0x9c; all other reserved state remains rejected. The hint is not forwarded to IGC. 14 real GPU tests passed (including actual full group sizes, barriers and output validation); Unity missing objects rendered. [Upstream report](https://github.com/b00t0x/WhateverXe/issues/31#issuecomment-7128573533).
- Heap depth: two exact instruction changes in donor SHA 6c8ab6cce50b9529679ee4fdf5b1c37d091677d945076f41cb4b7f8196c51449. The render/compute paths use the selected ResourceInfoEntry Hi-Z offset +0x1c instead of the parent embedded entry +0x19c. All original dirty/resolve/ordering checks retained. 96 compute +96 fragment tests, zero errors, three resolutions to 2496x1664 and four color formats; owner confirmed Spectator 1 artifacts disappear. [Upstream issue #204](https://github.com/b00t0x/WhateverXe/issues/204).
- RCS: native queue experiment retained from v0.1.5, render-local preemption suppression retained, no shared scheduler bit writes. Bounded load completed 2296/2296 commands, no pending commands/errors. Not a guarantee against future GPU resets. Earlier v0.1.0 reset remains documented.
- Real display link measured 59.98 Hz. GPU requests 1350 MHz, sampled 1100 MHz, power/current limits observed. No power-limit changes; FPS uplift not quantified.



## Default All-in-One profile status — 2026-11-25

The v0.1.7 RCS payload remains SHA-pinned and included for reproducibility, but the default Windows-first profile no longer adds -wex-sl4-rcs-singleport or -wex-sl4-rcs-nativequeue-trial. Those trial hooks were absent from the reference Surface's active boot arguments and are kept opt-in for deliberate testing. The tested heap-depth trial, DMC and eDP Keep/Softsleep profile remains enabled. The byte-pinned v0.1.7 binary still contains dormant RCS telemetry code; it is not activated in the default profile. The clean source patch is available, but no replacement binary is shipped until hardware regression. The optional RCS installer remains available for deliberate testing only after that validation.

## Source and tests
Full exact build delta: research/wex-sl4-graphics-v0.1.7-complete.patch (against upstream f26a368). Standalone depth delta against v0.1.5 baseline: research/wex-sl4-heap-depth-v0.1.7.patch. Compiler transformation: scripts/install_compute_hint_macos.py. Reproducers under research/graphics-v017-tests; numeric logs under docs/reports/graphics-v017. No personal EFI, game content, proprietary adapter binary or donor files published.

## Install / rollback
Use Windows-first QuickStart on graphics-fixes-v017 beta branch. Fresh install: standard donor installation, local signed compute-hint transformation, one graphics/EFI transition including the RCS payload, DMC/S0ix, eDP and audio. RCS single-port/native-queue trial flags are intentionally not enabled by default. Repair path preserves existing active kext and Windows loader, stages new kext alongside the prior one. Administrator approval and reboot required. Adapter patch refuses unknown donor bytes and retains original adapter in a root-only backup; run install_compute_hint_macos.py rollback with sudo to restore it. EFI recovery config and private OC backup are recorded by the installer; retain earlier bootable USB. Old v0.1.0 package remains historical recovery option.

No clean fresh install, long-term GPU stability, all sleep/wake combinations, or other hardware verified for this beta yet.
