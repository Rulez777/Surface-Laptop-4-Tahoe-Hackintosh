# Surface Laptop 4 Intel — CPU temperature and cooling profiles

**macOS Tahoe 26.7.1 · VirtualSMC 1.3.8 · BigSurface 1.2.0**

## Hardware

| Function | Status |
| --- | --- |
| Battery charge percentage | **Working** |
| Automatic EC fan operation | **Working** |
| Surface TMP performance profile selection | **Working** |
| CPU die SMC temperature key `TC0D` | Requires `SMCProcessor.kext 1.3.8` |
| Independent FAN RPM control | Not available via the documented SL4 interface |
| Automatic temperature-dependent TMP switching | Experimental, **disabled by default** |

Linux registers `MSHW0250` in the Surface Laptop 3/4 profile group with `ssam_node_tmp_perf_profile`. Independent `has_fan` / `ssam_node_fan_speed` support exists for later devices, not in the SL4 Intel registry.

**`PerformanceMode=4` is not a 100% fan-speed command.** It also changes CPU performance and can increase heat. Fan operation remains managed by the embedded controller (EC).

## CPU sensor: SMCProcessor 1.3.8

VirtualSMC provides the AppleSMC service. SMCProcessor adds the `TC0D` CPU die temperature key if the thermal hardware counters are available. An absent plugin produces `SMC result 0x84` (key not found).

**macOS-native installation (no USB, no Windows session):**

[Installation, inspection, backups and rollback](INSTALL-SMCPROCESSOR-RU.md)

Implementation: `install_smcprocessor_macos.py`. The script adds **only** `SMCProcessor.kext` to the existing internal OpenCore ESP after a full `EFI/OC` backup and `ocvalidate 1.0.8` validation. It preserves existing VirtualSMC, BigSurface, Metal 2, Bluetooth, keyboard, trackpad, Wi-Fi, Windows Boot Manager and boot configuration.

## Temperature probe and monitor

Run only after `SMCProcessor.kext` is installed and loaded.

**Read-only CPU temperature probe:**

```bash
python3 "$HOME/Downloads/sl4_thermal_guard.py" --probe
```

**Read-only one-minute monitor:**

```bash
python3 "$HOME/Downloads/sl4_thermal_guard.py" --monitor --samples 12
```

The monitor requires a valid `TC0D` key with `sp78` type. Invalid, missing and implausible readings terminate the probe. Battery temperature is not a replacement for CPU die temperature.

### Experimental thermal policy

| CPU die temperature | Proposed TMP profile |
| --- | --- |
| Below 80 °C | `3` — Better Performance |
| At least 80 °C for two consecutive 5-second samples | `4` — Best Performance |
| At most 72 °C for 60 seconds | `3` — Better Performance |
| At least 90 °C | `1` — Recommended |

At high temperature, a performance profile is **not equivalent to guaranteed fan acceleration**; `TMP=4` may raise heat output. This policy is experimental, **not** a substitute for native thermal protection and **not installed as a background service**. The `--control` mode is deliberately disabled unless invoked with explicit acknowledgement. No automatic usage is recommended before hardware validation.

## Quality checks

GitHub Actions runs Python syntax checks and synthetic temperature-policy, EFI staging, rollback and error handling tests. The real `VirtualSMC-1.3.8-RELEASE.zip` is downloaded and checked for plugin identity and binary format in CI. These software tests do not verify CPU die readings, reboot compatibility or fan RPM on physical hardware.

## References

[VirtualSMC](https://github.com/acidanthera/VirtualSMC) · [Linux device registry](https://github.com/torvalds/linux/blob/master/drivers/platform/surface/surface_aggregator_registry.c) · [Linux platform profile](https://github.com/torvalds/linux/blob/master/drivers/platform/surface/surface_platform_profile.c)
