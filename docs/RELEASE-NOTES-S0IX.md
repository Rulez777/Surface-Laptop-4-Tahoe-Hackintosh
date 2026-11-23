# SL4-S0ix-DMC v0.2.0 beta — Surface Laptop 4 Intel / Tahoe 26.7.1

**First downloadable, fully packaged postinstall release for the tested SL4 system Deep Idle + Intel Tiger Lake DMC combination.**

## Confirmed on the test machine

- Microsoft Surface Laptop 4 Intel 13.5", i7-1185G7, Iris Xe PCI 8086:9A49, macOS Tahoe 26.7.1, OpenCore 1.0.8.
- Intel Tiger Lake **DMC 2.12** program injected via custom WhateverXe 0.8.3, with DMC initialization and post-wake readback verified.
- **S0ixStandby 0.5.8** + **SSDT-DEEPIDLE.aml**, `IOPMDeepIdleSupported = Yes`.
- **Two genuine system Deep Idle → RTC wake cycles**, **8 seconds** and **71 seconds**, on AC, without a kernel reboot. Confirmed by `pmset`, `kern.sleeptime` and `machdep.xcpm.deep_idle_count=2`.
- Immediately after wake: Iris Xe **Metal 2**, 2496×1664 internal display online, DMC wake verification, normal CPU-speed limit. **A delayed RCS GPU Reset was recorded at 13:08:40 CET.** A similar hang occurred before S0ix, so causation is unresolved. See [GPU reset investigation](POST-S0IX-GPU-RCS-RESET-20261123.md).
- Owner separately confirms sleep is working. **This does not certify long-duration sleep, battery-only operation or reliable wake from closed lid across all users.** Platform LPIT/SLP_S0 residency was **0 μs and PC10 0%** in the available snapshot, so energy efficiency remains unproven.

## Downloads

**Asset:** `SL4-S0ix-DMC-0.2.0-beta.zip`, with these components:

- Executable installer `install.py` with hardware/OS/driver version checks, OpenCore validation, complete private OC backup, on-ESP recovery config and rollback.
- Precompiled **WhateverXe-SL4-S0IX-DMC.kext**. Verified against the exact code/data of the working device; only non-semantic Mach-O build UUID varies.
- `S0ixStandby.kext` 0.5.8, `SSDT-DEEPIDLE.aml`, `ocvalidate` 1.0.8.
- Unmodified Intel `tgl_dmc_ver2_12.bin`, bundle SHA-256 manifest, README quick start and original third-party license notices.

The archive **does not include `EFI/OC/config.plist`, private serials/SMBIOS, Windows Boot Manager or Windows data**.

## Quick installation

This is a **postinstall add-on, not a clean macOS installer**. Start with an already booting Tahoe 26.7.1 installation and tested eDP Keep+Softsleep/Metal 2.

1. Download and unzip `SL4-S0ix-DMC-0.2.0-beta.zip` in macOS `~/Downloads`.
2. Run `sudo python3 "$HOME/Downloads/SL4-S0ix-DMC-0.2.0-beta/install.py" check --esp disk0s1`, verifying that `disk0s1` is your internal ESP.
3. Run `sudo python3 "$HOME/Downloads/SL4-S0ix-DMC-0.2.0-beta/install.py" apply --esp disk0s1` and restart macOS.
4. Verify the booted DMC, Metal and Deep Idle flags and test supervised RTC wake as documented.

Full [quick start and Windows recovery](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/blob/main/docs/QUICKSTART-S0IX.md). Rollback is `sudo python3 "$HOME/Downloads/SL4-S0ix-DMC-0.2.0-beta/install.py" rollback --esp disk0s1`.

**Safety:** The installer leaves automatic idle system sleep **disabled** pending broader testing. Do not place an unverified sleeping laptop in a bag. Windows dual boot and the original WhateverXe remain intact.

## Source and third-party credits

- WhateverXe upstream: `f26a36880c49ea1063393d943527808c0f38feca` (BSD 3-Clause), with public `research/wex-sl4-edp-base.patch` and `research/wex-tgl-dmc-supervised.patch`.
- Lilu headers: `e4748cc081bf060302c7d3c44a643ce1d11b7e1d`; MacKernelSDK `3f750085caa17ec3a7880f11c11bf4f48cd6a164`.
- Intel DMC 2.12, SHA-256 `3c013ef0ad96ba73aee8e5bd04a8e27cc9b1c6e9183b1a83ce124485f325afca`, redistributable under **Intel LICENSE.i915** in original binary form (copyright/conditions included).
- S0ixStandby v0.5.8 BSD 3-Clause; OpenCorePkg validator 1.0.8 BSD 3-Clause.

This project is independent of Apple, Intel and Microsoft. Tested hardware/OS versions are narrowly pinned. User-specific boot configurations are not shared.
