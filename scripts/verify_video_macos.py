#!/usr/bin/env python3
"""Read-only validation of Surface Laptop 4 Tahoe browser-video prerequisites.

Reports driver/codec readiness, not a guarantee that every web video plays.
No EFI, macOS preferences, NVRAM or user data are modified.
"""
from __future__ import annotations
import argparse
import ctypes
import json
from pathlib import Path
import plistlib
import re
import subprocess
import sys

COREADMIN = Path("/Library/Preferences/FeatureFlags/Domain/CoreMedia.plist")
VIDEO_TOOLBOX = "/System/Library/Frameworks/VideoToolbox.framework/VideoToolbox"


def command(*args):
    return subprocess.run(args, capture_output=True, text=True, check=False)


def package_version(name):
    result = command("/usr/sbin/pkgutil", "--pkg-info", name)
    if result.returncode:
        return None
    match = re.search(r"^version:\s*(\S+)", result.stdout, re.MULTILINE)
    return match.group(1) if match else None


def read_coremedia_flag():
    if not COREADMIN.is_file():
        return None
    try:
        with COREADMIN.open("rb") as file:
            prefs = plistlib.load(file)
        return prefs.get("AllowOnePassMetalScaling", {}).get("Enabled")
    except (OSError, ValueError, plistlib.InvalidFileException, AttributeError):
        return None


def hardware_video_support():
    vt = ctypes.CDLL(VIDEO_TOOLBOX)
    check = vt.VTIsHardwareDecodeSupported
    check.argtypes = (ctypes.c_uint32,)
    check.restype = ctypes.c_bool
    return {name: bool(check(int.from_bytes(fourcc, "big")))
            for name, fourcc in (("H.264", b"avc1"), ("HEVC", b"hvc1"),
                                 ("VP9", b"vp09"), ("AV1", b"av01"))}


def get_report():
    if sys.platform != "darwin":
        raise RuntimeError("Run on the installed Surface in macOS Tahoe.")
    os_version = command("/usr/bin/sw_vers", "-productVersion").stdout.strip()
    kext = command("/usr/bin/kmutil", "showloaded").stdout
    display = command("/usr/sbin/system_profiler", "SPDisplaysDataType").stdout
    return {
        "macOS": os_version,
        "Lilu_loaded": "as.vit9696.Lilu" in kext,
        "WhateverXe_loaded": "org.b00t0x.WhateverXe (0.8.3)" in kext,
        "WhateverXe_Graphics_common_pkg": package_version("org.b00t0x.WhateverXe.Common"),
        "WhateverXe_Graphics_tahoe_pkg": package_version("org.b00t0x.WhateverXe.Tahoe"),
        "CoreMedia_AllowOnePassMetalScaling": read_coremedia_flag(),
        "Metal_2_reported": "Metal 2" in display,
        "video_hardware_decoders_advertised": hardware_video_support(),
        "browser_video_playback": "Not measured here; verify a YouTube H.264 video in Safari.",
    }


def ready(report):
    return (report["macOS"].startswith("26.")
            and report["Lilu_loaded"]
            and report["WhateverXe_loaded"]
            and report["WhateverXe_Graphics_common_pkg"] == "0.4.4"
            and report["WhateverXe_Graphics_tahoe_pkg"] == "0.4.4"
            and report["CoreMedia_AllowOnePassMetalScaling"] is False
            and report["Metal_2_reported"]
            and report["video_hardware_decoders_advertised"]["H.264"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Machine-readable status report.")
    args = parser.parse_args()
    report = get_report()
    state = ready(report)
    if args.json:
        print(json.dumps({"prerequisites_match_tested_setup": state, **report}, indent=2))
    else:
        print("Surface Laptop 4 Tahoe — read-only video prerequisites")
        for key, value in report.items():
            print(f"  {key}: {value}")
        print("MATCHES TESTED VIDEO CONFIGURATION:", "YES" if state else "NO")
        print("NOTE: This does not verify a video rendered on screen.")
        if not state:
            print("Check Graphics 0.4.4 installation and the versions in README.")
    return 0 if state else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, AttributeError) as exc:
        print("Video diagnostics failed:", exc, file=sys.stderr)
        sys.exit(2)
