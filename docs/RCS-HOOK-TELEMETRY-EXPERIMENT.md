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

## Independent recovery evidence (without touching the live EFI)

The pre-RCS full EFI archive at `~/Documents/SL4-EFI-FULL-BEFORE-RCS-20261123.zip`
was inspected in place (without extraction, mounting or writes) using
`python3 scripts/audit_rcs_recovery_backup.py --archive ~/Documents/SL4-EFI-FULL-BEFORE-RCS-20261123.zip`.
All **1,046 members** passed ZIP CRC checks. OpenCore, `bootx64.efi`,
Windows `bootmgfw.efi`, **28 enabled kexts**, **5 ACPI files** and **2 UEFI drivers**
were found with all paths resolved. The stored config predates v0.1.0 RCS.
The script explicitly returns `safe_to_install_experimental_kernel=false`
because a structurally complete backup is **not independently boot-tested**.
No serials, SMBIOS, UUIDs or private EFI were uploaded to GitHub.

## v0.1.2 source-only RCS queue-reason extension (compiled, not installed)

After v0.1.1, apply
[queue-reason telemetry extension](../research/wex-sl4-rcs-queue-reasons-v0.1.2.patch).
It keeps every existing scheduling decision intact, changes the public
IORegistry telemetry schema from seven to **12 little-endian uint32
words / 48 bytes** and increments only counters:

- Revision 2, active flag and original five RCS hook counters.
- Port-occupied deferral, distinct from not-ready (cs+0x1c3c=0) deferral.
- Calls forwarded into the original Intel `dequeueExecList` and
  `evalWaitQueue` methods.
- Rejected work because the other Execlist bank was busy.

`scripts/audit_rcs_gpu_resets_macos.py` now recognizes both telemetry
revision 1 and 2, fails closed on incompatible lengths and schema versions,
and reports unavailable on the installed v0.1.0 beta. A correct counter
result is still **not a proof of RCS stability or cause**.

The **isolated release build of revision 2 completed** from the full
Surface-customized WhateverXe source: experimental WhateverXe SHA-256
`d39bf6cfad635e3ee313a831415238a225ddd3e5b744b3013ec566eebc506eb7`,
AppleIntelTGLCompat SHA-256
`0b472648338447f4ea2457b7a47f2771bc04ec8a263a03416d347bed4e180e3e`.
Both match the local build manifest; no experimental binary is distributed.
The v0.1.1 + v0.1.2 patch chain applied to a copy of the original
source and reproduced the candidate source bytes exactly.

## Why compiled kext SHA-256 may differ with identical executable code

On this Mac, two consecutive builds of **unmodified**
AppleIntelTGLCompat contained exactly 16 differing bytes: their
linker-generated `LC_UUID` load command, not the machine-code sections.
The same was independently confirmed between the release-archive
v0.1.0-beta RCS payload and the locally staged RCS kext whose Mach-O
UUID matches the live `kmutil` loaded UUID.
`scripts/compare_macho_binary_uuids.py` verifies strict x86_64
Mach-O load-command boundaries, zeros only the 16-byte UUID field,
and compares hashes of all remaining file bytes. Both pairs matched
on the reference Surface, with no changes to either original file.
**This does not permit ignoring SHA-256 pinning** during installation:
any approved binary must retain its exact, versioned full-file hash.

## RCS opcode comparison before/after the single-port beta

Read-only `scripts/audit_rcs_ring_patterns_macos.py` parsed the 12
available November 22-23 `.gpuRestart` ring buffers, retaining only
opcode counts, not GPU memory addresses or sensitive report content.
`0x7a000204` appears in *all 12*, including events with other reported
IPEHR values, so this word cannot uniquely establish root cause.

Two pre-beta Spectator 3 reports at **17:13:45/17:13:59**
showed two `0x7a000204` words each and no `0x02800101/0x02800100`
arbitration words in the retained RCS window. The later **23:32:09**
WindowServer hang shows two `0x7a000204` words plus two each
arbitration disable/enable words. But arbitration words also occur
in earlier pre-beta reports (00:53 and 13:08), so their presence
cannot be uniquely attributed to the single-port change or treated
as a fault signature. Compare in the
[master plan](RCS-GPU-STABILITY-MASTER-PLAN.md).

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
