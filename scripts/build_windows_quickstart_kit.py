#!/usr/bin/env python3
"""Build a standalone Windows-first Surface Laptop 4 Tahoe Quick Start ZIP.

Public files only; Apple Recovery and upstream binaries are downloaded by
the Windows wizard directly from their publishers. Personal SMBIOS and EFI
are created exclusively on the user's Windows machine.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUTDIR="SL4-Tahoe-QuickStart"
FILES=(
 "QuickStart.cmd",
 "README.md",
 "docs/QUICKSTART.md",
 "docs/QUICKSTART-S0IX.md",
 "docs/INTERNAL-BOOT.md",
 "docs/SAFETY.md",
 "docs/DRIVERS.md",
 "docs/UNIVERSAL-SETUP.md",
 "docs/INPUT-KEYBOARD-TRACKPAD.md",
 "docs/VALIDATED-METAL-SL4.md",
 "data/seed.lzma.b64",
 "data/sl4_profiles.json",
 "packages/SL4-TGL-Input-Working-v1.zip",
 "packages/SL4-WEX-0.8.3-EDP-KeepSoftSleep.zip",
 "experiments/sl4-input/build-bigsurface-sl4.py",
 "scripts/build_sl4_input_pack.py",
 "scripts/build_efi.py",
 "scripts/dvmt60.py",
 "scripts/quiet_boot.py",
 "scripts/prepare_sl4_peripherals.py",
 "scripts/enable_xe_macos.py",
 "scripts/xe_acceleration.py",
 "scripts/windows_prepare_tahoe.py",
 "scripts/QuickStart-Windows.ps1",
 "scripts/QuickStart-Mac.command",
 "scripts/Start-SL4.ps1",
 "scripts/stage_internal_efi.ps1",
 "scripts/sl4_inventory.py",
 "scripts/sl4_setup.py",
 "scripts/install_audio_macos.py",
 "scripts/install_brightness_macos.py",
 "scripts/install_edp_keep_macos.py",
 "scripts/configure_surface_trackpad.sh",
)
PRIVATE_TOKENS=("SystemSerialNumber","private-eFi-OC","bootmgfw.efi")
INPUT_SHA="446441745f6c782ddc3d3915bc3d138e9e5f046ff545feba394994810051f8b3"

def sha(contents):
    return hashlib.sha256(contents).hexdigest()

def build(out):
    if out.exists():raise RuntimeError("Output already exists; refusing overwrite")
    files={}
    for name in FILES:
        src=ROOT/name
        if not src.is_file() or src.is_symlink():
            raise RuntimeError("Missing public source: "+name)
        if name.startswith("EFI/") or name.endswith("config.plist"):
            raise RuntimeError("Personal OpenCore file cannot be bundled")
        files[name]=src.read_bytes()
    if sha(files["packages/SL4-TGL-Input-Working-v1.zip"])!=INPUT_SHA:
        raise RuntimeError("Working Surface input driver ZIP SHA-256 changed")
    manifest={"format":1,"distribution":"Windows-first Tahoe installation toolkit",
              "private_efi_included":False,"installer_image_included":False,
              "mode":"downloads official Apple Recovery and builds private EFI on Windows",
              "sha256":{path:sha(content) for path,content in sorted(files.items())}}
    files["MANIFEST.json"]=(json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode()
    out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,raw in sorted(files.items()):
            info=zipfile.ZipInfo(OUTDIR+"/"+name,(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o100644<<16)
            z.writestr(info,raw)
    verify(out)
    return {"archive":str(out),"files":len(files),"bytes":out.stat().st_size,
            "sha256":sha(out.read_bytes())}

def verify(path):
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:raise RuntimeError("Corrupt ZIP")
        top=OUTDIR+"/"
        manifest=json.loads(z.read(top+"MANIFEST.json"))
        if manifest.get("private_efi_included") is not False:
            raise RuntimeError("Private EFI flag invalid")
        expected=set(manifest["sha256"])
        if {p[len(top):] for p in z.namelist()} != expected | {"MANIFEST.json"}:
            raise RuntimeError("ZIP member mismatch")
        for name,want in manifest["sha256"].items():
            if name.startswith("/") or ".." in Path(name).parts:
                raise RuntimeError("Unsafe archive path "+name)
            if sha(z.read(top+name))!=want:raise RuntimeError("Checksum mismatch: "+name)
        return len(expected)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--verify-only",action="store_true")
    args=p.parse_args()
    print(json.dumps({"verified_files":verify(args.out)} if args.verify_only
                     else build(args.out),indent=2))

if __name__=="__main__":main()
