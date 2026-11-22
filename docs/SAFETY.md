# Keep Windows intact

**This project booted Tahoe on a Surface Laptop 4 with Windows 11 on the internal SSD. It is not a destructive disk-imaging guide.**

## Before touching partitions

- Create and test a Windows backup and recovery USB. Back up the Microsoft EFI partition and your BitLocker recovery key.
- In Windows Disk Management, **shrink Windows first** to leave **unallocated** space. Do not delete or format the Windows volume to make room.
- Inspect the actual disks in Recovery with `diskutil list` and `gpt -r show /dev/diskN`. Device numbers change between boots, and must never be copied blindly from screenshots.
- Create APFS **only in confirmed unallocated space**. In the original test, Windows remained on `disk1s3`, while a distinct 148.4 GB APFS container became `disk1s4`. **Those identifiers are examples, not commands to run on another laptop.**
- Do not use `eraseDisk` or `partitionDisk` on the internal SSD. Never erase or overwrite `EFI SYSTEM`, `Microsoft Reserved` or the Windows NTFS volume.
- Keep OpenCore on the external USB until Tahoe and Windows can both boot reliably. For permanent USB-free startup, [stage the known-working OpenCore as a separate firmware entry](INTERNAL-BOOT.md). Never overwrite Windows Boot Manager or the UEFI fallback loader.
- The Samsung PM991 is a known macOS compatibility risk; successful detection at boot does not prove stable write operation. Keep reliable backups.

## Installer media

The tested USB used GPT with a FAT32 boot/Recovery partition and an exFAT data partition. Download Apple's genuine Recovery with OpenCore `macrecovery.py` and download `InstallAssistant.pkg` from Apple. The full PKG cannot live on FAT32 because it exceeds 4 GiB.

`UnPlugged.command` was used from `/Volumes/SL4DATA` to assemble and run the installer. Confirm the target volume is **Tahoe**, read the Task Summary, and never choose **Windows**.

## After installation

Run `diskutil list` and Windows Disk Management again, verify both OSes boot independently, and keep a copy of your **personal** OpenCore EFI in a safe private location. Do not publish SMBIOS serial, MLB, SystemUUID, ROM or boot logs containing those identifiers.

Read the [case study](RTC0-CASE-STUDY.md) for the actual ACPI change and previous unsuccessful attempts.
