# Preserve Windows 11 and the internal SSD

The Intel Surface Laptop 4 test machine now boots **Tahoe 26.7.1 with Metal 2** from its internal OpenCore EFI alongside Windows 11. This repository is not a disk-imaging guide, and the existing Windows installation and Microsoft boot files must remain intact.

## Confirmed test-machine layout

Physical Samsung PM991 256 GB (actual `diskutil list internal` on 2026-11-22):

| Internal partition | Type | Size |
| --- | --- | --- |
| `disk0s1` | EFI `SYSTEM` FAT32 | 272.6 MB |
| `disk0s2` | Microsoft Reserved | 16.8 MB |
| `disk0s3` | Windows 11 NTFS | 107.4 GB |
| `disk0s4` | APFS Tahoe container | 148.4 GB |

**These numbers/identifiers are specific to the test laptop and must not be assumed on other systems.** Never erase the internal SSD, Windows NTFS, Microsoft Reserved, `EFI/SYSTEM`, or Windows Boot Manager to apply graphics updates.

- Windows firmware path remains `\EFI\Microsoft\Boot\bootmgfw.efi`. The internal OpenCore path is **separate**: `\EFI\OC\OpenCore.efi`.
- The boot-critical Surface-specific `SSDT-RTC0-SL4.aml` uses `\_SB.PC00.LPCB`; do not remove it.
- The current, working accelerated graphics result depends on Graphics 0.4.4 installed inside Tahoe **plus** verified 60 MB DVMT properties. The pre-acceleration `-wex-noaccel` config remains a **rollback copy**, not the normal performance profile.
- The test machine's private working accelerated backup is `~/Downloads/SL4-WORKING-METAL.plist` in Tahoe. Earlier pre-acceleration backups were also taken. These files contain private identifiers; do not publish them.

## Before modifying anything

1. Back up Windows and Tahoe data. Securely store the disk encryption / BitLocker recovery key if enabled. Keep copies of current OpenCore and previous working `config.plist` **outside the ESP**.
2. Mount only the **existing internal ESP** as Administrator. In Windows its working mount was `S:`. Check the file location and current firmware entry before changing it.
3. Use matching **OpenCore 1.0.8** `ocvalidate.exe` and read-only inspection before applying the guarded graphics scripts. `ocvalidate` does not test whether hardware will boot.
4. Do not mix all candidate input/battery kexts. BigSurface may require different ACPI/SAM configuration and conflict with VoodooI2C or SMCBatteryManager.
5. Avoid unnecessary firmware NVRAM resets, Windows BCD changes, filesystem repairs, ESP formatting or partition edits. These can break dual boot without addressing the GPU.

## Post-install path (no removable media)

See [Quick Start](../README.md#quick-start-reproduce-the-validated-metal-2-state-existing-tahoe-no-removable-media) and [actual validated result](VALIDATED-METAL-SL4.md). Use the already installed Windows and Tahoe on the **internal SSD**: the Windows NTFS partition can be read by macOS to transfer the officially verified Graphics pkg. Never use the small Windows ESP to store macOS installation packages.

If an ESP mount fails in macOS, first confirm its filesystem and try a **read-only mount** rather than repair. The test ESP was successfully mounted via `sudo diskutil mount readOnly disk0s1` and subsequently mounted read/write without formatting; this is an observation from one test, not a general fix for disk corruption.

## If you are doing an initial macOS installation

Only use genuinely free/unallocated space for a new APFS container, and check the live partition map. Never use `eraseDisk` or `partitionDisk` on the shared physical SSD. The old first-install procedure is kept as a [historical record](LEGACY-FIRST-BOOT.md); it is not required to reproduce the current installed machine's Metal configuration, and it has **not** been revalidated as an end-to-end clean installation.

The Samsung PM991 is a potential macOS stability risk; a successful accelerated boot does not certify long-term SSD behavior, sleep or safe sustained writes.

Related: [internal boot](INTERNAL-BOOT.md) · [RTC0 case study](RTC0-CASE-STUDY.md) · [driver status](DRIVERS.md).
