# Deep system sleep investigation — SL4 Tiger Lake / Tahoe (2026-11-23)

**Status: unresolved.** As of 2026-11-23, a separate Tiger Lake DMC v2.12 firmware-loader candidate has been compiled, source-patch and parser checked; it has **not** been installed or boot-tested on this Surface. Details: [DMC sleep trial](DMC-SLEEP-TRIAL.md). This is evidence and a fault-isolation plan, **not an installed sleep fix**. The working accelerated eDP Keep + Softsleep configuration remains intact. Never treat successful display wake as evidence of actual S3/S0ix suspend/resume.

## Device and actual runtime state

- Microsoft Surface Laptop 4 Intel 13.5-inch, i7-1185G7 / Iris Xe 8086:9A49, Samsung PM991, macOS Tahoe 26.7.1, OpenCore 1.0.8, custom WhateverXe 0.8.3 eDP Keep/Softsleep.
- `pmset -g custom`: `sleep 0`, `displaysleep 0` on both AC and battery. AC `hibernatemode 0`; battery `hibernatemode 3`. A development `caffeinate` assertion prevents idle sleep; remote service also holds one.
- `pmset -g cap` reports generic macOS sleep support; **this is not proof** that Surface firmware implements a bootable S3 path or a working Modern Standby integration.
- `ioreg -p IOACPIPlane -lw0` exposes `MSHW0084` and `MSHW0250`. A bounded string search found no printed `_S3` or `S0ix` capability names, which **does not prove** the absence of any ACPI feature.
- `sysctl kern.hibernatecount` returned 0; `kern.hibernategraphicsready` was 0 in a runtime snapshot. These values alone do not diagnose the failed resume.
- One software-only display-off/on cycle using `pmset displaysleepnow`, then a wake assertion, advanced the eDP keep counter from 9 to 11 without a new crash diagnostic file in the brief observation window. **Physical screen light-up was not witnessed during this run.**
- Prior system-suspend experiment enabling S0ixStandby 0.5.8 and `SSDT-DEEPIDLE` ended with a non-recovering Surface requiring a restart. Both were rolled back. No new true S3/S0ix experiment occurred during the present session.
- A read-only stability snapshot recorded pre-existing GPU Reset / WindowServer / kernel-panic diagnostics from prior boots. Such reports must be preserved for investigation rather than interpreted as proof the machine is now stable.

## Closely related upstream evidence (not a Surface-specific diagnosis)

1. [WhateverXe issue #86](https://github.com/b00t0x/WhateverXe/issues/86), opened Nov 10, 2026, is an **accepted, open, external-test** issue: HP EliteBook 840 G8, the **same i7-1185G7 / 9A49**, and Tahoe 26.7.1 can hang on sleep entry during `GFX0(): Some drivers failed to handle setPowerState`, especially on AC following dark wakes. It also reproduced with S0ixStandby disabled. Hardware/display/EC/ACPI differ, so SL4 cannot be declared the same failure.
2. [S0ixStandby](https://github.com/labrouss/S0ixStandby) uses `SSDT-DEEPIDLE` + its own kext to select XNU Deep Idle (type 7) on firmware with supported modern-standby calls. Reported HP 840 G8 successes involve extra machine-specific AC wake management; issues remain with TGL framebuffer sleep, external monitors and lid wake.
3. [WhateverXe issue #63](https://github.com/b00t0x/WhateverXe/issues/63) describes **eDP display-only** black screen on another 9A49 laptop. The common `-nodisplaysleepDC6 -noDC9 dc6config=0` workarounds **failed** to resolve the original SL4 physical black screen before our custom eDP Keep + Softsleep add-on; do not replace the current patch with those flags alone.
4. [WhateverXe upstream README](https://github.com/b00t0x/WhateverXe) still treats generic system sleep as experimental and model-specific; an Intel GPU presenting Metal is not sufficient to certify wake.
5. [Linux Surface SL4 Intel battery issue #2303](https://github.com/linux-surface/linux-surface/issues/2303) includes discussion of modern-standby drain on one SL4, but it is neither a macOS workaround nor proof of the same failure.

## Distinguish failure classes before attempting fixes

| Failure | Observable evidence | Follow-up focus |
| --- | --- | --- |
| Screen-only failure | Remote/keyboard/audio responsive; eDP link-training errors or framebuffer offline | Preserve Keep + Softsleep; compare panel power and AGDC traces |
| GPU/driver refusal to enter system sleep | `pmset` `Failure during sleep`, named `GFX0`/setPowerState; OS may still be responsive until freeze | Study driver power-state ordering and TGL eDP/GPU reset without enabling additional ACPI |
| S0ix/firmware suspend failure | Kernel transitions into Deep Idle; hard freeze with no wake and no useful panic | ACPI LPS0 DSM/LPIT/EC and PCI/NVMe power sequencing; only supervised with non-USB recovery |
| Wake succeeds but battery drains | Confirmed resume after long interval, high measured consumption | Compare actual watts/charge drop, device wake sources and dark wakes on AC/battery |

No class is conclusively established for the prior failed SL4 S0ix test. An upstream GPU sleep-entry report is a lead, not root-cause proof.

## Safe next diagnostics — without sleeping or modifying EFI

- Capture `pmset -g custom`, `pmset -g cap`, `pmset -g assertions`, a bounded `pmset -g log` event timeline, runtime WhateverXe flags and historical GPU Reset / panic reports into **private** files; never upload full NVRAM or SMBIOS.
- Inspect previous reboot times relative to `pmset Entering Sleep` and whether `Failure during sleep`, `GFX0`, `NVMe`, `IGFB`, `IOPMSystemSleepType`, `DarkWake` appear. Separate events from different boots. Keep the serial/network identifiers redacted.
- Check whether the original S0ix failure had a published `IOPMDeepIdleSupported=Yes` and actual Deep Idle entry before hanging; this was not established in the handoff.
- Compare AC vs battery transitions without changing current profiles. Use existing `scripts/audit_sleep_macos.py` and `scripts/sl4_stability_audit_macos.py`; neither invokes suspend.
- Review the experimental upstream fixes **offline**, matching the actual WhateverXe/Graphics/Tahoe binaries and current eDP patch version. Do not automatically add S0ixStandby, `SSDT-DEEPIDLE`, unsupported GPU reset flags or change the bootloader.

## Required gate for any future actual sleep trial

A physical operator and trustworthy independent recovery are **required** because loss of remote access is an expected failure mode. Before the test: verify a fresh private copy of the **current** EFI and Windows boot path; validate OpenCore 1.0.8 configuration and known-good rollback; preserve current eDP kext and its SHA; capture pre-test logs and battery state. Trial **one** independent hypothesis, initially undocked, with a short observed interval and a precise success criterion: real ACPI/Deep Idle transition, physically visible wake, no GPU errors, all input/audio/wireless devices functioning afterwards. Only then repeat battery/AC cycles, long intervals, dock, and actual power measurement. Roll back if a single unresponsive boot or wake occurs. **Do not automatically retry failed sleep tests.**

Until a complete trial passes, the machine retains `sleep=0`. This conservative configuration is intentionally unsuitable for an unattended running laptop inside a bag.

See [display wake](EDP-WAKE.md), [sleep safety](SLEEP.md), and [validation ledger](VALIDATION-20261123.md).
