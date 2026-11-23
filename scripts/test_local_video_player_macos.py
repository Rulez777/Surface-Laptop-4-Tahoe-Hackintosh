#!/usr/bin/env python3
"""Read-only local file playback probe using installed notarized IINA's libmpv.

Builds an ephemeral C harness and plays selected local samples with mpv
--vo=null --ao=null --hwdec=no. This proves usable FFmpeg/software decoding
to EOF, NOT on-screen output, performance, or Intel video-engine acceleration.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "iina_libmpv_decode_probe.c"
MAX_FILES = 12
RESULT_RE = re.compile(
    r"^RESULT codec=(?P<codec>.+) dimensions=(?P<width>\d+)x(?P<height>\d+) "
    r"file_loaded=(?P<loaded>[01]) eof=(?P<eof>[01]) "
    r"end_error=(?P<error>-?\d+) decoder_dropped=(?P<dropped>-?\d+) "
    r"hardware_decode=no$", re.M)


def validate_files(items):
    if not items or len(items) > MAX_FILES:
        raise ValueError("Provide between 1 and 12 local video samples")
    for item in items:
        if not item.is_file() or item.is_symlink():
            raise ValueError("Video sample must be an ordinary local file")
        if item.suffix.lower() not in {".mp4", ".webm", ".mkv", ".mov", ".m4v"}:
            raise ValueError("Video sample extension is unsupported")


def parse_result(output, input_path):
    matches = list(RESULT_RE.finditer(output))
    if len(matches) != 1:
        raise RuntimeError("Unexpected libmpv test output")
    match = matches[0].groupdict()
    return {
        "filename": input_path.name,
        "codec": match["codec"],
        "width": int(match["width"]),
        "height": int(match["height"]),
        "end_of_file_reached": match["eof"] == "1",
        "video_stream_loaded": match["loaded"] == "1",
        "playback_error": int(match["error"]),
        "hardware_acceleration": "disabled",
        "software_decoded_to_eof": (
            match["eof"] == "1" and match["loaded"] == "1"
            and int(match["error"]) == 0
            and int(match["width"]) > 0 and int(match["height"]) > 0),
        "frame_count_measured": False,
    }


def invoke(cmd, *, timeout=90):
    result = subprocess.run(cmd, capture_output=True, text=True,
                            timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): "
            f"{(result.stderr + result.stdout)[-900:]}")
    return result.stdout


def inspect(files):
    if sys.platform != "darwin":
        raise RuntimeError("macOS is required")
    validate_files(files)
    frameworks = Path.home() / "Applications/IINA.app/Contents/Frameworks"
    lib = frameworks / "libmpv.2.dylib"
    if not lib.is_file() or lib.is_symlink():
        raise RuntimeError("IINA app/libmpv missing, install it first")
    if not SOURCE.is_file():
        raise RuntimeError("Bundled C probe source missing")
    with tempfile.TemporaryDirectory(prefix="sl4-iina-video-") as temp:
        binary = Path(temp) / "iina_decode_probe"
        invoke(["/usr/bin/clang", "-O2", "-Wall", "-Wextra", "-Werror",
                "-Wl,-rpath," + str(frameworks), str(SOURCE),
                "-o", str(binary), "-ldl"], timeout=90)
        videos = []
        for path in files:
            output = invoke([str(binary), str(lib), str(path)], timeout=90)
            videos.append(parse_result(output, path))
    return {
        "status": "pass" if all(v["software_decoded_to_eof"] for v in videos) else "fail",
        "installed_player": "IINA",
        "hardware_decode_verified": False,
        "video_rendered_on_screen": False,
        "driver_or_efi_changed": False,
        "files": videos,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, nargs="+", required=True,
                        help="Local video files to read and decode")
    args = parser.parse_args(argv)
    try:
        report = inspect(args.assets)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "pass" else 1
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print("SL4_LOCAL_VIDEO_TEST_ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
