#!/bin/zsh
# Windows-first Surface Laptop 4 i7 Tahoe all-in-one macOS finish and repair.
# Never changes the Windows boot manager; boot USB graphics stage is separate
# from an internal ESP, with an on-ESP and private local OpenCore backup.
set -euo pipefail
base="$(cd -- "$(dirname -- "$0")" && pwd)"
DMC='SL4-S0ix-DMC-0.2.0-beta.zip'
RCS='SL4-RCS-Stability-0.1.0-beta.zip'
DOLBY='SL4-Dolby-APOMac-Profiles-20261123.zip'
APOMAC='APOMac-0.1.0.dmg'
expected_graphics='f4c2d680a7c52c33a3f038ce6945da0aa2cc044e62b935a52ea046c7c473cfec'
expected_dmc='dd793ab5ce18079ae75484daae8a37766ccd466b181f40df79df74bdf34f30dd'
expected_rcs='21f3a54a9e870457128bb483cae9d5753178d30b44dfb2b70fed812904342960'
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
    verify "$base/$RCS" "$expected_rcs"
    verify "$base/$DOLBY" "$expected_dolby"
    verify "$base/$APOMAC" "$expected_apomac"
    verify "$base/WhateverXe-Graphics-0.4.4.pkg" "$expected_graphics"
    [[ -f "$base/ocvalidate" && -f "$base/enable_xe_macos.py" &&
       -f "$base/install_dolby_macos.py" ]] || {
        print -u2 "Incomplete all-in-one hardware installer on SL4DATA."
        return 4
    }
    python3 "$base/install_dolby_macos.py" check --bundle "$base/$DOLBY" --apomac-dmg "$base/$APOMAC"
    print "All five pinned graphics/audio assets verified."
}
install_audio() {
    sudo python3 "$base/install_dolby_macos.py" apply --bundle "$base/$DOLBY" --apomac-dmg "$base/$APOMAC"
    print "Dolby Clear Speech configured for built-in speakers and automatic login."
    print "On first launch, macOS may ask for System Audio Recording permission; click Allow."
}
install_from_usb() {
    local boot='/Volumes/MACOS-OC/EFI' tools="$HOME/Downloads/SL4-Tahoe-Installer-Tools"
    check_assets
    [[ -f "$boot/OC/config.plist" && -f "$boot/BOOT/BOOTx64.efi" ]] || {
        print -u2 "Windows-prepared MACOS-OC USB boot partition not mounted. Cannot stage graphics."
        return 5
    }
    print "Installing pinned Tahoe 26.7.1 graphics donors..."
    sudo /usr/sbin/installer -pkg "$base/WhateverXe-Graphics-0.4.4.pkg" -target /
    mkdir -p "$tools"
    cp "$base/ocvalidate" "$tools/ocvalidate"
    chmod 755 "$tools/ocvalidate"
    print "Staging Metal + DMC + eDP + single-port RCS fix in ONE OpenCore transition..."
    sudo python3 "$base/enable_xe_macos.py" check --efi "$boot" --release "$base/$DMC" --rcs "$base/$RCS" --ocvalidate "$tools/ocvalidate"
    sudo python3 "$base/enable_xe_macos.py" apply --efi "$boot" --release "$base/$DMC" --rcs "$base/$RCS" --ocvalidate "$tools/ocvalidate"
    install_audio
    print "ALL-IN-ONE READY. Restart from USB OpenCore. No separate RCS installer or sound import is required."
    print "Keep the USB recovery EFI and complete dual boot only after a successful accelerated Tahoe boot."
}
repair_existing() {
    local esp workspace patch
    check_assets
    if /usr/sbin/ioreg -p IOService -l -w0 2>/dev/null | /usr/bin/grep -q '"SL4RCSSinglePortReady" = Yes'; then
        print "RCS single-port patch is already active; keeping the working EFI untouched."
    else
        esp="$(python3 "$base/find_internal_esp.py")"
        print "Internal EFI detected: $esp. Running fail-closed RCS preflight."
        workspace="$(/usr/bin/mktemp -d "$HOME/Downloads/sl4-rcs-install.XXXXXX")"
        trap '[[ -n "${workspace:-}" && -d "$workspace" ]] && /bin/rm -rf "$workspace"' EXIT
        /usr/bin/ditto -x -k "$base/$RCS" "$workspace"
        patch="$workspace/SL4-RCS-Stability-0.1.0-beta/install.py"
        [[ -f "$patch" ]] || { print -u2 "RCS installer missing"; return 7; }
        sudo python3 "$patch" check --esp "$esp"
        sudo python3 "$patch" apply --esp "$esp"
        print "RCS staged in the INTERNAL EFI. Reboot needed to activate."
    fi
    install_audio
    print "ONE-CLICK REPAIR READY. No need to install RCS or audio separately."
}
print "Surface Laptop 4 Intel — Windows-first Tahoe all-in-one hardware setup"
print "  1) First Tahoe installation: Metal 2 + RCS fix + peripherals + Dolby Clear Speech"
print "  2) Already installed Tahoe: apply missing RCS fix + Dolby Clear Speech"
print "  3) Advanced read-only audio and brightness inspection"
print "  0) Exit"
read "choice?Choose: "
case "$choice" in
    1) install_from_usb ;;
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
    0) exit 0 ;;
    *) print -u2 "Unknown option"; exit 4 ;;
esac
