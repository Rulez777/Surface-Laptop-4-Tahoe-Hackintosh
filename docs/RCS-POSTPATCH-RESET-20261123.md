# Surface Laptop 4: RCS GPU Reset AFTER the 0.1.0 beta mitigation

**Status 2026-11-23: confirmed recurring GPU hang; NOT RESOLVED.**
Observed on the actual Microsoft Surface Laptop 4 i7-1185G7, Intel Iris
Xe PCI ID 8086:9A49, macOS Tahoe **26.7.1** (25G241).

See [Issue #5](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/issues/5).
This is an engineering handoff, not a claim of a working new graphics driver.

## What was measured directly

Three GPU Reset reports within eight hours, all with
Intel GPU Hang Summary signature **813**:

| Local time CET | Report application field | RCS context | IPEHR | Switch reason |
| --- | --- | ---: | --- | --- |
| 17:13:45 | Spectator 3 | 355 | 0x7b000008 | ELEMENT_SWITCH / ACTIVE_TO_IDLE |
| 17:13:59 | Spectator 3 | 355 | 0x7a000204 | WAIT_ON_SEMAPHORE / WAIT_ON_SCANLINE |
| **23:32:09** | **WindowServer** | **6** | **0x7a000204** | **WAIT_ON_SEMAPHORE / WAIT_ON_SCANLINE** |

The 17:13 game resets occurred *before* the v0.1.0 beta was shown
working. The **23:32** WindowServer reset occurred *after* the patch
was installed and reported ready.

The post-patch report explicitly says RCS is **busy in a batch buffer,
appears hung**; all other rings (CCS, BCS, VCS0/VCS2, VECS0) are
marked disabled/idle. RCS register dump:

- RING_HEAD 0x24e01978; RING_TAIL 0x00001a10.
- BB_ADDR 0x4302d81d.
- IPEHR 0x7a000204 (PIPE_CONTROL family).
- LastContextSwitchReason(0x184) = ELEMENT_SWITCH / WAIT_ON_SEMAPHORE / WAIT_ON_SCANLINE.
- GFXREG_COMMANDDBG_FAULT_REG = 0; EIR/ESR = 0.
- Page Table Appears to be okay in the reported dump.

Neither the report's Application: WindowServer field nor the IPEHR alone
proves that WindowServer originally submitted the broken GPU command,
or that PIPE_CONTROL is the root cause. No causal assignment to Steam,
ChatGPT, IINA or specific AV1/VP9 streams is justified.

## Current live boot: RCS recovery versus prevention

The actual loaded components were WhateverXe **0.8.3** (custom Surface
build), AppleIntelTGLCompat **0.8.1**, AppleIntelTGLGraphics **16.0.0**,
S0ixStandby **0.5.8**, with Metal 2 still available.

The kernel exposed SL4RCSSinglePortReady=Yes, TGLGpuRecReady=Yes,
TGLStampFixReady=Yes and SL4DMCLocalInitVerified=Yes. The effective
boot flags include -wex-sl4-rcs-singleport, -wex-tgl-no-posh,
-wex-tgl-gpurec, and -wex-tgl-stampfix.

Decoded little-endian IORegistry TGLGpuRecLive revision **2**:
flags=3 (register recovery plus orphan stamp), one qualified reset,
one sibling register restore, one sibling scheduler replay, one extra
register fix, no list-invalid or sibling-not-ready events.
**No sibling resubmission** was recorded. These are boot-cumulative
counters, not proof that normal desktop rendering resumed.
stamp_declined=45 counts rejected orphan-stamp completions, not extra
GPU resets.

TGLRCSTLBPreparserLive has **marker 133** and matching entry/return
counts. Its first field is a hard-coded marker, not a semantic version.

Hardware otherwise looked normal: low CPU utilisation,
**0 MB swap**, approximately 76 GiB free, CPU speed/scheduler
limits 100%, and no thermal or performance warnings.

## Why the existing patch is not yet sufficient

The source in [wex-sl4-rcs-singleport.patch](../research/wex-sl4-rcs-singleport.patch)
hooks five scheduler/preemption methods and installs two inline donor
byte changes. The gate requires the exact donor, symbol addresses and
-wex-sl4-rcs-singleport boot argument. The opt-in was active in the
failed configuration. Re-running the installer is not a fix.

The existing source does not expose continuously readable counters for
suppressedPreempt, deferredPort0 or rejectedPort1. The Ready=Yes
marker confirms that the hooks were installed, not how often they
were invoked nor correct behavior across every engine context.

Possible causes requiring evidence (NONE established yet):

1. Native RCS/PIPE_CONTROL ordering or semaphore hazard remaining
   despite the single-port workaround.
2. Residual multi-context path or an unintended defer/skip in the
   wrapDequeue and wrapEvalWait methods.
3. Post-reset incomplete GPU/display state or a lingering client stamp.
4. Interactions with independent DMC/eDP/no-POSH/recovery hooks.

Upstream reports on similar hardware:
- [WhateverXe #126](https://github.com/b00t0x/WhateverXe/issues/126):
  Tiger Lake 9A49 WindowServer hangs with IPEHR 0x7a000204.
- [WhateverXe #172](https://github.com/b00t0x/WhateverXe/issues/172):
  recurring Tiger Lake WindowServer RCS hangs on 0.8.3.
- [WhateverXe #109](https://github.com/b00t0x/WhateverXe/issues/109):
  opt-in recovery/stampfix improves aftermath, not necessarily prevention.
- WhateverXe 0.8.4 released on 2026-11-23; release notes do not
  document a direct fix for this deadlock. Updating would also drop
  Surface-specific custom patches unless ported and tested first.

## Safe, repeatable audit

New [audit_rcs_gpu_resets_macos.py](../scripts/audit_rcs_gpu_resets_macos.py)
reads bounded .gpuRestart reports and only approved kernel readiness
flags, revisioned recovery counters and known effective boot-arg flags.
It does not publish raw IORegistry, SMBIOS, EFI, NVRAM or serial values.

Run in an installed macOS project checkout (single shell line):

    python3 scripts/audit_rcs_gpu_resets_macos.py --since-hours 8 --json

Windows-first macOS QuickStart:

    zsh QuickStart-Mac.command --rcs-audit

Mac advanced menu option **7** is also read-only. The helper is
packaged in the Windows-first toolkit, offline toolkit and full
candidate driver pack. It requires no administrator access.

The sanitized reference result is in
[sl4-rcs-reset-audit-20261123.json](reports/sl4-rcs-reset-audit-20261123.json).

## Experimental hook-use telemetry (not installed)

A separate [source-only instrumentation proposal](RCS-HOOK-TELEMETRY-EXPERIMENT.md)
adds read-only counters to the existing RCS scheduler hooks and a versioned
IORegistry property. The source-only experimental kext compiles in isolation,
but is **not** installed on the reference Surface and does not solve the
RCS hang. The read-only GPU reset audit will report the optional counters
only when a future separately verified RCS kernel build publishes them;
current RCS v0.1.0 reports them as unavailable.

## Acceptance criteria for a real driver fix

1. Preserve Metal 2, display brightness, DMC/eDP, working manual and
   lid-triggered sleep/wake, audio, input, and Windows dual boot.
2. Require exact donor digest, symbol and byte-pattern preflight
   before a *separately versioned* experimental RCS build may be staged.
3. Keep every experimental mode opt-in with independently usable
   Windows and OpenCore recovery/rollback.
4. Add explicit hook-use telemetry for the RCS scheduler, independent
   from the existing GPU recovery counters.
5. Validate real desktop/browser/game and longer idle sessions,
   not only synthetic Metal commands or Ready=Yes.
6. Require **zero new** relevant GPU Reset reports under actual workloads;
   recovery counts alone are not sufficient.
7. Update the recommended all-in-one RCS package only after the
   physical Mac boot, runtime and rollback validation.

**No EFI, NVRAM, power policy, VideoToolbox or graphics-driver change
was made while producing this audit.**
