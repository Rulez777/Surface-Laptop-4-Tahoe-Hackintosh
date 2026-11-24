# Intel Tiger Lake RCS — generic-scheduler scope risk (2026-11-24)

**Status: source-only research candidate, not a verified GPU hang fix.**

Hardware: Microsoft Surface Laptop 4 i7-1185G7 / Iris Xe 8086:9A49.
Software: macOS Tahoe 26.7.1; customized WhateverXe 0.8.3.
Regression: [GitHub Issue #5](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/issues/5).
Project plan: [RCS GPU Stability Master Plan](RCS-GPU-STABILITY-MASTER-PLAN.md).

## Confirmed static source finding

The existing v0.1.0 RCS patch routes the generic
IGScheduler5::updateOptions() base-class symbol at donor offset
0x385e0. Its callback calls the native function, checks only that
the scheduler "this" pointer has a canonical kernel address, then
clears the scheduler byte bit 0x04 at offset +0x0c.

In contrast, IGHardwareRenderCommandStreamer5::allowPreemption()
is an explicitly render-engine-specific symbol. The current
base-class updateOptions hook does NOT check engine identity.
If the hooked method runs on a non-RCS scheduler, the workaround
can change scheduling options for other engines. Static analysis
supports this cross-engine risk, but actual non-RCS invocations
on the physical Surface are NOT yet measured.

The exact validated AppleIntelTGLGraphics 16.0.0 donor has SHA-256:
6c8ab6cce50b9529679ee4fdf5b1c37d091677d945076f41cb4b7f8196c51449.

This is not proof that cross-engine changes caused the November 23,
23:32 CET RCS GPU Reset. The RCS PIPE_CONTROL / WAIT_ON_SEMAPHORE
failure remains unresolved.

## v0.1.3 experimental, source-only candidate

[Layered RCS scheduler-scope patch](../research/wex-sl4-rcs-scheduler-scope-v0.1.3.patch)

Apply source patches in this order:

1. wex-sl4-rcs-singleport.patch — current v0.1.0 mitigation.
2. wex-sl4-rcs-hook-telemetry-v0.1.1.patch — initial hook counters.
3. wex-sl4-rcs-queue-reasons-v0.1.2.patch — deferral reason counters.
4. wex-sl4-rcs-scheduler-scope-v0.1.3.patch — scoped scheduler updates.

This candidate always calls the original IGScheduler5::updateOptions
method. It clears bit 0x04 afterwards only if the scheduler
address matches an RCS scheduler previously observed from one
of two render-specific callbacks. Unknown or unmatched scheduler
objects retain native scheduling behavior. No changes to
RCS dequeue/evalWait branch conditions, GPU commands or rings.

Optional SL4RCSHookTelemetryLive revision 3 is **15 little-endian
uint32 fields (60 bytes)**. The first 12 preserve the revision-2
layout. New fields are update_options_calls,
rcs_scheduler_updates_scoped and
updates_left_to_native_for_other_or_unknown. Kernel pointers are
NEVER published through IORegistry.

User-space decoder strictly accepts revision 1 (28 bytes), revision 2
(48 bytes) or revision 3 (60 bytes). Unknown layouts fail closed.

## Remaining kernel-safety questions

- Are render and media scheduler objects guaranteed distinct?
- Could the cached RCS scheduler pointer become stale across
  a GPU Reset, S0ix sleep/wake, teardown or pointer reuse?
- Does updateOptions run before the first render callback captures
  the target? Initially this candidate leaves RCS options native.
- Could this initial behavior allow preemption during a vulnerable
  window before the first RCS-specific suppression?
- Do any other methods write the same +0x0c byte?

Because these are unresolved, **DO NOT install this candidate**
or include a compiled binary in the default Windows-first toolkit.
Even successful compilation will not establish runtime safety.

## Verification with macOS offline

On an authorized Windows development PC, reconstructed the
v0.1.0–v0.1.2 source from actual GitHub patches. Generated and
successfully applied the v0.1.3 unified diff to a clean v0.1.2
copy, matching the candidate bytes.

Test coverage in tests/test_rcs_scheduler_scope_candidate.py checks:
the known original generic mutation, new matching-pointer scope,
original function call order, RCS-specific pointer acquisition,
absence of raw kernel pointers in 60-byte telemetry,
unchanged native dequeue/evalWait body and conservative state
models. These are source and model tests, not hardware tests.

No EFI, driver, NVRAM, display, sleep or Windows boot changes were made.

## Gate before real hardware validation

Obtain and verify a fresh backup of the installed EFI and independently
boot-test a recovery path. Then rebuild this candidate with the exact
MacKernelSDK/Lilu toolchain, validate source and binary SHA-256,
test live RCS scope telemetry, GUI/game, Metal 2, eDP brightness,
audio, sleep/wake and Windows. Only then assess a causal correction.

**Verified RCS GPU hang elimination: 0%.**
