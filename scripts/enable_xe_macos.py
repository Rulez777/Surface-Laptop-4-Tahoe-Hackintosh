#!/usr/bin/env python3
"""Surface Laptop 4 Tahoe one-step postinstall graphics + driver activation.

Called by QuickStart-Mac.command AFTER installing official WhateverXe Graphics
0.4.4. Prepares the Windows-created, private USB EFI only; does not overwrite
Windows EFI, BCD, APFS or current running kexts. Existing no-accel OpenCore
and copied personal SMBIOS survive as an on-USB recovery config.
"""
from __future__ import annotations
from pathlib import Path
import argparse
import datetime
import hashlib
import io
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import zipfile

GUID="7C436110-AB2A-4BBB-A880-FE41995C9F82"
D0=Path("/Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext/Contents/MacOS/AppleIntelTGLGraphicsFramebuffer")
D1=Path("/Library/Extensions/AppleIntelTGLGraphics.kext/Contents/MacOS/AppleIntelTGLGraphics")
SHA0="115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e"
SHA1="6c8ab6cce50b9529679ee4fdf5b1c37d091677d945076f41cb4b7f8196c51449"
RELEASE_SHA="dd793ab5ce18079ae75484daae8a37766ccd466b181f40df79df74bdf34f30dd"
BETA="SL4-S0ix-DMC-0.2.0-beta/"
DMC_PATH="WhateverXe-SL4-S0IX-DMC.kext"
SLEEP_PATH="S0ixStandby.kext"
SLEEP_AML="SSDT-DEEPIDLE.aml"
PNLF_AML="SSDT-PNLF.aml"
STARTUP_ARGS=("-wex-tgl-no-posh","-wex-tgl-gpurec","-wex-tgl-stampfix",
              "-nodisplaysleepDC6","-noDC9","dc6config=0",
              "-wex-edp-wake-trace","-wex-tgl-edp-keep",
              "-wex-tgl-edp-softsleep","-wex-sl4-tgl-dmc")
EXTRA_DRIVERS=("AppleALC.kext","SimpleHDA.kext","AirportItlwm.kext",
               "IntelBluetoothFirmware.kext","IntelBTPatcher.kext",
               "BlueToolFixup.kext","SMCProcessor.kext")

def require(ok,why):
    if not ok:raise RuntimeError(why)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def sha_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for block in iter(lambda:f.read(1048576),b""):
            h.update(block)
    return h.hexdigest()

def system_check():
    require(sys.platform=="darwin" and os.uname().machine=="x86_64",
            "Requires Intel macOS")
    version=subprocess.check_output(["/usr/bin/sw_vers","-productVersion"],text=True).strip()
    require(version=="26.7.1","Tahoe graphics donor differs on "+version+"; choose advanced mode")
    require(D0.is_file() and D1.is_file() and sha_file(D0)==SHA0 and sha_file(D1)==SHA1,
            "Official Graphics pkg 0.4.4 donor binaries missing or do not match this profile")

def config_preflight(raw,efi):
    require(efi.name=="EFI" and (efi/"OC/OpenCore.efi").is_file()
            and (efi/"BOOT/BOOTx64.efi").is_file(),
            "Expected USB's personal EFI root, not macOS or Windows volume")
    obj=plistlib.loads(raw)
    entries=obj["Kernel"]["Add"]
    names=[x["BundlePath"] for x in entries if x.get("Enabled")]
    for item in ("Lilu.kext","WhateverXe.kext","AMFIAnchor.kext","AMFIAnchorInjector.kext"):
        require(names.count(item)==1,"Missing or duplicate initial kext: "+item)
    require(names.index("Lilu.kext")<names.index("WhateverXe.kext"),"Lilu must load first")
    for item in EXTRA_DRIVERS:
        matches=[x for x in entries if x.get("BundlePath")==item]
        require(len(matches)==1 and not matches[0].get("Enabled"),
                "Expected staged-inactive driver on installer USB: "+item)
        require((efi/"OC/Kexts"/item/"Contents/Info.plist").is_file(),
                "Missing staged peripheral: "+item)
    props=obj["NVRAM"]["Add"][GUID]
    args=props["boot-args"].split()
    require("-wex-noaccel" in args and "-igfxdvmt" in args,
            "Expected pre-Graphics boot flags missing")
    require(props["csr-active-config"]==bytes.fromhex("03080000"),
            "Expected Graphics SIP settings missing")
    require("boot-args" in obj["NVRAM"]["Delete"][GUID],
            "NVRAM Delete boot-args missing")
    require(any(x.get("Enabled") and x.get("Path")=="SSDT-RTC0-SL4.aml"
            for x in obj["ACPI"]["Add"]),"Surface RTC ACPI missing")
    for item in (DMC_PATH,SLEEP_PATH):
        require(not any(x.get("BundlePath")==item for x in entries),
                "New graphics or S0ix already installed; refuse duplicate")
        require(not (efi/"OC/Kexts"/item).exists(),
                "Stale graphics/S0ix directory: "+item)
    require(not any(x.get("Path") in (SLEEP_AML,PNLF_AML)
            for x in obj["ACPI"]["Add"]), "Deep Idle/brightness already installed")
    require(not (efi/"OC/ACPI"/SLEEP_AML).exists() and
            not (efi/"OC/ACPI"/PNLF_AML).exists(),"Stale ACPI file on installer")
    return obj

def make_active(raw,efi):
    obj=config_preflight(raw,efi)
    entries=obj["Kernel"]["Add"]
    names=[x["BundlePath"] for x in entries]
    previous=entries[names.index("WhateverXe.kext")]
    previous["Enabled"]=False
    driver=dict(previous)
    driver["Enabled"]=True
    driver["BundlePath"]=DMC_PATH
    driver["Comment"]="Surface Laptop 4 Intel DMC + accelerated Xe + eDP"
    entries.insert(names.index("WhateverXe.kext")+1,driver)
    for item in EXTRA_DRIVERS:
        next(x for x in entries if x["BundlePath"]==item)["Enabled"]=True
    entries.append({"Arch":"x86_64","BundlePath":SLEEP_PATH,
                    "Comment":"Surface Laptop 4 Intel system Deep Idle",
                    "Enabled":True,"ExecutablePath":"Contents/MacOS/S0ixStandby",
                    "PlistPath":"Contents/Info.plist","MinKernel":"","MaxKernel":""})
    for item in (SLEEP_AML,PNLF_AML):
        obj["ACPI"]["Add"].append({"Enabled":True,
                                  "Comment":"Surface Intel "+item,"Path":item})
    args=[a for a in obj["NVRAM"]["Add"][GUID]["boot-args"].split()
          if a not in ("-wex-noaccel","-v","keepsyms=1","debug=0x100")]
    for a in STARTUP_ARGS:
        if a not in args:args.append(a)
    obj["NVRAM"]["Add"][GUID]["boot-args"]=" ".join(args)
    obj["Kernel"]["Quirks"]["DisableLinkeditJettison"]=True
    props=obj.setdefault("DeviceProperties",{}).setdefault("Add",{})
    props.setdefault("PciRoot(0x0)/Pci(0x1F,0x3)",{})["layout-id"]=(35).to_bytes(4,"little")
    return plistlib.dumps(obj,sort_keys=False)

def check_release(archive):
    require(archive.is_file() and sha_file(archive)==RELEASE_SHA,
            "Wrong public Surface DMC driver ZIP SHA256")
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None,"Archive corrupt")
        for x in (BETA+"payload/"+DMC_PATH+"/Contents/Info.plist",
                  BETA+"payload/"+DMC_PATH+"/Contents/MacOS/WhateverXe",
                  BETA+"payload/"+SLEEP_PATH+"/Contents/MacOS/S0ixStandby",
                  BETA+"payload/"+SLEEP_AML):
            require(x in z.namelist(),"Release missing "+x)
    return True

def aml_brightness():
    from install_brightness_macos import ORIGINAL_PNLF_UID14,patch_pnlf
    return patch_pnlf(ORIGINAL_PNLF_UID14)

def validate_config(raw,validator):
    require(validator.is_file(),"Matching OpenCore 1.0.8 validator absent")
    with tempfile.NamedTemporaryFile(prefix="sl4-oc-",suffix=".plist",delete=False) as fd:
        p=Path(fd.name)
        fd.write(raw)
    try:
        v=subprocess.run([str(validator),str(p)],capture_output=True,text=True,timeout=35)
        require(v.returncode==0,"ocvalidate rejected config: "+(v.stdout+v.stderr)[-350:])
    finally:p.unlink(missing_ok=True)

def plan(efi,archive,validator):
    system_check()
    check_release(archive)
    original=(efi/"OC/config.plist").read_bytes()
    newer=make_active(original,efi)
    validate_config(original,validator)
    validate_config(newer,validator)
    aml=aml_brightness()
    require(aml[:4]==b"SSDT" and sum(aml)%256==0,"PNLF table invalid")
    return original,newer,aml

def copy_release_kext(z,kext,efi):
    prefix=BETA+"payload/"+kext+"/"
    target=efi/"OC/Kexts"/kext
    require(not target.exists(),"Kext already installed: "+kext)
    names=[x for x in z.namelist() if x.startswith(prefix) and not x.endswith("/")]
    require(names,"Missing release bundle "+kext)
    for item in names:
        rel=Path(item[len(prefix):])
        require(not rel.is_absolute() and ".." not in rel.parts,"Unsafe release archive member")
        f=target/rel
        f.parent.mkdir(parents=True,exist_ok=True)
        f.write_bytes(z.read(item))
    require((target/"Contents/Info.plist").is_file(),"Invalid copied kext bundle")
    return target

def apply(efi,archive,validator):
    require(os.geteuid()==0,"Administrator rights needed to write macOS EFI")
    before,after,pnlf=plan(efi,archive,validator)
    oc=efi/"OC"
    require(shutil.disk_usage(oc).free > 12*1024*1024,
            "USB EFI free space insufficient")
    old=oc/"config.plist"
    import pwd
    user=os.environ.get("SUDO_USER") or pwd.getpwuid(os.getuid()).pw_name
    home=Path(pwd.getpwnam(user).pw_dir)
    backup=home/"Downloads/SL4-Tahoe-Graphics-Backup"/datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    require(not backup.exists(),"Backup name collision")
    backup.mkdir(parents=True)
    shutil.copytree(oc,backup/"OC")
    require(sha_file(backup/"OC/config.plist")==sha(before),"Backup failed")
    restore=oc/"config-SL4-before-Hardware.plist"
    require(not restore.exists(),"Previous restore config exists")
    with restore.open("xb") as file:
        file.write(before);file.flush();os.fsync(file.fileno())
    require(sha_file(restore)==sha(before),"On-USB restore config mismatch")
    staged=[]
    try:
        with zipfile.ZipFile(archive) as z:
            for name in (DMC_PATH,SLEEP_PATH):
                target=oc/"Kexts"/name
                staged.append(target)
                copy_release_kext(z,name,efi)
            aml=oc/"ACPI"/SLEEP_AML
            staged.append(aml)
            aml.write_bytes(z.read(BETA+"payload/"+SLEEP_AML))
            light=oc/"ACPI"/PNLF_AML
            staged.append(light)
            light.write_bytes(pnlf)
        pending=oc/".config-sl4-hardware-new.plist"
        require(not pending.exists(),"Unfinished pending config exists")
        staged.append(pending)
        with pending.open("xb") as file:
            file.write(after);file.flush();os.fsync(file.fileno())
        require(old.read_bytes()==before,"Config changed while preparing hardware")
        os.replace(pending,old)
        validate_config(old.read_bytes(),validator)
    except BaseException:
        if old.read_bytes()==after:
            pending=oc/".config-sl4-hardware-rollback.plist"
            with pending.open("xb") as file:file.write(before)
            os.replace(pending,old)
        for target in reversed(staged):
            if target.is_dir():shutil.rmtree(target)
            elif target.exists():target.unlink()
        raise
    print("SUCCESS: Metal 2 + tested DMC, BigSurface, Intel Wi-Fi/Bluetooth, audio, brightness, Deep Idle prepared on USB.")
    print("Original WhateverXe retained. USB config recovery:",restore)
    print("Personal complete OC backup:",backup)
    print("Restart from USB OpenCore; no Windows partition changed.")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("check","apply"))
    p.add_argument("--efi",type=Path,required=True,help="Windows-prepared USB EFI directory")
    p.add_argument("--release",type=Path,required=True)
    p.add_argument("--ocvalidate",type=Path,required=True)
    args=p.parse_args()
    efi=args.efi.resolve(strict=True)
    plan(efi,args.release,args.ocvalidate)
    print("VALIDATED: exact Graphics donor, OC configuration and driver release")
    if args.mode=="apply":apply(efi,args.release,args.ocvalidate)

if __name__=="__main__":
    try:main()
    except Exception as ex:
        print("STOP:",ex,file=sys.stderr)
        sys.exit(1)
