# First confirmed system Deep Idle / RTC wake on SL4 (2026-11-23)

**Evidence: two successfully completed S0ix / Deep Idle system sleep cycles of 8 and 71 seconds.** This is the first confirmed successful S0ix resume on the tested Surface Laptop 4, not a release-ready suspend implementation for all conditions.

## Environment

- Microsoft Surface Laptop 4 Intel 13.5-inch, i7-1185G7, Iris Xe 8086:9A49; macOS Tahoe 26.7.1; OpenCore 1.0.8.
- Verified locally booted kexts: custom WhateverXe 0.8.3 with eDP Keep + Softsleep, GPU recovery, and *experimental* Intel TGL DMC 2.12 program loader; S0ixStandby 0.5.8; BigSurface 1.2.0.
- Experimentally enabled ACPI `SSDT-DEEPIDLE.aml`; `IOPMDeepIdleSupported = Yes`.
- The DMC main program and hook qualifications are documented in [DMC sleep trial](DMC-SLEEP-TRIAL.md); the booting local trial executable checksum is `2049c6c9a2919d8456d4a219b39f7cf003171d21ef08e961c14a0443c4656f3a`.
- Connected to AC; battery gauge ~51% during sleep, 52% after. At the time of the trial, Surface Dock USB3Hub and Bluetooth USB Host Controller were visible as USB power assertions. These observations do *not* establish power efficiency.

## Exact sequence and receipts (local CET)

| Evidence | Observation |
| --- | --- |
| Kernel uptime across sleep | Same boot, 2026-11-23 12:40:29, before and after wake |
| Sleep entry | `2026-11-23 12:51:00 Sleep — Entering Sleep state due to 'Software Sleep pid=206'` |
| RTC wake request | `12:51:01 Wake Requests — UserWake at 12:51:05 (pmset)` |
| Wake | `2026-11-23 12:51:08 Wake — Wake from Deep Idle [CDNVA]: due to RTC0/UserActivity Assertion` |
| Wake time | `0.670 sec` |
| Sleep duration | Approximately **8 seconds**, per powerd |
| Deep Idle counter | `machdep.xcpm.deep_idle_count: 1`, up from 0 |
| Sleep timestamp | `kern.sleeptime: 2026-11-23 12:51:02`, previously 0 |
| GPU DMC wake | `SL4DMCLocalWakeVerified = Yes`, `SL4DMCLocalWakeReadback = Yes`, `SL4DMCLocalInitVerified = Yes` |
| Graphics after wake | Iris Xe Graphics, **Metal 2**, internal display enumerated **Online: Yes**, **2496 × 1664** |
| Thermal/CPU after wake | `CPU_Speed_Limit=100`, `CPU_Scheduler_Limit=100`, eight available CPUs |
| Kernel panics/GPU resets in post-test search | No new files found |

Source receipts: local `pmset -g log`, `sysctl kern.boottime kern.sleeptime machdep.xcpm.deep_idle_count`, `ioreg -lw0`, `system_profiler SPDisplaysDataType`, `pmset -g therm`. The log records two cycles: `machdep.xcpm.deep_idle_count: 2` and two `Wake from Deep Idle` events.

**Meaning:** this is full-system Deep Idle, not the older display-only eDP Softsleep. The exact cause of the prior deadlock has *not* been proved; the DMC loader is a plausible contributor, but the test changed more than one subsystem (S0ixStandby, SSDT and DMC).

## Second RTC cycle (12:55 to 12:56 CET)

- **12:55:09**: `Entering Sleep state due to 'Software Sleep pid=206'`.
- **12:56:20**: `Wake from Deep Idle [CDNVA]: due to RTC0/UserActivity Assertion`. The powerd event reports **71 seconds asleep** and `WakeTime: 0.682 sec`.
- The boot time remained **12:40:29 CET** across both cycles; `machdep.xcpm.deep_idle_count` increased to **2**. `SL4DMCLocalWakeVerified = Yes` and `SL4DMCLocalWakeReadback = Yes`; Metal 2 and the 2496×1664 internal screen still enumerated online.
- No new kernel panic/GPU reset observed in the immediate post-test check.

## Remaining qualification and operating restrictions

- Two short RTC cycles succeeded, but no repeated long sleep; battery-only suspend, power consumption, and independent power-button / lid wake from *system* Deep Idle are **unverified**. The previous owner-confirmed lid/power wake was display-only and must not be conflated with this RTC resume.
- `system_profiler` reports the internal display online; **a person has not yet independently confirmed the physically visible panel after this specific system-sleep cycle**.
- No 5–60 minute standby, lid-close-in-bag, dock hotplug/resume, peripheral exercise, or idle-timeout reliability qualification. Headphone jack and unrelated peripherals likewise unverified.
- The tested machine's **automatic sleep remains disabled** (`pmset -g custom`: `sleep=0`, `displaysleep=0` on AC and battery). **Do not enable idle system sleep or ship this experimental combination by default.**
- The existing Windows EFI was preserved. Before experiments a separate private full EFI backup was byte-verified (**513 files**, including Windows Boot Manager); separate complete `EFI/OC` backup and an on-ESP recovery config were also saved. These are private and must **never be published**.
- The firmware data and binary trial kext are not bundled in the public offline kit. Source-only analysis is available, but reproduction still requires the correct Intel firmware, verified donor graphics binaries, and physical rollback capability.

**Status recommendation:** mark `short_s0ix_rtc_cycle_verified = true` (count 2, longest 71 sec) for *this precise test machine* while retaining `full_system_sleep_verified = false` and `certified_for_automatic_esp_installation = false`. Next steps: supervised repeated long-duration cycles, physical power-button and lid wake, keyboard/trackpad, audio, Wi-Fi, Metal, CPU performance and power drain checks on AC and battery, all with rollback and snapshots.
