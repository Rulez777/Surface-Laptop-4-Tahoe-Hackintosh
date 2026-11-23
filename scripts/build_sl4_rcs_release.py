#!/usr/bin/env python3
"""Produce a deterministic, nonpersonal Windows-deliverable Mac RCS postinstall ZIP."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import zipfile

ROOT=Path(__file__).resolve().parents[1]
REL="SL4-RCS-Stability-0.1.0-beta"
BIN_SHA="e50614098810302d76049788b8d0c631279f985b96d806eaed025b983f176e21"
SIZE=1893968
def digest(b):return hashlib.sha256(b).hexdigest()
def require(x,msg):
    if not x:raise RuntimeError(msg)

def build(wex,validator,license_file,out):
    require(not out.exists(),"Refusing overwrite")
    binary=wex/"Contents/MacOS/WhateverXe"
    raw=bytearray(binary.read_bytes())
    require(len(raw)==SIZE and raw[:4]==bytes.fromhex("cffaedfe"),"Unexpected Mach-O size/header")
    # Only the Mach-O LC_UUID field is build-specific. Zero it in the archive to
    # make the packaged bytes deterministic; no executable instructions are changed.
    raw[1160:1176]=bytes(16)
    require(digest(raw)==BIN_SHA,"Driver's code or data differs from Surface-tested build")
    info=(wex/"Contents/Info.plist").read_bytes()
    props=plistlib.loads(info)
    require(props["CFBundleIdentifier"]=="org.b00t0x.WhateverXe" and props["CFBundleVersion"]=="0.8.3",
            "Unexpected WhateverXe identification")
    oc=validator.read_bytes()
    require(digest(oc)=="c76f907d5caad299889a2314ae68f03cd8538ad53f65a3c2c7c95ae0d0bb0b38",
            "Official OpenCore 1.0.8 validator mismatch")
    files={
        "install.py":(ROOT/"scripts/install_sl4_rcs_stability.py").read_bytes(),
        "QUICKSTART.md":(ROOT/"docs/QUICKSTART-RCS.md").read_bytes(),
        "SOURCE.patch":(ROOT/"research/wex-sl4-rcs-singleport.patch").read_bytes(),
        "LICENSES/WhateverXe-LICENSE.txt":license_file.read_bytes(),
        "payload/WhateverXe-SL4-RCS-STABILITY.kext/Contents/MacOS/WhateverXe":bytes(raw),
        "payload/WhateverXe-SL4-RCS-STABILITY.kext/Contents/Info.plist":info,
        "payload/ocvalidate":oc
    }
    require(b"SL4RCS" in files["SOURCE.patch"] and b"-wex-sl4-rcs-singleport" in files["SOURCE.patch"],
            "Source patch does not contain RCS mitigation")
    require(len(files["LICENSES/WhateverXe-LICENSE.txt"])>700,"Missing BSD license")
    manifest={"release":REL,"no_private_efi":True,
              "machine":"Surface Laptop 4 Intel i7-1185G7 PCI 8086:9A49",
              "macOS":"Tahoe 26.7.1","tested_gpu_reset_after_game":0,
              "synthetic_metal_command_buffers":400000,
              "game_stability_fully_verified":False,
              "rollback_required":True,
              "sha256":{name:digest(data) for name,data in sorted(files.items())}}
    files["MANIFEST.json"]=(json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode()
    out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,rawdata in sorted(files.items()):
            m=zipfile.ZipInfo(REL+"/"+name,date_time=(1980,1,1,0,0,0))
            m.compress_type=zipfile.ZIP_DEFLATED
            m.external_attr=((0o100755 if name.startswith("payload/") and
                              (name.endswith("WhateverXe") or name=="payload/ocvalidate") else 0o100644)<<16)
            z.writestr(m,rawdata)
    verify(out)
    return {"release":REL,"path":str(out),"bytes":out.stat().st_size,
            "sha256":digest(out.read_bytes()),"files":len(files)}

def verify(out):
    with zipfile.ZipFile(out) as z:
        require(z.testzip() is None,"Corrupt release ZIP")
        names=z.namelist()
        require(len(names)==8,"Incorrect release file count")
        pre=REL+"/"
        manifest=json.loads(z.read(pre+"MANIFEST.json"))
        require(manifest.get("no_private_efi") is True,"Private EFI flag invalid")
        assert {n[len(pre):] for n in names}==set(manifest["sha256"])|{"MANIFEST.json"}
        for key,h in manifest["sha256"].items():
            require(".." not in Path(key).parts and not Path(key).is_absolute(),"Unsafe path")
            require(digest(z.read(pre+key))==h,"ZIP payload mismatch: "+key)
        require(manifest["sha256"]["payload/WhateverXe-SL4-RCS-STABILITY.kext/Contents/MacOS/WhateverXe"]==BIN_SHA,
                "Wrong RCS binary SHA")
    return True

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--wex",type=Path)
    p.add_argument("--ocvalidate",type=Path)
    p.add_argument("--license-wex",type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--verify-only",action="store_true")
    a=p.parse_args()
    print(json.dumps({"verified":verify(a.out)} if a.verify_only else
                     build(a.wex,a.ocvalidate,a.license_wex,a.out),indent=2))
