# Surface Laptop 4 — performance collapse during low-battery charging

**2026-11-23, macOS Tahoe 26.7.1, i7-1185G7 / Iris Xe 8086:9A49. Status: CPU slowdown reproduced, then performance restored by a physically performed ordinary reboot. Root cause NOT YET verified.** The AC-reconnect workaround below does not bypass CPU thermal or battery safety controls.

## What is actually observed

1. After user-reported low-battery slowdown, macOS detects **AC power**, a **60 W** charger, and positive charging current. Battery rose from **22% to 52%** during supervised read-only checks, then stopped charging while AC stayed connected. The CPU cycle proxy remained close to 0.58 GHz (approx. 719 million cycles / 1.23 CPU seconds at 50%, and **582.2 MHz** in a repeated test at 52%). Charging alone did not restore observed performance before reboot. Charging was active up to the ~52% battery limit; the user performed a restart later, which restored CPU performance.
2. `pmset -g custom` reports `lowpowermode 0` on **both** AC and battery. `pmset -g therm` shows `CPU_Speed_Limit=100`, `CPU_Scheduler_Limit=100` and all **8** logical processors available. `machdep.xcpm.lpm_enabled=0`, `cpu_thermal_level=0`, `gpu_thermal_level=0`, and 48×100 MHz configured ratio upper limits. **These settings do not measure the actual running CPU frequency.**
3. CPU die `TC0D` consistently reads about 40–43 °C, well below a typical thermal threshold. A persistent classic CPU heat throttle is not supported by the available sensor readings.
4. One measured 3-million-round `PBKDF2-HMAC-SHA256` operation took **12.234 seconds**. 500,000 rounds took **1.96–1.98 seconds** during subsequent checks on this machine. Comparisons with another processor are not controlled benchmarking.
5. More importantly, macOS `/usr/bin/time -l` reported `1,252,178,937 cycles elapsed` across `2.03 user + 0.11 sys` CPU seconds (500,000 rounds): **approximately 585 MHz counted cycles per CPU second**. A second 250,000-round test at ~46% charged reported **669,072,051 cycles / 1.15 CPU seconds = 581.8 MHz**, a repeat at **50%** reported **718,849,943 cycles / 1.23 CPU seconds ≈ 584 MHz**, and the same instrumentation at **52% not charging** gave a **582.2 MHz proxy**. This is a **hardware counter-derived frequency proxy**, not calibrated APERF/MPERF or a direct MSR clock measurement. It is consistent with severe nonthermal clock reduction and unusually slow single-thread performance.
6. `BigSurface` shows `PerformanceMode = 1`. Per [the driver's README](https://github.com/Xiashangning/BigSurface), value **1 means Recommended**, **2 is Battery Saver**, **3 is Better Performance**, **4 is Best Performance**. The driver author says changing this property had **no observed effect**. `PerformanceMode=1` is not proof of a battery-saver mode, and `IORegistryEntrySetCFProperties` success is not evidence the EC applied mode 3.
7. We restarted the existing `com.rulez777.sl4-tmp3` LaunchDaemon on 2026-11-23 around 08:22; the root service logged a fresh guarded `TMP=3` request with temperature ~41 °C. The CPU's slower benchmark rate **did not recover**. Do not claim TMP3 fixes this slowdown.
8. Reports of Intel Surface Laptop CPUs stuck at ~0.2–0.4 GHz with normal temperatures and apparently correct software performance plans are documented (for examples, [Surface Laptop 5](https://learn.microsoft.com/en-us/answers/questions/5632485/surface-laptop-5-%28i7-1255u%29-randomly-becomes-extre) and [other Surface laptops](https://learn.microsoft.com/en-us/answers/questions/2340496/surface-laptop-4-dropping-cpu-function-to-0-2-gh-e)). Such reports raise the possibility of an EC/firmware/power-delivery clamp (e.g. PROCHOT/power limit), but **do not prove this Surface has the same fault**.

## Confirmed outcome after user-performed reboot

- The user reported physically restarting the Surface to clear the CPU speed cap. The boot time query indicated **2026-11-23 08:54:27 CET**, and both macOS and Desktop Commander returned online.
- With AC connected, battery held at **52% / not charging**, `lowpowermode=0`, and `CPU_Speed_Limit=100` unchanged, the **same 250,000-round** PBKDF2-HMAC-SHA256 benchmark improved from **1.18 s before reboot** to **0.21 s after reboot** (**5.62× faster**). Counter cycles per CPU-second proxy moved from **582.2 MHz** to **3413.0 MHz**; these are approximate counter ratios, not calibrated instantaneous CPU frequency.
- Repeating the test at 08:56:38 yielded **0.25 s** and approximate **3.19 GHz** proxy. A later same-workload measurement returned **0.19 s**, ~3.59 GHz counter proxy, after the supervised CPU-only thermal probe.
- A safe **30-second CPU-only partial-load test**, 2 workers at 55% duty and stop threshold 80 °C, completed with `TC0D` between **50–55 °C**. There was no new GPU Reset/panic in the immediate check.
- Metal 2, eDP Keep and Softsleep flags remained loaded after reboot; the original TMP3 root daemon and optional AC-reconnect user agent both automatically restarted. The live EFI and Windows bootloader were not touched.
- Recovery occurred **without charging beyond 52%**, and while BigSurface still reported `PerformanceMode=1` (Recommended). This strongly indicates the slowdown was **not** a persistent macOS Low Power Mode setting. It does **not** prove the fault was EC/firmware, nor demonstrate that the AC watcher, TMP3, or Battery Limit caused or cleared it.
- Detailed private-free comparison is generated by `python3 scripts/compare_power_snapshots.py --before <pre-reboot report.json> --after <post-reboot report.json>`. The read-only actual data was saved locally at `~/Downloads/SL4-CPU-RECOVERY-COMPARE-20261123.json` and intentionally not uploaded.
- An ordinary reboot provides a **confirmed recovery action for this incident**, not a preventative hardware fix. Monitor for recurrence, especially after another deep discharge or power-source event, and compare against this same fixed workload.

## Actions performed without EFI or Windows changes

- Read-only battery, XCPM, temperature, software throttle and historical crash diagnostics collected.
- Original TMP3 root daemon restarted once using `launchctl kickstart -k system/com.rulez777.sl4-tmp3`, preserving its existing source/LaunchDaemon. Neither firmware controls nor kexts were replaced.
- On the verified Mac, installed **user-level** `com.rulez777.sl4-ac-retry` LaunchAgent (logs in `~/Library/Logs/SL4-AC-Retry.log`). It waits for 3 consistent battery-to-AC samples with a 5-minute cooldown, confirms the exact Surface ACPI IDs and the installed TMP3 service manifest, checks CPU temperature below 75 °C, then asks the **existing** root service to restart. It does not ask for mode 4 or write directly to EC, EFI, NVRAM or CPU limit registers. **Its effect on future AC reconnections has not yet been physically measured.**
- All safety logic has portable state-machine unit tests; a user-level LaunchAgent can be stopped and removed without affecting the original root TMP3 service.

## Read-only one-line checks

On macOS from repository root: `python3 scripts/audit_power_macos.py --cycles 250000` prints a redacted diagnostic including CPU-cycle/CPU-second proxy. Compare the **same operation on the same machine** after charging and controlled reboot. For read-only service status: `python3 scripts/thermal/sl4_ac_retrigger.py --status`.

To remove the optional user-level AC watcher, with the logged-in macOS user: `python3 scripts/thermal/sl4_ac_retrigger.py --remove --ack DISABLE-AC-RECONNECT-RETRY`. The original root daemon remains installed.

A verified administrator can independently inspect actual CPU clocks with `sudo powermetrics --samplers cpu_power -i 1000 -n 3`. Root privileges were not available in the authorized remote terminal for this diagnostic, so no such `powermetrics` data was collected. Do **not** equate nominal `hw.cpufrequency=3 GHz` with actual clocks.

## Recovery decision tree

- **AC missing / discharging:** physically re-seat the charger, test a correctly rated compatible original supply, avoid hubs/docks while diagnosing. Verify actual `pmset -g batt` and the charger wattage before changing software.
- **AC connected, temperature high / software CPU limit less than 100:** resolve genuine thermal/safety fault and stop demanding tasks. Do not disable thermal or PROCHOT protection.
- **AC connected, charging, cool, CPU limit 100%, CPU cycle proxy severely low:** suspect a *separate* hardware/firmware clamp or incomplete Hackintosh CPU power-state handling. First record the counter baseline and compare after charging and a **physically supervised ordinary cold boot**. If needed, compare with Windows 11 on the **same Surface**, using Task Manager/HWiNFO to observe effective CPU frequency and power-limit warnings; this identifies whether the limitation persists across operating systems.
- **Charge repeatedly stops around 50%:** Microsoft's optional [Surface UEFI Battery Limit](https://learn.microsoft.com/en-us/surface/battery-limit) can intentionally cap charging at ~50%. It does not by itself establish the cause of CPU slowdown. Inspect UEFI only with a reliable rollback/boot path, and change the limit only if it conflicts with the owner's intended charging policy.
- **Freeze / reset is needed:** only a person physically at the Surface should perform a supervised restart/firmware power-cycle, with work saved and Windows/macOS recovery available. Remote restart or EC reset could permanently sever the connection; this project explicitly does not automate them.

## Not implemented as a 'fix'

Do not disable BD PROCHOT, spoof thermal sensors, force `PerformanceMode=4`, write CPU MSRs or change Windows `intelppm` service flags just to make a benchmark faster. These can hide electrical faults and create heat or hardware damage. True resolution requires evidence of the active limiting mechanism and at least one successful post-change CPU clock/benchmark result.

Related: [thermal TMP3 limitations](THERMAL-TMP3.md), [battery limit](BATTERY.md), [system-sleep research](SYSTEM-SLEEP-RESEARCH.md), [validation ledger](VALIDATION-20261123.md).
