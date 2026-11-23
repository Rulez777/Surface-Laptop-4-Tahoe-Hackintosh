#!/usr/bin/env python3
"""Generate a reproducible non-secret SL4 existing-install recovery toolkit ZIP.

Offline package only. Does not generate a bootable EFI, mount ESP or install.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SELECT=[
"README.md",
"data/sl4_profiles.json",
"docs/EDP-WAKE.md",
"docs/SLEEP.md",
"docs/SYSTEM-SLEEP-RESEARCH.md",
"docs/DMC-SLEEP-TRIAL.md",
"docs/S0IX-INITIAL-RTC-WAKE-20261123.md",
"docs/POST-S0IX-GPU-RCS-RESET-20261123.md",
"docs/LINUX-SURFACE-SLEEP-PORT.md",
"docs/BATTERY.md",
"docs/POWER-RECOVERY.md",
"docs/THERMAL-TMP3.md",
"docs/UNIVERSAL-SETUP.md",
"docs/VALIDATION-20261123.md",
"docs/SAFETY.md",
"docs/DRIVERS.md",
"docs/INPUT-KEYBOARD-TRACKPAD.md",
"docs/GRAPHICS-ACCELERATION.md",
"docs/VALIDATED-METAL-SL4.md",
"docs/MEDIA.md",
"docs/VIDEO-CODECS-20261123.md",
"scripts/Start-SL4.ps1",
"scripts/build_offline_kit.py",
"research/wex-tgl-dmc-supervised.patch",
"scripts/start_sl4_macos.sh",
"scripts/sl4_setup.py",
"scripts/sl4_inventory.py",
"scripts/sl4_stability_audit_macos.py",
"scripts/audit_power_macos.py",
"scripts/compare_power_snapshots.py",
"scripts/inspect_tgl_dmc.py",
"scripts/generate_tgl_dmc_trial_header.py",
"scripts/audit_sleep_macos.py",
"scripts/dvmt60.py",
"scripts/quiet_boot.py",
"scripts/add_optional_drivers.py",
"scripts/prepare_full_driver_pack.py",
"scripts/stage_full_kext_pack.py",
"scripts/xe_acceleration.py",
"scripts/install_audio_macos.py",
"scripts/install_brightness_macos.py",
"scripts/install_edp_keep_macos.py",
"scripts/install_wex_graphics_macos.sh",
"scripts/verify_video_macos.py",
"scripts/audit_codec_macos.py",
"scripts/install_media_fallback_macos.py",
"scripts/configure_surface_trackpad.sh",
"scripts/thermal/sl4_tmp3_service.py",
"scripts/thermal/sl4_thermal_guard.py",
"scripts/thermal/sl4_thermal_test.py",
"scripts/thermal/sl4_ac_retrigger.py",
"packages/SL4-WEX-0.8.3-EDP-KeepSoftSleep.zip",
]
FORBIDDEN=("SystemUUID","SystemSerialNumber","MLB","bootmgfw.efi","config.plist","SMBIOS")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def files():
    result={}
    for item in SELECT:
        p=ROOT/item
        if not p.is_file() or p.is_symlink():
            raise RuntimeError("Required source file missing or link: "+item)
        # Do not parse binary bundles as text; no local paths outside source tree.
        data=p.read_bytes()
        if item.startswith("data/") or item.endswith(".md"):
            if item != "data/seed.lzma.b64" and b"PRIVATE-ABCDEF" in data:
                raise RuntimeError("Private example marker accidentally included: "+item)
        result[item]=data
    return result


def write_archive(destination):
    if destination.exists():raise RuntimeError("Refusing to overwrite existing ZIP")
    if not destination.parent.is_dir():raise RuntimeError("Output parent missing")
    source=files()
    manifest={"format":1,"scope":"offline existing-install toolkit, NOT certified bootable EFI",
              "private_efi_included":False,
              "full_system_sleep_verified":False,
              "windows_bcd_modified":False,
              "files":{p:sha(contents) for p,contents in sorted(source.items())}}
    source["KIT-MANIFEST.json"]=(json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode("utf-8")
    temp=destination.with_name(destination.name+".tmp")
    if temp.exists():raise RuntimeError("Temporary ZIP path exists")
    try:
        with zipfile.ZipFile(temp,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as out:
            for path,data in sorted(source.items()):
                info=zipfile.ZipInfo(path,(1980,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=(0o100644<<16)
                out.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED)
        verify_archive(temp)
        temp.rename(destination)
    finally:
        if temp.exists():temp.unlink()
    return {"output":str(destination),"sha256":sha(destination.read_bytes()),
            "files":len(source),"private_efi_included":False,"boot_tested":False}


def verify_archive(path):
    with zipfile.ZipFile(path) as f:
        if f.testzip() is not None:raise RuntimeError("Corrupt toolkit ZIP")
        manifest=json.loads(f.read("KIT-MANIFEST.json"))
        if manifest["private_efi_included"] is not False:raise RuntimeError("Private EFI manifest flag wrong")
        if set(f.namelist())!=set(manifest["files"])|{"KIT-MANIFEST.json"}:
            raise RuntimeError("Unexpected archive member")
        for name,expected in manifest["files"].items():
            if name.startswith("/") or ".." in Path(name).parts:
                raise RuntimeError("Unsafe archive path: "+name)
            if sha(f.read(name))!=expected:
                raise RuntimeError("Checksum mismatch in ZIP: "+name)
        if any(name.lower().endswith("config.plist") for name in f.namelist()):
            raise RuntimeError("Personal EFI config must not be packaged")
        return len(manifest["files"])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--verify-only",action="store_true")
    a=p.parse_args()
    result={"files_verified":verify_archive(a.out)} if a.verify_only else write_archive(a.out)
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    try:main()
    except (RuntimeError,OSError,ValueError,KeyError,zipfile.BadZipFile) as error:
        p=__import__("sys")
        print("STOP:",error,file=p.stderr)
        p.exit(1)
