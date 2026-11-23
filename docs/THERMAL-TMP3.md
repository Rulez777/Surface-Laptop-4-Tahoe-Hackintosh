# Optional SL4 TMP=3 startup / resume request — experimental

**Status (2026-11-23):** the service is running on the tested Surface Laptop 4 Intel 13.5-inch under macOS Tahoe 26.7.1. Its startup request reaches the existing BigSurface IOKit interface and its live CPU-die sensor passes inspection. **The embedded controller (EC) accepting the request, changing the fan curve or changing fan RPM has not been demonstrated.** This is not a direct fan controller and is not a certified thermal solution.

## Scope and limitations

- Exactly the tested Surface Laptop 4 Intel ACPI identification (`MSHW0250` and `MSHW0084`). Unsupported models are rejected.
- Reads CPU-die sensor `TC0D` via `SMCProcessor.kext`; requires a plausible temperature below 80 °C before making a single TMP=3 request.
- On launch, waits for surface drivers and sends **one** request. Repeats after a detected **true system resume** using the macOS monotonic clock that excludes system sleep. Checks every five seconds; retries only while the request is pending.
- **Does not detect a simple display/backlight wake** as a system resume. System S3/S0ix is not confirmed working on our machine, so this path remains unvalidated.
- Does not auto-switch modes when AC adapter is plugged/unplugged; does not directly edit CPU power limits, fan RPM, OpenCore, macOS boot arguments or Windows settings. The indirect EC effects of TMP=3 remain unverified. Mode 4 is deliberately not used.
- IOKit success only means the request was sent to BigSurface. BigSurface may report success even when an internal EC operation fails. No claim of verified fan actuation is made.

## Source files

- [sl4_thermal_guard.py](../scripts/thermal/sl4_thermal_guard.py) — read-only CPU temperature probe / monitor and guarded manual TMP request.
- [sl4_tmp3_service.py](../scripts/thermal/sl4_tmp3_service.py) — opt-in root LaunchDaemon installer, status, remove, and startup/resume request loop.

They are copied verbatim from the live installed build for reproducibility. Publishing them does **not** mean this service has passed sustained load, power-source-change, real-resume or fan-curve tests.

## Read-only inspection

From a fresh repository clone in macOS Terminal:

```bash
python3 scripts/thermal/sl4_tmp3_service.py --inspect
python3 scripts/thermal/sl4_thermal_guard.py --probe
python3 scripts/thermal/sl4_thermal_guard.py --monitor --samples 6
```

The inspect operation does not write to the EC; it checks hardware identity, CPU sensor and the required sleep clock. The monitor samples every five seconds and does not request any profile changes.

## Optional service installation and rollback

Only on the exact supported machine after creating a system backup. Keep `sl4_tmp3_service.py` and `sl4_thermal_guard.py` in the same directory. From the repository root:

```bash
sudo python3 scripts/thermal/sl4_tmp3_service.py --install --ack INSTALL-SL4-TMP3
python3 scripts/thermal/sl4_tmp3_service.py --status
```

Installation refuses to overwrite an existing service. It places the source under `/Library/Application Support/SL4-TMP3/`, writes `/Library/LaunchDaemons/com.rulez777.sl4-tmp3.plist`, and stores file hashes in a manifest. Logs: `/var/log/sl4-tmp3.log` and `/var/log/sl4-tmp3.error.log`. The service is intentionally opt-in and **not** installed by the general EFI installer.

To remove **only** the owned service and files:

```bash
sudo python3 scripts/thermal/sl4_tmp3_service.py --remove --ack REMOVE-SL4-TMP3
```

This removal is not a hardware EC reset and does not change EFI. Removal refuses if the installed scripts differ from the manifest; investigate before doing any manual cleanup.

## Verified on this machine

- `launchctl` reports `com.rulez777.sl4-tmp3` running after startup.
- Log entries record one TMP=3 request after launch, with CPU-die readings between 43 °C and 73 °C across previous boots. No daemon errors were found in the sampled error log.
- On 2026-11-23, `--inspect` passed and a read-only check read CPU die 49 °C. The current installed source hashes match the manifest.
- **Not verified:** any RPM change, EC receipt, sustained loaded thermals, repeated real S3/S0ix wake, change of power source, battery drain or any safety benefit from TMP=3.

Do not replace the platform's built-in thermal protection or assume this software prevents overheating. See [sleep status](SLEEP.md) before making changes to macOS sleep settings.
