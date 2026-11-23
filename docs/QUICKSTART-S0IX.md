> **Current release v0.4.0 beta:** RCS and Dolby Clear Speech are now integrated into the standard Windows-first QuickStart. [See one-step install and recovery](AUDIO-ALL-IN-ONE.md). Earlier separate RCS/S0ix procedures below remain for advanced troubleshooting only.

# Quick start — Surface Laptop 4 Intel / macOS Tahoe S0ix

**Release:** SL4-S0ix-DMC-0.2.0-beta. **What works:** on the tested Surface, two genuine Deep Idle → RTC wake cycles (8 and 71 seconds), Metal 2, internal 2496×1664 display, and verified Intel DMC reload after sleep. The owner additionally reports working sleep. **Important:** a delayed RCS GPU Reset appeared after the successful tests (a matching failure existed before S0ix), and hardware S0ix/PC10 residency was not established. **What still needs testing:** long battery-only sleep, reliable lid/power-button wake, delayed GPU stability, and energy efficiency. [Investigation](POST-S0IX-GPU-RCS-RESET-20261123.md).

This is an **existing macOS installation postinstaller**, not a complete Hackintosh installer. It does not contain OpenCore config, SMBIOS, Windows partitions or any personal EFI.

## 1. Who can use this release

Only proceed if **all** of these already work:

- Microsoft Surface Laptop 4 **Intel 13.5-inch**, Intel Core **i7-1185G7**, Iris Xe **8086:9A49**.
- **macOS Tahoe 26.7.1** booting via existing **OpenCore 1.0.8** on the **internal SSD**, with a Windows 11 Boot Manager recovery option.
- **Metal 2**, built-in screen and brightness, BigSurface **1.2.0** and WhateverXe **0.8.3** eDP Keep + Softsleep already configured.
- Tahoe `AppleIntelTGLGraphics` and `AppleIntelTGLGraphicsFramebuffer` binaries match the **pinned** versions. The installer checks these hashes, CPU, GPU, ACPI and existing WEX bytes and refuses a mismatch.

If you **have not installed macOS yet**, use [internal dual boot](INTERNAL-BOOT.md) and [graphics + drivers](../README.md) first. **This package cannot make a nonbooting Surface boot** and is not certified for other CPUs, Surface versions, different Tahoe builds or different graphics drivers.

## 2. Install in a few commands — macOS Terminal

Download the prepared archive from the GitHub **Releases** page: [SL4-S0ix-DMC-0.2.0-beta](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/releases/tag/sl4-s0ix-v0.2.0-beta).

The release has a ZIP named `SL4-S0ix-DMC-0.2.0-beta.zip`. Download it to `~/Downloads` and extract the archive. It creates `~/Downloads/SL4-S0ix-DMC-0.2.0-beta`.

Optional one-line Terminal download and extraction:

```bash
cd "$HOME/Downloads" && curl -fL -o SL4-S0ix-DMC-0.2.0-beta.zip "https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/releases/download/sl4-s0ix-v0.2.0-beta/SL4-S0ix-DMC-0.2.0-beta.zip" && unzip -q SL4-S0ix-DMC-0.2.0-beta.zip
```

Confirm the **correct internal** EFI System Partition from `diskutil list`, normally `disk0s1` on the tested machine, then run:

```bash
sudo python3 "$HOME/Downloads/SL4-S0ix-DMC-0.2.0-beta/install.py" check --esp disk0s1
```

A successful preflight prints `READY_FOR_RELEASE_INSTALL`. It checks the release binaries, original graphics and existing OpenCore configuration **without modifying EFI**. It will stop if macOS, CPU/GPU, eDP drivers, ACPI, or Windows Boot Manager do not match.

Install:

```bash
sudo python3 "$HOME/Downloads/SL4-S0ix-DMC-0.2.0-beta/install.py" apply --esp disk0s1
```

The installer:

1. Creates a **private complete backup of your current `EFI/OC`** in `~/Downloads/SL4-S0IX-BACKUPS`; checks the original config hash.
2. Saves the original `config.plist` on the ESP under `EFI/OC/config-SL4-S0IX-restore-*.plist`, for Windows recovery.
3. Copies the checked **SL4 DMC / WhateverXe 0.8.3 kext**, **S0ixStandby 0.5.8** and **SSDT-DEEPIDLE.aml** into separate names. **Original WhateverXe stays present**.
4. Changes only the necessary `EFI/OC/config.plist` entries and the `-wex-sl4-tgl-dmc` boot argument; validates the final config with OpenCore 1.0.8's `ocvalidate`.
5. Checks Windows Boot Manager SHA-256 again and unmounts the ESP if the installer mounted it.

**Restart macOS from the Apple menu.** The OpenCore changes persist across every future reboot. The installer **does not enable automatic idle system sleep** by default; that requires independent longer / lid / battery tests. The system sleep can still be tested manually after the successful boot.

## 3. Verify the booted installation

In macOS Terminal, each command is one line:

```bash
system_profiler SPDisplaysDataType
```

```bash
ioreg -lw0 | grep -E 'SL4DMCLocalInitVerified|SL4DMCLocalWakeHookReady|SL4DMCLocalWakeVerified|IOPMDeepIdleSupported|TGLEDPKeepReady|TGLSoftSleepReady'
```

```bash
kmutil showloaded | grep -E 'WhateverXe|S0ixStandby|BigSurface'
```

Before sleeping, `SL4DMCLocalInitVerified`, `SL4DMCLocalWakeHookReady` and `IOPMDeepIdleSupported` must be `Yes`. After supervised sleep and wake, confirm `SL4DMCLocalWakeVerified = Yes`, a nonzero `machdep.xcpm.deep_idle_count`, and `Wake from Deep Idle` in the logs.

```bash
sysctl machdep.xcpm.deep_idle_count
```

```bash
pmset -g log | grep -E 'Entering Sleep|Wake from Deep Idle' | tail -10
```

**Test sleep with an accessible power button and a known way to restore Windows.** A screen that only goes dark is not evidence of system Deep Idle. Two software-reported RTC wakes do not by themselves prove physical package S0ix residency or battery savings. Monitor for delayed GPU resets and independently test lid and battery wake; never put an unverified sleeping laptop in a bag.

## 4. Rollback if the device fails or you want to revert

When macOS still boots, run:

```bash
sudo python3 "$HOME/Downloads/SL4-S0ix-DMC-0.2.0-beta/install.py" rollback --esp disk0s1
```

Reboot. The installer restores the exact prior config (hash verified) and leaves experimental kext files inactive. It does not delete the backup.

**If macOS no longer boots:** boot **Windows 11**, open PowerShell **as Administrator**, and restore the most recent on-ESP recovery config:

```powershell
mountvol S: /S; $r = Get-ChildItem 'S:\EFI\OC\config-SL4-S0IX-restore-*.plist' | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if (-not $r) { throw 'SL4 recovery config not found' }; Copy-Item -LiteralPath $r.FullName -Destination 'S:\EFI\OC\config.plist' -Force; mountvol S: /D
```

After that, restart and boot macOS; previous WhateverXe is still present. **Do not format the EFI partition or touch `EFI/Microsoft`.** For an issue with booting Windows itself, see [EFI safety](SAFETY.md).

## 5. Scope, source and licenses

The release ZIP contains only the **public install script, exact-source-built kexts, SSDT, Intel firmware image, pinned `ocvalidate`, SHA-256 manifest and required license notices**. No user boot configuration, serial, MLB, ROM or Windows BCD is ever published.

The WhateverXe patch is reproducible from the pinned upstream revision and the source-only [SL4 eDP baseline patch](../research/wex-sl4-edp-base.patch) plus [SL4 DMC patch](../research/wex-tgl-dmc-supervised.patch). Third-party rights: WhateverXe BSD 3-Clause, S0ixStandby BSD 3-Clause, Intel `LICENSE.i915`, and OpenCorePkg BSD 3-Clause. Intel's original DMC firmware is included unmodified; do not alter, reverse-engineer or claim Intel endorses this project.

See [the two RTC wake logs](S0IX-INITIAL-RTC-WAKE-20261123.md), [DMC implementation](DMC-SLEEP-TRIAL.md) and [sleep safety details](SLEEP.md).

## RCS Stability update (2026-11-23)

For Intel Surface Laptop 4 i7-1185G7 / Iris Xe 9A49 on **Tahoe 26.7.1**, see [RCS Stability 0.1.0 beta](QUICKSTART-RCS.md). The addon fixes a tested render-queue / preemption hang, and is installed **after** the graphics package and working Tahoe/DMC. Windows QuickStart 0.3.3 downloads and stages it for the Mac-side optional installer. It is not a fix for AV1/VP9 decoding; its preflight and private OpenCore rollback are mandatory. Do not install this kext on an unknown donor or the Windows installer USB.
