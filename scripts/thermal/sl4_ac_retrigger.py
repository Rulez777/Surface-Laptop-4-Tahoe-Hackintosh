#!/usr/bin/env python3
"""Conservative macOS AC-reconnect reminder for the existing SL4 TMP3 service.

The *system* LaunchDaemon already requests TMP3 at boot and verified wake.
This *user* LaunchAgent only asks launchd to restart that exact existing job
once after a stable battery->AC transition. No direct EC/CPU/fan writes,
no privileged shell, and no intervention while the battery is disconnected.
A successful request does NOT certify that BigSurface changed fan RPM/CPU speed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import time

LABEL = "com.rulez777.sl4-ac-retry"
TARGET = "system/com.rulez777.sl4-tmp3"
USER_DIR = Path.home() / "Library/Application Support/SL4-AC-Retry"
SOURCE_NAME = "sl4_ac_retrigger.py"
MANIFEST_NAME = "manifest.sha256"
PLIST = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
LOG = Path.home() / "Library/Logs/SL4-AC-Retry.log"
ERR = Path.home() / "Library/Logs/SL4-AC-Retry.error.log"
POLL = 15
STABLE_SAMPLES = 3
COOLDOWN_SECONDS = 300
DEFER_AFTER_AC_SECONDS = 10


def check(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def log(message):
    print("[" + dt.datetime.now().isoformat(timespec="seconds") + "] " + message, flush=True)


def sh(*args, timeout=10):
    proc = subprocess.run(list(args), capture_output=True, text=True, timeout=timeout)
    return proc


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for data in iter(lambda:inp.read(65536),b""):
            h.update(data)
    return h.hexdigest()


def parse_source(raw):
    """Fail closed on missing/mixed/garbled charging state."""
    first = next((line.strip() for line in raw.splitlines() if line.strip()), "")
    if first == "Now drawing from 'AC Power'":
        return "ac"
    if first == "Now drawing from 'Battery Power'":
        return "battery"
    return "unknown"


def get_source():
    proc = sh("/usr/bin/pmset", "-g", "batt")
    check(proc.returncode == 0, "Cannot read pmset power source")
    source = parse_source(proc.stdout)
    check(source != "unknown", "Unexpected pmset power state")
    return source


def acpi_verified():
    proc = sh("/usr/sbin/ioreg", "-p", "IOACPIPlane", "-lw0", timeout=20)
    check(proc.returncode == 0, "Cannot inspect ACPI hardware")
    check("MSHW0250" in proc.stdout and "MSHW0084" in proc.stdout,
          "Not the verified Surface Laptop 4 Intel ACPI profile")


def check_original_service():
    root = Path("/Library/Application Support/SL4-TMP3")
    manifest = root/"manifest.json"
    service = root/"sl4_tmp3_service.py"
    guard = root/"sl4_thermal_guard.py"
    check(manifest.is_file() and service.is_file() and guard.is_file(),
          "Original TMP3 root service is not installed")
    import json
    cfg=json.loads(manifest.read_text(encoding="utf-8"))
    check(cfg.get("service") == "com.rulez777.sl4-tmp3", "Unexpected root service label")
    check(cfg.get("source_hash") == digest(service) and cfg.get("guard_hash") == digest(guard),
          "Installed TMP3 service hash differs from its manifest")
    plist=Path("/Library/LaunchDaemons/com.rulez777.sl4-tmp3.plist")
    check(plist.is_file(), "Root service LaunchDaemon missing")
    with plist.open("rb") as source:
        data=plistlib.load(source)
    check(data.get("Label") == "com.rulez777.sl4-tmp3"
          and data.get("ProgramArguments",[])[-2:]==[str(service),"--daemon"],
          "Unexpected root service daemon command")


def confirm_safe_request():
    """Root daemon validates CPU temp <80C; user-side preflight <=75C as guard."""
    acpi_verified()
    check_original_service()
    check(get_source() == "ac", "Adapter no longer connected; refusing request")
    sensor_file = Path("/Library/Application Support/SL4-TMP3/sl4_thermal_guard.py")
    import importlib.util
    spec=importlib.util.spec_from_file_location("sl4_power_guard",str(sensor_file))
    check(spec is not None and spec.loader is not None, "Temperature guard unavailable")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sensor=mod.CpuDie()
    try:
        temp=sensor.read()
    finally:
        sensor.close()
    check(15.0 <= temp <75.0,"CPU temperature too high/unreliable, no request")
    return temp


class SourceWatcher:
    """Emit a single reconnect event after stable samples and a cooldown."""
    def __init__(self, first, now):
        self.stable=first
        self.candidate=first
        self.count=0
        self.last_request = now - COOLDOWN_SECONDS

    def sample(self, source, now):
        if source not in ("ac","battery"):
            self.candidate=None
            self.count=0
            return False
        if source == self.stable:
            self.candidate=source
            self.count=0
            return False
        if source != self.candidate:
            self.candidate=source
            self.count=1
            return False
        self.count += 1
        if self.count < STABLE_SAMPLES:
            return False
        self.stable=source
        self.count=0
        if source=="ac" and now-self.last_request >= COOLDOWN_SECONDS:
            self.last_request=now
            return True
        return False


def restart_existing():
    temperature=confirm_safe_request()
    result=sh("/bin/launchctl","kickstart","-k",TARGET,timeout=20)
    check(result.returncode==0,
          "Launchctl could not restart existing TMP3 service: "+result.stderr.strip()[:250])
    log("Stable AC reconnection; CPU die %.1f C, requested existing TMP3 daemon restart. EC/RPM/CPU performance not verified."%temperature)


def watcher():
    check(sys.platform=="darwin", "macOS only")
    check(os.geteuid()!=0,"User LaunchAgent only; cannot run as root")
    acpi_verified()
    check_original_service()
    now=time.monotonic()
    original=get_source()
    state=SourceWatcher(original,now)
    log("Started, initial source="+original+"; monitoring real battery->AC transitions only")
    pending_at=None
    while True:
        time.sleep(POLL)
        try:
            source=get_source()
        except (RuntimeError,OSError,subprocess.SubprocessError) as e:
            log("Power source unknown: "+str(e))
            continue
        now=time.monotonic()
        if state.sample(source,now):
            pending_at=now+DEFER_AFTER_AC_SECONDS
            log("Stable AC reconnection detected; waiting before TMP3 request")
        if source!="ac":
            pending_at=None
        if pending_at is not None and now>=pending_at:
            pending_at=None
            try:
                restart_existing()
            except (RuntimeError,OSError,ValueError,subprocess.SubprocessError) as e:
                log("TMP3 restart skipped: "+str(e))


def plist_contents():
    return {"Label":LABEL,
            "ProgramArguments":[sys.executable,str(USER_DIR/SOURCE_NAME),"--watch"],
            "RunAtLoad":True,"KeepAlive":True,
            "ThrottleInterval":60,
            "StandardOutPath":str(LOG),
            "StandardErrorPath":str(ERR)}


def validate_install():
    check(USER_DIR.is_dir() and not USER_DIR.is_symlink(),"Missing installed folder")
    path=USER_DIR/SOURCE_NAME
    cfg=USER_DIR/MANIFEST_NAME
    check(path.is_file() and not path.is_symlink() and cfg.is_file(),
          "Installed agent files incomplete")
    check(digest(path)==cfg.read_text(encoding="ascii").strip(),
          "Installed script changed; refusing remove")
    check(PLIST.is_file() and not PLIST.is_symlink(),"LaunchAgent plist missing")
    with PLIST.open("rb") as f:
        data=plistlib.load(f)
    check(data.get("Label")==LABEL
          and data.get("ProgramArguments",[])[-2:]==[str(path),"--watch"],
          "LaunchAgent differs from known config")


def install(ack):
    check(ack=="ENABLE-AC-RECONNECT-RETRY","Explicit acknowledgement required")
    check(sys.platform=="darwin" and os.geteuid()!=0,"Install as logged-in macOS user")
    acpi_verified()
    check_original_service()
    check(not USER_DIR.exists() and not PLIST.exists(),
          "User agent already installed; refusing overwrite")
    check(PLIST.parent.is_dir(),"User LaunchAgents directory missing")
    check(LOG.parent.is_dir(),"User Logs directory missing")
    source=Path(__file__).resolve()
    check(source.is_file() and not source.is_symlink(),"Invalid source script")
    created=False
    try:
        USER_DIR.mkdir(mode=0o700)
        created=True
        shutil.copy2(source,USER_DIR/SOURCE_NAME)
        (USER_DIR/MANIFEST_NAME).write_text(digest(USER_DIR/SOURCE_NAME)+"\n",encoding="ascii")
        with PLIST.open("wb") as out:
            plistlib.dump(plist_contents(),out,sort_keys=False)
        uid=os.getuid()
        proc=sh("/bin/launchctl","bootstrap","gui/"+str(uid),str(PLIST),timeout=20)
        check(proc.returncode==0,"Could not start user agent: "+proc.stderr.strip())
    except BaseException:
        if PLIST.exists():PLIST.unlink()
        if created and USER_DIR.is_dir():shutil.rmtree(USER_DIR)
        raise
    log("AC-reconnect user agent enabled. No ESP/EC direct writes and no system sleep changes.")


def remove(ack):
    check(ack=="DISABLE-AC-RECONNECT-RETRY","Explicit acknowledgement required")
    check(sys.platform=="darwin" and os.geteuid()!=0,"Remove as logged-in macOS user")
    validate_install()
    uid=os.getuid()
    proc=sh("/bin/launchctl","bootout","gui/"+str(uid)+"/"+LABEL,timeout=20)
    check(proc.returncode==0,"Could not stop user agent: "+proc.stderr.strip())
    PLIST.unlink()
    (USER_DIR/SOURCE_NAME).unlink()
    (USER_DIR/MANIFEST_NAME).unlink()
    USER_DIR.rmdir()
    log("User agent removed. Original TMP3 root daemon was not changed.")


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    group=cli.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect",action="store_true")
    group.add_argument("--watch",action="store_true")
    group.add_argument("--install",action="store_true")
    group.add_argument("--remove",action="store_true")
    group.add_argument("--status",action="store_true")
    cli.add_argument("--ack",default="")
    args=cli.parse_args()
    if args.inspect:
        acpi_verified()
        check_original_service()
        print("Power source:",get_source())
        print("Preflight:",confirm_safe_request() if get_source()=="ac" else "Battery source; no TMP3 request")
        print("Current BigSurface registry value may NOT change in response to a successful mode request")
    elif args.install:install(args.ack)
    elif args.remove:remove(args.ack)
    elif args.watch:watcher()
    elif args.status:
        result=sh("/bin/launchctl","print","gui/"+str(os.getuid())+"/"+LABEL)
        print(result.stdout[:3500] if result.returncode==0 else "User agent not running")
        if LOG.is_file():
            print("Recent log:",*LOG.read_text(encoding="utf-8",errors="replace").splitlines()[-4:],sep="\n")


if __name__=="__main__":
    try:main()
    except KeyboardInterrupt:log("Stopped")
    except (RuntimeError,OSError,ValueError,subprocess.SubprocessError) as error:
        log("STOP: "+str(error))
        sys.exit(1)
