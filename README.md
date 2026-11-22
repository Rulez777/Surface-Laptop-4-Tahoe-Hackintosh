<p align="center"><img src="assets/hero.svg" alt="Surface Laptop 4 running a macOS-inspired desktop — concept artwork" width="100%"></p>

# Surface Laptop 4 × macOS Tahoe

**A real-world Tiger Lake Hackintosh project: booting macOS Tahoe on Microsoft's Surface Laptop 4.**

![OpenCore](https://img.shields.io/badge/OpenCore-1.0.8-2c80aa?style=flat-square) ![Tahoe](https://img.shields.io/badge/macOS-Tahoe_26.x-5356aa?style=flat-square) ![Status](https://img.shields.io/badge/Status-macOS_booted-237a63?style=flat-square) ![Hardware](https://img.shields.io/badge/CPU-i7--1185G7-414c64?style=flat-square)

> **Status — November 2026:** macOS Tahoe **has booted on the device**, after reaching Recovery and installing to a separate APFS partition alongside Windows 11. This is **not** a claim that every component works, that graphics acceleration is enabled, or that the system has passed extended stability testing.
>
> **The breakthrough:** a Surface-specific legacy RTC0 injection under `\_SB.PC00.LPCB`. Multiple earlier boot attempts stopped shortly after NVMe/APFS initialization. Adding `SSDT-RTC0-SL4.aml` was the final isolated change before Recovery successfully appeared.

## Quick Start

**Read this first:** This is a community project, not a one-click universal installer. **Back up Windows and the Microsoft EFI partition.** Never erase the whole internal SSD. The published EFI is a **sanitized template**: you **must generate your own SMBIOS** and compile the Surface-specific RTC0 table before use.

1. **Confirm your hardware.** This work was done on **Surface Laptop 4 (Intel), i7-1185G7, Iris Xe 96 EU (`8086:9A49`)**, with the laptop's `\_SB.PC00.LPCB` ACPI path. Other Surface variants — notably AMD versions — are not validated. Check your OEM ACPI first.
2. **Download this repository** and extract it on a Windows PC with Python 3 installed. Download **OpenCore 1.0.8 RELEASE** from [acidanthera](https://github.com/acidanthera/OpenCorePkg/releases/tag/1.0.8) and extract it to `Downloads\OC108` (the RTC sample is under `Docs/AcpiSamples/Binaries/SSDT-RTC0.aml`).
3. **Generate unique SMBIOS identifiers** with [GenSMBIOS](https://github.com/corpnewt/GenSMBIOS) for the tested `MacBookPro16,2` profile. Do **not** reuse anyone else's serial, MLB, UUID or ROM. Keep them out of GitHub.
4. **Finalize the EFI** from a PowerShell window in the extracted project directory. Replace the four example placeholders in this **single-line** command with your freshly generated values:

   ```powershell
   py -3 scripts/finalize_efi.py --sample "$HOME\Downloads\OC108\Docs\AcpiSamples\Binaries\SSDT-RTC0.aml" --serial "YOUR_UNIQUE_SERIAL" --mlb "YOUR_UNIQUE_MLB" --uuid "YOUR_UNIQUE_UUID" --rom "YOUR_12_HEX_CHAR_ROM" --output EFI-output
   ```

5. **Validate OpenCore 1.0.8** before copying the result to USB. From the project directory:

   ```powershell
   & "$HOME\Downloads\OC108\Utilities\ocvalidate\ocvalidate.exe" "EFI-output\EFI\OC\config.plist"
   ```

   Expect `No issues found`. Check that `EFI-output\EFI\OC\ACPI\SSDT-RTC0-SL4.aml` exists. If the validator lives elsewhere, locate it within the **same OpenCore 1.0.8 release**.
6. **Prepare a dedicated GPT USB** with a ~2 GiB **FAT32** volume (e.g. `MACOS-OC`) and a larger **exFAT** volume (e.g. `SL4DATA`). Copy the **contents** of `EFI-output` to FAT32 so the structure contains `EFI/BOOT/BOOTx64.efi` and `EFI/OC/config.plist`. The FAT32 volume also holds `com.apple.recovery.boot/BaseSystem.dmg` and `BaseSystem.chunklist`, downloaded from Apple via OpenCore's [`macrecovery.py`](https://github.com/acidanthera/OpenCorePkg/tree/master/Utilities/macrecovery). Do not put the full installer package on FAT32: it exceeds FAT32's 4 GiB limit.
7. **Obtain the full macOS installer directly from Apple.** Place `InstallAssistant.pkg`, the Apple Recovery files, and the upstream [`UnPlugged.command`](https://github.com/corpnewt/UnPlugged) on `SL4DATA`. Obtain a Tahoe version supported by your WhateverXe release; verify downloads and versions. **No Apple installers are hosted here.**
8. Boot the Surface from USB (**Volume Down while powering on**, or via Surface UEFI boot selection), choose **`macOS Base System (External)`** in OpenCore. In Recovery, verify your storage with `diskutil list`; launch `bash /Volumes/SL4DATA/UnPlugged.command` after confirming the exFAT volume is mounted. If using UnPlugged, choose **only a dedicated APFS macOS volume**, then read its task summary carefully. Do not select or erase the Windows volume or the Microsoft EFI partition.
9. During restarts continue booting from the USB OpenCore menu and select the macOS installer/installed macOS entry as needed. **Keep the known-good USB and backup EFI.** Do not copy or replace the Windows EFI until you understand the boot chain.

If you only need the key RTC0 fix for an existing OpenCore setup, skip to [The breakthrough](#the-breakthrough-the-surface-rtc0-fix).

## The tested machine

| Component | Hardware / approach |
|---|---|
| Laptop | Microsoft Surface Laptop 4 (Intel edition) |
| CPU | Intel Core i7-1185G7 (Tiger Lake-UP3) |
| Graphics | Intel Iris Xe, 96 EUs, PCI `8086:9A49` |
| RAM | 16 GB |
| SSD | Samsung PM991 256 GB, with Windows 11 on a separate partition |
| OpenCore | 1.0.8 |
| Graphics boot stack | WhateverXe 0.8.3 + Lilu 1.7.2; `-wex-noaccel` for first boot |
| USB stack | USBToolBox + UTBMap; Tahoe-matched A0ED injector |
| macOS | Tahoe 26.x; tested installation target Tahoe 26.7.1 |
| Firmware caveat | Surface-specific ACPI, `\_SB.PC00.LPCB` rather than `\_SB.PCI0.LPCB` |

## Hardware status

| Component | Status | Notes |
|---|---|---|
| Booting Tahoe | **Booted** | Device owner reached Recovery GUI and subsequently macOS Tahoe. |
| Windows 11 dual-boot layout | **Partitions preserved** | Windows remained on its original partition during APFS creation; independent repeated Windows boot verification not yet documented. |
| Iris Xe display output | **Basic output** | GUI displayed; full Metal acceleration **not verified**. |
| WhateverXe Graphics system component | **Not verified** | Post-install graphics package and acceleration require separate testing. |
| Built-in keyboard / trackpad | **Unknown** | Surface Aggregator Module input may need model-specific drivers. No confirmed BigSurface Laptop 4 support here. |
| Touchscreen / pen | **Unknown** | Do not assume functionality. |
| Wi-Fi / Bluetooth | **Not verified** | Kexts may be present but were not enabled for the initial successful boot. |
| Audio | **Not verified** | AppleALC was disabled for initial boot. |
| Sleep, battery, brightness, cameras | **Not verified** | Require platform-specific testing. |
| Samsung PM991 NVMe stability | **Risk / unverified** | Initialization succeeded in boot logs. Reliable APFS writes, TRIM and long-term stability still require testing. |

## The breakthrough: the Surface RTC0 fix

This was not solved by changing random USB or CPU flags. After testing multiple Tahoe and Sequoia Recovery versions and graphics flags, the laptop repeatedly stopped at a verbose screen shortly after `apfs_module_start`, with a **nonfatal** USBToolBox XHCI message last. A different USB stick, a Tahoe-specific USB controller injector and borrowed Booter memory quirks did not resolve it.

A Windows export of `HKLM\HARDWARE\ACPI` revealed **12 OEM ACPI tables**. The Surface firmware has a time-and-alarm device with HID `ACPI000E` at `\_SB.SRTC`, but the exported tables contained no conventional `PNP0B00` RTC. Its LPC path is `\_SB.PC00.LPCB`, not `\_SB.PCI0.LPCB` as in the generic RTC sample.

**What changed:** the official OpenCore 1.0.8 `SSDT-RTC0.aml` was patched in its AML body to replace the four ASCII bytes `PCI0` → `PC00` (same length), its ACPI 8-bit checksum was recomputed, and the result was added to `ACPI -> Add` as `SSDT-RTC0-SL4.aml` with `Enabled = True`. The PNP0B00 EISA ID is represented by `41 D0 0B 00` in AML, not literal ASCII text. The included `scripts/finalize_efi.py` reproduces this transformation and validates the output.

The user then successfully reached macOS Recovery; subsequently they reported booting into Tahoe. **This is a strong single-change correlation, not a controlled demonstration that RTC0 is the only possible fix for every Surface Laptop 4.**

Do not add an unmodified `SSDT-RTC0.aml`: its `PCI0.LPCB` scope does not match the tested Surface's `PC00.LPCB` path.

## What's in this repository?

```text
EFI-template/EFI/       Sanitized snapshot of the pre-RTC0 working OpenCore base
scripts/finalize_efi.py Generate RTC0-SL4, personal SMBIOS, and complete EFI-output
assets/hero.svg         Project concept artwork (not a photograph of the tested setup)
docs/BOOT-STORY.md      What worked, what failed, and how to reproduce it
docs/SAFETY.md          Windows dual-boot precautions and recovery notes
```

The template includes third-party kexts/drivers from their respective upstream projects. Their versions are pinned to the recorded successful boot path; **newer is not automatically more reliable**. Review upstream licenses and update cautiously, one component at a time. The `EFI-template` is not boot-ready until finalized.

## Boot flags and important limitations

The first-boot configuration contains:

```text
-v keepsyms=1 debug=0x100 npci=0x2000 -allow3d -disablegfxfirmware -wex-noaccel
```

WhateverGreen is disabled (not meant to be enabled together with WhateverXe here); the earlier X-STATION V2 Booter memory quirk experiment was **reverted** to Surface's MAT=1 configuration before the successful RTC0 test. Several bundled Wi-Fi/audio/Bluetooth kexts are intentionally disabled. **Do not enable everything at once.**

The project uses an experimental Tiger Lake graphics stack and a problematic Samsung PM991 SSD. A successful GUI boot does **not** establish Metal acceleration, stable suspend/resume, reliable NVMe writes, keyboard, touchpad, or built-in Wi-Fi support.

## Credits & references

- [OpenCorePkg](https://github.com/acidanthera/OpenCorePkg) — OpenCore and official ACPI samples
- [Dortania ACPI Guide](https://dortania.github.io/Getting-Started-With-ACPI/) — RTC/AWAC concepts
- [WhateverXe](https://github.com/b00t0x/WhateverXe) — Iris Xe support
- [AMFIAnchor](https://github.com/b00t0x/AMFIAnchor) — AMFI support
- [Lilu](https://github.com/acidanthera/Lilu), [VirtualSMC](https://github.com/acidanthera/VirtualSMC)
- [USBToolBox](https://github.com/USBToolBox/kext) — USB mapping stack
- [UnPlugged](https://github.com/corpnewt/UnPlugged) — Recovery installer workflow
- [X-STATION V2](https://github.com/Akariayumu/xstation-v2-hackintosh) — valuable Tiger Lake reference, but **do not blindly copy its Booter memory quirks**

Community project. Not affiliated with Apple or Microsoft. All product names and trademarks belong to their respective owners. macOS installation on non-Apple hardware may be inconsistent with Apple's software license agreement; review the license applicable in your jurisdiction. You are responsible for backups and any modifications to your hardware.

*Hero image is illustrative artwork, not a screenshot or a claim of tested graphics acceleration.*