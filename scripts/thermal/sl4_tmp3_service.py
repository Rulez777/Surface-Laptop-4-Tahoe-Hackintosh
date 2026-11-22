#!/usr/bin/env python3
"""Surface Laptop 4 Intel: optional macOS TMP=3 startup/resume service.

Not a fan RPM controller. Uses existing BigSurface SurfaceBatteryDriver,
only requests TMP=3 after startup / detected wake, never TMP=4 or raw fan RPM.
No EFI, NVRAM, Windows, kext, CPU power-limit, or boot-argument edits.

Modes:
  --inspect: read-only hardware, CPU die and service capability check
  --install --ack INSTALL-SL4-TMP3: install LaunchDaemon, activate it
  --status: read-only launchctl service status
  --remove --ack REMOVE-SL4-TMP3: stop service and remove its owned files
  --daemon: internal launchd-only process; first request after startup, then wake
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import time

LABEL = "com.rulez777.sl4-tmp3"
ROOT = Path("/Library/Application Support/SL4-TMP3")
PLIST = Path("/Library/LaunchDaemons") / f"{LABEL}.plist"
GUARD_NAME = "sl4_thermal_guard.py"
SCRIPT_NAME = "sl4_tmp3_service.py"
MANIFEST = "manifest.json"
STDOUT = "/var/log/sl4-tmp3.log"
STDERR = "/var/log/sl4-tmp3.error.log"

POLL_SECONDS = 5
WAIT_AFTER_WAKE = 10
RETRY_SECONDS = 25
MAX_TEMP = 80.0
RESUME_THRESHOLD_SECONDS = 20


def check(ok, error):
    if not ok:
        raise RuntimeError(error)


def log(message):
    print(f"[{dt.datetime.now().isoformat(timespec='seconds')}] {message}", flush=True)


def file_sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def cpu_and_surface_module(path):
    check(path.is_file() and not path.is_symlink(), f"Missing guard source: {path}")
    spec = importlib.util.spec_from_file_location("sl4_guard_for_tmp3", str(path))
    check(spec is not None and spec.loader is not None, "Cannot load guard module")
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    for member in ("check_hardware", "CpuDie", "BigSurface"):
        check(hasattr(obj, member), f"Missing guard API {member}")
    return obj


def hardware_safety(guard):
    check(sys.platform == "darwin", "Only on installed macOS")
    guard.check_hardware()
    check(hasattr(time, "CLOCK_UPTIME_RAW") and hasattr(time, "clock_gettime"),
          "CLOCK_UPTIME_RAW is required for reliable wake detection")


def uptime():
    return time.clock_gettime(time.CLOCK_UPTIME_RAW)


class WakeDetector:
    """Compare wall clock with CLOCK_UPTIME_RAW (which excludes system sleep)."""

    def __init__(self, wall, up):
        self.wall, self.up = wall, up

    def detect(self, wall, up):
        elapsed_wall = wall - self.wall
        elapsed_uptime = up - self.up
        self.wall, self.up = wall, up
        return (elapsed_wall >= RESUME_THRESHOLD_SECONDS and
                elapsed_wall - elapsed_uptime >= RESUME_THRESHOLD_SECONDS and
                elapsed_uptime >= 0)


def request_once(guard):
    """Fail closed: no TMP write without a fresh plausible, cool CPU die reading."""
    sensor = guard.CpuDie()
    try:
        temperature = sensor.read()
    finally:
        sensor.close()
    check(15.0 <= temperature < MAX_TEMP,
          f"CPU DIE {temperature:.2f} C: outside 15–<80 C, no TMP request")
    guard.BigSurface().set(3)
    log(f"CPU DIE {temperature:.2f} C; one TMP=3 request sent (IOKit only; EC/fan RPM unverified)")
    return temperature


def run_daemon():
    check(os.geteuid() == 0, "Root required for LaunchDaemon")
    guard = cpu_and_surface_module(Path(__file__).resolve().with_name(GUARD_NAME))
    hardware_safety(guard)
    log("Started; profile TMP=3 on startup/wake only; no RPM control")
    last_wall, last_up = time.time(), uptime()
    tracker = WakeDetector(last_wall, last_up)
    pending, ready_at = True, last_up + WAIT_AFTER_WAKE
    next_attempt = ready_at
    while True:
        now_up = uptime()
        if tracker.detect(time.time(), now_up):
            pending, ready_at = True, now_up + WAIT_AFTER_WAKE
            next_attempt = ready_at
            log("Wake detected; deferring TMP3 until Surface drivers resume")
        if pending and now_up >= ready_at and now_up >= next_attempt:
            try:
                request_once(guard)
                pending = False
            except (RuntimeError, OSError, subprocess.SubprocessError, ValueError) as error:
                log(f"TMP3 request deferred: {error}")
                next_attempt = now_up + RETRY_SECONDS
        time.sleep(POLL_SECONDS)


def plist_config():
    return {
        "Label": LABEL,
        "ProgramArguments": [str(Path(sys.executable).resolve()), str(ROOT/SCRIPT_NAME), "--daemon"],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 60,
        "ProcessType": "Background",
        "StandardOutPath": STDOUT,
        "StandardErrorPath": STDERR,
    }


def subprocess_launchctl(*args, expect_success=True):
    result = subprocess.run(["/bin/launchctl", *args], capture_output=True, text=True, timeout=30)
    if expect_success:
        check(result.returncode == 0,
              f"launchctl {' '.join(args)} failed: {result.stdout.strip()} {result.stderr.strip()}")
    return result


def preflight(guard_path):
    guard = cpu_and_surface_module(guard_path)
    hardware_safety(guard)
    sensor = guard.CpuDie()
    try:
        temperature = sensor.read()
    finally:
        sensor.close()
    log(f"CPU die TC0D {temperature:.2f} C; hardware and sleep clock ready")
    return guard


def install(ack, source):
    check(ack == "INSTALL-SL4-TMP3", "Install requires --ack INSTALL-SL4-TMP3")
    check(os.geteuid() == 0, "Install requires sudo")
    check(not PLIST.exists() and not ROOT.exists(),
          "TMP3 service already exists; refusing overwrite")
    preflight(source.with_name(GUARD_NAME))
    check(Path(sys.executable).is_file(), "Python executable missing")
    check(source.is_file() and not source.is_symlink(), "Service source invalid")
    pl = plist_config()
    check(pl["ProgramArguments"][0].startswith("/"), "Expected absolute Python path")
    installed = False
    try:
        ROOT.mkdir(mode=0o755, parents=False)
        for name in (SCRIPT_NAME, GUARD_NAME):
            src = source.with_name(name)
            dst = ROOT/name
            check(src.is_file() and not src.is_symlink(), "Missing source: " + str(src))
            shutil.copyfile(src, dst)
            os.chmod(dst, 0o644)
            os.chown(dst, 0, 0)
            check(file_sha(src) == file_sha(dst), "Installed script differs: " + name)
        manifest = {"service": LABEL, "source_hash": file_sha(ROOT/SCRIPT_NAME),
                    "guard_hash": file_sha(ROOT/GUARD_NAME), "python": pl["ProgramArguments"][0]}
        (ROOT/MANIFEST).write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
        os.chown(ROOT/MANIFEST, 0, 0)
        os.chmod(ROOT/MANIFEST, 0o644)
        os.chown(ROOT, 0, 0)
        os.chmod(ROOT, 0o755)
        with PLIST.open("wb") as out:
            plistlib.dump(pl, out, sort_keys=False)
        os.chown(PLIST, 0, 0)
        os.chmod(PLIST, 0o644)
        subprocess_launchctl("bootstrap", "system", str(PLIST))
        installed = True
        log("LaunchDaemon installed and bootstrapped. Request is pending initial sensor check.")
        log(f"Status: sudo launchctl print system/{LABEL}")
        log(f"Log: {STDOUT}")
    except BaseException:
        if installed:
            subprocess_launchctl("bootout", f"system/{LABEL}", expect_success=False)
        if PLIST.exists():
            PLIST.unlink()
        if ROOT.exists():
            shutil.rmtree(ROOT)
        raise


def owned_service():
    check(PLIST.is_file() and not PLIST.is_symlink(), "LaunchDaemon plist missing")
    data = plistlib.loads(PLIST.read_bytes())
    check(data.get("Label") == LABEL and
          data.get("ProgramArguments", [None, None])[-2:] == [str(ROOT/SCRIPT_NAME), "--daemon"],
          "Not the expected SL4 TMP3 service")
    manifest = ROOT/MANIFEST
    check(manifest.is_file(), "Service manifest missing")
    info = json.loads(manifest.read_text(encoding="utf-8"))
    check(info.get("service") == LABEL, "Service manifest wrong label")
    for filename, key in ((SCRIPT_NAME, "source_hash"), (GUARD_NAME, "guard_hash")):
        dst=ROOT/filename
        check(dst.is_file() and not dst.is_symlink() and file_sha(dst)==info.get(key),
              "Installed script does not match manifest: "+filename)
    return info


def remove(ack):
    check(ack == "REMOVE-SL4-TMP3", "Remove requires --ack REMOVE-SL4-TMP3")
    check(os.geteuid() == 0, "Remove requires sudo")
    owned_service()
    result = subprocess_launchctl("bootout", f"system/{LABEL}", expect_success=False)
    if result.returncode:
        # For an already stopped service, launchctl print also fails.
        check(subprocess_launchctl("print", f"system/{LABEL}", expect_success=False).returncode != 0,
              "Cannot stop active service; refusing to delete its executable")
    PLIST.unlink()
    for name in (SCRIPT_NAME,GUARD_NAME,MANIFEST):
        (ROOT/name).unlink()
    ROOT.rmdir()
    log("LaunchDaemon removed; no EFI, hardware profiles or fan control changed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--inspect", action="store_true", help="Read-only hardware capability check")
    actions.add_argument("--install", action="store_true", help="Install opt-in root LaunchDaemon")
    actions.add_argument("--remove", action="store_true", help="Stop and remove only this service")
    actions.add_argument("--status", action="store_true", help="Print current launchd job state")
    actions.add_argument("--daemon", action="store_true", help="Internal launchd process")
    parser.add_argument("--ack", default="")
    args = parser.parse_args()
    source = Path(__file__).resolve()
    if args.inspect:
        preflight(source.with_name(GUARD_NAME))
        print("INSPECT PASS: no writes; TMP3 startup/resume service available")
    elif args.install:
        install(args.ack, source)
    elif args.remove:
        remove(args.ack)
    elif args.status:
        result=subprocess_launchctl("print", f"system/{LABEL}", expect_success=False)
        print(result.stdout.strip() if result.returncode == 0 else
              f"Not loaded (launchctl exit {result.returncode}): {result.stderr.strip()}")
    elif args.daemon:
        check(source.parent == ROOT, "Daemon runs only from installed root-owned directory")
        owned_service()
        run_daemon()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped")
    except (RuntimeError, OSError, ValueError, plistlib.InvalidFileException,
            subprocess.SubprocessError) as error:
        log(f"STOP: {error}")
        sys.exit(1)
