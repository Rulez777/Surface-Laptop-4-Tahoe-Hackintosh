# Surface Laptop 4 Intel — experimental keyboard and trackpad build

**Status: source adaptation prepared; the five-kext build and hardware function have NOT yet been verified. This branch is separate from the working Metal 2 / Wi-Fi baseline.**

Target: Microsoft Surface Laptop 4 13.5-inch Intel Core i7-1185G7 / Tiger Lake, macOS Tahoe 26.7.1, existing internal OpenCore 1.0.8.

## Why a custom driver is required

On the test laptop, `ioreg -p IOACPIPlane` shows existing `\_SB.PC00.UA00`, `\_SB.GPI0` and `\_SB.SSH` (`MSHW0084`). Do **not** add the Surface Laptop 5 SSDT-SAM; it would duplicate the original SSAM device. `BigSurface.kext` in the existing EFI is disabled. Stock BigSurface's VoodooSerial only matches older Ice Lake/Kaby Lake UARTs.

The device-specific ACPI table is [linux-surface/acpidumps/surface_laptop_4_intel/ssdt9.dsl](https://github.com/linux-surface/acpidumps/blob/master/surface_laptop_4_intel/ssdt9.dsl):

- UART: `\_SB.PC00.UA00`, **4 Mbps**, hardware flow control, 8-N-1.
- GPIO: `\_SB.GPI0`, interrupt pin **0x012A**, ActiveHigh / Edge, SharedAndWake.
- Existing `MSHW0084` hub: in firmware, do **not** inject an alternative `SSH`.
- Device `MSHW0250`: Surface Laptop 4 13.5-inch Intel platform identifier, recognized by linux-surface's SSAM registry.

Tiger Lake LPSS UART0 PCI ID is `8086:A0A8`, with a 100 MHz base source. The experimental builder adapts the [Surface Laptop 5 BigSurface builder](https://github.com/Lulurala3119/BigSurface-for-Surface-Laptop-5/blob/87c3ef9754215ffc6f8331ba7c4cdfbb6f2dc59c/SL5/build-bigsurface-sl5.py) to match **A0A8** rather than SL5's **51A8**, using the same 16/25 clock divisor to yield a 64 MHz UART clock; includes the upstream Tiger Lake-LP `INT34C5`/ `INTC1055` GPIO personality. Actual behavior on SL4 remains to be measured.

## Build (does not change the ESP)

A macOS Intel GitHub Actions build is defined in [sl4-sam-experimental.yml](../../.github/workflows/sl4-sam-experimental.yml). It compiles the five experimental kexts and checks for the correct UART and GPIO matches, then publishes an artifact named **SL4-BigSurface-EXPERIMENTAL** if all build stages succeed.

Local build on macOS with Xcode Command Line Tools and Python 3:

```bash
python3 experiments/sl4-input/build-bigsurface-sl4.py
```

The output is in `~/Downloads/bigsurface-sl4/out`. This command does **not** touch EFI or install any drivers. It downloads pinned upstream source revisions in a fresh temporary build folder.

The five expected kexts are **VoodooGPIO**, **VoodooSerial**, **VoodooInput**, **BigSurface**, and **BigSurfaceHIDDriver**. The code is experimental and requires validation of proper load order and Tahoe compatibility.

## Installation precautions

Before even staging the candidate binaries:

1. Retain a **verified private, known-bootable Metal 2 / Wi-Fi EFI backup** off the ESP plus the earlier `-wex-noaccel` backup.
2. Inspect actual kext dependencies and provider/consumer ordering. Avoid loading both this stack and the existing VoodooI2C/VoodooGPIO/VoodooInput stack. Do **not** enable two battery providers: BigSurface's battery and SMCBatteryManager may conflict.
3. Run OpenCore 1.0.8 `ocvalidate` on a **staged** config; do not edit Windows `EFI/Microsoft`, `EFI/BOOT`, partitioning or NVRAM boot order.
4. First boot must retain external keyboard/mouse access and a confirmed recovery route through Windows Boot Manager. Do not remove Lilu, WhateverXe, AMFIAnchor, Graphics 0.4.4 or the 60 MB DVMT patch.
5. Verify load via `kmutil showloaded` and active devices in `ioreg`, then actually type on built-in keyboard and use trackpad. A successfully compiled kext **does not establish** that it functions on this model.

**Do not install from this branch until a build succeeds and the installation profile is separately checked.** The `main` branch stays untouched.
