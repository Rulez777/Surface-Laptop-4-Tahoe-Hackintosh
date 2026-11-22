# Sleep and wake — not working reliably

**Hardware:** Surface Laptop 4 Intel 13.5-inch, Core i7-1185G7, Intel Iris Xe `8086:9A49`, macOS Tahoe 26.7.1, OpenCore 1.0.8, WhateverXe 0.8.3, WhateverXe Graphics 0.4.4.

## Verified status

**System sleep/wake is not supported by the current validated build.** Previously, sleep caused an unresponsive system and reboot. A controlled test on 2026-11-22 with pre-release S0ixStandby 0.5.8 and `SSDT-DEEPIDLE` also left the Surface unresponsive. The device was restarted and the experiment **fully rolled back** from OpenCore. Neither experimental driver nor SSDT belongs in the production package.

Known-good graphics, input, audio, brightness, and Windows dual boot were preserved. The internal ESP was verified with OpenCore 1.0.8 `ocvalidate`.

The first S0ix attempt did not produce a conclusive sleep/wake transition record in `pmset`; the exact point of failure is **not established**. It must not be reported as successful standby or assigned to a specific culprit without stronger evidence. Two earlier panic reports contained stack frames in WhateverXe / AppleIntelTGLGraphics / IOAcceleratorFamily2, so graphics power-state transitions remain a plausible, **unconfirmed** risk.

## Temporary safety workaround

To prevent *automatic idle system sleep* on a machine prone to sleep hangs, use:

```bash
sudo pmset -a sleep 0
```

This is **not functional system sleep**. Display dimming and display-only sleep can remain available. **Closing the lid may still request system sleep**; do not close the lid or put a running machine into a bag until sleep is independently verified.

Do not install experimental S0ixStandby or `SSDT-DEEPIDLE` on other Surface models by following this repository's supported setup. A working ACPI device matching `PNP0D80` and a validated OpenCore config do not prove that suspend or wake will succeed.

## Future work

1. Isolate sleep-entry failure versus wake/display failure with persistent logs and a recoverable boot path.
2. Investigate the graphics driver power-state interactions without compromising Metal 2.
3. Test power-button wake with no external dock or display, then repeated and extended cycles on AC and battery.
4. Only after repeatable success, ship a validated, rollback-capable sleep installer for the exact compatible hardware.

Related upstream research: [S0ixStandby](https://github.com/labrouss/S0ixStandby), [WhateverXe issue #86](https://github.com/b00t0x/WhateverXe/issues/86), [WhateverXe issue #141](https://github.com/b00t0x/WhateverXe/issues/141). These reports describe related Tiger Lake symptoms, **not a confirmed fix for this Surface**.
