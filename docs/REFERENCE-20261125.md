# November 25 reference beta

Exact target: Surface Laptop 4 Intel 13.5-inch i7-1185G7, Iris Xe 8086:9A49, Tahoe 26.7.1, OpenCore 1.0.8. Includes the current boot-tested WhateverXe 0.8.5 binary (UUID C0141235-F042-36AF-B422-CD003A339044) and matching source snapshot, RAPL 18 W PL1 / 30 W PL2 (lower-only relative to firmware, preserving protection bits), HWP/RAPL observation and AC-only Low Power Mode (CPU request ceiling 24). The existing graphics donors, audio, input, wireless and sleep baseline remain pinned. No personal serial, MLB, ROM, UUID or EFI included.

## Installation

1. Prepare USB with Quick Start on Windows. Install Tahoe, finish the standard Metal 2 hardware setup and confirm internal dual boot.
2. On macOS with SL4DATA mounted, open QuickStart-Mac.command with --menu and select 8 (reference beta). Alternatively run ./QuickStart-Mac.command --reference-20261125. Explicit administrator authorization is required. Reboot.
3. Roll back with menu option 9 or --reference-rollback. The private backup remains on the local Mac. Do not delete it; keep the recovery USB. The installer refuses unknown donors, unexpected graphics binaries or changed EFI on rollback.

Observed on one reference machine: ~42 FPS after level reloads at native 2496x1664, compared with ~21 FPS initially. GPU ~10 W after AC CPU policy change, temperature 62–64 C during measured period. DisplayLink clock ~60 Hz. 60 FPS, compositor issue, repeatable first-entry performance, AV1/VP9 hardware acceleration, lid/internal-input wake and iPhone Mirroring are NOT verified. No game modifications or experimental UI transparency settings are applied. A fresh end-to-end install of this beta has not been physically validated. Existing macOS power sleep timers are preserved. The optional AC Low Power Mode applies globally on AC, not just games; rollback restores the old setting.
