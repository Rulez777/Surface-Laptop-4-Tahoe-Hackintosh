# Tiger Lake DMC source-only sleep investigation (2026-11-23)

**Status updated 2026-11-23:** the experimental kext **was installed and booted on the test Surface**, followed by **two confirmed genuine S0ix / Deep Idle RTC wakes (8 and 71 seconds)** with DMC wake verification and working Metal 2. It is still not a general reliable sleep fix. Automatic sleep remains disabled. See [first RTC wake evidence](S0IX-INITIAL-RTC-WAKE-20261123.md). The Windows EFI was preserved.

## Evidence and exact target

- This SL4 Intel 13.5" has i7-1185G7, Iris Xe 8086:9A49, macOS Tahoe 26.7.1 (25G241), WhateverXe 0.8.3 custom eDP Keep/Softsleep and Graphics 0.4.4. The internal ESP `disk0s1` remains unmounted; Power Management `sleep=0`, `displaysleep=0` both AC/battery.
- On a different Tiger Lake-H35 9A49 system, loading the complete Intel DMC v2.12 program removed a **silent deadlock** on S0ix entry while preserving Metal on the internal display. Other tests still failed on HDMI and WindowServer. This does **not** prove the same patch will fix SL4 S0ix; its *previous* S0ix hang was not conclusively classified.
- Public source: [WhateverXe #157](https://github.com/b00t0x/WhateverXe/issues/157) and [S0ixStandby #3](https://github.com/labrouss/S0ixStandby/issues/3). Crucial upstream correction: fixed-size `mmioaddr[20]` + `mmiodata[20]` arrays; using `[mmio_count]` erroneously reads zeros and disables DMC event handlers.
- Obtained a public copy of `i915/tgl_dmc_ver2_12.bin` from GitHub mirror `naups/i915-firmware`; **not redistributed**. File size **19,760 bytes**; SHA256 `3c013ef0ad96ba73aee8e5bd04a8e27cc9b1c6e9183b1a83ce124485f325afca`. Main DMC program SHA1 **`f2d9bebcd53a51abe92902770622cef2aed1ecc6`** matches the public independent report. Main program at `0x80000`, **4,460 dwords / 17,840 B**, first dword `0x0c004040`. Nine control writes were verified nonzero; first `0x8f074=0x86fc0`, VBLANK event 0x32 is rewritten to 0x2e per i915's TGL workaround.
- Local original Graphics donor SHA256: framebuffer `115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e`, accelerator `6c8ab6cce50b9529679ee4fdf5b1c37d091677d945076f41cb4b7f8196c51449`. Required symbols match known offsets: `hwInitializeCState=0x43972`, fast register write `0x5ed7e`, read `0x5ed62`, accelerator `systemDidWake=0x2897a`. Their instruction prologues were checked against the exact binaries, not inferred from another release.

## Implementation (opt-in and booted on the test Surface; not released for general installation)

Source-only patch: `research/wex-tgl-dmc-supervised.patch`. It adds a local-only header `kern_sl4_dmc_trial.hpp` and hooks two donor callbacks with a strict, explicit opt-in **`-wex-sl4-tgl-dmc`**.

1. `hwInitializeCState` original runs, then the full verified DMC main program is written with the donor's register accessor `controller+0xc40`. The first dword is read back. A controller pointer is cached *only on verified success*.
2. `IntelAccelerator::systemDidWake` original runs, then the same DMC is uploaded again via the captured controller pointer, with a readback.
3. Both routes check exact symbol addresses, offsets, donor function prologues, Tiger Lake PCI ID `0x9A49`, and the opt-in boot argument. Other systems should not activate the trial.
4. Runtime observability: `SL4DMCLocalInitHookReady`, `SL4DMCLocalWakeHookReady`, `SL4DMCLocalInitVerified`, `SL4DMCLocalWakeVerified` and separate readback counters. Runtime receipts after the two real RTC wakes show `SL4DMCLocalInitVerified = Yes`, `SL4DMCLocalWakeVerified = Yes` and `SL4DMCLocalWakeReadback = Yes`. These verify this narrow hardware transition, not general resume stability.

### Local offline trial build, already performed

The source tree remains at `~/Downloads/SL4-WEX-DMC-SLEEP-EXPERIMENT-20261123`. The compiled **experimental** kext is `build/SL4-DMC-ISOLATED/WhateverXe.kext` (version 0.8.3, executable SHA256 `2049c6c9a2919d8456d4a219b39f7cf003171d21ef08e961c14a0443c4656f3a`). Source WEX baseline and kernel build settings were preserved. Compiler/linker checks passed, including kernel-lifecycle symbols and absence of forbidden userspace/DriverKit imports. A second independent build started from an untouched copy of the known baseline, applied the published patch with `patch -p1`, generated the same DMC data header, and compiled successfully. Both resulting executables are **1,888,640 bytes** and differ only in 15 bytes of the automatically generated 16-byte Mach-O UUID (`LC_UUID`, file positions 1160–1175); after normalizing the UUID, all executable bytes match. The second binary has raw SHA256 `1887c3ee090ee8f04a697d860d4064e36a4bd999d501ac4e1e32b4be67ad5602`. **These builds still do not establish that the two hooks execute correctly or that sleep works.**

The distributable source repository contains `scripts/inspect_tgl_dmc.py` (strict parser), `scripts/generate_tgl_dmc_trial_header.py` (generates `kern_sl4_dmc_trial_data.hpp` after validating the user-supplied firmware), and a source-only patch. **It deliberately excludes the firmware binary, generated 4,460-dword array and compiled kext** from the offline toolkit. Any future deployment requires separate permission, licensing review, binary pinning and physical tests.

For a verified official firmware copy stored locally (not a downloaded random blob), a read-only one-line check from repository root is: `python3 scripts/inspect_tgl_dmc.py /path/to/tgl_dmc_ver2_12.bin`. Header generation is offline: `python3 scripts/generate_tgl_dmc_trial_header.py /path/to/tgl_dmc_ver2_12.bin --out /path/to/private/WhateverXe/kern_sl4_dmc_trial_data.hpp`. Apply `research/wex-tgl-dmc-supervised.patch` **only to the exact WEX source baseline** and recompile using the existing standalone `tools/build.py`; a source patch is not a ready OpenCore EFI.

## Why this does not yet qualify as a safe general-purpose sleep fix

- A private full EFI backup (**513 files, including Windows Boot Manager**) and separate complete OC copies were byte-for-byte verified before staging. A restore config is held on ESP. Restoring after a failed boot still requires reliable physical access to the system or Windows; do not assume automatic rollback.
- The older experimental S0ixStandby + SSDT-DEEPIDLE stack had hung the SL4 on 2026-11-22. Adding experimental DMC upload coincided with success on 2026-11-23, but cannot by itself prove which component fixed the original hang. No automatic S3 path is advertised.
- In the successful 2026-11-23 configuration, `SL4DMCLocalInitVerified` and `SL4DMCLocalWakeVerified` were both `Yes` after **two** real RTC-wake cycles (8 and 71 seconds), and Metal 2 plus internal screen enumeration survived.
- The `LID0._PRW` GPE `0x4B` research SSDT is **not installed**. System lid-open and power-button wake from Deep Idle still need independent physical testing; an ACPI change can cause dark-wake loops.
- The framebuffer-controller pointer was usable across the two short tests, but not validated for overnight sleep, lid close/open, off-AC operation or repeated external display hotplug. This trial must not be shipped as a production automatic installer.
- The eDP Keep + Softsleep patch retains display link state during **display-only** sleep; long-term interaction with DMC and actual power residency is unknown.

## Validation gates for eventual release

Keep automatic system sleep disabled (`pmset sleep 0`) for both power profiles until testing includes longer repeated system sleeps on AC and battery, user-visible physical lid/power wake, usable keyboard and trackpad, sound/microphone, Wi-Fi/Bluetooth, Metal, CPU frequency and thermals, and power consumption. Reboot-free RTC wake is promising but does not establish these outcomes.

**Observed result on the single test machine:** two genuine S0ix RTC wakes (8 and 71 seconds) completed with verified DMC reload and no observed GPU reset or kernel panic. **Reliable everyday system sleep is not yet certified.** For exact timestamps and raw counters see [RTC-wake evidence](S0IX-INITIAL-RTC-WAKE-20261123.md).
