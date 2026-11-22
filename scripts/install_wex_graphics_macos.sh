#!/bin/bash
# macOS Tahoe 26.7+ only. Install the official WhateverXe Graphics v0.4.4
# package after validating its SHA256. Does not modify EFI or boot flags.
set -euo pipefail
EXPECTED="f4c2d680a7c52c33a3f038ce6945da0aa2cc044e62b935a52ea046c7c473cfec"
PKG="${1:-/Volumes/SL4DATA/WhateverXe-Graphics-0.4.4.pkg}"
if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "x86_64" ]; then
  echo "STOP: x86_64 macOS is required" >&2; exit 1
fi
VERSION="$(sw_vers -productVersion)"
MAJOR="${VERSION%%.*}"
REST="${VERSION#*.}"
MINOR="${REST%%.*}"
if [ "$MAJOR" -ne 26 ] || [ "$MINOR" -lt 7 ]; then
  echo "STOP: Graphics 0.4.4 requires macOS Tahoe 26.7+; detected $VERSION" >&2; exit 1
fi
if [ ! -f "$PKG" ]; then
  echo "STOP: package not found: $PKG" >&2; exit 1
fi
FOUND="$(shasum -a 256 "$PKG" | awk '{print $1}')"
if [ "$FOUND" != "$EXPECTED" ]; then
  echo "STOP: official Graphics 0.4.4 SHA256 mismatch" >&2; exit 1
fi
echo "Validated official package SHA256: $FOUND"
echo "macOS: $VERSION"
echo "Current SIP status:"
csrutil status || true
echo "AMFIAnchor status (inspect InstallStatus and LoadedAnchors):"
ioreg -r -c AMFIAnchor -l | grep -E 'InstallStatus|LoadedAnchors' || true
echo
echo "This package installs graphics drivers into /Library and rebuilds AuxKC."
echo "It is NOT a firmware driver or a standalone OpenCore kext."
echo "The package is not notarized; proceed only with the verified upstream release."
printf "Type INSTALL-WEX-GRAPHICS to install: "
read -r answer
if [ "$answer" != "INSTALL-WEX-GRAPHICS" ]; then
  echo "Cancelled"; exit 1
fi
sudo installer -pkg "$PKG" -target /
echo "INSTALLER SUCCESS. Do not remove -wex-noaccel until preparing the internal EFI"
echo "using scripts/xe_acceleration.py --mode enable from Windows."
echo "Restart only after the installer reports success and the EFI is ready."
