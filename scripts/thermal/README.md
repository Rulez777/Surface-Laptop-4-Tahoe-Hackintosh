# Surface Laptop 4 Intel: experimental thermal guardian (macOS Tahoe)

**Current status: SOURCE + SYNTHETIC TESTS ONLY. NOT A PROVEN AUTOMATIC FAN CONTROLLER.**

The test owner reports:
- SL4 Intel `i7-1185G7`, `MSHW0250`, Tahoe 26.7.1; Windows fan runs.
- BigSurface keyboard/trackpad and **battery charge reporting work**.
- SurfaceBatteryDriver is active, initially `PerformanceMode=1`.
- An explicit `PerformanceMode=4` then `3` IOKit request returned success and the user subsequently heard the fan. **Actual RPM, delivered EC profile and temperature response have not been measured.**
- During Steam game download the laptop previously overheated/froze. Do **not** stress-test to validate this code.

## Why there is no literal "100% fan at 80 C" mode on SL4

Linux's `drivers/platform/surface/surface_aggregator_registry.c` maps SL4 Intel `MSHW0250` to the SL3/SL4 group: `ssam_node_tmp_perf_profile`. It deliberately omits `ssam_node_fan_speed` and the `has_fan` property available for SL5. Linux's `surface_platform_profile.c` maps this to TMP profiles **1 (normal), 2 (battery saving), 3 (better performance), 4 (best performance)**. Those are NOT raw fan RPM commands. On the SL4 the embedded controller (EC) decides real fan speed. BigSurface sends TMP command 0x03, but its `SurfaceBatteryDriver::setProperties` returns IOKit success even when its internal SSH command fails. **No confirmed fan-speed feedback exists.**

An automatic 80 C -> 4 transition may allow more CPU power and **increase** the temperature; therefore an independent CPU temperature monitor is mandatory and the active mode is disabled by default. The guard **cannot promise maximum fan RPM**.

Sources:
- [Linux hardware registry](https://github.com/torvalds/linux/blob/master/drivers/platform/surface/surface_aggregator_registry.c)
- [Linux Surface performance driver](https://github.com/torvalds/linux/blob/master/drivers/platform/surface/surface_platform_profile.c)
- [SL4 Intel low-performance cooling issue](https://github.com/linux-surface/linux-surface/issues/561)
- [BigSurface](https://github.com/Xiashangning/BigSurface)

## Monitor design

`sl4_thermal_guard.py` uses only the **CPU die `TC0D`** SMC key with type `sp78`, never battery temperature (`TB*`), GPU or CPU proximity (`TC0P`). `SMCProcessor.kext` may be necessary; the previously uploaded `kmutil` output had `VirtualSMC` but did not confirm `SMCProcessor`. If `TC0D` is absent, monitoring **refuses to run** rather than guess a temperature.

- Starting state: `TMP 3` (Better Performance), not battery saver.
- `>= 80 C` for **2 consecutive 5-s samples**: policy *proposes* `TMP 4` (not full RPM).
- `<= 72 C` continuously for **60 seconds**: proposes return to `TMP 3`.
- `>= 90 C`: proposes `TMP 1` (recommended, NOT `TMP 2` battery saver) as a heat-reducing fallback; wait for cooldown.
- Invalid, implausible or missing temperature -> **no new profile request**; after two missed readings, if the program had requested TMP 4, it requests TMP 3; after three consecutive errors it aborts.

These are experimental software policy thresholds, **not established safe hardware limits**, and they do not replace the CPU's built-in protections. This program does not edit EFI, kexts, NVRAM, battery charging, BIOS or Windows. It is NOT installed as a persistent daemon, and cannot be an independent thermal safety system if macOS freezes.

### 1. Read-only diagnostics — recommended first

From a normal user session (requires Python 3 / Apple Command Line Tools already installed):

```bash
curl -fL --retry 3 "https://raw.githubusercontent.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/experimental/sl4-thermal-guard/scripts/thermal/sl4_thermal_guard.py" -o "$HOME/Downloads/sl4_thermal_guard.py" && python3 "$HOME/Downloads/sl4_thermal_guard.py" --probe
```

Expected on compatible SMC: `Validated SMC CPU DIE TC0D = XX.XX C`. If `TC0D missing` or `AppleSMC open failed`, **STOP**. This is information, not permission to install another kext without a separate backup/review.

### 2. Read-only monitor (12 samples = 1 minute)

```bash
python3 "$HOME/Downloads/sl4_thermal_guard.py" --monitor --samples 12
```

This logs CPU die readings and the **proposed** profile, but **never changes the EC**.

### 3. Optional hardware trial — DO NOT RUN UNTIL SENSOR VALIDATED

The command below is **NOT recommended for unattended operation**. The software is experimental and no physical RPM feedback exists.

```bash
sudo python3 "$HOME/Downloads/sl4_thermal_guard.py" --control --ack I-UNDERSTAND-TMP-IS-NOT-FAN-RPM --samples 12
```

This does not install a LaunchDaemon and exits after 12 readings. On entry, the program may request TMP 3 (the owner's currently functional profile); it must be run only on cool hardware with a verified die sensor and independent Windows recovery. Leave an external keyboard/mouse. At sustained >=80 C, it may request TMP 4, and at >=90 C TMP 1. **This is a profile controller, not a 100% fan command.** Do not run Steam or deliberately heat the laptop for testing.

Restore currently preferred profile `TMP 3` with the previously tested `sl4fan 3` command in the same shell where that function was defined; after a fresh shell session the function must be redefined. Do not assume `ioreg` reflects actual runtime EC profile.

## Verification and limitations

This first revision has not been executed on the owner's Tahoe system. It has synthetic policy tests in `test_sl4_thermal_guard.py`. The CLI ABI and SMC `TC0D` availability **must be verified on actual SL4 hardware** before enabling automatic TMP control. macOS Tahoe `powermetrics --samplers smc` is not reliable as a source across configurations, so it is deliberately not a dependency here.

**Security:** `--probe` and `--monitor` do not request root or make EC calls. `--control` requires root and a deliberate acknowledgement. The code should be inspected before running, especially the CoreFoundation and AppleSMC IOKit calls.

**Known remaining work:** Confirm `TC0D` from `SMCProcessor`, cross-check actual CPU sensor temperature against Windows under equal idle load, confirm the EC's fan reaction to each TMP mode, and verify protection under reboots/sleep/crashes. Only then consider a persistent service and integration with the normal installer. Battery monitoring is already working and must not be replaced.
