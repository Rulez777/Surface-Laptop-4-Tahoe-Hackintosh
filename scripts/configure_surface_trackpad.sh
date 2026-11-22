#!/bin/sh
# Surface Laptop 4 Intel / BigSurface HID — user-level macOS touchpad preferences.
# Reported working on one Surface Laptop 4 Intel / Tahoe 26.7.1, 2026-11-22.
# No EFI edits, no sudo, no kext modifications. Existing BigSurface stack required.
set -eu
if [ "$(uname -s)" != "Darwin" ]; then
  echo "STOP: run this on macOS." >&2
  exit 2
fi
if [ "$(id -u)" -eq 0 ]; then
  echo "STOP: run as the logged-in macOS user, NOT through sudo." >&2
  exit 2
fi
defaults write com.apple.AppleMultitouchTrackpad Clicking -bool true
defaults write com.apple.AppleMultitouchTrackpad TrackpadRightClick -bool true
defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerTapGesture -int 0
defaults write com.apple.AppleMultitouchTrackpad ForceSuppressed -bool true
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad Clicking -bool true
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadThreeFingerTapGesture -int 0
defaults -currentHost write NSGlobalDomain com.apple.mouse.tapBehavior -int 1
defaults write NSGlobalDomain com.apple.trackpad.forceClick -bool false
killall cfprefsd >/dev/null 2>&1 || true
if [ -x /System/Library/PrivateFrameworks/SystemAdministration.framework/Resources/activateSettings ]; then
  /System/Library/PrivateFrameworks/SystemAdministration.framework/Resources/activateSettings -u || true
fi
echo "Applied BigSurface trackpad preferences to current user. Test tap-to-click, two-finger right-click, and physical click."
echo "If no immediate change, sign out and sign back in. Some behaviors depend on BigSurfaceHIDDriver."
