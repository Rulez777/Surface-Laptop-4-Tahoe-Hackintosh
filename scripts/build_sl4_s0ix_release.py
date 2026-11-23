#!/usr/bin/env python3
"""Build the public, non-personal SL4 S0ix postinstall release ZIP.

Pins every binary byte; allows a nondeterministic Mach-O UUID but requires
all executable code/data to match the physically tested Surface binary.
No EFI, bootloader, config.plist, serial, identity or Windows BCD is included.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
RELEASE="SL4-S0ix-DMC-0.2.0-beta"
OUTNAME=RELEASE+".zip"
WEX_EXPECTED="7fcbf0fdb3c2e02f68941f3644902a10b06dd7ba824164c353c96ad6080ee0ac"
S0IX_ARCHIVE_SHA="f925e780829191dd836f16e991a889f7d50b3b98217cc4ef42ccf9f7c2c2279d"
S0IX_BIN_SHA="5203911400cc595e840d712e8b5538b2ecdae798f46faed1d802904917efb8a5"
AML_SHA="477c92c60a767cde3baef858932d652a91b962f5e01cd7baf6467c544c7a46f0"
OCVAL_SHA="c76f907d5caad299889a2314ae68f03cd8538ad53f65a3c2c7c95ae0d0bb0b38"
FIRMWARE_SHA="3c013ef0ad96ba73aee8e5bd04a8e27cc9b1c6e9183b1a83ce124485f325afca"


def require(ok,reason):
    if not ok:raise RuntimeError(reason)


def hash_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wex",type=Path,required=True,help="Prebuilt WhateverXe.kext generated from pinned upstream+patches")
    p.add_argument("--s0ix",type=Path,required=True,help="Unmodified S0ixStandby 0.5.8 release ZIP")
    p.add_argument("--aml",type=Path,required=True,help="Pinned SSDT-DEEPIDLE.aml")
    p.add_argument("--ocvalidate",type=Path,required=True)
    p.add_argument("--intel-firmware",type=Path,required=True,help="Unmodified i915/tgl_dmc_ver2_12.bin")
    p.add_argument("--license-intel",type=Path,required=True)
    p.add_argument("--license-s0ix",type=Path,required=True)
    p.add_argument("--license-wex",type=Path,required=True)
    p.add_argument("--license-oc",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    require(not args.out.exists(),"Refusing to overwrite an existing release ZIP")
    bin=args.wex/"Contents/MacOS/WhateverXe"
    raw=bytearray(bin.read_bytes())
    require(len(raw)==1888640 and raw[:4]==b"\xcf\xfa\xed\xfe","Wrong WhateverXe Intel Mach-O")
    raw[1160:1176]=bytes(16)
    require(hashlib.sha256(raw).hexdigest()==WEX_EXPECTED,"Untested WhateverXe code/data")
    for path,expected,desc in ((args.s0ix,S0IX_ARCHIVE_SHA,"S0ix ZIP"),
                              (args.aml,AML_SHA,"SSDT-DEEPIDLE"),
                              (args.ocvalidate,OCVAL_SHA,"ocvalidate 1.0.8"),
                              (args.intel_firmware,FIRMWARE_SHA,"unmodified Intel firmware")):
        require(path.is_file() and hash_file(path)==expected,desc+" SHA mismatch")
    for path in (args.license_intel,args.license_s0ix,args.license_wex,args.license_oc):
        require(path.is_file() and path.stat().st_size>400,"Missing license notice: "+str(path))
    require((ROOT/"scripts/install_sl4_s0ix_release.py").is_file(),"Installer missing")
    require((ROOT/"docs/QUICKSTART-S0IX.md").is_file(),"Quick start missing")
    with tempfile.TemporaryDirectory(prefix="sl4-release-") as t:
        dest=Path(t)/RELEASE
        payload=dest/"payload"
        payload.mkdir(parents=True)
        (dest/"LICENSES").mkdir()
        shutil.copytree(args.wex,payload/"WhateverXe-SL4-S0IX-DMC.kext",symlinks=False)
        with zipfile.ZipFile(args.s0ix) as z:
            for info in z.infolist():
                if info.is_dir():continue
                path=Path(info.filename)
                require(path.parts[:1]==("S0ixStandby.kext",) and
                        ".." not in path.parts,"Unexpected release ZIP member")
                out=payload.joinpath(*path.parts)
                out.parent.mkdir(parents=True,exist_ok=True)
                out.write_bytes(z.read(info))
                if path.parts[-1]=="S0ixStandby":
                    out.chmod(0o755)
        shutil.copy2(args.aml,payload/"SSDT-DEEPIDLE.aml")
        shutil.copy2(args.ocvalidate,payload/"ocvalidate")
        (payload/"ocvalidate").chmod(0o755)
        shutil.copy2(args.intel_firmware,payload/"tgl_dmc_ver2_12.bin")
        shutil.copy2(args.license_intel,dest/"LICENSES/LICENSE.i915")
        shutil.copy2(args.license_s0ix,dest/"LICENSES/S0ixStandby-LICENSE")
        shutil.copy2(args.license_wex,dest/"LICENSES/WhateverXe-LICENSE.txt")
        shutil.copy2(args.license_oc,dest/"LICENSES/OpenCorePkg-LICENSE.txt")
        shutil.copy2(ROOT/"scripts/install_sl4_s0ix_release.py",dest/"install.py")
        shutil.copy2(ROOT/"docs/QUICKSTART-S0IX.md",dest/"QUICKSTART.md")
        # Reject any private EFI or identifiers in release asset names.
        all_files=sorted([x for x in dest.rglob("*") if x.is_file()])
        require(len(all_files)<25,"Unexpected package count")
        for f in all_files:
            relative=str(f.relative_to(dest))
            require("config.plist" not in relative and "bootmgfw" not in relative and
                    "SMBIOS" not in relative and "EFI/" not in relative,
                    "Private/system EFI file appeared in public package")
        manifest={"release":RELEASE,"supported_machine":"Surface Laptop 4 Intel i7-1185G7 8086:9A49",
                  "macOS":"26.7.1","OpenCore":"1.0.8",
                  "one_machine_rtc_wake_tests":[8,71],
                  "auto_idle_sleep_enabled_by_installer":False,
                  "clean_install":False,"tested_on_other_hardware":False,
                  "no_private_efi":True,
                  "sha256":{str(f.relative_to(dest)):hash_file(f) for f in all_files}}
        (dest/"MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n")
        args.out.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(args.out,"x",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for f in sorted(dest.rglob("*")):
                if f.is_file():
                    z.write(f,arcname=f"{RELEASE}/"+str(f.relative_to(dest)))
        with zipfile.ZipFile(args.out) as z:
            require(z.testzip() is None,"Release archive corrupt")
            names=set(z.namelist())
            prefix=f"{RELEASE}/"
            require(prefix+"install.py" in names and
                    prefix+"payload/ocvalidate" in names and
                    prefix+"MANIFEST.json" in names,"Incomplete release ZIP")
            for path,sha in manifest["sha256"].items():
                require(hashlib.sha256(z.read(prefix+path)).hexdigest()==sha,
                        "Release payload hash mismatch: "+path)
        print(json.dumps({"release":RELEASE,"asset":str(args.out),
                          "sha256":hash_file(args.out),
                          "bytes":args.out.stat().st_size,"files":len(all_files)+1,
                          "includes_private_efi":False,"supported":False if False else True},indent=2))


if __name__=="__main__":
    try:main()
    except Exception as error:
        import sys
        print("BUILD STOP:",error,file=sys.stderr)
        sys.exit(1)
