#!/usr/bin/env python3
"""Explicit opt-in reference graphics and AC power beta, after successful Metal boot."""
import argparse,hashlib,json,os,plistlib,pwd,re,subprocess,sys,tempfile,zipfile
from pathlib import Path
from contextlib import contextmanager
import enable_xe_macos as base
import find_internal_esp

ARCHIVE="SL4-Reference-20261125-beta.zip"
ARCHIVE_SHA="c5c9674b9e138d9493c9dcef18f73d58d9ad06e9586364cd66eee6460267e8c1"
BIN_SHA="761bbc610fcda3d3293e8226b64528eb6a30a3b54d1bc419b09dc4a15eb253c7"
TARGET="WhateverXe-SL4-RCS-V017-TRIAL.kext"
BIN="Contents/MacOS/WhateverXe"
INFO="Contents/Info.plist"
NEW_FLAGS=("-wex-edp-wake-trace","-wex-sl4-power-limit-observe","-wex-sl4-rapl-cap")
REMOVE_FLAGS=("-wex-sl4-rcs-singleport","-wex-sl4-rcs-nativequeue-trial")
OLD_SHA={"94669172f4c2a52937b587c5eb3fdb73ff030963397aa094e575d9c4b54863d3","1d8a55f44f1d487c931a3638ef40dcb3f3f9a329984600bf0ce86b2277166bc7"}
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
    if not ok:raise RuntimeError(msg)
def run(*args):
    return subprocess.check_output([str(a) for a in args],text=True)
def bundle(path):
    require(sha(path.read_bytes())==ARCHIVE_SHA,"Reference ZIP checksum mismatch")
    with zipfile.ZipFile(path) as z:
        m=json.loads(z.read("MANIFEST.json"))
        require(m["no_private_efi"] and m["experimental"] and m["version"]=="0.8.5","Wrong manifest")
        require(set(z.namelist())==set(m["sha256"])|{"MANIFEST.json"},"Unexpected ZIP member")
        for n,h in m["sha256"].items():
            require(not Path(n).is_absolute() and ".." not in Path(n).parts and sha(z.read(n))==h,"Bad ZIP member")
        b=z.read("WhateverXe.kext/"+BIN);i=z.read("WhateverXe.kext/"+INFO)
        require(sha(b)==BIN_SHA and plistlib.loads(i)["CFBundleVersion"]=="0.8.5","Wrong reference kext")
        return b,i
def candidate(raw):
    c=plistlib.loads(raw)
    es=[e for e in c["Kernel"]["Add"] if e.get("Enabled") and "WhateverXe" in e["BundlePath"]]
    require(len(es)==1 and es[0]["BundlePath"]==TARGET,"First finish normal Quick Start graphics and internal dual boot")
    args=c["NVRAM"]["Add"][base.GUID]["boot-args"].split()
    require(all(x in args for x in ("-allow3d","-wex-sl4-tgl-dmc","-wex-sl4-heap-depth-trial")),"Missing working graphics baseline")
    require("boot-args" in c["NVRAM"]["Delete"][base.GUID],"NVRAM Delete missing")
    args=[x for x in args if x not in REMOVE_FLAGS]
    args+= [x for x in NEW_FLAGS if x not in args]
    c["NVRAM"]["Add"][base.GUID]["boot-args"]=" ".join(args)
    return plistlib.dumps(c,sort_keys=False)
def write(p,b):
    with p.open("wb") as f:f.write(b);f.flush();os.fsync(f.fileno())
    require(p.read_bytes()==b,"Readback mismatch")
@contextmanager
def mounted():
    esp=find_internal_esp.find()
    d=plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil","info","-plist",esp]))
    own=not d.get("MountPoint")
    if own:run("/usr/sbin/diskutil","mount",esp)
    try:
        d=plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil","info","-plist",esp]))
        e=Path(d["MountPoint"])/"EFI"
        require((e/"OC/config.plist").is_file() and (e/"Microsoft/Boot/bootmgfw.efi").is_file(),"Wrong internal EFI")
        yield e
    finally:
        os.sync()
        if own:run("/usr/sbin/diskutil","unmount",esp)
def ac_policy():
    s=run("/usr/bin/pmset","-g","custom").split("AC Power:")[-1]
    m=re.search(r"(?m)^\s*lowpowermode\s+([01])\s*$",s)
    require(m,"Cannot identify AC Low Power Mode")
    return int(m[1])
def power(n):run("/usr/bin/pmset","-c","lowpowermode",str(n))
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=("check","apply","rollback"));p.add_argument("--bundle",type=Path,required=True);p.add_argument("--ocvalidate",type=Path,required=True)
    a=p.parse_args()
    require(os.geteuid()==0,"Use sudo for internal ESP access")
    base.system_check()
    require("Metal Support: Metal 2" in run("/usr/sbin/system_profiler","SPDisplaysDataType"),"Working Metal 2 required")
    b,i=bundle(a.bundle)
    u=os.environ.get("SUDO_USER")
    require(u and u!="root","Run from a normal administrator login")
    home=Path(pwd.getpwnam(u).pw_dir)
    backup=home/"Documents/SL4-REFERENCE-20261125-BACKUP"
    with mounted() as e:
        cfg=e/"OC/config.plist";k=e/"OC/Kexts"/TARGET;win=e/"Microsoft/Boot/bootmgfw.efi"
        raw=cfg.read_bytes();old=k.joinpath(BIN).read_bytes();info=k.joinpath(INFO).read_bytes();wh=sha(win.read_bytes())
        run(a.ocvalidate,cfg)
        if a.action=="rollback":
            m=json.loads((backup/"state.json").read_text())
            require(sha(raw)==m["after"] and sha(old)==BIN_SHA and sha(info)==sha(i) and wh==m["windows"],"EFI changed; manual rollback required")
            new=(backup/"config.plist").read_bytes();b=(backup/"WhateverXe.bin").read_bytes();i=(backup/"Info.plist").read_bytes()
            require(sha(new)==m["before"] and sha(b)==m["old_binary"] and sha(i)==m["old_info"],"Corrupt backup")
            newpower=m["old_ac"]
        else:
            require(sha(old) in OLD_SHA,"Unrecognized active graphics binary; no overwrite")
            new=candidate(raw);newpower=1
            require(not backup.exists(),"Backup exists; resolve previous reference trial first")
        base.validate_config(new,a.ocvalidate)
        oldpower=ac_policy()
        if a.action=="check":
            print("READY: exact supported donor and previous graphics, backup and rollback required; no changes");return
        if a.action=="apply":
            backup.mkdir(mode=0o700)
            for n,v in [("config.plist",raw),("WhateverXe.bin",old),("Info.plist",info)]:write(backup/n,v)
            write(backup/"state.json",(json.dumps({"before":sha(raw),"after":sha(new),"old_binary":sha(old),"old_info":sha(info),"windows":wh,"old_ac":oldpower})+"\n").encode())
        try:
            write(k/BIN,b);write(k/INFO,i);write(cfg,new)
            run(a.ocvalidate,cfg)
            require(sha(win.read_bytes())==wh,"Windows boot file changed")
            power(newpower)
            require(ac_policy()==newpower,"AC policy not applied")
        except BaseException:
            write(k/BIN,old);write(k/INFO,info);write(cfg,raw);power(oldpower);raise
        if a.action=="rollback":
            backup.rename(backup.with_name(backup.name+"-restored-"+str(int(__import__("time").time()))))
        print("REFERENCE_"+a.action.upper()+"_VERIFIED; reboot required; Windows untouched")
if __name__=="__main__":
    try:main()
    except Exception as exc:print("STOP:",exc,file=sys.stderr);sys.exit(1)
