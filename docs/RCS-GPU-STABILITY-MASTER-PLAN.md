# Surface Laptop 4 Intel — RCS GPU Stability Master Plan

**Date:** 2026-11-24 CET. **Authoritative tracker:** [Issue #5](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/issues/5).
**State:** actively investigated; **the GPU hang is not fixed or certified**.
Changes to this plan must be committed alongside related experiments.

## 0. Goal and non-negotiable constraints

**Goal:** eliminate recurring RCS GPU hangs / WindowServer freezes on
Microsoft Surface Laptop 4 Intel i7-1185G7, Iris Xe `8086:9A49`,
macOS Tahoe 26.7.1 (25G241), **without sacrificing** working
Metal 2, internal eDP, display brightness, DMC/soft-sleep, S0ix
wake, Dolby audio, input, video H.264/HEVC, and Windows 11 dual boot.

A compiled kext, an IORegistry readiness flag, successful synthetic
GPU stress, or a temporary absence of reports is *not* a proof of fix.
At least one real-world post-patch GPU Reset must be eliminated with
measured, reproduced before/after testing, no new regressions, and a
verified rollback.

Do **not** deploy an experimental kernel driver, rewrite EFI/NVRAM,
disable Metal, turn off sleep, reboot or stage an unverified replacement
into the boot path without all specified recovery gates and controlled
physical-host test approval. Work in isolated source trees.
Current user's system must remain bootable and responsive.

## 1. Baseline, evidence, reproducibility — COMPLETE (100%)

1.1 [DONE] Record the reference host and exact loaded
WhateverXe 0.8.3, AppleIntelTGLCompat 0.8.1,
AppleIntelTGLGraphics 16.0.0, S0ixStandby 0.5.8.
Metal 2 works; thermal/swap/power indicators normal.

1.2 [DONE] Identify GPU Resets at **Nov 23 17:13:45**, 17:13:59
(pre-RCS beta), and **23:32:09** (post-RCS-beta);
later RCS instance `WindowServer`, context 6,
`IPEHR=0x7a000204`, `WAIT_ON_SEMAPHORE | WAIT_ON_SCANLINE`.

1.3 [DONE] Decode `TGLGpuRecLive` revision 2:
1 qualified reset, 1 sibling state restore, 1 sibling scheduler replay,
0 sibling resubmissions, 0 list-invalid. Recovery is not prevention.

1.4 [DONE] Merge the read-only public diagnostic in PR #6,
commit `a0582a9`. Current commands:
`python3 scripts/audit_rcs_gpu_resets_macos.py --since-hours 8 --json`
and `zsh scripts/QuickStart-Mac.command --rcs-audit`.

1.5 [DONE] Verify the actual AppleIntelTGLGraphics donor binary
SHA-256 `6c8ab6cce50b9529679ee4fdf5b1c37d091677d945076f41cb4b7f8196c51449`.
Check live `SL4RCSSinglePortReady=Yes` but do not interpret as stability.

## 2. Native RCS control-flow root cause — IN PROGRESS (~45%)

2.1 [DONE] Disassemble actual `dequeueExecList` at
`0x3b3b6`, `evalWaitQueue` at `0x3b4ee`, scheduler
`updateOptions` at `0x385e0`, and render preemption hook
targets at `0x3d9a6`/`0x3d9d2`.
Use `llvm-objdump` against the **verified exact donor**.

2.2 [DONE] Identify RCS v0.1.0's early return before native
`dequeueExecList` when either active bank Execlist element
is non-null **or** streamer `cs[0x1c3c]` is clear.
Original `dequeueExecList` handles throttling, evaluates work queues
and can prepare/submits Execlists. Premature exit can postpone
these operations. This is a **starvation hypothesis, not verified
causality**, because the driver may be called again after progress.

2.3 [DONE] Map `cs[0x1c3c]` in the donor:
constructor, software context switch interrupt, native
submit ExecList, GPU reset, scheduler dispatch, preemption and CSB
idle/active events all use this byte. Separately record
occupied-port versus not-ready deferral, rather than one blended count.

2.4 [IN PROGRESS] Correlate ring-buffer entry `0x7a000204` and associated
PIPE_CONTROL flags with the queue state and context ID.
Distinguish shader/command deadlock from wake/GPU-reset aftermath.

2.5 [BLOCKED ON CONTROLLED BOOT] Obtain **measured** per-hook deferral percentages from
a safely boot-tested experimental kernel. Determine whether
`deferred_occupied_port` or `deferred_not_ready` grows during
observed lag, and compare with recovery counts and native calls.

2.6 [IN PROGRESS] Rule out source-compatible causes in other GPU hooks,
RCS TLB preparser, no-POSH, power transitions, DMC wake,
CCS sibling reset and WindowServer context teardown.

2.6a [SOURCE RISK IDENTIFIED] Generic IGScheduler5::updateOptions hook
currently clears flag 0x04 for every kernel scheduler pointer without an
RCS engine identity check. The v0.1.3 source-only scoped candidate and
its unresolved lifetime/first-callback hazards are documented in
[RCS scheduler scope research](RCS-SCHEDULER-SCOPE-RESEARCH-20261124.md).
The host Mac was offline during this experiment, so no new hardware
measurements or driver build were made.

2.7 [TODO] Produce a precise method-level cause and a minimum
patch with rollback; no arbitrary suppression of RCS scheduling
or unmeasured timeouts.

## 3. Instrumentation and candidate driver — IN PROGRESS (~60% for
instrumentation, **0% for verified hang fix**)

3.1 [DONE] Source-only [draft PR #7](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/pull/7),
v0.1.1 revision-1 `SL4RCSHookTelemetryLive` counters:
dequeue calls, evalWait calls, suppression and deferrals.

3.2 [DONE] Successfully compile release WhateverXe + Compat
from an isolated copy of the exact customized Surface source.
Manifest SHA and applied source patch byte equivalence validated.
**No experimental binary is distributed or installed.**

3.3 [DONE] Prepare optional layered v0.1.2 instrumentation patch:
schema revision 2 splits occupied-port versus not-ready deferrals
and counts native fallback calls. No scheduler control-flow
conditions are modified.

3.4 [DONE] Rebuild v0.1.2 and verify patch chain
v0.1.0 -> v0.1.1 -> v0.1.2, test strict decoder for both
revision 1 and 2, and validate release manifests.

3.4a [SOURCE ONLY, NOT BUILT ON MAC] Proposed a v0.1.3
generic-scheduler scope correction. It only clears bit 0x04 when
the scheduler pointer matches a previously classified RCS scheduler.
Layered source patch and branch-state tests pass on Windows,
but pointer reuse/lifetime, RCS first-callback ordering, actual
compile and kernel runtime are unverified. See
[RCS scheduler scope research](RCS-SCHEDULER-SCOPE-RESEARCH-20261124.md).
**Do not install or merge as a validated graphics fix.**

3.5 [TODO] After an A/B-safe test environment exists, collect
real callback counters during the affected desktop and game work,
without inducing known dangerous GPU hangs.

3.6 [TODO] Only after 2.4–2.7 and 3.5, create a separate
versioned *behavior* candidate, derive expected correctness
from the verified donor, simulate branch conditions, rebuild and
verify dependency/ABI before a controlled boot.

## 4. Independently recoverable boot and safety — IN PROGRESS (~45%)

4.1 [DONE] Audit original pre-RCS full EFI ZIP
`~/Documents/SL4-EFI-FULL-BEFORE-RCS-20261123.zip`
in place, **read-only**. It contains 1,046 archive entries, valid
OpenCore and Windows boot manager, 28 enabled kexts, five ACPI
files and two UEFI drivers with all references resolved; ZIP CRCs pass.
Archive has *no active RCS beta* and predates installed graphics change.

4.2 [DONE] Create strict read-only
`scripts/audit_rcs_recovery_backup.py`: ZIP path traversal, CRC,
FAT duplicate names, symlink and ZIP bomb protection,
enabled OpenCore path resolution, no private identifiers emitted.
It explicitly emits `bootability_verified=false`,
`safe_to_install_experimental_kernel=false`.

4.3 [BLOCKED] Obtain a **fresh backup of the present EFI** and verify
OpenCore `config.plist`, loaded current kext, bootloader and EFI
manifest match actual installed state. Do not mount or write EFI merely
to claim this completed.

4.4 [BLOCKED] Verify an independent boot path that remains functional if
the experimental kext crashes before macOS login. Validate the
Windows recovery route and **physical boot selection**.

4.5 [TODO] Create and independently test a versioned candidate
installer with rollback-by-default and an explicit fail-closed
donor/digest/hardware guard. Never overwrite or replace working
`WhateverXe` without these prerequisites.

4.6 [BLOCKED] Controlled reboot and physical test of experimental
kernel must remain **not started** until 4.3–4.5 are verified.
A ZIP's complete contents do not prove bootability.

## 5. Real-device behavior and regression — NOT STARTED (0%)

5.1 [TODO] Snapshot baseline performance/latency,
RCS hang count, `WindowServer` health, screen brightness,
sleep/wake and media codecs *before* behavior changes.

5.2 [TODO] Controlled experimental kernel boot with user-approved
recovery ready. Confirm current GUI, Metal 2, display, keyboard
and network function and read new telemetry revision 2.

5.3 [TODO] Use the actual ordinary desktop workload and user-selected
game that experienced stalls; record delta counters and any RCS report.

5.4 [TODO] Repeat after targeted fix, including sleep/wake and
full-display recovery. Do not infer stability from a brief session.

5.5 [TODO] Test rollback using independent recovery, then verify
original EFI hashes, Windows unchanged and macOS returns to baseline.

## 6. Universal Windows-first installer, CI, release — IN PROGRESS
(**diagnostic integration ~60%; fixed RCS release 0%**)

6.1 [DONE] Merge read-only audit (PR #6) into main, stop describing
v0.1.0 as fully fixed.

6.2 [DONE] Include read-only diagnostics and report in Windows-first
QuickStart, offline toolkit and candidate driver pack.

6.3 [DONE for read-only tooling] Bundle recovery backup checker and user-visible
menu entry, CI tests, and reference evidence; keep kernel experiment
**source only** in PR #7.

6.4 [TODO] After physical validation from steps 2–5, integrate
*verified* new kext with exact binary SHA and reproducible source
patch into new all-in-one release. Do not silently upgrade users.

6.5 [TODO] Prove Windows first install + existing Tahoe repair
+ rollback on the supported hardware; publish validated limits.

## Execution notes / next safe actions

**Now**: continue source-only cross-engine scheduler audit,
review v0.1.3 pointer-lifetime safety, and run reproducible CI.
When the Mac comes online, compile only in an isolated source tree and
compare loaded baseline diagnostics; do not deploy experimental kexts.
Prior priority: finish source-only diagnostics/backup validation, build and
qualify v0.1.2 instrumented source, read exact donor control-flow,
automate tests and CI, update PR #7. Do not deploy a guessed fix.

**Physical-test barrier**: 4.3, 4.4 and 4.5 must be proven before 5.2.
If a stable independent recovery is unavailable, this plan remains
blocked at the controlled boot step; continue all source-only work.

**Progress accounting:** percentages indicate research/preparation
within individual workstreams, *not* probability that the graphics
bug is fixed. **Overall confirmed hang elimination: 0%.**
