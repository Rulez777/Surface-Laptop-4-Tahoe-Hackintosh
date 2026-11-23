# Battery and charging observations — Surface Laptop 4 Intel (2026-11-23)

**Scope:** read-only diagnostics on the tested i7-1185G7, macOS Tahoe 26.7.1 machine. No UEFI firmware, charging profile, battery driver or EC settings were modified.

## Observed behavior

- The Surface switched from battery power to AC; charging was reported near 49%.
- Later, macOS showed AC connected at **52%**, **not charging**. `system_profiler SPPowerDataType` reported `Condition: Normal`, cycle count 110, `Fully Charged: No`, `Charging: No`.
- A contemporaneous `AppleSmartBattery` reading reported `ExternalConnected=Yes`, `IsCharging=No`, `FullyCharged=No`, `InstantAmperage=0`, current capacity **2811** and max capacity **5626** in SMC-reported units. This corresponds to roughly half of the present max battery capacity, despite UI rounding to 52%.
- `PermanentFailureStatus=0` was visible. This alone does not rule out other charging or firmware issues.
- No battery serial, internal identifier, device MAC, SMBIOS or full IORegistry dump is included in this document.

## Likely cause (not yet confirmed)

Microsoft's official [Surface Battery Limit documentation](https://learn.microsoft.com/en-us/surface/battery-limit) says that this optional UEFI setting intentionally stops charging at about **50%**. [Microsoft's troubleshooting article](https://support.microsoft.com/en-us/surface/battery/surface-battery-won-t-charge-or-surface-won-t-run-on-battery) likewise advises checking Battery Limit if charge stalls near 50%.

This is **consistent** with the data but no UEFI setting was inspected, and macOS's third-party BigSurface battery integration may report charge states differently. Do not infer a failed battery, charger or TMP3 malfunction from this snapshot. **Do not disable Battery Limit automatically**: the owner may intend to preserve battery longevity while connected to AC.

## Remaining verification

Only during a physically supervised firmware visit: determine if Battery Limit Mode is enabled in Surface UEFI, confirm the intended charging policy, and compare charging status with Windows without altering BCD, boot order or EFI. If disabled and charging still consistently halts at half capacity, separately inspect adapter capability, Surface firmware/battery health and macOS BigSurface driver reporting. A single 52% reading cannot establish a reliable charge profile.

For an entirely read-only current snapshot, run `pmset -g batt` and view the selected non-sensitive `AppleSmartBattery` properties. Avoid copying complete IORegistry output into public issues.

Battery charge limits are independent of full system S3/S0ix support. See [deep sleep research](SYSTEM-SLEEP-RESEARCH.md).
