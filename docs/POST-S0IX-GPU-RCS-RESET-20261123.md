# Delayed RCS GPU Reset after SL4 S0ix RTC wakes (2026-11-23)

**Status: graphics reliability remains unresolved. Do not certify automatic system sleep.**

## Evidence from the tested Surface Laptop 4 Intel

- Platform: i7-1185G7, Iris Xe 8086:9A49, macOS Tahoe 26.7.1, experimental WhateverXe 0.8.3 DMC v2.12, S0ixStandby 0.5.8 and SSDT-DEEPIDLE.
- Powerd logged genuine RTC Deep Idle sleep/wake cycles at **12:51:00–12:51:08 (8 seconds)** and **12:55:09–12:56:20 (71 seconds)**. The deep idle count became 2, both wakes verified Intel DMC reload. The third, lid-related DarkWake at 13:03:18–13:03:24 did NOT increment the S0ix sleep counter.
- Immediate post-wake checks saw no new GPU diagnostics and reported a working Metal 2 2496x1664 internal display, but at **13:08:40 CET** a new GPU Reset report appeared: /Library/Logs/DiagnosticReports/Kernel_2026-11-23-130840_MacBook-Pro-Surface.gpuRestart.
- Its hardware signature is **813**, app **WindowServer**, context **6**, **RCS busy in batch buffer** (CCS/BCS idle), submitted stamp **0x00023015**, returned **0x00023011** (four outstanding). IPEHR=0x7a000204, ACTHD=0x415bf0b8. It is a render command-streamer hang rather than a new kernel panic. Kernel boot time stayed at 12:40:29 CET.
- Importantly, a **pre-S0ix** GPU Reset from **2026-11-22 23:11:07** had the same signature **813**, context **6**, RCS busy in batch buffer and a four-stamp gap (submitted 0x00003d2f, returned 0x00003d2b). An older 2026-11-23 00:53:55 reset was a different signature **801**. The matching pre-S0ix render hang establishes that this failure mode pre-existed these sleep trials. It does NOT rule out a wake-related contribution to the new episode.
- At 13:13 CET, Metal 2 and the panel remained available, with no additional GPU Reset/panic report observed since 13:08:40.

## Power and wake limits

- The software's **Deep Idle RTC wake** works for two manually supervised cycles on this one device. This is not a general lifetime or multi-hour reliability result.
- Platform LPIT/SLP_S0 residency remained **0 us**, PC10 **0%** (PC6 65%, PC2 33%); **CNVI** remained the final platform sleep blocker even with Wi-Fi radio temporarily off. No actual battery drain was measured.
- No verified power-button or physical lid-open wake from full system sleep. Do not conflate the 13:03 DarkWake with a completed third S0ix cycle.
- No conclusive evidence attributes the delayed RCS hang specifically to S0ix, the DMC replacement, Wi-Fi, WindowServer, or a particular EFI setting. Do not apply speculative extra resets or disable hardware blindly.

## Safe current configuration

- At final check on 2026-11-23: macOS and graphics running; Wi-Fi en1 restored On, default network route en0 (Surface Dock); display idle guard LaunchAgent restored; automatic system and display sleep remain **disabled (sleep=0, displaysleep=0)** on both power profiles.
- Temporary test RTC wake events removed; unrelated OS wake events left unchanged.
- Windows Boot Manager preserved, with private whole EFI backup (513 files), pre-S0ix complete OC backup and on-EFI original config backups available. **Do not publish the raw GPU report, personal EFI or boot-identifying fields.**

## Release gate

Before enabling automatic closed-lid/idle sleep: isolate render RCS hang with repeatable graphics stress and post-wake tracing, verify physical button and lid wake, demonstrate repeated longer sleeps without delayed GPU resets, check energy use and package C-states on battery, and retain a tested rollback.

Source-only related research: [DMC loader](DMC-SLEEP-TRIAL.md), [RTC sleep evidence](S0IX-INITIAL-RTC-WAKE-20261123.md). Prior downstream GPU instability documented in the project predates S0ix. This incident must be counted in post-sleep stability reports.
