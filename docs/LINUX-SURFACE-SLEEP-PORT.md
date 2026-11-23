# Linux-surface suspend vs this Surface Laptop 4 Tahoe installation
Date: 2026-11-23. **Research only — no actual system suspend has been fixed or enabled.**

## Exact target and what is verified

- Target: Microsoft Surface Laptop 4 13.5-inch Intel, Core i7-1185G7 / Iris Xe PCI 8086:9A49, macOS Tahoe 26.7.1, working custom WhateverXe 0.8.3 eDP Keep/Softsleep, BigSurface 1.2.0.
- Runtime ACPI exposes `\_SB.LID0` (PNP0C0D) and `\_SB.PEPD` (INT33A1, PNP0D80).
- Runtime sleep is intentionally disabled on AC **and** battery: `pmset sleep=0`, `displaysleep=0`; two existing `caffeinate` assertions also prevent automatic idle sleep/display-off. `machdep.xcpm.deep_idle_count=0` and `kern.sleeptime={sec=0}` after the most recent boot. **No physical S0ix test was made this session.**
- Running BigSurface bundle version matches the inspected local source build (v1.2.0); the actual binary identity of the currently loaded EFI kext cannot be proven without inspecting the private unmounted ESP. The **local source implementation** can be compared, but should not be asserted byte-identical with the loaded kext.
- Prior S0ixStandby v0.5.8 plus SSDT-DEEPIDLE attempt hung; was rolled back. Current display-only wake works per previous user confirmation, but this does not prove system sleep.

## Primary linux-surface sources and exact lessons

1. **Status, not a complete guarantee:** feature matrix updated 2026-11-12 lists **SL4 Intel S0ix ✓**, **Suspend ?** and **Hibernate ?**. A 2026-10 issue describes 10–27% S0ix residency on one SL4I with poor drain, so even a suspend/resume cycle is not sufficient to certify proper power savings.
   - https://github.com/linux-surface/linux-surface/wiki/Supported-Devices-and-Features
   - https://github.com/linux-surface/linux-surface/issues/2303
2. **Lid wake uses explicit GPE 0x4B:** Linux `drivers/platform/surface/surface_gpe.c` selects `Surface_Laptop_4_1950:1951` and `lid_device_props_l4B`. Its suspend callback uses `acpi_set_gpe_wake_mask(NULL, 0x4B, ACPI_GPE_ENABLE)`; resume disables that wake mask. The Linux README explains that the Surface lid lacks an ACPI `_PRW` (the standard source of wake GPEs), so this action is required on some systems.
   - https://github.com/torvalds/linux/blob/master/drivers/platform/surface/surface_gpe.c
   - https://github.com/linux-surface/surface-gpe
3. **Actual SL4 Intel ACPI dump (2021, historical, not current firmware):** the disassembled DSDT at `surface_laptop_4_intel/dsdt.dsl` defines `Name (SS3, Zero)`, and `_S3` only conditionally `If (SS3)` → the **historical firmware does not advertise S3**. It also defines `\_SB.LID0` without a `_PRW`, `\_GPE._L4B` that issues `Notify(\_SB.LID0, 0x80)`, and the PEPD compatible ID `PNP0D80` that indicates Intel low-power platform support. Reconfirm all facts against the **current DSDT** before applying patches.
   - https://github.com/linux-surface/acpidumps/blob/master/surface_laptop_4_intel/dsdt.dsl
4. **Surface Aggregator (SAM/SSAM) ordering:** Linux `drivers/platform/surface/aggregator/core.c` sends a **DISPLAY_OFF** notification during prepare, **D0_EXIT**, arms the EC wake IRQ, suspends its controller, then on resume restarts the controller, disarms the EC wake IRQ, sends **D0_ENTRY**, and eventually **DISPLAY_ON**. The Surface registry also uses device links to keep children and the SSAM controller in a safe suspend/resume order.
   - https://github.com/torvalds/linux/blob/master/drivers/platform/surface/aggregator/core.c
   - https://github.com/torvalds/linux/blob/master/drivers/platform/surface/aggregator/controller.c
   - https://github.com/torvalds/linux/blob/master/drivers/platform/surface/surface_aggregator_registry.c
5. **LPS0 firmware coordination:** Linux `drivers/acpi/x86/s2idle.c` runs Intel/Microsoft LPS0 `_DSM` notifications such as `SCREEN_OFF (3)`, `MS_ENTRY (7)`, `ENTRY (5)` and corresponding exit/display-on operations. Its OS, PCI runtime power management, Intel i915 GPU and Intel PMC coordination are Linux-specific; macOS cannot load these drivers.
   - https://github.com/torvalds/linux/blob/master/drivers/acpi/x86/s2idle.c
6. **The existing macOS BigSurface already performs part of the above:** `/Users/surface/Downloads/bigsurface-sl4/src/BigSurface/BigSurface/SurfaceSerialHub/SurfaceSerialHubDriver.cpp` uses `setPowerState` to send `DISPLAY_OFF=0x15`, `D0_EXIT=0x33` and, after wake, `D0_ENTRY=0x34`, `DISPLAY_ON=0x16` via its Surface UART protocol. This is very similar to the Linux SSAM notification sequence; **do not duplicate** these commands in another kext.
7. **Potential differences, NOT proven faults:** I found no separate SL4 `0x4B` lid GPE *wake-mask arm/disarm* equivalent in the inspected BigSurface UART driver, nor proof that its Surface Aggregator interrupt is armed as a system-wakeup source. Its GPIO event source is enabled at runtime, which is not the same thing as enabling a wake GPE during sleep. This finding requires actual kernel/ACPI power-state testing before drawing conclusions.

## Offline-only candidate for a subsequent supervised test

A research source-only candidate is at `research/SSDT-SL4-LIDWAKE.dsl` (not compiled, not in EFI, not in any installation bundle). For Darwin only, it adds `_PRW` on `\_SB.LID0` returning wake GPE `0x4B` and lowest wake-capable state `0x03`, as used by experimental S0ixStandby's per-machine lid-wake approach. This is **not a verified port** of Linux `acpi_set_gpe_wake_mask` behavior to AppleACPIPlatform; the ACPI OS must actually act on `_PRW`.

Danger: arming that GPE may cause dark wakes during charging or on lid events, and re-suspend may hang the TGL framebuffer. **This candidate does not fix the previously observed S0ix sleep-entry hang**, which must be isolated first. The old DSDT has no `LID0._PRW`, but the current firmware and other injected SSDTs are unverified. Never load a duplicate `_PRW` or modify the active EFI without confirming this.

Reference for the experiment's method, caveats and prior adverse dark wakes:
https://github.com/labrouss/S0ixStandby/blob/main/acpi/SSDT-LIDWAKE.dsl

## Gate and sequence to actually fix sleep

**Preconditions:** independent boot/recovery method without USB; readable private backup of *current* complete EFI and working Windows loader; current OpenCore 1.0.8 config validated; physical operator ready to force restart/restore if remote connection drops; full source ACPI dump of current firmware; no recent unresolved boot corruption. These are not all satisfied by remote unprivileged session.

1. Diagnose **entry vs resume** before adding wake fixes. The prior failure mode needs exact transition traces. Capture GPU `GFX0 setPowerState`, SSAM/BigSurface power hooks, LPS0 `_DSM`, PCI/NVMe and framebuffer transitions in private logs. A failing GPU power-state transition before idle entry cannot be repaired by just arming lid wake.
2. Reconcile BigSurface SAM power callbacks with Linux's ordering. Test whether the EC wake IRQ and lid GPE are armed in the actual Deep Idle phase, without issuing duplicate notifications. If source patches are needed, implement macOS-native IOKit power-state hooks rather than copying Linux GPL-2.0 driver code.
3. Confirm XNU deep-idle / S0ixStandby mechanism is actually supported by the live CPU/firmware and that `IOPMDeepIdleSupported` appears only after supervised staging. Keep the existing eDP Keep/Softsleep GPU patch; do not downgrade or disable Metal.
4. Once entry and power-button resume are confirmed, test the **optional** LID0 GPE 0x4B candidate in a separate reversible stage. Guard against AC/battery dark-wake loops and failed framebuffer re-sleep. Add repeated 5-second and 60-second and longer cycles only after earlier passes.
5. Verify actual PC10/S0ix residency or battery consumption, plus input, audio, network, Metal, display, CPU speed and charging after wake. Only then enable automatic idle system sleep, and only with a full rollback method that works when the display does not wake.

**Current decision:** keep `sleep=0`. Neither the Linux code nor the offline `_PRW` research by itself warrants a live unattended sleep test. Do not modify Windows, the internal EFI, LPS0 registers, EC wake IRQ masks or ACPI during this analysis. The candidate is intentionally unavailable for one-click installation.
