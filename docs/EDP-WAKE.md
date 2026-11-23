# Internal eDP display wake — Keep + Softsleep (2026-11-23)

**Tested hardware:** Microsoft Surface Laptop 4 Intel 13.5-inch, Core i7-1185G7, Intel Iris Xe `8086:9A49`, Samsung PM991, macOS Tahoe 26.7.1, OpenCore 1.0.8.

## Current status

The internal panel has been observed to **turn off and recover a visible image** when using the sleep/power button and after closing/reopening the lid, with our custom WhateverXe 0.8.3 **eDP Keep + Softsleep** driver. This is corroborated by instrumented driver traces. The same machine previously lost the eDP video link on display-only wake (`0xE00002BC`); the new trace shows the backlight going off and on without those recorded link-training failures.

**Important distinction:** Only *display sleep / lid-related display wake* is validated here. Full ACPI system sleep (S3/S0ix) is **not validated**; `pmset sleep 0` remains in effect on our machine, and the S0ixStandby + SSDT-DEEPIDLE experiment was unsuccessful. Never represent these tests as successful suspend-to-RAM.

This is a **reversible post-install add-on** for a system that already boots macOS Tahoe with **Metal 2** and WhateverXe 0.8.3. It is not a generic driver for all Surface laptops.

## Download

The versioned [ready-to-use ZIP](../packages/SL4-WEX-0.8.3-EDP-KeepSoftSleep.zip) includes the tested binary, macOS installer, official OpenCore 1.0.8 validator, attribution and recovery instructions.

SHA-256 of ZIP: `42664cbf1ebd3a4a169daa1adceb4e470adcdeddf691ff557e0ca06b83efa301`

SHA-256 of WhateverXe 0.8.3 binary: `0796d12158b9c6806a83e4f455f84eee9280a0148406b8d4f0764234f00df91a`

You can use the script from a cloned repository **without manually unpacking the ZIP**. The script detects and verifies the bundled archive.

### 1. Verify the target

In macOS Terminal, with your cloned repository at `~/Downloads/SL4-Tahoe-Git`, identify **your own** internal EFI partition:

```bash
diskutil list
```

The tested Surface uses `disk0s1`. Other disk layouts must use the identifier actually reported by `diskutil list`. **Never format or repartition the ESP.**

Run a read-only compatibility/configuration check (the installer temporarily mounts EFI to inspect it, then unmounts):

```bash
sudo python3 "$HOME/Downloads/SL4-Tahoe-Git/scripts/install_edp_keep_macos.py" check --esp disk0s1
```

Checks include the exact Intel CPU/GPU IDs, the validated framebuffer donor, WhateverXe 0.8.3, Lilu order, OpenCore NVRAM boot-args handling, and a working accelerated graphics profile. If it refuses the hardware, **do not bypass the checks**. A different Tiger Lake laptop, macOS release or donor could have different internal offsets.

### 2. Apply

```bash
sudo python3 "$HOME/Downloads/SL4-Tahoe-Git/scripts/install_edp_keep_macos.py" apply --esp disk0s1
```

This will:
- Preserve your existing OpenCore directory in a private backup under `~/Downloads/SL4-EDP-BACKUPS`.
- Preserve the active WhateverXe kext and create a *new* `WhateverXe-SL4-EDP-KeepSoftSleep.kext`.
- Verify the new kext checksum and existing graphics requirements.
- Enable the three additional optional mechanisms (`-wex-edp-wake-trace`, `-wex-tgl-edp-keep`, `-wex-tgl-edp-softsleep`) plus the known tested TGL GPU recovery/power boot flags, without duplicating existing flags.
- Validate OpenCore before and after applying the change, and store a separate recovery config in `EFI/OC`.
- **Never** touch `EFI/Microsoft`, partitions, firmware boot order, personal SMBIOS identity or macOS system files.

Restart macOS. Confirm the screen works before testing wake:

```bash
nvram boot-args
```

```bash
system_profiler SPDisplaysDataType
```

```bash
ioreg -lw0 -p IOService | grep -E 'TGLEDPKeepReady|TGLSoftSleepReady|TGLEDPKept|TGLGpuRecReady'
```

For the validated donor, the first two flags should be `Yes`. `TGLEDPKept` should be nonzero. This is a **software** check; actual light-up must be visually confirmed.

### 3. Test in a recoverable environment

Have Windows Boot Manager available. Begin with display-only sleep, confirm the physical panel lights again, then cautiously test opening/closing the lid. Avoid a full S3/S0ix experiment. Our tested Mac remains configured with `sleep 0` and `displaysleep 0` on AC and battery; the driver alone does not change your `pmset` configuration. Lid actions may still request deeper power states on other setups.

Keep the remote access/physical recovery path until you have confirmed repeated wake cycles. Do not store a running laptop in a bag based on this patch.

### 4. Roll back

If macOS still boots:

```bash
sudo python3 "$HOME/Downloads/SL4-Tahoe-Git/scripts/install_edp_keep_macos.py" rollback --esp disk0s1
```

Restart. The original kext remains on the ESP; rollback restores the exact previous `config.plist` and original boot-args. The script will refuse automatic rollback if the configuration has been edited since installation.

If macOS fails to boot, select **Windows Boot Manager**, mount the internal EFI with `mountvol S: /S`, and restore your `config.plist` from the saved pre-install `EFI/OC/config-SL4-before-EDP-YYYYMMDD-HHMMSS.plist` or the private `SL4-EDP-BACKUPS` copy. Preserve `EFI/Microsoft`; do not format the partition.

## Implementation and verification

The custom WhateverXe 0.8.3 retains previously validated TGL GPU recovery and stamp fixes. It adds read-only **WakeTrace**, **eDP Keep** (avoid needless full mode-setting when an already-trained pipe A/DDI A eDP link matches), and **Softsleep** (leave the link powered and turn off only the backlight during display sleep).

The donor `AppleIntelTGLGraphicsFramebuffer` (version 16.0.0) was verified before hooking all four required native function offsets and exact prologue bytes. SHA-256: `115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e`.

On this Surface in the first instrumented softsleep test, `PP_CONTROL` moved `0x67 → 0x63 → 0x67`, and `TGLEDPKept` increased from 5 to 7. No `LINK_TRAINING` failure appeared in that bounded log. After an automatic recovery reboot, both Metal 2 and the internal panel remained available. The owner subsequently confirmed visible wake after the power/sleep button and closing/opening the lid.

The source integration is based on the upstream [Tiger Lake eDP keep + softsleep research patch](https://github.com/user-attachments/files/34506718/wex-tgl-edp-keep-softsleep-v2.patch). This repository distributes an unofficial **prebuilt** 0.8.3 add-on with checksums and attribution; it does not publish a personalized OpenCore EFI.

See [sleep limitations](SLEEP.md) for the distinction between display-only sleep and full system suspend.
