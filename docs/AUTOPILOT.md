# Surface Laptop 4 — Windows-first Autopilot v0.5.0 beta

This is the most automated install we can safely offer from a clean Windows 11 machine. The starting point is one double-click of `QuickStart.cmd`, not a manually assembled EFI or preinstalled Tahoe. The same CMD resumes its own workflow after macOS has been installed and tested.

**Exact validated target:** Microsoft Surface Laptop 4, Intel Core i7-1185G7, Iris Xe PCI 8086:9A49, ALC274 10EC:123E, macOS Tahoe **26.7.1**. The system is not automatically certified for other CPUs, GPUs, OS versions or Surface models.

## How the automatic flow works

**Windows — double-click `QuickStart.cmd`.** It selects the built-in Surface profile, installs Python if missing, prepares a personalized OpenCore EFI, downloads Apple Recovery and pinned graphics/driver dependencies, and checks their SHA-256 signatures. It identifies eligible removable USB disks automatically; if there is exactly one, it selects it. Before erasing any USB it requires **the exact disk-specific phrase `ERASE USB N`** and UAC approval. It never erases Windows partitions, Microsoft EFI or Steam. If no USB is inserted, prepared files are retained for a later retry via `QuickStart.cmd advanced`.

**Hardware boot and Apple Recovery.** Physically boot the Surface from the prepared `MACOS-OC` USB (Volume Down + Power, with Surface UEFI Secure Boot disabled). In Recovery, create a macOS APFS container **only in existing unallocated space** and use Apple's own installer and Setup Assistant. This step cannot safely be skipped: neither Windows CMD nor a portable recovery download can decide which internal partitions may be modified, bypass UEFI Security controls, accept Apple's installation conditions or create the user's macOS account without interactive setup.

**First Tahoe login — open `SL4DATA/QuickStart-Mac.command` once.** The script **automatically selects** the first-install or repair path based on actual Metal acceleration, RCS readiness and the source OpenCore USB. No separate menu choices, RCS patch, kext selection or manual Dolby profile import. macOS still requests administrator authentication for system/EFI writes. The integrated script installs the official Graphics package, verifies the Tahoe CoreMedia H.264/HEVC setting, stages the exact RCS + DMC + eDP Softsleep + S0ix hardware profile, registers the APOMac login item and selects the original Dolby **Clear Speech** profile. **No `pmset` writes**; sleep and display wake retain the user's actual settings.

**First reboot — automatic verification.** The installer registers a per-user macOS LaunchAgent `com.sl4.autoverify`. On the next login, it confirms that the actual accelerated graphics and S0ix kexts are loaded, eDP/Softsleep/DMC/RCS IORegistry readiness flags are present, Metal 2 works, CoreMedia video fix is active and the exact built-in-speaker Dolby profile exists. It only reads `pmset`. If any check fails, it **does not mark the USB ready**. On success, it writes `SL4-AUTO-READY.json` to the USB `SL4DATA` volume. If the boot USB is removed before this check, no marker is written.

**Final Windows entry — double-click the same `QuickStart.cmd` again.** With the prepared USB inserted and the readiness marker present, the script independently rehashes the tested RCS binary and OpenCore config on the matching USB disk. It then invokes the existing internal-OpenCore staging process, with its full Windows boot-manager backup, UAC authorization and explicit confirmation. It does **not** silently change EFI/Microsoft or repartition the SSD. An additional firmware boot entry is optional, and user approval is still required to change boot entries.

After that, Windows and macOS should be selectable through OpenCore/UEFI. Physical validation of both systems, keyboard, sound, sleep and video is still recommended.

## Things an ordinary program cannot do without explicit permission

- Turn off Surface UEFI Secure Boot or press the power/volume keys.
- Choose or erase macOS's target partition on the user's behalf without a trustworthy user selection.
- Skip Apple Recovery and the macOS Setup Assistant on a new machine.
- Automatically grant APOMac the protected **Screen & System Audio Recording** permission. Apple requires the user to allow it. [Apple's current instructions](https://support.apple.com/en-my/guide/mac-help/mchl592e5686/26/mac/26).
- Test real lid/RTC wake, YouTube rendering and speaker sound without the hardware and the user.

## Diagnostic and rollback

Use `QuickStart-Advanced.cmd` (or `QuickStart.cmd advanced`) for the previous guided Windows menu; use `zsh /Volumes/SL4DATA/QuickStart-Mac.command --menu` for the Mac advanced menu. The original OpenCore config and a complete private EFI/OC backup remain available on the installer USB and macOS Downloads. The previous releases are still accessible independently. The new LaunchAgent only checks readiness and writes a non-secret marker; it **never runs as root**, erases disks, changes BCD/EFI or grants app permissions.

For read-only automatic-route diagnostics run `zsh /Volumes/SL4DATA/QuickStart-Mac.command --inspect-auto`. For full first-boot validation run `python3 /Volumes/SL4DATA/auto_verify_first_boot_macos.py check --source /Volumes/SL4DATA`. The command reports failure instead of creating the marker if any required active driver or video compatibility condition is missing.

**Limits:** no new installation of v0.5.0 has yet completed the full physical boot-to-USB-to-Recovery-to-Tahoe sequence on another machine. MacOS Tahoe 26.7.1 is strictly enforced for the driver-stage preflight. The Apple Recovery downloader may offer a different OS version as upstream releases change; verify that the installer is Tahoe 26.7.1 before proceeding. This remains a beta until the full workflow is proven on a clean reference Windows machine.
