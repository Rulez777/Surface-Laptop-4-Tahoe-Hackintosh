#!/bin/zsh
# Windows-first Surface Laptop 4 i7 Tahoe all-in-one macOS finish and repair.
# Never changes the Windows boot manager; boot USB graphics stage is separate
# from an internal ESP, with an on-ESP and private local OpenCore backup.
set -euo pipefail
base="$(cd -- "$(dirname -- "$0")" && pwd)"
DMC='SL4-S0ix-DMC-0.2.0-beta.zip'
INPUT='SL4-TGL-Input-SleepWake-v2-beta.zip'
RCS='SL4-Graphics-Performance-0.1.7-beta.zip'
DOLBY='SL4-Dolby-APOMac-Profiles-20261123.zip'
APOMAC='APOMac-0.1.0.dmg'
expected_graphics='f4c2d680a7c52c33a3f038ce6945da0aa2cc044e62b935a52ea046c7c473cfec'
expected_dmc='dd793ab5ce18079ae75484daae8a37766ccd466b181f40df79df74bdf34f30dd'
expected_input='11744d792a6c5ec9bc5f77dac4f020b095991c4eb604d7e232d9cab560896018'
expected_rcs='bdbb6aad67ebcfc2185281c5ea8dca267cdd6e3c2aad3371bd701e3b5417880d'
expected_dolby='ff029e860aec93763dc5fac3032c154a82fc571deb5cc08b5a9ad005907cc013'
expected_apomac='525a6adef1cbad76906d620656c93d7b1da1b3c8d6189b3f12648cfb221006fd'

if [[ "$(uname -s)" != Darwin || "$(uname -m)" != x86_64 ]]; then
    print -u2 "Requires Intel macOS, not Windows or Apple Silicon."
    exit 1
fi

verify() {
    local file="$1" want="$2" got
    [[ -f "$file" ]] || { print -u2 "Missing component: $file"; return 2; }
    got="$(/usr/bin/shasum -a 256 "$file" | /usr/bin/awk '{print $1}')"
    [[ "$got" == "$want" ]] || { print -u2 "Unexpected checksum: $file"; return 3; }
}
check_assets() {
    verify "$base/$DMC" "$expected_dmc"
    verify "$base/$INPUT" "$expected_input"
    verify "$base/$RCS" "$expected_rcs"
    verify "$base/$DOLBY" "$expected_dolby"
    verify "$base/$APOMAC" "$expected_apomac"
    verify "$base/WhateverXe-Graphics-0.4.4.pkg" "$expected_graphics"
    [[ -f "$base/ocvalidate" && -f "$base/enable_xe_macos.py" &&
       -f "$base/install_dolby_macos.py" &&
       -f "$base/install_compute_hint_macos.py" &&
       -f "$base/install_hdrp_swsb_macos.py" &&
       -f "$base/install_sl4_sleepwake_macos.py" &&
       -f "$base/auto_verify_first_boot_macos.py" ]] || {
        print -u2 "Incomplete all-in-one hardware installer on SL4DATA."
        return 4
    }
    python3 "$base/install_dolby_macos.py" check --bundle "$base/$DOLBY" --apomac-dmg "$base/$APOMAC"
    print "All six pinned graphics/audio/input/sleep-wake assets verified."
}
verify_sleepwake_efi() {
    local efi="$1"
    python3 - "$efi" <<'PY'
import pathlib, plistlib, hashlib, sys
efi = pathlib.Path(sys.argv[1])
oc = efi / "OC"
cfg = plistlib.loads((oc / "config.plist").read_bytes())
boot = cfg.get("NVRAM", {}).get("Add", {}).get("7C436110-AB2A-4BBB-A880-FE41995C9F82", {})
boot_args = boot.get("boot-args", "")
boot_arg_list = (boot_args.decode("utf-8") if isinstance(boot_args, bytes) else str(boot_args)).split()
for disabled_flag in ("-wex-edp-wake-trace","-wex-sl4-rcs-singleport","-wex-sl4-rcs-nativequeue-trial"):
    if disabled_flag in boot_arg_list:
        raise SystemExit("Default EFI unexpectedly enables disabled trial/diagnostic flag: " + disabled_flag)
def enabled(name):
    return [x for x in cfg["Kernel"]["Add"] if x.get("BundlePath") == name + ".kext" and x.get("Enabled")]
for name, version in (("VoodooGPIO","1.2.5"),("BigSurface","1.2.1")):
    entries = enabled(name)
    if len(entries) != 1:
        raise SystemExit("Missing or duplicate enabled " + name + ".kext")
    info = plistlib.loads((oc/"Kexts"/(name+".kext")/"Contents/Info.plist").read_bytes())
    if info.get("CFBundleVersion") != version:
        raise SystemExit("Wrong " + name + " version in EFI")
aml = oc/"ACPI/SSDT-SL4-LIDWAKE.aml"
if not aml.is_file() or hashlib.sha256(aml.read_bytes()).hexdigest() != "96efe9f179bbf62b9d30c2742f6d5be303d0c78b5f569b31c562e0035903aefb":
    raise SystemExit("Missing or incorrect SL4 lid-wake SSDT")
if not any(x.get("Path")=="SSDT-SL4-LIDWAKE.aml" and x.get("Enabled") for x in cfg["ACPI"]["Add"]):
    raise SystemExit("Lid-wake SSDT is not enabled in ACPI/Add")
if cfg.get("Misc",{}).get("Debug",{}).get("SysReport",True) is not False:
    raise SystemExit("OpenCore SysReport must be disabled in the public profile")
print("VERIFIED: VoodooGPIO 1.2.5, BigSurface 1.2.1, SL4 lid-wake SSDT, SysReport=False")
PY
}
install_sleepwake_internal() {
    local disk="$1" mountpoint="" status=0
    # find_internal_esp.py returns a device identifier, not a mount path.
    # Remount explicitly read/write so the guarded installer can validate and stage.
    if [[ "$disk" != disk[0-9]s[0-9] ]]; then
        print -u2 "Unexpected internal ESP identifier: $disk"
        return 6
    fi
    mountpoint="$(/usr/sbin/diskutil info -plist "$disk" | /usr/bin/python3 -c 'import plistlib,sys; print(plistlib.load(sys.stdin.buffer).get("MountPoint") or "")')"
    if [[ -n "$mountpoint" ]]; then
        sudo /usr/sbin/diskutil unmount "$disk" || return 6
    fi
    sudo /usr/sbin/diskutil mount "$disk" || return 6
    mountpoint="$(/usr/sbin/diskutil info -plist "$disk" | /usr/bin/python3 -c 'import plistlib,sys; print(plistlib.load(sys.stdin.buffer).get("MountPoint") or "")')"
    if [[ -z "$mountpoint" || ! -d "$mountpoint/EFI" ]]; then
        print -u2 "Could not resolve mounted internal EFI directory for $disk"
        sudo /usr/sbin/diskutil unmount "$disk" >/dev/null 2>&1 || true
        return 6
    fi
    sudo python3 "$base/install_sl4_sleepwake_macos.py" --mode apply --efi "$mountpoint/EFI" \
      --artifact "$base/$INPUT" --backup-dir "$HOME/Downloads/SL4-SLEEPWAKE-BACKUPS" \
      --ocvalidate "$base/ocvalidate" --ack STAGE-SL4-SLEEPWAKE || status=$?
    sync
    sudo /usr/sbin/diskutil unmount "$disk" || return 6
    return "$status"
}
install_audio() {
    sudo python3 "$base/install_dolby_macos.py" apply --bundle "$base/$DOLBY" --apomac-dmg "$base/$APOMAC"
    print "Dolby Clear Speech configured for built-in speakers and automatic login."
    print "On first launch, macOS may ask for System Audio Recording permission; click Allow."
}
verify_coremedia_h264() {
    local file='/Library/Preferences/FeatureFlags/Domain/CoreMedia.plist' flag
    [[ -f "$file" ]] || { print -u2 "WhateverXe Graphics did not install Tahoe CoreMedia compatibility flag"; return 15; }
    flag="$(/usr/libexec/PlistBuddy -c 'Print :AllowOnePassMetalScaling:Enabled' "$file" 2>/dev/null)" || {
        print -u2 "Cannot read CoreMedia video playback compatibility flag"; return 15
    }
    [[ "$flag" == "false" ]] || {
        print -u2 "Unexpected CoreMedia AllowOnePassMetalScaling setting; refusing to stage RCS"; return 15
    }
    print "VERIFIED: Tahoe CoreMedia compatibility for existing H.264/HEVC playback."
}
report_sleep_policy_unchanged() {
    # READ-ONLY: respect the user's working sleep/wake and display-wake policy.
    # pmset sleep=0 can still permit manual sleep, and is NOT set here.
    print "Current user power settings (preserved; no adjustments):"
    /usr/bin/pmset -g custom
    print "Clamshell wake uses the SL4 F11 GPE profile; SAM keyboard/trackpad wake is enabled but still requires physical validation."
    print "Real lid, power-button and battery sleep must be checked on each machine."
}
install_from_usb() {
    local boot='/Volumes/MACOS-OC/EFI' tools="$HOME/Downloads/SL4-Tahoe-Installer-Tools"
    check_assets
    [[ -f "$boot/OC/config.plist" && -f "$boot/BOOT/BOOTx64.efi" ]] || {
        print -u2 "Windows-prepared MACOS-OC USB boot partition not mounted. Cannot stage graphics."
        return 5
    }
    verify_sleepwake_efi "$boot"
    print "Installing pinned Tahoe 26.7.1 graphics donors..."
    sudo /usr/sbin/installer -pkg "$base/WhateverXe-Graphics-0.4.4.pkg" -target /
    verify_coremedia_h264
    mkdir -p "$tools"
    cp "$base/ocvalidate" "$tools/ocvalidate"
    chmod 755 "$tools/ocvalidate"
    print "Staging Metal + DMC + eDP + the reference heap-depth profile in ONE OpenCore transition..."
    print "Experimental RCS single-port/native-queue trial hooks remain disabled by default."
    sudo python3 "$base/enable_xe_macos.py" check --efi "$boot" --release "$base/$DMC" --rcs "$base/$RCS" --ocvalidate "$tools/ocvalidate"
    sudo python3 "$base/install_hdrp_swsb_macos.py" apply
    sudo python3 "$base/enable_xe_macos.py" apply --efi "$boot" --release "$base/$DMC" --rcs "$base/$RCS" --ocvalidate "$tools/ocvalidate"
    report_sleep_policy_unchanged
    install_audio
    print "ALL-IN-ONE READY. Restart from USB OpenCore. Experimental RCS trial hooks remain opt-in."
    print "Keep the USB recovery EFI and complete dual boot only after a successful accelerated Tahoe boot."
}
repair_existing() {
    local esp
    check_assets
    esp="$(python3 "$base/find_internal_esp.py")"
    print "Ensuring the pinned SL4 input + lid-wake profile in the INTERNAL EFI..."
    install_sleepwake_internal "$esp"
    sudo python3 "$base/install_hdrp_swsb_macos.py" check
    if rcs_trial_ready; then
        print "An existing RCS trial is already active; leaving its boot arguments and driver untouched."
        print "WARNING: this remains a beta trial; Loaded/Ready is not proof of long-term stability."
    else
        print "RCS single-port/native-queue trial hooks are disabled in the default profile."
        print "The pinned RCS payload remains available for deliberate opt-in; no experimental flags are added."
    fi
    sudo python3 "$base/install_hdrp_swsb_macos.py" apply
    install_audio
    print "ONE-CLICK REPAIR READY. Existing graphics and power settings are preserved."
}
# Detect first installation vs existing accelerated Tahoe. User can still open
# the advanced menu deliberately with --menu. Nothing touches a different
# computer; all asset, donor and OpenCore preflight remains mandatory.
graphics_loaded() {
    /usr/sbin/system_profiler SPDisplaysDataType 2>/dev/null | /usr/bin/grep -q 'Metal Support: Metal 2'
}
rcs_trial_ready() {
    local props="$(/usr/sbin/ioreg -p IOService -l -w0 2>/dev/null)"
    [[ "$props" == *'"SL4RCSNativeQueueTrialReady" = Yes'* &&
       "$props" == *'"SL4HeapDepthTrialReady" = Yes'* ]] &&
        /usr/bin/kmutil showloaded 2>/dev/null | /usr/bin/grep -q '1DAD98CE-CD44-3CA8-9BEE-CE65F3B47DBF'
}
usb_efi_ready() {
    [[ -f /Volumes/MACOS-OC/EFI/OC/config.plist &&
       -f /Volumes/MACOS-OC/EFI/BOOT/BOOTx64.efi ]]
}
usb_staged() {
    [[ -f /Volumes/MACOS-OC/EFI/OC/config.plist ]] || return 1
    /usr/libexec/PlistBuddy -c 'Print :Kernel:Add' /Volumes/MACOS-OC/EFI/OC/config.plist 2>/dev/null |
        /usr/bin/grep -q 'WhateverXe-SL4-RCS-V017-TRIAL.kext'
}
arm_postboot_check() {
    local script="$base/auto_verify_first_boot_macos.py"
    [[ -f "$script" ]] || {
       print -u2 "Missing auto verification helper: $script"
       return 24
    }
    python3 "$script" install --source "$base"
    print "After the next successful accelerated macOS login, the verification agent checks DMC, heap-depth, screen wake, video and Dolby. RCS trial hooks are optional."
}
choose_automatic_action() {
    if rcs_trial_ready || graphics_loaded; then
        print "AUTO DETECT: existing accelerated Tahoe — repair input/sleep-wake and Dolby without reinstalling graphics."
        repair_existing
        if rcs_trial_ready; then
            python3 "$base/auto_verify_first_boot_macos.py" check --source "$base" || true
        fi
        return
    fi
    if usb_efi_ready; then
        if usb_staged; then
            print "AUTO DETECT: graphics stage already prepared on USB; reboot from that USB to activate the default profile. RCS trial hooks stay disabled."
            return
        fi
        print "AUTO DETECT: first Tahoe boot, setting up original Surface hardware."
        # Root permission is requested once and cached; macOS TCC audio consent
        # remains an explicit first-use click, never bypassed.
        sudo -v
        install_from_usb
        arm_postboot_check
        return
    fi
    print -u2 "Could not identify a verified accelerated Tahoe or Windows-prepared MACOS-OC USB. Mount MACOS-OC and SL4DATA, then retry; nothing changed."
    return 20
}
inspect_automatic_action() {
    if rcs_trial_ready || graphics_loaded; then
        print "AUTO_ROUTE=repair_existing (existing accelerated Tahoe)"
    elif usb_efi_ready && usb_staged; then
        print "AUTO_ROUTE=pending_reboot (USB already staged)"
    elif usb_efi_ready; then
        print "AUTO_ROUTE=install_from_usb (fresh Tahoe)"
    else
        print "AUTO_ROUTE=blocked (requires Windows-prepared MACOS-OC USB)"
    fi
    print "INSPECTION_ONLY: no EFI, power policy, audio or app changes."
}
reference_profile() {
    sudo python3 "$base/install_reference_20261125.py" "$1" --bundle "$base/SL4-Reference-20261125-beta.zip" --ocvalidate "$base/ocvalidate"
}
show_advanced_menu() {
    print "Surface Laptop 4 Intel — advanced macOS setup"
    print "  1) First Tahoe installation"
    print "  2) Already installed Tahoe — repair input/sleep-wake / audio"
    print "  3) Read-only audio and brightness inspection"
    print "  8) Opt in: Nov 25 reference graphics + AC GPU priority beta"
    print "  9) Roll back Nov 25 reference beta"
    print "  7) Read-only RCS GPU reset audit (no EFI or driver changes)"
    print "  0) Exit"
    read "choice?Choose: "
    case "$choice" in
        1) install_from_usb; arm_postboot_check ;;
        2) repair_existing ;;
        3)
            esp="$(python3 "$base/find_internal_esp.py")"
            audio="$base/drivers/install_audio_macos.py"
            brightness="$base/drivers/install_brightness_macos.py"
            [[ -f "$audio" ]] || audio="$base/install_audio_macos.py"
            [[ -f "$brightness" ]] || brightness="$base/install_brightness_macos.py"
            sudo python3 "$audio" inspect --esp "$esp"
            sudo python3 "$brightness" inspect --esp "$esp"
            ;;
        8) reference_profile apply ;;
        9) reference_profile rollback ;;
        7) python3 "$base/audit_rcs_gpu_resets_macos.py" --since-hours 24 ;;
        0) exit 0 ;;
        *) print -u2 "Unknown option"; exit 4 ;;
    esac
}
case "${1:---auto}" in
    --auto) choose_automatic_action ;;
    --inspect-auto) inspect_automatic_action ;;
    --auto-first) install_from_usb; arm_postboot_check ;;
    --auto-repair) repair_existing ;;
    --menu) show_advanced_menu ;;
    --reference-20261125) reference_profile apply ;;
    --reference-check) reference_profile check ;;
    --reference-rollback) reference_profile rollback ;;
    --rcs-audit) python3 "$base/audit_rcs_gpu_resets_macos.py" --since-hours 24 ;;
    *) print -u2 "Usage: QuickStart-Mac.command [--auto|--auto-first|--auto-repair|--menu|--rcs-audit|--reference-20261125|--reference-check|--reference-rollback]"; exit 3 ;;
esac
