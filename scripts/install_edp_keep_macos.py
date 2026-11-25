#!/usr/bin/env python3
"""Reversible post-install WhateverXe 0.8.3 eDP keep+softsleep on Intel Surface Laptop 4.
Only edits the private existing OpenCore OC directory; never touches EFI/Microsoft,
NVRAM variables, partitions, FileVault, system sleep settings or macOS extensions.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import os
from pathlib import Path
import plistlib
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

KEXT_NAME = "WhateverXe-SL4-EDP-KeepSoftSleep.kext"
ZIP_NAME = "SL4-WEX-0.8.3-EDP-KeepSoftSleep.zip"
BINARY_SHA = "0796d12158b9c6806a83e4f455f84eee9280a0148406b8d4f0764234f00df91a"
DONOR_SHA = "115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e"
DONOR = Path("/Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext/Contents/MacOS/AppleIntelTGLGraphicsFramebuffer")
APPLE_GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
FLAGS = ("-wex-tgl-no-posh", "-wex-tgl-gpurec", "-wex-tgl-stampfix",
         "-nodisplaysleepDC6", "-noDC9", "dc6config=0",
         "-wex-tgl-edp-keep", "-wex-tgl-edp-softsleep")
MIN_ESP = 100 * 1024 * 1024
MAX_ESP = 2 * 1024 * 1024 * 1024

def require(condition, why):
    if not condition:
        raise RuntimeError(why)

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def run(cmd):
    p = subprocess.run([str(v) for v in cmd], capture_output=True, text=True)
    require(p.returncode == 0, "Command failed: " + " ".join(map(str, cmd)) + " :: " + (p.stdout + p.stderr)[-800:])
    return p.stdout

def discover_bundle():
    here = Path(__file__).resolve().parent
    direct = here / "WhateverXe.kext"
    validator = here / "tools/ocvalidate"
    if direct.is_dir() and validator.is_file():
        return direct, validator, None
    candidates = [here/"packages"/ZIP_NAME, here.parent/"packages"/ZIP_NAME, here/ZIP_NAME]
    archive = next((p for p in candidates if p.is_file()), None)
    require(archive is not None, "Bundle missing. Download the complete ZIP from GitHub (or clone the repository).")
    td = tempfile.TemporaryDirectory(prefix="sl4-edp-bundle-")
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        require(len(names) < 100, "Unexpected ZIP layout")
        require(all(not Path(n).is_absolute() and ".." not in Path(n).parts for n in names), "Unsafe ZIP paths")
        kexts = [n for n in names if n.endswith("/WhateverXe.kext/Contents/MacOS/WhateverXe")]
        require(len(kexts) == 1, "Package must contain one WhateverXe binary")
        pkg_prefix = kexts[0].split("/WhateverXe.kext/Contents/MacOS/WhateverXe")[0]
        require(pkg_prefix != "" and (pkg_prefix + "/WhateverXe.kext/Contents/Info.plist") in names, "Missing Info.plist")
        require((pkg_prefix + "/tools/ocvalidate") in names, "Missing bundled OpenCore 1.0.8 validator")
        z.extractall(td.name)
    pkg = Path(td.name) / pkg_prefix
    return pkg/"WhateverXe.kext", pkg/"tools/ocvalidate", td

def check_bundle(kext, validator):
    binary = kext/"Contents/MacOS/WhateverXe"
    require(binary.is_file() and sha(binary) == BINARY_SHA, "WhateverXe binary checksum mismatch")
    info = plistlib.loads((kext/"Contents/Info.plist").read_bytes())
    require(info.get("CFBundleIdentifier") == "org.b00t0x.WhateverXe" and
            info.get("CFBundleVersion") == "0.8.3", "Wrong WhateverXe kext ID/version")
    require(validator.is_file(), "OpenCore 1.0.8 ocvalidate missing")
    validator.chmod(validator.stat().st_mode | 0o100)
    return binary

def check_machine():
    require(sys.platform == "darwin", "Run this installer inside macOS, not Windows")
    require(DONOR.is_file() and sha(DONOR) == DONOR_SHA,
            "Framebuffer mismatch. Supported only with verified Tahoe AppleIntelTGLGraphicsFramebuffer 16.0.0.")
    cpu = run(["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"])
    require("i7-1185G7" in cpu, "Untested CPU. Only SL4 Intel i7-1185G7 is qualified.")
    igpu = run(["/usr/sbin/ioreg", "-p", "IOService", "-r", "-n", "IGPU", "-l", "-w0"]).lower()
    require('"device-id" = <499a0000>' in igpu and '"vendor-id" = <86800000>' in igpu,
            "Unexpected GPU: expected Intel Iris Xe 8086:9A49")
    version = run(["/usr/bin/sw_vers", "-productVersion"]).strip()
    require(version.startswith("26."), "Only macOS Tahoe 26.x has been tested")
    return version

def esp_info(device):
    require(re.fullmatch(r"disk[0-9]+s[0-9]+", device), "Use a partition identifier, e.g. disk0s1")
    item = plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil", "info", "-plist", device]))
    require(item.get("DeviceIdentifier") == device and item.get("Content") == "EFI"
            and item.get("Internal") and not item.get("Removable")
            and MIN_ESP <= item.get("TotalSize",0) <= MAX_ESP,
            "Device is not an internal EFI System Partition")
    return item

class MountedEFI:
    def __init__(self, device):
        self.device, self.owned, self.temp, self.path = device, False, None, None
    def __enter__(self):
        info = esp_info(self.device)
        if info.get("MountPoint"):
            self.path = Path(info["MountPoint"])/"EFI"
        else:
            self.temp = tempfile.TemporaryDirectory(prefix="sl4-edp-esp-", dir="/private/tmp")
            run(["/sbin/mount_msdos","-o","rw","/dev/"+self.device,self.temp.name])
            self.owned = True
            require(esp_info(self.device).get("MountPoint") == self.temp.name, "EFI mount path unexpectedly changed")
            self.path = Path(self.temp.name)/"EFI"
        require((self.path/"OC/config.plist").is_file() and
                (self.path/"Microsoft/Boot/bootmgfw.efi").is_file(),
                "Expected OpenCore and Windows boot manager missing; leave ESP unchanged")
        return self.path
    def __exit__(self, kind, error, tb):
        if self.owned:
            for attempt in range(5):
                p = subprocess.run(["/usr/sbin/diskutil","unmount",self.device],capture_output=True,text=True)
                if p.returncode == 0 and not esp_info(self.device).get("MountPoint"):
                    break
                import time
                time.sleep(2)
            else:
                raise RuntimeError("EFI could not be unmounted; close Finder/Spotlight, unmount manually before reboot")
            if self.temp:
                self.temp.cleanup()
            run(["/usr/sbin/diskutil", "verifyVolume", self.device])

def inspect_config(efi, config):
    entries = config.get("Kernel",{}).get("Add",[])
    active = [(i,e) for i,e in enumerate(entries) if e.get("Enabled") and "WhateverXe" in e.get("BundlePath","")]
    require(len(active) == 1, "Expected exactly one enabled WhateverXe kext")
    i,e = active[0]
    require(not any(x.get("Enabled") and x.get("BundlePath","") == "WhateverGreen.kext" for x in entries),
            "WhateverGreen conflicts with WhateverXe")
    require(any(x.get("Enabled") and x.get("BundlePath") == "Lilu.kext" for x in entries[:i]),
            "Enabled Lilu.kext must load before WhateverXe")
    source = efi/"OC/Kexts"/e["BundlePath"]
    info = plistlib.loads((source/"Contents/Info.plist").read_bytes())
    require(info.get("CFBundleIdentifier") == "org.b00t0x.WhateverXe" and
            info.get("CFBundleVersion") == "0.8.3", "Existing WhateverXe is not version 0.8.3")
    nv = config["NVRAM"]["Add"][APPLE_GUID]
    bootargs = nv.get("boot-args","")
    require(isinstance(bootargs,str) and "-wex-noaccel" not in bootargs.split(),
            "Metal must already work; -wex-noaccel is not supported")
    require(all(x in bootargs.split() for x in ("-igfxdvmt","-allow3d","-disablegfxfirmware")),
            "Missing tested DVMT/graphics boot arguments")
    require("boot-args" in config["NVRAM"]["Delete"][APPLE_GUID],
            "OpenCore NVRAM Delete must contain boot-args to override stale NVRAM flags")
    return i,e,nv,bootargs

def validate(validator,config):
    run([validator,config])

def backup_dir():
    username = os.environ.get("SUDO_USER") or pwd.getpwuid(os.getuid()).pw_name
    home = Path(pwd.getpwnam(username).pw_dir)
    return home/"Downloads/SL4-EDP-BACKUPS"

def apply(esp, kext, validator, state_root):
    require(os.geteuid() == 0, "Installer requires sudo")
    require(not (state_root/"latest.json").exists(),
            "An installation is already recorded. Restore it first or remove state manually after review.")
    with MountedEFI(esp) as efi:
        cfgpath = efi/"OC/config.plist"
        original = cfgpath.read_bytes()
        config = plistlib.loads(original)
        index, entry, nv, args = inspect_config(efi,config)
        require(entry["BundlePath"] != KEXT_NAME, "Patch already installed: no changes needed")
        previous_bundle_path = entry["BundlePath"]
        target = efi/"OC/Kexts"/KEXT_NAME
        require(not target.exists(), "Target kext name already exists; refuse overwrite")
        win = efi/"Microsoft/Boot/bootmgfw.efi"
        win_hash = sha(win)
        validate(validator,cfgpath)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = state_root/stamp
        backup.mkdir(parents=True,mode=0o700,exist_ok=False)
        shutil.copytree(efi/"OC",backup/"OC",symlinks=True)
        before_hash = hashlib.sha256(original).hexdigest()
        require(sha(backup/"OC/config.plist") == before_hash, "Full OpenCore backup failed verification")
        backup_efi = cfgpath.with_name("config-SL4-before-EDP-"+stamp+".plist")
        with backup_efi.open("xb") as f:
            f.write(original); f.flush(); os.fsync(f.fileno())
        require(sha(backup_efi) == before_hash, "EFI recovery config corrupt")
        shutil.copytree(kext,target,symlinks=True)
        require(sha(target/"Contents/MacOS/WhateverXe") == BINARY_SHA, "Copied binary checksum mismatch")
        config["Kernel"]["Add"][index]["BundlePath"] = KEXT_NAME
        tokens = args.split()
        for flag in FLAGS:
            if flag.startswith("dc6config="):
                require(not any(x.startswith("dc6config=") and x != flag for x in tokens),
                        "Conflicting DC6 power option")
            if flag not in tokens:
                tokens.append(flag)
        nv["boot-args"] = " ".join(tokens)
        after = plistlib.dumps(config,sort_keys=False)
        pending = cfgpath.with_name("config-SL4-EDP-pending-"+stamp+".plist")
        with pending.open("xb") as f:
            f.write(after); f.flush(); os.fsync(f.fileno())
        validate(validator,pending)
        require(sha(cfgpath) == before_hash and sha(win) == win_hash,
                "EFI changed during preparation: refusing install")
        os.replace(pending,cfgpath)
        validate(validator,cfgpath)
        require(sha(win) == win_hash, "Windows EFI changed unexpectedly")
        state = {"esp":esp,"at":stamp,"original_config_sha256":before_hash,
                 "new_config_sha256":sha(cfgpath),"backup_config":str(backup/"OC/config.plist"),
                 "original_kext_name":previous_bundle_path,"installed_kext_name":KEXT_NAME,
                 "binary_sha256":BINARY_SHA,"windows_boot_sha256":win_hash}
        (backup/"state.json").write_text(__import__("json").dumps(state,indent=2)+"\n")
        state_root.mkdir(parents=True,exist_ok=True)
        (state_root/"latest.json").write_text(__import__("json").dumps(state,indent=2)+"\n")
        print("INSTALLED. Restart macOS to activate the eDP fix.")
        print("PREVIOUS EFI/OC BACKUP:", backup/"OC")
        print("Windows EFI unchanged. Do not enable S3 system sleep.")

def rollback(esp, validator, state_root):
    require(os.geteuid() == 0, "Rollback requires sudo")
    record = state_root/"latest.json"
    require(record.is_file(), "No local state found; use your own pre-install OC/config.plist backup")
    state = __import__("json").loads(record.read_text())
    require(state["esp"] == esp, "State belongs to a different EFI partition")
    old = Path(state["backup_config"])
    require(old.is_file() and sha(old) == state["original_config_sha256"], "Backup is missing/corrupt")
    with MountedEFI(esp) as efi:
        configpath = efi/"OC/config.plist"
        require(sha(configpath) == state["new_config_sha256"],
                "Configuration changed since install; manual review required")
        win = efi/"Microsoft/Boot/bootmgfw.efi"
        require(sha(win) == state["windows_boot_sha256"], "Windows EFI unexpectedly changed")
        validate(validator,old)
        pending = configpath.with_name("config-SL4-EDP-rollback-pending.plist")
        with pending.open("xb") as f:
            f.write(old.read_bytes()); f.flush(); os.fsync(f.fileno())
        os.replace(pending,configpath)
        validate(validator,configpath)
        print("ORIGINAL CONFIG RESTORED, effective next boot.")
        print("Original kext remains intact:",state["original_kext_name"])
        record.rename(state_root/("rolled-back-"+state["at"]+".json"))

def main():
    p = argparse.ArgumentParser(description="Install/rollback tested Tiger Lake eDP Keep + Softsleep (existing Tahoe/OpenCore only)")
    p.add_argument("mode",choices=("check","apply","rollback"))
    p.add_argument("--esp",required=True,help="Internal EFI partition identifier, e.g. disk0s1; verify with diskutil list")
    args=p.parse_args()
    bundle,validator,temporary=discover_bundle()
    try:
        check_bundle(bundle,validator)
        version=check_machine()
        require(os.geteuid() == 0, "Use sudo for mount, config validation and rollback")
        if args.mode=="check":
            with MountedEFI(args.esp) as efi:
                configfile=efi/"OC/config.plist"
                validate(validator,configfile)
                i,e,nv,args_current=inspect_config(efi,plistlib.loads(configfile.read_bytes()))
                print("COMPATIBLE:",version,"donor",DONOR_SHA,"current kext",e["BundlePath"])
                print("Dry-run OK. This changes nothing.")
        elif args.mode=="apply":
            apply(args.esp,bundle,validator,backup_dir())
        else:
            rollback(args.esp,validator,backup_dir())
    finally:
        if temporary:
            temporary.cleanup()

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("STOP:",error,file=sys.stderr)
        sys.exit(1)
