#!/bin/zsh
# Mac side of the Windows-first Surface Tahoe setup.
# Source: USB SL4DATA or its copy in macOS Downloads.
set -euo pipefail
base="$(cd -- "$(dirname -- "$0")" && pwd)"
echo "Surface Laptop 4 — complete hardware setup in macOS"
echo "This assistant is for AFTER booting Tahoe with USB OpenCore."
if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "x86_64" ]; then
  echo "Requires Intel macOS." >&2
  exit 1
fi
echo "macOS: $(sw_vers -productVersion)"
echo "1) Install official Tahoe Iris Xe Graphics driver"
echo "2) Prepare/repair Tahoe drivers (existing macOS)"
echo "3) Install audio and brightness on already-booting Tahoe"
echo "0) Exit"
read "choice?Choose: "
case "$choice" in
  1)
    pkg="$base/WhateverXe-Graphics-0.4.4.pkg"
    expected="f4c2d680a7c52c33a3f038ce6945da0aa2cc044e62b935a52ea046c7c473cfec"
    [ -f "$pkg" ] || { echo "Graphics package missing on SL4DATA." >&2; exit 2; }
    actual="$(shasum -a 256 "$pkg" | awk '{print $1}')"
    [ "$actual" = "$expected" ] || { echo "Graphics SHA-256 mismatch." >&2; exit 2; }
    sudo installer -pkg "$pkg" -target /
    echo "Official Graphics package installed."
    boot="/Volumes/MACOS-OC/EFI"
    [ -f "$boot/OC/config.plist" ] || { echo "Connect your Windows-prepared USB (volume MACOS-OC) before finishing graphics." >&2; exit 3; }
    tools="$HOME/Downloads/SL4-Tahoe-Installer-Tools"
    mkdir -p "$tools"
    cp "$base/ocvalidate" "$tools/ocvalidate"
    chmod 755 "$tools/ocvalidate"
    sudo python3 "$base/enable_xe_macos.py" check --efi "$boot" --release "$base/SL4-S0ix-DMC-0.2.0-beta.zip" --ocvalidate "$tools/ocvalidate"
    sudo python3 "$base/enable_xe_macos.py" apply --efi "$boot" --release "$base/SL4-S0ix-DMC-0.2.0-beta.zip" --ocvalidate "$tools/ocvalidate"
    echo "Metal 2, Wi-Fi/Bluetooth, audio, brightness and S0ix boot profile prepared on USB."
    echo "Restart from USB OpenCore. Your original EFI is backed up."
    ;;
  2)
    if [ ! -f "$base/SL4-S0ix-DMC-0.2.0-beta.zip" ]; then
      echo "Driver bundle not found in SL4DATA." >&2; exit 3
    fi
    mkdir -p "$HOME/Downloads/SL4-Drivers"
    cp -n "$base/SL4-S0ix-DMC-0.2.0-beta.zip" "$HOME/Downloads/SL4-Drivers/"
    cd "$HOME/Downloads/SL4-Drivers"
    unzip -n -q "SL4-S0ix-DMC-0.2.0-beta.zip"
    echo "Driver bundle ready:"
    echo "$HOME/Downloads/SL4-Drivers/SL4-S0ix-DMC-0.2.0-beta/install.py"
    echo "Run its check and apply modes for the EXACT compatible Intel Surface profile."
    echo "For audio and brightness run scripts/drivers/install_audio_macos.py and install_brightness_macos.py with --esp."
    ;;
  3)
    echo "Use a verified internal EFI and keep Windows Boot Manager intact."
    printf "Enter actual internal EFI partition (from diskutil list; e.g. disk0s1): "
    read -r esp
    [ -n "$esp" ] || { echo "EFI identifier required" >&2; exit 7; }
    sudo python3 "$base/drivers/install_audio_macos.py" inspect --esp "$esp"
    sudo python3 "$base/drivers/install_brightness_macos.py" inspect --esp "$esp"
    echo "Preflight complete; to apply run each installer with apply --esp $esp."
    ;;
  0) exit 0 ;;
  *) echo "Unknown option" >&2; exit 4 ;;
esac
