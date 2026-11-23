#!/usr/bin/env python3
"""Build and run isolated VideoToolbox hardware-session probes on macOS.

No root, driver patches, EFI writes or persistent installation. Uses the system
Command Line Tools clang compiler and releases temporary test executables.
Hardware session creation is NOT equivalent to actual frame decoding.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
SOURCE_BASIC = ROOT / "probe_video_session_macos.c"
SOURCE_REAL = ROOT / "probe_real_asset_sessions_macos.m"
ERRORS = {
    -12906: "kVTCouldNotFindVideoDecoderErr",
    -12909: "kVTVideoDecoderBadDataErr",
    -12910: "kVTVideoDecoderUnsupportedDataFormatErr",
    -12913: "kVTVideoDecoderNotAvailableNowErr",
}


def require_inputs(assets):
    if len(assets) > 12:
        raise ValueError("Limit to 12 locally supplied media samples")
    for p in assets:
        if not p.is_file() or p.is_symlink():
            raise ValueError("Sample must be a normal existing local file: " + p.name)
        if p.suffix.lower() not in {".mp4", ".mov", ".webm", ".m4v"}:
            raise ValueError("Unsupported sample extension: " + p.name)


def build_command(source, destination):
    if source == SOURCE_BASIC:
        return ["clang", "-O2", "-Wall", "-Wextra", "-Werror",
                "-framework", "CoreFoundation",
                "-framework", "CoreMedia",
                "-framework", "VideoToolbox",
                str(source), "-o", str(destination)]
    if source == SOURCE_REAL:
        return ["clang", "-fobjc-arc", "-O2", "-Wall", "-Wextra", "-Werror",
                "-framework", "Foundation",
                "-framework", "AVFoundation",
                "-framework", "VideoToolbox",
                "-framework", "CoreMedia",
                str(source), "-o", str(destination)]
    raise ValueError("Only two vetted probe sources are permitted")


def run(*argv, timeout=45):
    result = subprocess.run(argv, capture_output=True, text=True,
                            check=False, timeout=timeout)
    if result.returncode:
        raise RuntimeError(
            f"{argv[0]} exited {result.returncode}: {(result.stderr + result.stdout)[-1200:]}"
        )
    return result.stdout


def annotated_status(status):
    return {"code": status, "name": ERRORS.get(status, "noErr" if status == 0 else "other")}


def annotate(report):
    """Add OSStatus meanings without claiming unavailable hardware is working."""
    for codec in report.get("codecs", []):
        for key in ("hardware_required_status", "unrestricted_status"):
            if isinstance(codec.get(key), int):
                codec[key + "_detail"] = annotated_status(codec[key])
    for asset in report.get("assets", []):
        for key in ("require_hardware", "allow_software"):
            record = asset.get(key)
            if isinstance(record, dict) and isinstance(record.get("os_status"), int):
                record["status_detail"] = annotated_status(record["os_status"])
    return report


def inspect(assets):
    if sys.platform != "darwin":
        raise RuntimeError("Only installed macOS can inspect native VideoToolbox")
    if shutil.which("clang") is None:
        raise RuntimeError("Apple Command Line Tools (clang) are required")
    require_inputs(assets)
    with tempfile.TemporaryDirectory(prefix="sl4-vt-probe-") as directory:
        temp = Path(directory)
        result = {}
        for src, key in ((SOURCE_BASIC, "empty_format_probe"),
                         (SOURCE_REAL, "real_asset_probe")):
            if key == "real_asset_probe" and not assets:
                continue
            binary = temp / src.stem
            run(*build_command(src, binary), timeout=90)
            output = run(str(binary), *(str(path) for path in assets)
                         if key == "real_asset_probe" else (), timeout=75)
            result[key] = annotate(json.loads(output))
    return {
        "probe_version": 1,
        "device_or_driver_changed": False,
        "hardware_decode_verified": False,
        "real_frame_decode_tested": False,
        "interpretation": (
            "No decoded frames or media-engine telemetry are measured. Even "
            "successful VT sessions do not prove Intel hardware decoding. "
            "If VideoToolbox reports decoder not found (-12906), it could not "
            "find an eligible decoder for that exact format on this system."
        ),
        "results": result,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--assets", nargs="*", type=Path, default=[],
                   help="Optional local AV1/VP9/H264/HEVC MP4/WebM test files")
    args = p.parse_args(argv)
    try:
        print(json.dumps(inspect(args.assets), indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("VT_SESSION_PROBE_ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
