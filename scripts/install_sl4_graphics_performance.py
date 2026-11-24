#!/usr/bin/env python3
"""Reversible postinstall SL4 graphics performance beta (never for initial Windows/Recovery USB boot).
Mac-specific execution, exact donor identification, no automatic system sleep changes.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
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

RELEASE = "SL4-Graphics-Performance-0.1.7-beta"
TARGET = "WhateverXe-SL4-RCS-V017-TRIAL.kext"
UUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
FLAGS = ("-wex-sl4-rcs-singleport","-wex-sl4-rcs-nativequeue-trial","-wex-sl4-heap-depth-trial")
WEX_SHA = "94669172f4c2a52937b587c5eb3fdb73ff030963397aa094e575d9c4b54863d3"
DONOR_SHA = "6c8ab6cce50b9529679ee4fdf5b1c37d091677d945076f41cb4b7f8196c51449"
KEXT_ID = "org.b00t0x.WhateverXe"
DONOR = Path("/Library/Extensions/AppleIntelTGLGraphics.kext/Contents/MacOS/AppleIntelTGLGraphics")
HERE = Path(__file__).resolve().parent

def require(ok, message):
    if not ok:
        raise RuntimeError(message)

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def run(*args):
    p=subprocess.run([str(x) for x in args],text=True,capture_output=True)
    require(p.returncode == 0,"Command failed: "+" ".join(str(x) for x in args)+" "+(p.stderr+p.stdout)[-850:])
    return p.stdout

def examine_bundle():
    manifest_path=HERE/"MANIFEST.json"
    require(manifest_path.is_file(),"Missing signed-off release manifest")
    m=json.loads(manifest_path.read_text())
    require(m.get("release")==RELEASE and m.get("no_private_efi") is True,"Release manifest invalid")
    require(isinstance(m.get("sha256"),dict),"Missing manifest checksums")
    for name,sha in m["sha256"].items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "Unsafe release path")
        p=HERE/name
        require(p.is_file() and digest(p)==sha,"Release component mismatch: "+name)
    binary=HERE/"payload"/TARGET/"Contents/MacOS/WhateverXe"
    require(binary.is_file() and digest(binary)==WEX_SHA,"Unrecognized RCS WhateverXe binary")
    info=plistlib.loads((HERE/"payload"/TARGET/"Contents/Info.plist").read_bytes())
    require(info.get("CFBundleIdentifier")==KEXT_ID and info.get("CFBundleVersion")=="0.8.3",
            "Wrong WhateverXe plugin")
    validator=HERE/"payload/ocvalidate"
    require(validator.is_file(),"Missing OpenCore 1.0.8 validator")
    return validator

def preflight_hardware():
    require(sys.platform=="darwin" and os.uname().machine=="x86_64","Requires Intel macOS")
    require(run("/usr/bin/sw_vers","-productVersion").strip()=="26.7.1","Only Tahoe 26.7.1 is tested")
    cpu=run("/usr/sbin/sysctl","-n","machdep.cpu.brand_string")
    require("i7-1185G7" in cpu,"Only SL4 i7-1185G7 tested")
    require(DONOR.is_file() and digest(DONOR)==DONOR_SHA,"Different Intel graphics donor; refuse to patch")
    gpu=run("/usr/sbin/ioreg","-p","IOService","-r","-n","IGPU","-l","-w0").lower()
    require('"device-id" = <499a0000>' in gpu and '"vendor-id" = <86800000>' in gpu,
            "Not a verified Intel Iris Xe 8086:9A49")
    display=run("/usr/sbin/system_profiler","SPDisplaysDataType")
    require("Metal Support: Metal 2" in display,"Working Metal 2 is a prerequisite")

@contextmanager
def mounted_esp(esp):
    require(re.fullmatch(r"disk[0-9]+s[0-9]+",esp),"Expected partition identifier disk0s1")
    d=plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil","info","-plist",esp]))
    require(d.get("Content")=="EFI" and d.get("Internal") and not d.get("Removable"),
            "Not an internal non-removable EFI System Partition")
    require(100*1024**2 <= d.get("TotalSize",0) <= 2*1024**3,
            "Unrecognized EFI partition capacity")
    owned=False
    tmp=None
    try:
        if d.get("MountPoint"):
            mount=Path(d["MountPoint"])
            require(not d.get("VolumeReadOnly",False),"Mounted EFI is read-only")
        else:
            require(os.geteuid()==0,"Use sudo to mount EFI")
            tmp=tempfile.TemporaryDirectory(prefix="sl4-rcs-esp-",dir="/private/tmp")
            run("/sbin/mount_msdos","-o","rw","/dev/"+esp,tmp.name)
            mount=Path(tmp.name)
            owned=True
        efi=mount/"EFI"
        require((efi/"OC/config.plist").is_file() and
                (efi/"Microsoft/Boot/bootmgfw.efi").is_file(),"OpenCore or Windows boot manager missing")
        yield efi
    finally:
        if owned:
            run("/usr/sbin/diskutil","unmount",esp)
            tmp.cleanup()

def cfg_inspect(efi):
    cfg=efi/"OC/config.plist"
    data=plistlib.loads(cfg.read_bytes())
    a=data["Kernel"]["Add"]
    live=[(i,e) for i,e in enumerate(a) if e.get("Enabled") and "WhateverXe" in e.get("BundlePath","")]
    require(len(live)==1,"Require exactly one enabled WhateverXe")
    pos,entry=live[0]
    require(entry["BundlePath"]!=TARGET,"RCS patch already selected; no reinstall needed")
    require(any(e.get("Enabled") and e.get("BundlePath")=="Lilu.kext" for e in a[:pos]),
            "Lilu must precede active WhateverXe")
    prior=efi/"OC/Kexts"/entry["BundlePath"]
    require(prior.is_dir() and (prior/"Contents/MacOS/WhateverXe").is_file(),"Current kext missing")
    inf=plistlib.loads((prior/"Contents/Info.plist").read_bytes())
    require(inf.get("CFBundleIdentifier")==KEXT_ID and inf.get("CFBundleVersion")=="0.8.3",
            "Current WhateverXe must be 0.8.3")
    args=data["NVRAM"]["Add"][UUID]["boot-args"].split()
    require(all(x in args for x in ("-allow3d","-wex-tgl-gpurec",
            "-wex-tgl-stampfix","-wex-sl4-tgl-dmc")),"Existing Tahoe DMC/3D boot profile required")
    require("boot-args" in data["NVRAM"]["Delete"][UUID],"OpenCore boot-args Delete missing")
    return cfg,data,pos,args

def validate(validator,file):
    run(validator,file)

def state_home():
    user=os.environ.get("SUDO_USER") or pwd.getpwuid(os.getuid()).pw_name
    return Path(pwd.getpwnam(user).pw_dir)/"Documents/SL4-GRAPHICS-V017-BACKUPS"

def check(esp,validator):
    preflight_hardware()
    with mounted_esp(esp) as efi:
        path,cfg,pos,args=cfg_inspect(efi)
        validate(validator,path)
        require(shutil.disk_usage(efi).free>5*1024**2,"EFI lacks space for parallel RCS kext")
        print("READY_FOR_RCS_INSTALL",pos,"original",cfg["Kernel"]["Add"][pos]["BundlePath"])
        print("Windows Boot Manager will remain untouched.")

def apply(esp,validator):
    require(os.geteuid()==0,"Use sudo for EFI modifications")
    preflight_hardware()
    root=state_home()
    require(not (root/"latest.json").exists(),"Existing RCS installation state: rollback before reinstall")
    with mounted_esp(esp) as efi:
        cfgpath,config,pos,args=cfg_inspect(efi)
        validate(validator,cfgpath)
        want=efi/"OC/Kexts"/TARGET
        require(not want.exists(),"Target kext already exists: refusing overwrite")
        require(shutil.disk_usage(efi).free>6*1024**2,"EFI lacks free space")
        before=digest(cfgpath)
        win=efi/"Microsoft/Boot/bootmgfw.efi"
        windows_hash=digest(win)
        stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
        backup=root/stamp
        require(not backup.exists(),"Backup folder collision")
        backup.mkdir(parents=True,exist_ok=False)
        shutil.copytree(efi/"OC",backup/"OC",symlinks=True)
        require(digest(backup/"OC/config.plist")==before,"Complete OC backup failed")
        original_on_efi=cfgpath.with_name("config-SL4-RCS-before-"+stamp+".plist")
        original_on_efi.write_bytes(cfgpath.read_bytes())
        require(digest(original_on_efi)==before,"On-ESP recovery config failed")
        shutil.copytree(HERE/"payload"/TARGET,want)
        require(digest(want/"Contents/MacOS/WhateverXe")==WEX_SHA,"Copied RCS driver differs")
        config["Kernel"]["Add"][pos]["BundlePath"]=TARGET
        config["Kernel"]["Add"][pos]["Comment"]="SL4 graphics performance v0.1.7 beta, native queue + heap depth"
        config["NVRAM"]["Add"][UUID]["boot-args"]=" ".join(args+[f for f in FLAGS if f not in args])
        pending=cfgpath.with_name("config-SL4-RCS-pending-"+stamp+".plist")
        require(not pending.exists(),"Pending config collision")
        pending.write_bytes(plistlib.dumps(config,sort_keys=False))
        validate(validator,pending)
        require(digest(cfgpath)==before and digest(win)==windows_hash,
                "EFI or Windows boot manager changed during preparation")
        os.replace(pending,cfgpath)
        validate(validator,cfgpath)
        require(digest(win)==windows_hash,"Windows Boot Manager unexpectedly changed")
        record={"esp":esp,"backup_config":str(backup/"OC/config.plist"),
                "pre_config_sha":before,"post_config_sha":digest(cfgpath),
                "windows_sha":windows_hash,"at":stamp,"prior_kext":backup/"OC",
                "new_kext":TARGET}
        record["prior_kext"]=str((backup/"OC/Kexts"))
        (backup/"state.json").write_text(json.dumps(record,indent=2)+"\n")
        root.mkdir(exist_ok=True)
        (root/"latest.json").write_text(json.dumps(record,indent=2)+"\n")
        print("INSTALLED_RCS_PATCH. Reboot and check: ioreg -p IOService -l -w0 | grep SL4HeapDepthTrialReady")
        print("RECOVERY_CONFIG",original_on_efi)
        print("WIN_BOOT_UNTOUCHED",windows_hash)

def rollback(esp,validator):
    require(os.geteuid()==0,"Use sudo for rollback")
    record=state_home()/"latest.json"
    require(record.is_file(),"No RCS installer state found")
    d=json.loads(record.read_text())
    require(d["esp"]==esp,"Backup belongs to another EFI partition")
    prior=Path(d["backup_config"])
    require(prior.is_file() and digest(prior)==d["pre_config_sha"],"Backup config missing or corrupt")
    with mounted_esp(esp) as efi:
        cfg=efi/"OC/config.plist"
        win=efi/"Microsoft/Boot/bootmgfw.efi"
        require(digest(cfg)==d["post_config_sha"] and digest(win)==d["windows_sha"],
                "EFI changed since installation; manual review needed")
        validate(validator,prior)
        tmp=cfg.with_name("config-SL4-RCS-rollback-pending.plist")
        require(not tmp.exists(),"Rollback temp config already exists")
        tmp.write_bytes(prior.read_bytes())
        os.replace(tmp,cfg)
        validate(validator,cfg)
        require(digest(cfg)==d["pre_config_sha"] and digest(win)==d["windows_sha"],
                "Rollback verification failed")
    record.unlink()
    print("ORIGINAL_CONFIG_RESTORED; reboot to load old WhateverXe; previous kext retained.")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=("check","apply","rollback"))
    p.add_argument("--esp",required=True)
    o=p.parse_args()
    validator=examine_bundle()
    {"check":check,"apply":apply,"rollback":rollback}[o.command](o.esp,validator)

if __name__=="__main__":
    try:main()
    except Exception as e:
        print("RCS INSTALL STOP:",e,file=sys.stderr)
        sys.exit(1)
