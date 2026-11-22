# Full driver pack and accelerated graphics — Intel Surface Laptop 4

**Goal:** fast OpenCore, real Iris Xe hardware acceleration where supported, and every identified peripheral driver available for testing on the installed macOS Tahoe. This is a staged transition, not a one-click "enable everything" profile.

**Confirmed starting point (2026-11-22):** internal OpenCore on the Samsung PM991 was staged from the working Kingston, quiet boot enabled, Windows Boot Manager preserved, independent firmware entry created. An actual no-USB boot, WhateverXe Graphics, and Surface SAM peripherals still require testing.

> **Back up first.** Keep the original Kingston recovery USB unchanged. The internal SSD has Windows and Tahoe on separate partitions. If new graphics breaks the internal boot, use Kingston to load Tahoe in `-wex-noaccel` mode and restore the backed-up internal `config.plist` using Windows.

## Phase A — Windows: download and stage all known driver candidates

Use **PowerShell as Administrator**. The following commands each occupy a single line and are intentionally independent. Replace the clone location if necessary.

Before pulling, inspect local modifications (do not discard any private files):

```powershell
git -C "$HOME\Downloads\SL4-Tahoe-Git" status --short
```

Update the project:

```powershell
git -C "$HOME\Downloads\SL4-Tahoe-Git" pull --ff-only
```

Check the existing incomplete package **without deleting or publishing it**:

```powershell
if (Test-Path "$HOME\Downloads\SL4-FULL-DRIVERS") { Get-ChildItem "$HOME\Downloads\SL4-FULL-DRIVERS" -Force | Select-Object Name,Length,LastWriteTime }
```

**Reuse S: if already mounted.** Mount the internal Windows ESP only when that letter is free:

```powershell
if (Test-Path "S:\EFI\OC\config.plist") { Write-Host "Using already-mounted ESP on S:" } elseif (Test-Path "S:\") { throw "S: is occupied by a different volume; stop" } else { mountvol S: /S; if (-not (Test-Path "S:\EFI\OC\config.plist")) { throw "ESP does not contain expected OpenCore config; stop" } }
```

Verify that S: is an EFI System Partition on the **internal Samsung SSD**, not Kingston:

```powershell
Get-Partition -DriveLetter S | Select-Object DiskNumber,PartitionNumber,Type,GptType,Size | Format-List
```

Inspect the Tiger Lake graphics requirements, without writing:

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode inspect --efi "S:\EFI"
```

Download **all** currently identified optional driver kexts, the Surface touch daemon candidate, **WhateverXe Graphics 0.4.4** and matching **OpenCore 1.0.8 ocvalidate.exe** into C:. GitHub release ZIPs and Graphics pkg are verified against the release digests where available:

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\prepare_full_driver_pack.py" --source "S:\EFI" --out "$HOME\Downloads\SL4-FULL-DRIVERS" --cache "$HOME\Downloads\SL4-KEXT-CACHE"
```

If an older build failed while copying `S:\\EFI\\Microsoft\\Boot\\BCD`, update Git first and rerun the same download command. The current tool copies **only `EFI\\OC`**. An unfinished `SL4-FULL-DRIVERS/optional-EFI` is renamed `optional-EFI.failed-...` instead of deleted, and valid previously downloaded archives are reused. Corrupt/partial downloads are re-fetched. The resulting `manifest.json` is an atomic completion marker; staging refuses packs without it. Archived folders may contain private EFI/SMBIOS information; do not publish them. Do not run the staging commands until `FULL CANDIDATE DRIVER PACK READY` appears.

Independently run the **matching OpenCore 1.0.8 validator** against the generated configuration:

```powershell
& "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe" "$HOME\Downloads\SL4-FULL-DRIVERS\optional-EFI\EFI\OC\config.plist"
```

Do not continue if `ocvalidate` reports any errors.

The next two commands **stage the full candidate set in the internal EFI, but keep new/untested kexts disabled**. They compare the generated pack against the live internal EFI, verify kext files and retain a complete `EFI/OC` backup on C:. Windows EFI/BCD stays untouched.

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\stage_full_kext_pack.py" --mode inspect --internal-efi "S:\EFI" --pack-efi "$HOME\Downloads\SL4-FULL-DRIVERS\optional-EFI\EFI" --backup-dir "$HOME\Downloads\SL4-KEXT-BACKUPS"
```

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\stage_full_kext_pack.py" --mode apply --internal-efi "S:\EFI" --pack-efi "$HOME\Downloads\SL4-FULL-DRIVERS\optional-EFI\EFI" --backup-dir "$HOME\Downloads\SL4-KEXT-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
```

Type `STAGE-FULL-KEXT-PACK` only after inspecting the planned list. Drivers already present in the proven EFI are left untouched. The extra kexts are **physically staged** in `S:\EFI\OC\Kexts` and listed as disabled entries; they will not be loaded until a compatible profile is tested.

Now prepare the **required SIP value and boot flags** for WhateverXe Graphics, but **preserve `-wex-noaccel` for the package-install boot**:

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode prepare --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
```

The command requires `PREPARE-XE-EFI` confirmation before changing SIP/boot flags. **SIP `0x803` is less restrictive than default Apple SIP; do not apply without understanding the trust implications.** The script checks the presence and order of Lilu, WhateverXe, AMFIAnchor and its injector, as well as the custom RTC0 fix. It now adds **both `boot-args` and `csr-active-config` to `NVRAM/Delete`** (under Apple's GUID), because simply updating `NVRAM/Add` would not overwrite variables already persisted by firmware. This also ensures the subsequent removal of `-wex-noaccel` can take effect. The actual SIP setting must still be verified after boot.

Copy the graphics installer **and SHA256-checking helper** onto Kingston's **exFAT data volume**, not its EFI. Kingston is only used to transfer files, not to boot macOS:

```powershell
$d=Get-Volume -FileSystemLabel "SL4DATA" | Where-Object DriveLetter | Select-Object -First 1; if(!$d){throw "SL4DATA not mounted"}; Copy-Item "$HOME\Downloads\SL4-FULL-DRIVERS\macOS-Installers\WhateverXe-Graphics-0.4.4.pkg" "$($d.DriveLetter):\" -Force; Copy-Item "$HOME\Downloads\SL4-Tahoe-Git\scripts\install_wex_graphics_macos.sh" "$($d.DriveLetter):\" -Force
```

Unmount the internal ESP:

```powershell
mountvol S: /D
```

## Phase B — macOS: install WhateverXe Graphics into the installed OS

Boot **internal OpenCore** with **Kingston disconnected** (the independent UEFI entry created earlier). It should still boot using `-wex-noaccel` with the quiet four-second picker.

If it boots, connect Kingston as a **data drive**. In Tahoe Terminal, confirm the macOS version:

```bash
sw_vers -productVersion
```

**Stop if the installed OS is older than 26.7.** Check the official package hash before installation:

```bash
shasum -a 256 "/Volumes/SL4DATA/WhateverXe-Graphics-0.4.4.pkg"
```

Expected SHA-256: `f4c2d680a7c52c33a3f038ce6945da0aa2cc044e62b935a52ea046c7c473cfec`.

Install the verified package using the helper (requires admin credentials and a working input device). It now **refuses installation** unless IORegistry shows AMFIAnchor `InstallStatus=1` and the `org.b00t0x.AMFIAnchorInjector` signing provider:

```bash
bash "/Volumes/SL4DATA/install_wex_graphics_macos.sh" "/Volumes/SL4DATA/WhateverXe-Graphics-0.4.4.pkg"
```

**Do not proceed** if the installer reports an error. Follow its restart instructions. The Graphics installer modifies macOS `/Library` and rebuilds AuxKC; merely copying a `.pkg` to EFI cannot enable acceleration.

## Phase C — Windows: remove `-wex-noaccel` from the internal EFI

After the macOS installer completes successfully, boot Windows, mount `S:` again and enable graphics:

```powershell
mountvol S: /S
```

```powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\xe_acceleration.py" --mode enable --efi "S:\EFI" --backup-dir "$HOME\Downloads\SL4-OC-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe"
```

The script requires explicit confirmation of a successful installation of Graphics 0.4.4, then removes **only `-wex-noaccel`**, preserving RTC0, other WEX arguments and the fast OpenCore picker. It keeps a private verified backup of `config.plist`.

```powershell
mountvol S: /D
```

Boot the internal OpenCore entry again. If Tahoe launches, check `system_profiler SPDisplaysDataType`, Metal apps and the actual window animation speed. A reported GPU name alone is not proof of Metal acceleration. **The test-machine Iris Xe 96 EU has not yet been validated with hardware acceleration.**

## Peripherals and limits

The prepared full pack includes AppleALC, Tahoe AirportItlwm (alpha), Intel Bluetooth, BlueToolFixup, SMCBatteryManager, VoodooPS2, VoodooI2C/HID, BigSurface, NVMeFix, RestrictEvents and IPTSDaemon. They are candidates, not one mutually-compatible stack. In particular:

- **BigSurface 6.5** is from 2023 and lists older Surface models. It may conflict with **VoodooI2C/HID** and **SMCBatteryManager**. There is no published fully qualified Surface Laptop 4 + Tahoe SAM/input setup; these remain disabled until model-specific testing.
- **Intel Wi-Fi/Bluetooth and AppleALC** can be enabled in isolated tests after graphics stability has been established; exact hardware and kext compatibility remain unverified.
- **NVMeFix** is not automatically enabled on Samsung PM991. Stability is more important than speculative NVMe gains.
- No kext can be guaranteed to deliver "peak performance" without confirming **Metal acceleration, XCPM CPU power management, thermals, SSD performance, sleep/wake and I/O stability** on this machine.

For a black screen, use the unchanged Kingston fallback, restore the `config.plist` saved by `xe_acceleration.py`, then revisit WEX/Graphics/AMFIAnchor/SIP. Do **not** erase or repartition the internal SSD to troubleshoot graphics.

Upstream: [WhateverXe](https://github.com/b00t0x/WhateverXe) · [Graphics](https://github.com/b00t0x/WhateverXe-Graphics) · [AMFIAnchor](https://github.com/b00t0x/AMFIAnchor) · [BigSurface](https://github.com/Xiashangning/BigSurface).
