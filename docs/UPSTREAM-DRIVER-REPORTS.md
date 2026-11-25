# Upstream driver changes — 2026-11-25

This record describes the patches prepared for the maintainers of the external drivers used by the Surface Laptop 4 Intel profile. The patches are source proposals; they do not imply upstream acceptance.

## VoodooGPIO — Xiashangning/VoodooGPIO

Patch: research/upstream/voodoogpio-sl4-tgl-lp-sleepwake.patch

- Adds the Tiger Lake-LP GPIO personality for the Surface ACPI IDs INT34C5 and INTC1055, using the pin-table source pinned to VoodooI2C/VoodooGPIO commit d415406ecf25b5e322d3db9a4abab5719106fac1.
- Adds a guarded mapping for the SL4 lid input (software GPIO 0x12B to hardware GPP_F11 pin 206) and the F11 GPE 0x4B arm/recovery path.
- Preserves the live OEM RXINV polarity across GPIO resume instead of restoring a stale saved polarity.
- Adds the single-pin wake API used by the Surface Aggregator Module for GPIO 0x12A.
- Keeps the bounded one-second watchdog only on the exact observed SL4 Tiger Lake-LP hardware fingerprint. It waits for two stable samples and only re-enables the single lid GPE bit; it does not clear the pending GPE status bit.
- Removes temporary probe timers, IORegistry sample counters/properties and per-event wake logs from the production build.

Validation: five kexts compile; archive and OpenCore integration tests pass; the built VoodooGPIO binary contains none of the temporary probe/telemetry strings. Four physical clamshell cycles were previously observed with VoodooGPIO 1.2.4. The clean 1.2.5 rebuild still requires its own physical regression before it can be described as hardware-verified.

## BigSurface — Xiashangning/BigSurface

Patch: research/upstream/bigsurface-sl4-sam-wake.patch

- Adds an explicit SL4-only Info.plist property for the Surface Serial Hub personality.
- Arms the SAM keyboard/trackpad wake GPIO 0x12A only when the SL4 property is enabled and the discovered pin/IRQ match the expected edge-rising configuration.
- Uses the VoodooGPIO setWakeForPin API; it does not add a general-purpose wake policy for other Surface models.
- Removes per-event SAM wake logging from the production path.

Validation: clean five-kext build and package checks pass. SAM keyboard/trackpad wake has not yet been physically confirmed on the reference machine.

## VoodooSerial — Xiashangning/VoodooSerial

Patch: research/upstream/voodooserial-sl4-tgl-uart.patch

- Adds Intel UART PCI ID 8086:A0A8 for Surface Laptop 4 Tiger Lake-U.
- Programs the LPSS UART clock from 100 MHz to the 64 MHz rate expected by the driver's 4 Mbaud divisor, using M/N = 16/25.

Validation: included in the clean five-kext build; no separate UART-only hardware regression is claimed.

## WhateverXe — b00t0x/WhateverXe

Patch: research/wex-sl4-rcs-clean-production.patch

- Removes temporary RCS hook counters and the OSSerializer telemetry endpoint.
- Removes the temporary IORegistry telemetry properties and the per-initialization readiness log.
- Leaves the functional RCS patch routes and their scheduling branches unchanged.

Validation: source tests report 221 passed, 0 failed and 3 skipped; the skipped cases require native upstream donor components. A clean source build completes. The rebuilt binary is not substituted for the byte-pinned v0.1.7 package because it has not received a reference-hardware regression. The current byte-pinned v0.1.7 binary still contains the older RCS telemetry implementation; it remains dormant because the All-in-One default profile leaves the RCS single-port/native-queue trial boot flags disabled. Do not opt in to those trial flags until a cleaned binary has completed hardware regression.
