# Tiger Lake DMC source-only sleep investigation (2026-11-23)

**Status: experimental kext compiled; NEVER INSTALLED on the active Surface; real system sleep/resume remains UNVERIFIED and disabled.** This note documents a specific candidate derived from public reports on other Tiger Lake laptops. It is not an automatic sleep fix, is not part of the approved SL4 profile, and does not modify Windows or the live ESP.

## Evidence and exact target

- This SL4 Intel 13.5" has i7-1185G7, Iris Xe 8086:9A49, macOS Tahoe 26.7.1 (25G241), WhateverXe 0.8.3 custom eDP Keep/Softsleep and Graphics 0.4.4. The internal ESP `disk0s1` remains unmounted; Power Management `sleep=0`, `displaysleep=0` both AC/battery.
- On a different Tiger Lake-H35 9A49 system, loading the complete Intel DMC v2.12 program removed a **silent deadlock** on S0ix entry while preserving Metal on the internal display. Other tests still failed on HDMI and WindowServer. This does **not** prove the same patch will fix SL4 S0ix; its *previous* S0ix hang was not conclusively classified.
- Public source: [WhateverXe #157](https://github.com/b00t0x/WhateverXe/issues/157) and [S0ixStandby #3](https://github.com/labrouss/S0ixStandby/issues/3). Crucial upstream correction: fixed-size `mmioaddr[20]` + `mmiodata[20]` arrays; using `[mmio_count]` erroneously reads zeros and disables DMC event handlers.
- Obtained a public copy of `i915/tgl_dmc_ver2_12.bin` from GitHub mirror `naups/i915-firmware`; **not redistributed**. File size **19,760 bytes**; SHA256 `3c013ef0ad96ba73aee8e5bd04a8e27cc9b1c6e9183b1a83ce124485f325afca`. Main DMC program SHA1 **`f2d9bebcd53a51abe92902770622cef2aed1ecc6`** matches the public independent report. Main program at `0x80000`, **4,460 dwords / 17,840 B**, first dword `0x0c004040`. Nine control writes were verified nonzero; first `0x8f074=0x86fc0`, VBLANK event 0x32 is rewritten to 0x2e per i915's TGL workaround.
- Local original Graphics donor SHA256: framebuffer `115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e`, accelerator `6c8ab6cce50b9529679ee4fdf5b1c37d091677d945076f41cb4b7f8196c51449`. Required symbols match known offsets: `hwInitializeCState=0x43972`, fast register write `0x5ed7e`, read `0x5ed62`, accelerator `systemDidWake=0x2897a`. Their instruction prologues were checked against the exact binaries, not inferred from another release.

## Implementation (isolated, not enabled)

Source-only patch: `research/wex-tgl-dmc-supervised.patch`. It adds a local-only header `kern_sl4_dmc_trial.hpp` and hooks two donor callbacks with a strict, explicit opt-in **`-wex-sl4-tgl-dmc`**.

1. `hwInitializeCState` original runs, then the full verified DMC main program is written with the donor's register accessor `controller+0xc40`. The first dword is read back. A controller pointer is cached *only on verified success*.
2. `IntelAccelerator::systemDidWake` original runs, then the same DMC is uploaded again via the captured controller pointer, with a readback.
3. Both routes check exact symbol addresses, offsets, donor function prologues, Tiger Lake PCI ID `0x9A49`, and the opt-in boot argument. Other systems should not activate the trial.
4. Runtime observability: `SL4DMCLocalInitHookReady`, `SL4DMCLocalWakeHookReady`, `SL4DMCLocalInitVerified`, `SL4DMCLocalWakeVerified` and separate readback counters. The flags are **not** present in today's running kernel because this candidate has not booted.

### Local offline trial build, already performed

The source tree remains at `~/Downloads/SL4-WEX-DMC-SLEEP-EXPERIMENT-20261123`. The compiled, disabled, **experimental** kext is `build/SL4-DMC-ISOLATED/WhateverXe.kext` (version 0.8.3, executable SHA256 `2049c6c9a2919d8456d4a219b39f7cf003171d21ef08e961c14a0443c4656f3a`). Source WEX baseline and kernel build settings were preserved. Compiler/linker checks passed, including kernel-lifecycle symbols and absence of forbidden userspace/DriverKit imports. A second independent build started from an untouched copy of the known baseline, applied the published patch with `patch -p1`, generated the same DMC data header, and compiled successfully. Both resulting executables are **1,888,640 bytes** and differ only in 15 bytes of the automatically generated 16-byte Mach-O UUID (`LC_UUID`, file positions 1160–1175); after normalizing the UUID, all executable bytes match. The second binary has raw SHA256 `1887c3ee090ee8f04a697d860d4064e36a4bd999d501ac4e1e32b4be67ad5602`. **These builds still do not establish that the two hooks execute correctly or that sleep works.**

The distributable source repository contains `scripts/inspect_tgl_dmc.py` (strict parser), `scripts/generate_tgl_dmc_trial_header.py` (generates `kern_sl4_dmc_trial_data.hpp` after validating the user-supplied firmware), and a source-only patch. **It deliberately excludes the firmware binary, generated 4,460-dword array and compiled kext** from the offline toolkit. Any future deployment requires separate permission, licensing review, binary pinning and physical tests.

For a verified official firmware copy stored locally (not a downloaded random blob), a read-only one-line check from repository root is: `python3 scripts/inspect_tgl_dmc.py /path/to/tgl_dmc_ver2_12.bin`. Header generation is offline: `python3 scripts/generate_tgl_dmc_trial_header.py /path/to/tgl_dmc_ver2_12.bin --out /path/to/private/WhateverXe/kern_sl4_dmc_trial_data.hpp`. Apply `research/wex-tgl-dmc-supervised.patch` **only to the exact WEX source baseline** and recompile using the existing standalone `tools/build.py`; a source patch is not a ready OpenCore EFI.

## Why this cannot be installed remotely as a safe finished fix

- The current live ESP has Windows Boot Manager and is unmounted; remote terminal policy blocks root, EFI mounts, and forced reboot. Several full older backups are root-owned, thus **a current independently usable private backup and Windows rollback have NOT been verified**.
- The previously broken experimental `S0ixStandby.kext` and `SSDT-DEEPIDLE` were rolled back. Even with DMC, a **separate, supervised** activation of macOS Deep Idle is needed before any true suspend can be tested. This adds multiple independent variables and risks both GPU and firmware deadlocks.
- The additional experimental `LID0._PRW` GPE `0x4B` is **not** part of this trial; it is only a later wake-source fix, after power-button resume works. It can cause dark wake loops and repeated framebuffer hangs. See [Linux-surface analysis](LINUX-SURFACE-SLEEP-PORT.md).
- A pointer captured during `hwInitializeCState` has not been proven valid through SL4 Deep Idle. Runtime hook/IORegistry receipts and post-resume stability must be verified before releasing, and the candidate is **not suitable for unattended or one-click deployment**.
- The current eDP Keep + Softsleep patch deliberately avoids display link shutdown; this may interact with DMC / S0ix residency. The combined behavior has not been evaluated. Do not change eDP behavior to achieve artificially better power numbers.

## Required on-device validation gate

A person must be physically at the laptop, with a proven way to restore Windows/macOS boot and the known-good signed-off OC config without USB. Mount and backup the **correct internal** ESP with verified WBM, pin all kext/config hashes, stage *one* experimental candidate with automatic sleep still disabled, then make a supervised reboot and independently verify Metal, brightness, microphone, sound, Wi-Fi and CPU speed *before* any system sleep. Install Deep Idle only if a prior staged candidate boots normally. Trigger one short manual sleep with external cables disconnected, recover by power button, check actual `pmset` Deep Idle events, counters, UI and physical display. If freeze occurs, restore the known-good EFI, never blindly repeat. Longer cycles and lid GPE tests only follow successful entries. **Without these tests, keep `pmset sleep=0` and do not market the feature as completed.**

Current conclusion: **candidate software builds**, but a **working system sleep on the Surface has not yet been established**.
