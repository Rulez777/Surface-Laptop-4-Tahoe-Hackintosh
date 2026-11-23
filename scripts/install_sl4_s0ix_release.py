#!/usr/bin/env python3
"""Fail-closed permanent SL4 Tiger Lake / Tahoe S0ix postinstaller.

Requires an *already working, accelerated* Tahoe 26.7.1 installation with
OpenCore 1.0.8, BigSurface and byte-pinned eDP Keep+Softsleep WhateverXe.
Does not build a clean EFI or install macOS. Never modifies EFI/Microsoft.
Modes: check, apply, rollback; all use --esp diskNsM.
This installer does NOT enable automatic idle sleep.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
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

RELEASE="SL4-S0ix-DMC-0.2.0-beta"
ROOT=Path(__file__).resolve().parent
PAYLOAD=ROOT/"payload"
WEX=PAYLOAD/"WhateverXe-SL4-S0IX-DMC.kext"
S0IX=PAYLOAD/"S0ixStandby.kext"
AML=PAYLOAD/"SSDT-DEEPIDLE.aml"
OCVAL=PAYLOAD/"ocvalidate"
WEX_TARGET="WhateverXe-SL4-S0IX-DMC.kext"
S0IX_TARGET="S0ixStandby.kext"
AML_TARGET="SSDT-DEEPIDLE.aml"
NV_GUID="7C436110-AB2A-4BBB-A880-FE41995C9F82"
BASE_WEX_SHA="0796d12158b9c6806a83e4f455f84eee9280a0148406b8d4f0764234f00df91a"
# Mach-O LC_UUID is nondeterministic between builds. Normalize only the verified
# 16-byte UUID payload after validating its offset and architecture.
DMC_NORMALIZED_SHA="7fcbf0fdb3c2e02f68941f3644902a10b06dd7ba824164c353c96ad6080ee0ac"
S0IX_SHA="5203911400cc595e840d712e8b5538b2ecdae798f46faed1d802904917efb8a5"
AML_SHA="477c92c60a767cde3baef858932d652a91b962f5e01cd7baf6467c544c7a46f0"
OCVAL_SHA="c76f907d5caad299889a2314ae68f03cd8538ad53f65a3c2c7c95ae0d0bb0b38"
DONOR_FB=Path("/Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext/Contents/MacOS/AppleIntelTGLGraphicsFramebuffer")
DONOR_AC=Path("/Library/Extensions/AppleIntelTGLGraphics.kext/Contents/MacOS/AppleIntelTGLGraphics")
DONOR_FB_SHA="115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e"
DONOR_AC_SHA="6c8ab6cce50b9529679ee4fdf5b1c37d091677d945076f41cb4b7f8196c51449"
BOOT_ARG="-wex-sl4-tgl-dmc"
REQUIRED_ARGS={"-allow3d","-disablegfxfirmware","-igfxdvmt","-wex-tgl-gpurec",
               "-wex-tgl-edp-keep","-wex-tgl-edp-softsleep"}
MIN_ESP=250_000_000
MAX_ESP=350_000_000


def require(condition,why):
    if not condition:raise RuntimeError(why)


def hash_file(p):
    digest=hashlib.sha256()
    with Path(p).open("rb") as file:
        for chunk in iter(lambda:file.read(1048576),b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_wex(p):
    data=bytearray(Path(p).read_bytes())
    require(len(data)==1888640,"Unknown DMC kext executable length")
    require(data[:4]==b"\xcf\xfa\xed\xfe","Unexpected Mach-O header")
    # UUID offset checked against the tested Intel x86_64 Mach-O linker image.
    data[1160:1176]=bytes(16)
    return hashlib.sha256(data).hexdigest()


def run(*items):
    args=list(map(str,items))
    p=subprocess.run(args,text=True,capture_output=True,timeout=60,check=False)
    require(p.returncode==0,"Command failed: "+" ".join(args)+": "+(p.stdout+p.stderr)[-450:])
    return p.stdout


def mac_preflight():
    require(sys.platform=="darwin" and os.uname().machine=="x86_64",
            "Requires Intel macOS, not Apple Silicon or Windows")
    require(run("/usr/bin/sw_vers","-productVersion").strip()=="26.7.1",
            "Only Tahoe 26.7.1 has been tested")
    require("i7-1185G7" in run("/usr/sbin/sysctl","-n","machdep.cpu.brand_string"),
            "Unexpected CPU; not an SL4 Intel i7-1185G7")
    igpu=run("/usr/sbin/ioreg","-r","-n","IGPU","-lw0").lower()
    require('"device-id" = <499a0000>' in igpu and '"vendor-id" = <86800000>' in igpu,
            "Expected Intel Iris Xe PCI 8086:9A49")
    require(DONOR_FB.is_file() and hash_file(DONOR_FB)==DONOR_FB_SHA and
            DONOR_AC.is_file() and hash_file(DONOR_AC)==DONOR_AC_SHA,
            "Installed Tahoe TGL graphics donor differs; refuse unsafe offsets")
    kexts=run("/usr/bin/kmutil","showloaded")
    require("com.xavier.BigSurface (1.2.0)" in kexts and
            "org.b00t0x.WhateverXe (0.8.3)" in kexts,
            "Working BigSurface and WhateverXe must be active first")
    acpi=run("/usr/sbin/ioreg","-p","IOACPIPlane","-lw0")
    require("PEPD" in acpi and "PNP0D80" in acpi and "MSHW0084" in acpi,
            "Unexpected Surface PEPD ACPI profile")
    return True


def validate_assets():
    exe=WEX/"Contents/MacOS/WhateverXe"
    kext=S0IX/"Contents/MacOS/S0ixStandby"
    require(exe.is_file() and normalized_wex(exe)==DMC_NORMALIZED_SHA,
            "WhateverXe DMC release binary does not match tested code")
    require(kext.is_file() and hash_file(kext)==S0IX_SHA,
            "S0ixStandby binary differs from pinned 0.5.8 release")
    require(AML.is_file() and hash_file(AML)==AML_SHA and
            AML.read_bytes().startswith(b"SSDT") and
            len(AML.read_bytes())==int.from_bytes(AML.read_bytes()[4:8],"little") and
            sum(AML.read_bytes())%256==0,
            "Deep Idle SSDT invalid")
    require(OCVAL.is_file() and hash_file(OCVAL)==OCVAL_SHA,
            "Pinned ocvalidate 1.0.8 absent or changed")
    w=plistlib.loads((WEX/"Contents/Info.plist").read_bytes())
    s=plistlib.loads((S0IX/"Contents/Info.plist").read_bytes())
    require(w.get("CFBundleIdentifier")=="org.b00t0x.WhateverXe" and
            w.get("CFBundleVersion")=="0.8.3" and
            s.get("CFBundleIdentifier")=="com.labrouss.S0ixStandby" and
            s.get("CFBundleVersion")=="0.5.8","Unexpected kext versions")
    require((ROOT/"LICENSES/LICENSE.i915").is_file() and
            (ROOT/"LICENSES/WhateverXe-LICENSE.txt").is_file() and
            (ROOT/"LICENSES/S0ixStandby-LICENSE").is_file(),
            "Missing mandatory third-party copyright/license notices")
    return True


def disk_info(device):
    require(re.fullmatch(r"disk[0-9]+s[0-9]+",device)!=None,
            "--esp must be exact partition name, e.g. disk0s1")
    i=plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil","info","-plist",device]))
    require(i.get("DeviceIdentifier")==device and i.get("Content")=="EFI" and
            i.get("Internal") and not i.get("Removable") and
            MIN_ESP <= i.get("TotalSize",0) <= MAX_ESP,
            "Refusing unexpected/removable EFI partition")
    return i


@contextlib.contextmanager
def mount_esp(device):
    i=disk_info(device)
    mounted_here=False
    if not i.get("MountPoint"):
        require(os.geteuid()==0,"Run with sudo so the internal ESP can be mounted")
        run("/usr/sbin/diskutil","mount",device)
        mounted_here=True
        i=disk_info(device)
    mount=i.get("MountPoint")
    require(mount and Path(mount).is_dir(),"Internal ESP did not mount")
    root=Path(mount)/"EFI"
    require((root/"OC/config.plist").is_file() and
            (root/"OC/OpenCore.efi").is_file() and
            (root/"Microsoft/Boot/bootmgfw.efi").is_file(),
            "Expected OpenCore + Windows Boot Manager not found")
    try:yield root
    finally:
        if mounted_here:
            run("/usr/sbin/diskutil","unmount",device)


def current_config(efi):
    oc=efi/"OC"
    cfg=oc/"config.plist"
    raw=cfg.read_bytes()
    obj=plistlib.loads(raw)
    require(obj.get("PlatformInfo",{}).get("Generic",{}).get("SystemProductName")==
            "MacBookPro16,2","Unexpected OpenCore SMBIOS model")
    cpuid=obj.get("Kernel",{}).get("Emulate",{}).get("Cpuid1Data",b"")
    require(isinstance(cpuid,bytes) and cpuid[:4]==bytes.fromhex("e5060700"),
            "Expected tested Ice Lake CPUID spoof")
    entries=obj["Kernel"]["Add"]
    active=[(n,k) for n,k in enumerate(entries) if k.get("Enabled") and
            "WhateverXe" in k.get("BundlePath","")]
    require(len(active)==1,"Expected one enabled WhateverXe")
    pos,entry=active[0]
    require(any(k.get("Enabled") and k.get("BundlePath")=="Lilu.kext" for k in entries[:pos]),
            "Lilu must load before WhateverXe")
    nv=obj["NVRAM"]["Add"][NV_GUID]
    args=nv.get("boot-args")
    require(isinstance(args,str) and REQUIRED_ARGS.issubset(set(args.split())) and
            "boot-args" in obj["NVRAM"]["Delete"][NV_GUID],
            "Missing working eDP/Metal boot arguments or NVRAM override")
    oldbundle=oc/"Kexts"/entry["BundlePath"]
    require(oldbundle.is_dir(),"Current WhateverXe bundle missing from ESP")
    binary=oldbundle/"Contents/MacOS/WhateverXe"
    require(binary.is_file(),"Current WhateverXe binary missing")
    h=hash_file(binary)
    if h==BASE_WEX_SHA:
        state="edp_ready"
    elif normalized_wex(binary)==DMC_NORMALIZED_SHA:
        state="dmc_already_active"
    else:
        raise RuntimeError("Current WhateverXe is NOT tested Keep+Softsleep or DMC; SHA mismatch")
    return raw,obj,pos,args,state


def validate_config(payload):
    import tempfile
    with tempfile.NamedTemporaryFile(prefix="sl4-config-check-",suffix=".plist",delete=False) as tmp:
        path=Path(tmp.name)
        tmp.write(payload)
    try:
        run("/usr/bin/plutil","-lint",path)
        run(OCVAL,path)
    finally:path.unlink(missing_ok=True)


def build_config(original,pos,args):
    data=plistlib.loads(original)
    en=data["Kernel"]["Add"]
    acpis=data["ACPI"]["Add"]
    require(not any(k.get("Enabled") and "S0ix" in k.get("BundlePath","") for k in en),
            "S0ixStandby already active; refuse duplicate")
    require(not any(k.get("Path")==AML_TARGET for k in acpis),
            "SSDT-DEEPIDLE already present; refuse duplicate")
    require(BOOT_ARG not in args.split(),"DMC opt-in already present")
    en[pos]["BundlePath"]=WEX_TARGET
    en.append(dict(Arch="x86_64",BundlePath=S0IX_TARGET,
                   Comment="SL4 Intel tested RTC sleep; S0ixStandby 0.5.8 (opt in)",
                   Enabled=True,ExecutablePath="Contents/MacOS/S0ixStandby",
                   MaxKernel="",MinKernel="",PlistPath="Contents/Info.plist"))
    acpis.append(dict(Comment="SL4 Intel verified S0ix RTC wake; SSDT-DEEPIDLE",
                      Enabled=True,Path=AML_TARGET))
    data["NVRAM"]["Add"][NV_GUID]["boot-args"]=args+" "+BOOT_ARG
    result=plistlib.dumps(data,sort_keys=False)
    validate_config(result)
    return result


def backup_home():
    name=os.environ.get("SUDO_USER") or pwd.getpwuid(os.getuid()).pw_name
    require(name not in ("root",""),"Must execute from a logged-in user account")
    home=Path(pwd.getpwnam(name).pw_dir)
    root=home/"Downloads/SL4-S0IX-BACKUPS"
    root.mkdir(parents=True,exist_ok=True)
    return root


def atomic(path,data):
    pending=path.parent/("."+path.name+".SL4-S0IX-new")
    require(not pending.exists(),"Pending configuration update already exists")
    try:
        with pending.open("xb") as file:
            file.write(data);file.flush();os.fsync(file.fileno())
        require(pending.read_bytes()==data,"Atomic staged config differs")
        os.replace(pending,path)
    finally:pending.unlink(missing_ok=True)


def check(device):
    mac_preflight()
    validate_assets()
    with mount_esp(device) as efi:
        before,obj,pos,args,state=current_config(efi)
        validate_config(before)
        enabled=[x for x in obj["Kernel"]["Add"] if x.get("Enabled") and
                 x.get("BundlePath")=="S0ixStandby.kext"]
        deep=[x for x in obj["ACPI"]["Add"] if x.get("Enabled") and
              x.get("Path")==AML_TARGET]
        if state=="edp_ready":
            proposed=build_config(before,pos,args)
            require(not (efi/"OC/Kexts"/WEX_TARGET).exists() and
                    not (efi/"OC/Kexts"/S0IX_TARGET).exists() and
                    not (efi/"OC/ACPI"/AML_TARGET).exists(),
                    "Stale trial files already on ESP")
            label="READY_FOR_RELEASE_INSTALL"
        elif enabled and deep and BOOT_ARG in args.split():
            label="EXPERIMENTAL_DMC_S0IX_ALREADY_ACTIVE"
        else:
            label="DMC_PRESENT_BUT_S0IX_INCOMPLETE_DO_NOT_OVERWRITE"
        print(label)
        print("Current active WEX:",obj["Kernel"]["Add"][pos]["BundlePath"])
        print("OC config SHA256:",hash_file(efi/"OC/config.plist"))
        print("Windows boot manager SHA256:",hash_file(efi/"Microsoft/Boot/bootmgfw.efi"))
        print("Installer does not overwrite Windows or enable idle sleep.")


def apply(device):
    require(os.geteuid()==0,"Administrator authorization required")
    mac_preflight()
    validate_assets()
    from datetime import datetime
    with mount_esp(device) as efi:
        original,obj,pos,args,state=current_config(efi)
        if state=="dmc_already_active":
            print("DMC already active. Refusing to overwrite or duplicate S0ix.")
            return
        validate_config(original)
        updated=build_config(original,pos,args)
        oc=efi/"OC"
        target=oc/"Kexts"/WEX_TARGET
        s0ix=oc/"Kexts"/S0IX_TARGET
        aml=oc/"ACPI"/AML_TARGET
        require(not target.exists() and not s0ix.exists() and not aml.exists(),
                "Old S0ix experiment detected; clean up manually before retry")
        require(shutil.disk_usage(oc).free>20*1024*1024,
                "Insufficient free space on the EFI partition")
        wbm=efi/"Microsoft/Boot/bootmgfw.efi"
        win_hash=hash_file(wbm)
        backup_root=backup_home()
        stamp=datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup=backup_root/stamp
        backup.mkdir(mode=0o700,exist_ok=False)
        shutil.copytree(oc,backup/"OC")
        require(hash_file(backup/"OC/config.plist")==hashlib.sha256(original).hexdigest(),
                "Private complete OC backup invalid")
        saved=oc/("config-SL4-S0IX-restore-"+stamp+".plist")
        try:
            with saved.open("xb") as f:
                f.write(original);f.flush();os.fsync(f.fileno())
            require(hash_file(saved)==hashlib.sha256(original).hexdigest(),
                    "Windows-accessible config recovery invalid")
            shutil.copytree(WEX,target,symlinks=False)
            shutil.copytree(S0IX,s0ix,symlinks=False)
            shutil.copy2(AML,aml)
            require(normalized_wex(target/"Contents/MacOS/WhateverXe")==DMC_NORMALIZED_SHA,
                    "Copied DMC binary not validated")
            require(hash_file(s0ix/"Contents/MacOS/S0ixStandby")==S0IX_SHA and
                    hash_file(aml)==AML_SHA,"Copied S0ix or SSDT not valid")
            require(hash_file(oc/"config.plist")==hashlib.sha256(original).hexdigest(),
                    "OC changed during staging")
            atomic(oc/"config.plist",updated)
            validate_config((oc/"config.plist").read_bytes())
            require(hash_file(wbm)==win_hash,"Windows loader changed unexpectedly")
            state_record=dict(esp=device,at=stamp,
                       original_config_sha256=hashlib.sha256(original).hexdigest(),
                       release_config_sha256=hashlib.sha256(updated).hexdigest(),
                       windows_boot_sha256=win_hash,
                       original_wex_bundle=obj["Kernel"]["Add"][pos]["BundlePath"],
                       new_wex_bundle=WEX_TARGET,
                       saved_esp_config=saved.name,
                       other_created=[WEX_TARGET,S0IX_TARGET,AML_TARGET],
                       automatic_system_sleep_enabled=False)
            (backup/"state.json").write_text(json.dumps(state_record,indent=2)+"\n")
            (backup_root/"latest.json").write_text(json.dumps(
                {"state":str(backup/"state.json")},indent=2)+"\n")
        except BaseException:
            if (oc/"config.plist").read_bytes()==updated:
                atomic(oc/"config.plist",original)
            if target.exists():shutil.rmtree(target)
            if s0ix.exists():shutil.rmtree(s0ix)
            if aml.exists():aml.unlink()
            raise
        print("STAGED PERMANENT S0IX-RTC COMBINATION; reboot to activate.")
        print("Original WEX kept:",state_record["original_wex_bundle"])
        print("Private backup:",backup/"OC")
        print("Windows-accessible original config:",saved)
        print("Windows Boot Manager unchanged. Auto idle system sleep NOT enabled.")


def rollback(device):
    require(os.geteuid()==0,"Administrator authorization required")
    home=backup_home()
    pointer=home/"latest.json"
    require(pointer.is_file(),"No previous SL4-S0ix installer state")
    record=json.loads(pointer.read_text())
    state_file=Path(record["state"])
    require(state_file.is_file() and state_file.parent.parent==home,
            "Unrecognized installer state path")
    data=json.loads(state_file.read_text())
    require(data["esp"]==device and data["new_wex_bundle"]==WEX_TARGET,
            "Rollback state belongs to different ESP")
    with mount_esp(device) as efi:
        oc=efi/"OC"
        cfg=oc/"config.plist"
        require(hash_file(cfg)==data["release_config_sha256"],
                "Config changed since install; safe automatic rollback is impossible")
        old=state_file.parent/"OC/config.plist"
        require(old.is_file() and hash_file(old)==data["original_config_sha256"] and
                hash_file(oc/data["saved_esp_config"])==data["original_config_sha256"],
                "Original config backups absent or mismatch")
        require(hash_file(efi/"Microsoft/Boot/bootmgfw.efi")==data["windows_boot_sha256"],
                "Windows boot loader changed unexpectedly")
        validate_config(old.read_bytes())
        atomic(cfg,old.read_bytes())
        require(hash_file(cfg)==data["original_config_sha256"],
                "Rollback config not verified")
        print("RESTORED previous OpenCore config. Reboot to deactivate S0ix.")
        print("Original boot driver remains intact; staged bundles kept inert.")
        pointer.rename(home/("rolled-back-"+data["at"]+".json"))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode",choices=("check","apply","rollback"))
    ap.add_argument("--esp",required=True,help="Internal EFI partition, e.g. disk0s1")
    args=ap.parse_args()
    if args.mode=="check":check(args.esp)
    elif args.mode=="apply":apply(args.esp)
    else:rollback(args.esp)


if __name__=="__main__":
    try:main()
    except (RuntimeError,ValueError,KeyError,OSError,subprocess.SubprocessError) as exc:
        print("STOP:",exc,file=sys.stderr)
        sys.exit(1)
