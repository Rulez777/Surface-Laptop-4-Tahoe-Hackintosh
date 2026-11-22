# Surface Laptop 4 (Tiger Lake) — Tahoe Recovery GUI reached after SSDT-RTC0 injection

**Status:** I subsequently booted macOS Tahoe after the RTC0 Recovery breakthrough. Metal acceleration, input devices, sleep and long-term dual-boot stability remain unverified.

## Hardware and software

- Microsoft Surface Laptop 4 (Intel variant), Intel Core i7-1185G7, Tiger Lake-UP3, 16 GiB RAM.
- Intel Iris Xe 96 EU, PCI ID `8086:9A49`.
- Internal Samsung PM991 256 GB, PCI vendor/device `144D:A809`; Windows 11 installed. **Do not erase or repartition without a separately verified procedure and backup.**
- USB: Kingston DataTraveler 2.0, ~28.84 GiB, GPT; FAT32 `MACOS-OC` for OpenCore/Recovery, exFAT `SL4DATA` for full InstallAssistant.pkg.
- OpenCore 1.0.8; Tahoe 26.7.1 target. Verified Apple BaseSystem.dmg by signed chunklist, plus locally SHA-256-checked InstallAssistant.pkg.
- Recovery GUI confirmed only after adding Surface-specific RTC0 SSDT on top of the previously prepared Tahoe OpenCore configuration.

## Important finding from OEM ACPI (read from `HKLM\\HARDWARE\\ACPI`)

A Windows registry export (`reg export HKLM\\HARDWARE\\ACPI`) was decoded into 12 ACPI tables. In the OEM tables, the Surface exposes the Time and Alarm device with ACPI hardware ID `ACPI000E` at `\\_SB.SRTC`, but no legacy RTC device with hardware ID `PNP0B00` was found. LPC is at `\\_SB.PC00.LPCB` (rather than the generic OpenCore sample path `\\_SB.PCI0.LPCB`).

**Working change in the most recent test:** add a legacy RTC0 SSDT *under the Surface-specific LPC path* and enable it in `ACPI -> Add`:

- Base: OpenCore 1.0.8 `Docs/AcpiSamples/Binaries/SSDT-RTC0.aml`.
- Transform the four-byte AML name `PCI0` to `PC00` (same length) in the AML body; do **not** alter the OEM DSDT or rename the actual OEM ACPI000E device.
- Recalculate the ACPI table's 8-bit checksum after the binary change.
- Write the generated table as `EFI/OC/ACPI/SSDT-RTC0-SL4.aml`.
- Append `{"Comment":"Surface Laptop 4: OEM ACPI000E / no PNP0B00; macOS-only RTC0", "Enabled":true, "Path":"SSDT-RTC0-SL4.aml"}` to OpenCore `config.plist` `ACPI -> Add`.
- Validate `config.plist` with `ocvalidate.exe` **OpenCore 1.0.8**.

A known initial patcher error searched the EISA identifier for `PNP0B00` in wrong endianness. The correct ACPI AML encoding is the byte sequence **`41 D0 0B 00`**. The corrected **FIX2** script checks this, the sample structure, ACPI header length and checksum, and identity of the intended Kingston USB before writing.

## Timeline: what did not reach Recovery

1. Tahoe Recovery and Monterey Recovery, numerous CPU, NVMe, XHCI, and graphics parameter variations, did not show GUI on the earlier VendorCo USB. A separate problem caused the VendorCo FAT32 volume to become RAW, so it was replaced.
2. Clean Kingston USB was created with the existing tested EFI and Tahoe Recovery. The system still stopped on verbose boot output after NVMe/APFS setup, frequently with a nonfatal USBToolBox XHCI message displayed last.
3. A Tahoe `8086:A0ED` AppleUSBXHCISPT matching injector was enabled. It did **not** independently resolve the GUI issue.
4. Four X-STATION V2 Booter quirks were tested, and GUI still did not appear. They were **restored** before the RTC0 test because X-STATION and Surface firmware have different MAT support.
5. OEM ACPI analysis found `ACPI000E` without `PNP0B00`; the RTC0 table was generated with the correct `PC00.LPCB` path. I then reached the Tahoe Recovery GUI.

**Interpretation:** this is a compelling single-change correlation, not a formally controlled proof that RTC0 was the sole cause. Its exact effect and generality to other BIOS revisions and models need independent replication.

## How to reproduce on another Surface Laptop 4

**Prerequisites:** an existing functional OpenCore 1.0.8 USB for Tahoe that reaches kernel startup, a complete backup of the EFI, OpenCore `ocvalidate.exe` and the OpenCore `SSDT-RTC0.aml` sample. Validate that the target laptop really has `\\_SB.PC00.LPCB`, a Time and Alarm `ACPI000E` device, and no usable `PNP0B00`, before using this tailored SSDT. ACPI tables differ by firmware and CPU model; never blindly apply this fix to all Surface devices.

1. Save a complete backup of the existing USB EFI outside the USB.
2. Generate the modified AML from the official OpenCore `SSDT-RTC0.aml` sample, replacing `PCI0` -> `PC00` *in the table body*, then recomputing the ACPI checksum. The included `SL4-RTC0-Surface.py` (FIX2) automates this with input checks.
3. Register `SSDT-RTC0-SL4.aml` in `ACPI -> Add` as enabled.
4. Validate `config.plist` with the matching OpenCore version of `ocvalidate` and verify the file hash, then boot `macOS Base System (External)` via OpenCore.
5. Report exact model, BIOS version, EFI driver/kext versions, screenshots/logs, and whether macOS eventually installs and boots with graphics acceleration.

**Windows PowerShell 5.1 / 7, single-line examples:**

```powershell
py -3 "$HOME\Downloads\SL4-RTC0-SURFACE-FIX2\SL4-RTC0-Surface.py" --mode inspect --disk 1
```

```powershell
py -3 "$HOME\Downloads\SL4-RTC0-SURFACE-FIX2\SL4-RTC0-Surface.py" --mode apply --disk 1
```

The FIX2 patcher has hard-coded identity and checksum requirements for the *specific* Kingston USB and existing EFI. For other machines, adapt and review the code, hashes, and ACPI paths before applying. Do not disable safety checks just to make it run.

## Current known-good configuration notes

- OpenCore 1.0.8, `MacBookPro16,2` SMBIOS; do **not** publish actual serial/MLB/ROM/UUID from a live `config.plist`.
- WhateverXe 0.8.3 with `-allow3d -disablegfxfirmware -wex-noaccel`; WhateverGreen disabled. These were not sufficient on their own.
- USBToolBox/UTBMap present; Monterey-only mapping disabled on Tahoe; Tahoe A0ED matching injector enabled as of the last pre-RTC0 test.
- Surface-specific OEM `SsdtPld` ACPI deletion enabled (to avoid a previously observed `RHUB.HS09` failure).
- The earlier X-STATION Booter-memory quirks were rolled back to the Surface configuration (firmware previously reported MAT=1).
- The exact post-RTC0 SHA-256 of the live `config.plist` was not independently recorded after the successful test.

## Privacy, licensing and caveats

This report is sanitized: **do not post** the test machine’s raw OEM registry export (which may disclose platform particulars), complete live `config.plist` (SMBIOS serial/MLB/ROM/UUID), Windows machine logs with personal paths, or redistributable third-party kext/Apple installer binaries unless permitted by their licenses. Publish the small patch and documentation instead. The RTC0 change established successful **Recovery GUI entry**; Tahoe subsequently booted. Long-term stability and peripheral support still require testing.

References: [OpenCorePkg](https://github.com/acidanthera/OpenCorePkg), [Dortania ACPI guide](https://dortania.github.io/Getting-Started-With-ACPI/), [WhateverXe](https://github.com/b00t0x/WhateverXe), [X-STATION V2](https://github.com/Akariayumu/xstation-v2-hackintosh).