# Surface Laptop 4 Intel — RCS hook observability research (source only)

**Status: compiled, source patch reproducible; NOT installed, NOT a GPU hang fix.**

Reference host: Microsoft Surface Laptop 4 Intel i7-1185G7, Intel Iris Xe PCI
`8086:9A49`, macOS Tahoe 26.7.1, installed experimental WhateverXe 0.8.3
RCS v0.1.0 beta. A confirmed post-install RCS GPU Reset occurred on
2026-11-23 at **23:32:09 CET** despite `SL4RCSSinglePortReady=Yes`.
See [recorded GPU reset investigation](RCS-POSTPATCH-RESET-20261123.md)
and [Issue #5](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/issues/5).

## Source-only candidate

[Telemetry-only patch](../research/wex-sl4-rcs-hook-telemetry-v0.1.1.patch)
is a **layered patch to apply after** the original
[wex-sl4-rcs-singleport.patch](../research/wex-sl4-rcs-singleport.patch)
and the existing Surface graphics/eDP/DMC patches. It intentionally
does not include a new binary kext, signed system drivers, personalized
OpenCore EFI, or an automatic install path.

The patch changes only two source files:
`WhateverXe/kern_sl4_rcs_singleport.hpp` and `WhateverXe/kern_xe.cpp`.

- Records each entry to existing `wrapDequeue` and `wrapEvalWait` hooks
  while the RCS fix is active (atomic, unsigned 32-bit counters).
- Reuses the previously existing counters for preemption suppression,
  port-0 deferrals and port-1 rejections.
- Publishes a lazily serialized `SL4RCSHookTelemetryLive` property on
  the IORegistry root **only when the existing RCS install guard succeeds**.
- Adds no timer, GPU command, reset, persistent log, NVRAM write, EFI
  operation, disk modification or change to the branch paths of the
  scheduler fix.
- Does **not** patch an additional unknown Tiger Lake donor address or
  change RCS work ordering.

The property is a 28-byte, little-endian array of seven `uint32_t`:

| Index | Field | Meaning |
| --- | --- | --- |
| 0 | `revision` = 1 | Versioned schema |
| 1 | `dequeue_calls` | Hook invocations |
| 2 | `eval_wait_calls` | Hook invocations |
| 3 | `preempt_suppressed` | Existing preemption-suppression counter |
| 4 | `deferred_port0` | Existing branch deferrals |
| 5 | `rejected_port1` | Existing port-1 rejection attempts |
| 6 | `active` = 0/1 | Whether RCS patch is currently active |

These counters are boot-cumulative, may wrap at `2**32`, and are
**not a proof of video frames being rendered, a stable scheduler, or
absence of GPU Reset**. The patch only improves diagnosis.

## Validated on the physical Surface, without installation

- Separate source tree cloned from the original validated customized
  WhateverXe 0.8.3 build, with the same local Lilu and MacKernelSDK.
- Release build completed using Apple's Command Line Tools
  (`python3 tools/build.py --release`), compiling **both**
  `WhateverXe.kext` and `AppleIntelTGLCompat.kext` with the telemetry
  code. Compiler warning output came from the existing Lilu headers;
  the build completed.
- Experimental WhateverXe binary SHA-256:
  `1e6b44bd3a0f0b894079d328a4389155bca73bc7fc1eed691bf474716b7e296b`.
- Experimental compat provider binary SHA-256:
  `98906b845cda9c3b0c4eefbf3b0b9c38050102e369d7b23c3a33bb14b1773b4a`.
- Both SHA-256 digests matched the build manifest exactly.
- The 3,067-byte unified source patch was applied to a temporary copy
  of the original source with `git apply --check` + `git apply`.
  Both resulting files were **byte-for-byte identical** to the
  separately built experimental code. Original source files were
  preserved.
- Added parsing of the optional property to the user-space,
  read-only `audit_rcs_gpu_resets_macos.py`. The user-space decoder
  checks size, schema version and binary values before reporting counts.
- Existing installed v0.1.0 has no `SL4RCSHookTelemetryLive`;
  the script correctly reports **unavailable** rather than zero counts.
- The physical Surface remains running the installed WhateverXe 0.8.3,
  S0ixStandby 0.5.8 and Metal 2; **the experimental kext was not staged,
  injected or installed in the live EFI**.

## Next engineering gate

Before any runtime experiment, the candidate needs an independent,
verified recovery boot path, an EFI snapshot and a reversible install
procedure that leaves eDP, sleep, display brightness, audio and
Windows boot intact. It then needs real-world GUI/game testing and
post-reset comparisons. Merely compiling a telemetry kext does not
qualify it for release, and does not fix the observed freeze.

Until a changed RCS scheduling implementation is validated in the
kernel, Issue #5 remains **unresolved** and the existing v0.1.0 binary
remains the actual installed driver.

The telemetry patch is opt-in **research source only**, not part of
the default Windows-first installation, nor an automatic macOS repair.
