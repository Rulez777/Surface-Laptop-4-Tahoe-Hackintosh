# Historical initial-install notes (before verified Metal 2 configuration)

This is the **original first-boot workflow** preserved for historical reproducibility. It was written before Metal 2 was confirmed on the test Surface and is not the recommended no-removable-media **post-install** quick start. Do not use the accelerated boot args here until the official Graphics pkg and 60 MB DVMT configuration are in place. The clean-checkout EFI builder was **not independently boot-verified**. See [validated Metal](VALIDATED-METAL-SL4.md) for the actual tested result.

## Historical initial installation

**Requirements:** Intel Surface Laptop 4 (tested: i7-1185G7), Python 3 on Windows, a 32 GB+ USB drive, and a backup of Windows.

**1. Clone the repository.**

```powershell
git clone https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh.git
```

**2. Generate private SMBIOS values.** Use [GenSMBIOS](https://github.com/corpnewt/GenSMBIOS) with model `MacBookPro16,2`. Generate a unique serial, MLB, SystemUUID and six-byte ROM. Never copy someone else’s serial numbers.

**3. Build the EFI and driver bundle.** Run inside the cloned project folder, replacing all placeholders:

```powershell
py -3 scripts/build_efi.py --serial YOUR_SERIAL --mlb YOUR_MLB --uuid YOUR_UUID --rom YOUR_12_HEX_DIGIT_ROM --out EFI-output
```

The script fetches official **OpenCore 1.0.8, Lilu 1.7.2, VirtualSMC 1.3.8, WhateverXe 0.8.3, AMFIAnchor 0.1.2, USBToolBox 1.2.0 and HfsPlus**, adds the Surface USB map and Intel A0ED injector, generates **SSDT-RTC0-SL4**, and checks the result with OpenCore `ocvalidate` on Windows. The output is `EFI-output/EFI/`. **The builder has not yet been independently boot-tested from a clean checkout; the confirmed boot used the original test-machine EFI.**

**4. Prepare the USB** as GPT with two volumes:

| Volume | Format | Files |
|---|---|---|
| `MACOS-OC` (~2 GB) | FAT32 | `EFI/` from the builder, and `com.apple.recovery.boot/BaseSystem.dmg` + `BaseSystem.chunklist` |
| `SL4DATA` (remaining space) | exFAT | Apple `InstallAssistant.pkg`, `BaseSystem.dmg`, `BaseSystem.chunklist`, and [UnPlugged.command](https://github.com/corpnewt/UnPlugged) |

Download Apple Recovery using OpenCore [macrecovery.py](https://github.com/acidanthera/OpenCorePkg/tree/master/Utilities/macrecovery). The tested Tahoe path used Board ID `Mac-CFF7D910A743CAAF`. Download the full Tahoe `InstallAssistant.pkg` **directly from Apple**; it is larger than FAT32’s file limit. Apple installer files are not distributed here.

**5. Boot and install.** Boot the Surface from USB, select **macOS Base System (External)** in OpenCore, then check the disks in Recovery with `diskutil list`. If `SL4DATA` is mounted, run:

```bash
bash /Volumes/SL4DATA/UnPlugged.command
```

Use **only a dedicated APFS macOS volume** as the installation target, choose **Copy**, review the final summary, and follow the installer. Keep booting through USB OpenCore during installation.

> **Windows dual-boot:** I used unallocated space for a separate Tahoe APFS container. Do not erase the internal SSD, Windows NTFS, Microsoft Reserved or Windows EFI partitions. See [safe partitioning](docs/SAFETY.md).

**Post-install: faster OpenCore.** The tested USB still had diagnostic logging. I provide a [quiet boot profile](docs/QUIET-BOOT.md) that removes verbose logs, shows the picker for 4 seconds, and supports saving **macOS Tahoe as default with Ctrl+Enter**. Windows remains selectable. The EFI builder now produces the quiet profile by default; use `--verbose-boot` to keep debug output for troubleshooting.

**6. Boot without the USB (after both OSes work).** Copy the *known-good Kingston* `EFI/OC` to the internal Windows EFI System Partition using the read-only/staging tool. Then add a **separate OpenCore firmware entry**, keeping Windows Boot Manager unchanged. Follow [Boot without USB](docs/INTERNAL-BOOT.md). Test Windows and Tahoe separately **before** making OpenCore the default. This internal boot method is documented but not yet verified on the test Surface.

**7. Optional hardware drivers.** Build a *separate* experimental EFI containing audio, Intel Wi-Fi/Bluetooth, BigSurface, VoodooI2C/VoodooPS2 and battery kexts. They are staged **disabled** by default, with opt-in test profiles for audio, Wi-Fi and Bluetooth:

```powershell
py -3 scripts/add_optional_drivers.py --source EFI-output/EFI --out EFI-peripherals
```

See [drivers and test profiles](docs/DRIVERS.md). **Do not enable conflicting experimental input drivers together.**

**8. Install the full driver candidate pack and graphics acceleration.** Follow [Full performance setup](docs/FULL-PERFORMANCE.md) to stage all available kexts on the internal ESP, install WhateverXe Graphics 0.4.4 **inside macOS**, then remove `-wex-noaccel` from the internal OpenCore configuration with a verified rollback. Keep the original Kingston rescue EFI unchanged. The full package is prepared for testing; acceleration on the specific 96-EU Surface is not yet confirmed.

