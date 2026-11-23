# Sleep and wake — two S0ix / RTC wake cycles confirmed; extended reliability unverified

**Hardware:** Surface Laptop 4 Intel 13.5-inch, i7-1185G7, Intel Iris Xe `8086:9A49`, macOS Tahoe 26.7.1, OpenCore 1.0.8.

## Current verified result (2026-11-23)

**Display wake now works on the tested machine with the custom WhateverXe 0.8.3 eDP Keep + Softsleep add-on.** The owner confirmed the panel wakes using the sleep/power button and after closing/reopening the lid. Diagnostics independently confirm the backlight transitions from `PP_CONTROL 0x67 → 0x63 → 0x67` while keeping the eDP link trained, avoiding the previously observed `0xE00002BC` display reinitialization error.

Install and rollback instructions, binary checksums and hardware requirements are in [EDP wake](EDP-WAKE.md).

**Two separate genuine S0ix / Deep Idle RTC wakes completed on 2026-11-23:** the system slept at **12:51:00 CET** and woke at **12:51:08 CET** (8 seconds); then slept at **12:55:09 CET** and woke at **12:56:20 CET** (71 seconds), both without a reboot, with `machdep.xcpm.deep_idle_count=2` and verified DMC reload. The internal display was enumerated online with Metal 2 working. These are **two short RTC-only tests** and do not establish dependable lid / power-button wake or battery life. [Full evidence](S0IX-INITIAL-RTC-WAKE-20261123.md).

The tested Surface still has `pmset sleep 0` and `displaysleep 0` on AC and battery. The eDP Softsleep mechanism deliberately leaves the display link powered while darkening its backlight during **display-only** transitions.

## Prior unsuccessful S0ix system-sleep experiment

On 2026-11-22, experimental S0ixStandby 0.5.8 and `SSDT-DEEPIDLE` left the Surface unresponsive; the system required a restart. The entire S0ix experiment was rolled back. **Do not bundle these drivers** or claim system sleep is solved.

On 2026-11-23, a new *experimentally built* WhateverXe DMC 2.12 loader was booted with S0ixStandby and the same Deep Idle SSDT, and two short RTC wake cycles (8 and 71 seconds) then succeeded. The precise root cause of the earlier failure is still unproven, and other Intel Surface configurations remain untested.

## Safety settings

The owner's machine continues to use:

```bash
sudo pmset -a sleep 0 displaysleep 0
```

This prevents automatic idle system sleep and display-off on the tested configuration. It **does not** guarantee closing the lid cannot trigger deeper sleep under a different setup, and does not validate sleep in a bag. Do not copy power settings blindly to a machine with a different ACPI profile or operating environment.

Keep independent Windows Boot Manager recovery, preserve a full private OC backup, and verify the built-in screen visually. A green `ioreg` flag is not physical proof.

## Read-only diagnostic snapshot

On macOS, from a repository clone, run `python3 scripts/audit_sleep_macos.py --output "$HOME/Downloads/sl4-sleep-audit.json"`. This uses only `pmset` and `ioreg` queries. It cannot enable sleep, write EFI, or claim a physical wake is successful. It refuses to overwrite an existing snapshot, and does not capture personal SMBIOS identifiers.

See [deep sleep investigation and evidence](SYSTEM-SLEEP-RESEARCH.md), the [now booted but still experimental TGL DMC firmware loader](DMC-SLEEP-TRIAL.md), the [two confirmed Deep Idle RTC wakes](S0IX-INITIAL-RTC-WAKE-20261123.md), and the [Linux-surface sleep implementation comparison](LINUX-SURFACE-SLEEP-PORT.md) for the exact SL4 Intel lid GPE `0x4B`, the existing Surface Aggregator driver logic, and the required supervised recovery gate.

## Open work

Confirm repeatable display-only wake across multiple short and extended cycles, docked/undocked, AC/battery, lid close/open and power button. Qualify the observed real S0ix transition over repeated longer tests on AC and battery, separately from lid and power-button wake, with persistent logs and tested fallback.

Upstream research: [S0ixStandby](https://github.com/labrouss/S0ixStandby), [WhateverXe issue #86](https://github.com/b00t0x/WhateverXe/issues/86), [WhateverXe issue #141](https://github.com/b00t0x/WhateverXe/issues/141).
