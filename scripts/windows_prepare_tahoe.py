#!/usr/bin/env python3
"""Prepare a personal Surface Laptop 4 macOS Tahoe installer FROM WINDOWS.

This is the Windows entry point for users starting with Windows, NOT a
postinstall tool. It creates a complete, isolated boot/recovery staging folder
with a generated *private* SMBIOS, downloads Apple Recovery from Apple using
OpenCore macrecovery, obtains the published OpenCore release and stages the
SL4 driver packages. Does not modify ANY real disk, ESP, BCD or boot order.
USB formatting is an independent, opt-in PowerShell action requiring physical
device selection and an exact typed destructive-action confirmation.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import urllib.request
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OC_URL="https://github.com/acidanthera/OpenCorePkg/releases/download/1.0.8/OpenCore-1.0.8-RELEASE.zip"
OC_SHA="2011e8b7216ecb2645d97ea710df965947edd406846e92050b9bc4190be6d27b"
RELEASE_URL="https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/releases/download/sl4-s0ix-v0.2.0-beta/SL4-S0ix-DMC-0.2.0-beta.zip"
RELEASE_SHA="dd793ab5ce18079ae75484daae8a37766ccd466b181f40df79df74bdf34f30dd"
RCS_URL="https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/releases/download/sl4-rcs-v0.1.0-beta/SL4-RCS-Stability-0.1.0-beta.zip"
RCS_SHA="21f3a54a9e870457128bb483cae9d5753178d30b44dfb2b70fed812904342960"
RCS_FILENAME="SL4-RCS-Stability-0.1.0-beta.zip"
DOLBY_FILENAME="SL4-Dolby-APOMac-Profiles-20261123.zip"
DOLBY_SHA="ff029e860aec93763dc5fac3032c154a82fc571deb5cc08b5a9ad005907cc013"
APOMAC_URL="https://github.com/mkroplewski/APOMac/releases/download/v0.1.0/APOMac-0.1.0.dmg"
APOMAC_FILENAME="APOMac-0.1.0.dmg"
APOMAC_SHA="525a6adef1cbad76906d620656c93d7b1da1b3c8d6189b3f12648cfb221006fd"
GRAPHICS_URL="https://github.com/b00t0x/WhateverXe-Graphics/releases/download/v0.4.4/WhateverXe-Graphics-0.4.4.pkg"
GRAPHICS_SHA="f4c2d680a7c52c33a3f038ce6945da0aa2cc044e62b935a52ea046c7c473cfec"
INPUT_SHA="446441745f6c782ddc3d3915bc3d138e9e5f046ff545feba394994810051f8b3"
BOARD="Mac-CFF7D910A743CAAF"
MLB_FOR_RECOVERY="00000000000000000"
PROFILE="surface-laptop-4-intel-i7-1185g7-13"
MARKER="PRIVATE-SMBIOS-NOT-FOR-SHARING.txt"


def require(test,message):
    if not test:raise RuntimeError(message)


def sha(file):
    h=hashlib.sha256()
    with Path(file).open("rb") as source:
        for block in iter(lambda:source.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def fetch(url,dest,expected_sha):
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.is_file() and sha(dest)==expected_sha:
        print("Verified cache:",dest.name)
        return dest
    require(not dest.exists(),"Cached artifact differs from pinned checksum: "+str(dest))
    temporary=dest.with_name(dest.name+".partial")
    require(not temporary.exists(),"Partial download exists; review/remove only this file: "+str(temporary))
    print("Downloading and verifying:",dest.name,flush=True)
    try:
        request=urllib.request.Request(url,headers={"User-Agent":"SL4-Windows-Tahoe-Preparer/1"})
        with urllib.request.urlopen(request,timeout=120) as stream,temporary.open("xb") as f:
            shutil.copyfileobj(stream,f)
        require(sha(temporary)==expected_sha,"Upstream download checksum mismatch: "+dest.name)
        os.replace(temporary,dest)
    finally:
        if temporary.exists():temporary.unlink()
    return dest


def identity_from_macserial(oc_zip):
    require(sys.platform=="win32","macserial.exe Windows identity generation only")
    with zipfile.ZipFile(oc_zip) as source:
        binary=source.read("Utilities/macserial/macserial.exe")
    import tempfile
    with tempfile.TemporaryDirectory(prefix="sl4-macserial-") as temp:
        path=Path(temp)/"macserial.exe"
        path.write_bytes(binary)
        result=subprocess.run([str(path),"--generate","--model","MacBookPro16,2","--num","1"],
                              capture_output=True,text=True,timeout=30)
        require(result.returncode==0,"Official macserial could not generate private SMBIOS")
        match=re.fullmatch(r"([A-Z0-9]{8,18})\s*\|\s*([A-Z0-9]{15,20})",
                           result.stdout.strip())
        require(match is not None,"Unexpected official macserial output format")
        rom=bytearray(secrets.token_bytes(6))
        rom[0]=(rom[0]|2)&0xfe
        return {"serial":match.group(1),"mlb":match.group(2),
                "uuid":str(uuid.uuid4()).upper(),"rom":rom.hex().upper()}


def copy_assets(stage,zip_path):
    with zipfile.ZipFile(zip_path) as archive:
        names=archive.namelist()
        prefix="SL4-S0ix-DMC-0.2.0-beta/"
        require(prefix+"install.py" in names and prefix+"MANIFEST.json" in names,
                "Published S0ix driver bundle incomplete")
        require(archive.testzip() is None,"Bad SL4 driver bundle")
    out=stage/"SL4DATA"
    out.mkdir()
    shutil.copy2(zip_path,out/zip_path.name)
    require(sha(out/zip_path.name)==RELEASE_SHA,"Copied driver bundle corrupted")
    return out


def checked_rcs_addon(path):
    """Verify the public addon before any Windows/USB stage is built."""
    require(path.is_file() and sha(path)==RCS_SHA,"Unexpected SL4 RCS addon ZIP SHA-256")
    with zipfile.ZipFile(path) as z:
        require(z.testzip() is None,"Corrupt RCS addon")
        pre="SL4-RCS-Stability-0.1.0-beta/"
        manifest=json.loads(z.read(pre+"MANIFEST.json"))
        require(manifest.get("release")=="SL4-RCS-Stability-0.1.0-beta" and
                manifest.get("no_private_efi") is True,"Unexpected RCS addon manifest")
        name="payload/WhateverXe-SL4-RCS-STABILITY.kext/Contents/MacOS/WhateverXe"
        require(manifest.get("sha256",{}).get(name)=="e50614098810302d76049788b8d0c631279f985b96d806eaed025b983f176e21",
                "Wrong tested RCS kext")
        for rel,expected in manifest["sha256"].items():
            require(not Path(rel).is_absolute() and ".." not in Path(rel).parts,
                    "Unsafe RCS archive member")
            require(hashlib.sha256(z.read(pre+rel)).hexdigest()==expected,
                    "RCS addon content differs: "+rel)
        require(pre+"install.py" in z.namelist(),"RCS postinstall helper missing")
    return path


def macrecovery_from_oc_zip(oc_zip, dest):
    with zipfile.ZipFile(oc_zip) as oc:
        blob=oc.read("Utilities/macrecovery/macrecovery.py")
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        require(dest.is_file() and dest.read_bytes()==blob,
                "Cached macrecovery script differs from official OpenCore release")
    else:
        dest.write_bytes(blob)
    return dest


def prepare(args):
    require(sys.platform=="win32" or args.fixture_mode,
            "Use Windows for preparing the installer")
    stage=args.out.expanduser().absolute()
    cache=args.cache.expanduser().absolute()
    require(not stage.exists(),"Stage folder already exists; choose another --out")
    require(stage!=cache and stage not in cache.parents and cache not in stage.parents,
            "Stage and cache directories must be separate")
    cache.mkdir(parents=True,exist_ok=True)
    oc=fetch(OC_URL,cache/"OpenCore-1.0.8-RELEASE.zip",OC_SHA)
    require(zipfile.is_zipfile(oc),"Official OpenCore ZIP not valid")
    graphics=fetch(GRAPHICS_URL,cache/"WhateverXe-Graphics-0.4.4.pkg",GRAPHICS_SHA)
    input_pack=ROOT/"packages/SL4-TGL-Input-Working-v1.zip"
    require(input_pack.is_file() and sha(input_pack)==INPUT_SHA,
            "Working Surface keyboard/trackpad package missing or differs")
    drivers=fetch(RELEASE_URL,cache/"SL4-S0ix-DMC-0.2.0-beta.zip",RELEASE_SHA)
    rcs=checked_rcs_addon(ROOT/"packages"/RCS_FILENAME)
    apomac=fetch(APOMAC_URL,cache/APOMAC_FILENAME,APOMAC_SHA)
    dolby=ROOT/"packages"/DOLBY_FILENAME
    require(dolby.is_file() and sha(dolby)==DOLBY_SHA,
            "Bundled Surface Dolby correction differs from user-tested version")
    identity=args.identity or identity_from_macserial(oc)
    require(isinstance(identity,dict) and all(x in identity for x in ("serial","mlb","uuid","rom")),
            "Missing private SMBIOS fields")
    # Refuse stage on an existing directory. No actual ESP is ever addressed.
    stage.mkdir(mode=0o700)
    try:
        private=stage/"PRIVATE"
        private.mkdir()
        (stage/MARKER).write_text("This directory contains private SMBIOS data. Do not upload the EFI folder or PRIVATE.\n")
        (private/"identity.json").write_text(json.dumps(identity,indent=2)+"\n",encoding="utf-8")
        target=stage/"personal-boot"
        cmd=[sys.executable,str(ROOT/"scripts/build_efi.py"),
             "--identity-file",str(private/"identity.json"),
             "--input-pack",str(input_pack),
             "--peripherals","--dvmt-60","--out",str(target),"--cache",str(cache)]
        if args.verbose_boot:cmd.insert(-4,"--verbose-boot")
        if args.fixture_mode:
            # Tests only, replace subprocess and monkeypatch fixtures.
            subprocess.run(cmd,check=True)
        else:
            subprocess.run(cmd,check=True,timeout=1800)
        efi=target/"EFI"
        require((efi/"OC/config.plist").is_file() and
                (efi/"BOOT/BOOTx64.efi").is_file(),"New EFI not produced")
        recovery=stage/"com.apple.recovery.boot"
        mac_script=macrecovery_from_oc_zip(oc,cache/"macrecovery.py")
        cmd=[sys.executable,str(mac_script),"-b",args.board_id,
             "-m",MLB_FOR_RECOVERY,"-os",args.os_selection,
             "-o",str(recovery),"download"]
        print("Getting original Apple macOS Recovery for Tahoe...",flush=True)
        subprocess.run(cmd,check=True,timeout=3600)
        dmgs=list(recovery.glob("*.dmg"))
        lists=list(recovery.glob("*.chunklist"))
        require(len(dmgs)==1 and len(lists)==1 and
                dmgs[0].stat().st_size>100_000_000 and
                lists[0].stat().st_size>100,
                "Apple recovery download is incomplete")
        data=copy_assets(stage,drivers)
        shutil.copy2(graphics,data/graphics.name)
        shutil.copy2(input_pack,data/input_pack.name)
        shutil.copy2(rcs,data/RCS_FILENAME)
        shutil.copy2(apomac,data/APOMAC_FILENAME)
        shutil.copy2(dolby,data/DOLBY_FILENAME)
        shutil.copy2(ROOT/"scripts/install_dolby_macos.py",data/"install_dolby_macos.py")
        shutil.copy2(ROOT/"scripts/auto_verify_first_boot_macos.py",data/"auto_verify_first_boot_macos.py")
        shutil.copy2(ROOT/"scripts/audit_rcs_gpu_resets_macos.py",data/"audit_rcs_gpu_resets_macos.py")
        shutil.copy2(ROOT/"scripts/audit_rcs_recovery_backup.py",data/"audit_rcs_recovery_backup.py")
        shutil.copy2(ROOT/"scripts/compare_macho_binary_uuids.py",data/"compare_macho_binary_uuids.py")
        shutil.copy2(ROOT/"scripts/audit_rcs_ring_patterns_macos.py",data/"audit_rcs_ring_patterns_macos.py")
        # Official matching macOS ocvalidate and one-click graphics transition.
        with zipfile.ZipFile(oc) as oc_archive:
            validator=oc_archive.read("Utilities/ocvalidate/ocvalidate")
        (data/"ocvalidate").write_bytes(validator)
        (data/"ocvalidate").chmod(0o755)
        shutil.copy2(ROOT/"scripts/enable_xe_macos.py",data/"enable_xe_macos.py")
        shutil.copy2(ROOT/"scripts/find_internal_esp.py",data/"find_internal_esp.py")
        shutil.copy2(ROOT/"scripts/install_brightness_macos.py",data/"install_brightness_macos.py")
        # Postinstall helper and scripts: portable and non-personal.
        shutil.copy2(ROOT/"scripts/QuickStart-Mac.command",data/"QuickStart-Mac.command")
        scripts=data/"drivers"
        scripts.mkdir()
        for name in ("install_audio_macos.py","install_brightness_macos.py",
                     "install_edp_keep_macos.py","install_sl4_rcs_stability.py","configure_surface_trackpad.sh",
                     "xe_acceleration.py","dvmt60.py","prepare_sl4_peripherals.py"):
            shutil.copy2(ROOT/"scripts"/name,scripts/name)
        if args.installassistant:
            f=args.installassistant.expanduser().resolve(strict=True)
            require(f.is_file() and f.suffix.lower()==".pkg" and
                    f.name=="InstallAssistant.pkg","Specify Apple's InstallAssistant.pkg")
            shutil.copy2(f,data/f.name)
        manifest={
            "schema":1,"mode":"windows_new_macos_setup","profile":PROFILE,
            "selected_os":args.os_selection,"experimental":args.experimental,
            "recovery_board":args.board_id,"recovery_source":"Apple via OpenCore macrecovery",
            "efi_path":"personal-boot/EFI","recovery_path":"com.apple.recovery.boot",
            "payload_path":"SL4DATA","private_efi":True,
            "no_disk_modified":True,"windows_untouched":True,
            "recovery_sha256":{x.name:sha(x) for x in dmgs+lists},
            "bootloader_sha256":sha(efi/"OC/OpenCore.efi"),
            "driver_release_sha256":RELEASE_SHA,
            "rcs_stability_sha256":RCS_SHA,
            "speaker_correction_sha256":DOLBY_SHA,
            "apomac_dmg_sha256":APOMAC_SHA,
            "main_graphics_path":"RCS-integrated on first Metal activation",
            "macos_audio_permission_must_be_approved_by_user":True,
            "macos_autopilot_first_boot_check":True,
            "manual_os_recovery_install_still_required":True,
            "input_kexts_sha256":INPUT_SHA,
            "graphics_installer_sha256":GRAPHICS_SHA}
        (stage/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
        print("WINDOWS PREPARE FINISHED",stage)
        print("NEXT: choose USB disk number, then QuickStart.cmd menu -> Write USB.")
        print("FIRST BOOT: In OpenCore choose macOS Base System (External) / Recovery (arrow keys + Enter).")
        print("Do not select Windows Boot Manager or an existing macOS system for the initial Recovery boot.")
        print("No Windows disk or EFI modified.")
    except BaseException:
        # Preserve private stage/partial downloads for deliberate recovery.
        print("PREPARATION INCOMPLETE; private stage preserved:",stage,file=sys.stderr)
        raise


def repair_only(args):
    """Download all public driver assets from Windows, without needing macOS."""
    require(sys.platform=="win32" or args.fixture_mode,
            "Windows is required for the repair package preparer")
    target=args.out.expanduser().absolute()
    cache=args.cache.expanduser().absolute()
    require(not target.exists(),"Repair output directory already exists")
    require(target!=cache and target not in cache.parents and cache not in target.parents,
            "Cache and repair folder must be independent")
    cache.mkdir(parents=True,exist_ok=True)
    oc=fetch(OC_URL,cache/"OpenCore-1.0.8-RELEASE.zip",OC_SHA)
    graphics=fetch(GRAPHICS_URL,cache/"WhateverXe-Graphics-0.4.4.pkg",GRAPHICS_SHA)
    drivers=fetch(RELEASE_URL,cache/"SL4-S0ix-DMC-0.2.0-beta.zip",RELEASE_SHA)
    rcs=checked_rcs_addon(ROOT/"packages"/RCS_FILENAME)
    apomac=fetch(APOMAC_URL,cache/APOMAC_FILENAME,APOMAC_SHA)
    dolby=ROOT/"packages"/DOLBY_FILENAME
    require(dolby.is_file() and sha(dolby)==DOLBY_SHA,
            "Bundled Surface Dolby correction differs from user-tested version")
    inp=ROOT/"packages/SL4-TGL-Input-Working-v1.zip"
    require(inp.is_file() and sha(inp)==INPUT_SHA,"Working keyboard/trackpad package missing")
    out=target/"SL4DATA"
    out.mkdir(parents=True,mode=0o700)
    try:
        shutil.copy2(graphics,out/graphics.name)
        shutil.copy2(drivers,out/drivers.name)
        shutil.copy2(inp,out/inp.name)
        shutil.copy2(rcs,out/RCS_FILENAME)
        shutil.copy2(apomac,out/APOMAC_FILENAME)
        shutil.copy2(dolby,out/DOLBY_FILENAME)
        files=("QuickStart-Mac.command","enable_xe_macos.py","find_internal_esp.py",
               "install_sl4_rcs_stability.py","install_dolby_macos.py",
               "auto_verify_first_boot_macos.py",
               "audit_rcs_gpu_resets_macos.py",
               "audit_rcs_recovery_backup.py",
               "compare_macho_binary_uuids.py",
               "audit_rcs_ring_patterns_macos.py",
               "install_brightness_macos.py","install_audio_macos.py",
               "install_edp_keep_macos.py","configure_surface_trackpad.sh")
        for name in files:
            shutil.copy2(ROOT/"scripts"/name,out/name)
        with zipfile.ZipFile(oc) as archive:
            validator=archive.read("Utilities/ocvalidate/ocvalidate")
        (out/"ocvalidate").write_bytes(validator)
        (out/"ocvalidate").chmod(0o755)
        manifest={"format":1,"mode":"existing_tahoe_driver_repair",
                  "downloads":{"graphics":GRAPHICS_SHA,"dmc_s0ix":RELEASE_SHA,
                               "native_input":INPUT_SHA,"rcs_stability":RCS_SHA,
                               "speaker_correction":DOLBY_SHA,"apomac_dmg":APOMAC_SHA},
                  "windows_disk_modified":False,
                  "requires_mac_host_validation":True}
        (target/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        print("EXISTING TAHOE DRIVER REPAIR READY:",out)
        print("Copy SL4DATA to a removable drive or macOS Downloads; run its macOS helper.")
        print("The existing OpenCore EFI and Windows were NOT modified.")
    except BaseException:
        print("Repair stage incomplete; review the private local folder",file=sys.stderr)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--cache",type=Path,required=True)
    parser.add_argument("--repair-only",action="store_true",help="Windows: download all supported Tahoe driver repair files")
    parser.add_argument("--os-selection",choices=["latest","default"],default="latest",
                        help="Apple Recovery selection; latest recommended for Tahoe")
    parser.add_argument("--board-id",default=BOARD)
    parser.add_argument("--verbose-boot",action="store_true")
    parser.add_argument("--experimental",action="store_true",
                        help="Allow explicitly requested alternate recovery identity or hardware")
    parser.add_argument("--installassistant",type=Path)
    parser.add_argument("--fixture-mode",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--identity",type=json.loads,help=argparse.SUPPRESS)
    args=parser.parse_args()
    require(args.experimental or args.board_id==BOARD,
            "Different recovery board requires --experimental")
    if args.repair_only:
        repair_only(args)
    else:
        prepare(args)


if __name__=="__main__":
    try:main()
    except Exception as e:
        print("STOP:",e,file=sys.stderr)
        sys.exit(1)
