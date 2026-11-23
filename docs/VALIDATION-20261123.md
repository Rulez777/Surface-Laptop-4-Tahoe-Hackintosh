# Surface Laptop 4 Tahoe — verification ledger (2026-11-23)

**Test unit:** Surface Laptop 4 Intel 13.5-inch, i7-1185G7, Iris Xe 8086:9A49, Samsung MZ9LQ256HBJQ-00000 / PM991, macOS Tahoe 26.7.1. This ledger distinguishes observed tests from previous owner confirmations, and from tasks that cannot be verified through a remote session.

## Verified with read-only commands this session

| Area | Evidence | Confidence |
| --- | --- | --- |
| macOS boot | Tahoe 26.7.1 running from internal APFS, separate Microsoft Windows partition present | Runtime observation only |
| Graphics | `system_profiler` reports Iris Xe / Metal 2, internal 2496×1664 HiDPI | Software query; physical image previously owner-confirmed |
| eDP Keep/Softsleep | `TGLEDPKeepReady=Yes`, `TGLSoftSleepReady=Yes`; controlled display-only test `pmset displaysleepnow` followed by `caffeinate -u`; `TGLEDPKept 9 → 11` | Programmatic display-only cycle; **physical light-up not verified this session** |
| Audio | Default built-in audio output and microphone input enumerated | Physical playback/recording not performed this session |
| Input | BigSurface and HID kexts loaded; user previously confirmed keyboard/touchpad | No live key/gesture verification this session |
| Wireless | Wi-Fi hardware port present; Intel AX201 previously confirmed | No throughput/Bluetooth transfer test this session |
| Brightness | PNLF/UID 19 fix previously verified and persistent per project log | No physical adjustment this session |
| Drivers | Lilu 1.7.2, WhateverXe 0.8.3, VirtualSMC/SMCProcessor 1.3.8, AppleALC 1.9.8, SimpleHDA 1.0.2, BigSurface 1.2.0, BigSurfaceHIDDriver 1.0.0 all loaded | Current-kernel versions verified |
| Thermal | `TC0D` sensor successful; installed TMP3 LaunchDaemon running, zero bytes sampled stderr; 35 s CPU-only partial load test (two 55%-duty workers) 45–56 °C with 80 °C auto-stop | Does **not** prove EC changed fan profile or RPM |
| Battery charging cap | At ~52% with AC connected, `AppleSmartBattery` reported `IsCharging=No`, current/max 2811/5626, cycle count 110; Microsoft's optional Surface UEFI Battery Limit intentionally holds around 50% | Probable, not confirmed; UEFI setting has not been inspected; [battery notes](BATTERY.md) |
| **Current CPU performance regression (08:20–08:34 CET)** | 60 W AC adapter connected and charging 22→52% (then AC attached but stopped charging), software low-power off and CPU speed limit 100%, CPU die ~40–43 °C. 500k PBKDF2-SHA256 rounds 1.96–1.98s; user-space `time -l` cycle/CPU-time proxy ~582–585 MHz even at 52% charge, while nominal CPU base is 3 GHz. BigSurface mode 1 is Recommended, **not Battery Saver**. TMP3 restart did not restore performance; a user-level AC reconnect watcher was installed at ~08:31 and was running. | Severe slowdown reproduced before the 08:54 reboot; subsequent symptom recovery confirmed, but the true EC/CPU power-limit cause remains unverified; [details](POWER-RECOVERY.md) |
| **CPU performance restored by reboot (08:54 CET)** | Physical user reboot; same 250k-round benchmark **1.18 s → 0.21 s (5.62×)** while AC still attached, battery 52%, software CPU limits 100%, BigSurface mode still 1. Counter proxy ~582 → ~3413 MHz. A subsequent 30 s bounded CPU-only thermal test at 2×55% duty completed at 50–55 °C, and benchmark remained fast (0.19 s). | Confirmed symptom recovery after reboot; **underlying cause and future recurrence unknown**; [comparison tool](../scripts/compare_power_snapshots.py) |
| **System sleep (2026-11-23 update)** | S0ixStandby 0.5.8 + SSDT-DEEPIDLE + experimental WhateverXe DMC boot successfully; **two confirmed Deep Idle RTC wake cycles (8 s and 71 s)**, `machdep.xcpm.deep_idle_count=2`, DMC wake readback verified, Metal 2 retained | **Manual RTC wake verified on one Surface only**; SLP_S0/LPIT residency 0, package PC10 0, `CNVI` last blocker at halt; power-button/lid wake, sustained battery savings and idle auto-sleep unverified, so `pmset sleep=0` remains |
| Crash evidence | Snapshot counted 8 GPU resets, 3 kernel panics, 5 WindowServer reports in prior 24 h; none by file timestamp since current boot | Older crashes remain relevant; absence of new reports is not a stress proof |
| Local automated tests | All 82 tests passed on macOS; portable staging/backup, hash, fail-closed logic exercised in synthetic EFI fixtures | Tests are not equivalent to a real clean installation |
| Windows offline recovery workflow | On a separate Windows 11 PC, five sequential PowerShell wrapper actions — Inspect, Backup, Prepare, VerifyBackup, RestoreOffline — succeeded against a synthetic EFI; re-verified restored copy and unchanged source hashes | No live ESP, BCD or EFI was touched; not a live boot test |
| Source control | Shared hardware profile/installer sources and docs published; separate private EFI not included | Clean public clone and deterministic ZIP verified |

## Critical limitations

1. **System S0ix is experimental, not production-certified.** Two supervised Deep Idle sleeps (8 and 71 seconds) resumed via RTC on 2026-11-23 with DMC. A third attempted clamshell-related dark wake lasted 6 seconds but did not increment the S0ix sleep counter. On the 71-second test LPIT/SLP_S0 and package PC10 residency were zero; CNVI remained active. No battery-energy, overnight, independent lid or power-button wake certification. Keep automatic idle sleep disabled and private EFI/Windows rollback verified.
2. **Power management** still has automatic system sleep disabled and a remote-service `caffeinate` assertion. Thus screen-wake success does not prove deep-sleep power savings. No overnight battery-drain or laptop-in-bag certification.
3. **Fan/RPM** readings are unavailable through a validated API for this model. BigSurface `PerformanceMode` accepts an IOKit request but EC response and true fan behavior are unmeasured.
4. **Private live EFI** is unmounted; remote terminal security policy blocks privileged mount/administration commands. Previously saved, root-owned private backups exist. They were **not** restored or revalidated at this step. The new toolkit never modified the ESP or Windows.
5. No physical test of 3.5 mm audio, external dock, audio recording/playback, Bluetooth transfer, multi-hour CPU/GPU sustained load, independent Windows cold boot, or reproduction on another Surface.
6. The hardware matcher intentionally refuses automatic ESP writing even on matching hardware, because matching CPU/GPU/ACPI IDs alone does not prove a safe boot on a different laptop.

## New portable workflow

- Read-only hardware scan on Windows/macOS, filtering private serials/UUIDs and returning explicit compatibility status.
- Shared `data/sl4_profiles.json` with specific hardware allowlist and pinned SHA-256 artifacts.
- Private off-ESP EFI inspection, backup, content hash verification and optional offline staging (explicit opt-in, no overwriting).
- Reject unverified S0ix/DEEPIDLE, conflicting enabled kexts, missing files and dependency-order faults.
- Deterministic public offline existing-install toolkit ZIP; **not a bootable EFI** and contains no `config.plist`.
- Read-only stability/sleep snapshot tools and portable unit tests.

## Unfinished acceptance tests before a stable full installer can be claimed

- Mount and validate **actual** current EFI with appropriate administrative authorization, run official ocvalidate 1.0.8 against the live configuration and create a fresh full encrypted-safe backup.
- Physically supervise repeated lid and button cycles, true power-transition tests (only after root-cause fix), battery drain measurements and external display/dock tests.
- Validate thermal behavior against a *measurable* EC/fan interface, compare mode profiles, and run controlled extended CPU+GPU load tests with temperature limits.
- Validate a complete clean Windows + Tahoe install, using Windows-only recovery and the shared driver workflow, first on the current supported SL4, then on additional compatible models.
- Add true installer/recovery workflows **only after** their effects on bootloader, Windows BCD and personal SMBIOS can be independently verified.

These incomplete conditions are not silently re-labelled “passed.” Existing macOS and Windows partitions have been preserved.
