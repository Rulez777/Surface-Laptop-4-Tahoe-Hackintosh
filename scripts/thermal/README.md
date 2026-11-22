# Surface Laptop 4 Intel — CPU temperature and thermal profiles

**macOS Tahoe 26.7.1 · VirtualSMC / SMCProcessor 1.3.8 · BigSurface 1.2.0**

## Hardware status

| Component | Status |
| --- | --- |
| Battery charge percentage | **Working** |
| CPU die SMC temperature `TC0D` | **Working** |
| Surface performance profile request | **Working at IOKit API level**; EC acknowledgement unavailable |
| Fan operation | **Working** |
| Automatic fan RPM override | **Not available through documented SL4 Intel interface** |
| Automatic CPU-temperature-based profile switching | **Disabled for safety** |

macOS Tahoe and OpenCore 1.0.8 load `SMCProcessor.kext 1.3.8`. The `TC0D` sensor returns CPU die temperature in °C.

## Cooling interface on the SL4

The Linux Surface registry maps SL4 Intel `MSHW0250` to the SL3/SL4 group with `ssam_node_tmp_perf_profile`, **without** the `has_fan` and `ssam_node_fan_speed` interfaces exposed on SL5.

TMP mode indices: `1` — Normal (Balanced), `2` — Battery Saver (Low Power), `3` — Better Performance (Balanced Performance), `4` — Best Performance.

BigSurface `SurfaceBatteryDriver` has an original `PerformanceMode=1` configuration key; its wake code reapplies that configured value. A one-time mode `3` request can be lost after sleeping or rebooting. The `ioreg` property reflects the **configured** value, not an EC readback of the current mode.

A Surface Laptop 4 Intel Linux report describes thermal throttling with poor fan response in the **low-power mode (TMP 2)**. This does **not** prove the same effect for TMP 1 on macOS. Better/Best performance profiles can run fans faster but can also increase the CPU's power and heat.

**No verified path to "100% fan at 80 °C" exists for the Surface Laptop 4 Intel. The original mode-3 → mode-4 on 80 °C policy is withdrawn.** Never use TMP 4 as a thermal failsafe.

Sources:
- [Microsoft Surface fan behavior](https://support.microsoft.com/en-us/surface/performance/fan-behavior-and-fan-noise-in-a-surface-device)
- [Linux Surface Laptop 4 Intel throttling report](https://github.com/linux-surface/linux-surface/issues/561)
- [Linux Surface device registry](https://github.com/torvalds/linux/blob/master/drivers/platform/surface/surface_aggregator_registry.c)
- [Linux Surface mode implementation](https://github.com/torvalds/linux/blob/master/drivers/platform/surface/surface_platform_profile.c)
- [BigSurface source](https://github.com/Xiashangning/BigSurface)

## Monitor and diagnostic commands

**Read-only CPU temperature:**

```bash
python3 "$HOME/Downloads/sl4_thermal_guard.py" --probe
```

**Read-only CPU temperature, 12 samples (about 1 minute):**

```bash
python3 "$HOME/Downloads/sl4_thermal_guard.py" --monitor --samples 12
```

**Read-only loaded profile configuration and macOS thermal limits:**

```bash
ioreg -r -c SurfaceBatteryDriver -lw0 | grep -E 'PerformanceMode'; pmset -g therm
```

No fan command is sent by `--probe` or `--monitor`; `writes=OFF`. A momentary temperature spike to 88 °C does not, by itself, prove throttling; check CPU power and thermal limit samples separately.

## Controlled one-shot experiment

**Only if the CPU is cooler than 80 °C and the previous manual mode 3 test produced audible fan operation.** A new explicit test is needed to measure fan response; no CPU stress test.

Download updated monitor:

```bash
curl -fL --retry 3 "https://raw.githubusercontent.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/experimental/sl4-thermal-guard/scripts/thermal/sl4_thermal_guard.py" -o "$HOME/Downloads/sl4_thermal_guard.py"
```

Then request the already used `TMP 3` profile once:

```bash
sudo python3 "$HOME/Downloads/sl4_thermal_guard.py" --set-profile 3 --ack SET-TMP-3-NOT-FAN-RPM
```

The script checks the real CPU die temperature immediately before sending, refuses a request at `>=80 °C`, and sends only one `PerformanceMode=3` request via BigSurface. It does **not** request maximum fan speed, run a persistent daemon or change EFI. IOKit success does **not** verify EC acceptance; `ioreg` may still show 1. Stop if unstable, unusually hot, or the fan does not respond as expected.

### Unsafe automatic control disabled

`--control` exits with an explicit error before contacting the EC. The prior automatic `3 → 4` transition at 80 °C risked increasing CPU heat without increasing fan speed. Profile persistence, CPU power limits, fan RPM and EC acknowledgement remain unresolved.

## TMP 3 at macOS startup and resume

**Optional LaunchDaemon:** [macOS installation, status and removal](TMP3-AUTOSTART-RU.md).

The service requests only `PerformanceMode=3` after startup or detected system wake, with a fresh CPU die reading below 80 °C. It does **not** request `TMP=4`, continuously write to the EC, alter EFI or bypass CPU thermal protection. The service is **not installed automatically**. Fan response on resume still needs a physical verification.

## SMCProcessor installation

[macOS Tahoe driver installation and rollback](INSTALL-SMCPROCESSOR-RU.md)

Existing installed `SMCProcessor.kext 1.3.8` works with VirtualSMC 1.3.8 and `TC0D`; no reinstallation required.

## Verification

GitHub CI syntax and synthetic tests cover temperature parsing, no-write monitoring, safety refusal and the reversible SMCProcessor installer. CI checks the official `VirtualSMC-1.3.8-RELEASE.zip` format. Actual fan RPM and EC acknowledgment are not available.
