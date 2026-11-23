#!/usr/bin/env python3
"""Cross-platform fail-closed SL4 EFI workflow.

This tool NEVER writes to a live EFI System Partition, BCD, NVRAM, or disk
layout. Works from Windows/macOS with a *private local EFI directory*.
Safe actions: inspect, backup, prepare, verify-backup. Even 'prepare' creates
only an isolated recovery/staging folder, not a bootable certified install.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"data/sl4_profiles.json"
PRIVATE_MARKER="PRIVATE-EFI-NOT-FOR-GITHUB.txt"
DISALLOWED_KEXTS={"S0ixStandby.kext","VoodooI2C.kext","SMCBatteryManager.kext"}
WINDOWS_REL="Microsoft/Boot/bootmgfw.efi"


def require(ok,msg):
    if not ok: raise RuntimeError(msg)


def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as fd:
        for piece in iter(lambda:fd.read(1048576),b""): h.update(piece)
    return h.hexdigest()


def safe_tree(root):
    require(root.exists() and root.is_dir() and not root.is_symlink(),"Source EFI must be a real directory")
    for p in root.rglob("*"):
        require(not p.is_symlink(),"Symlink/reparse link not allowed in private EFI: "+str(p.relative_to(root)))
        require(p.is_file() or p.is_dir(),"Unknown entry type: "+str(p.relative_to(root)))


def source_efi(path):
    p=path.resolve(strict=True)
    require(p.name.upper()=="EFI","Source must be the directory named EFI; not an ESP root or drive root")
    require((p/"OC/config.plist").is_file() and (p/"OC/OpenCore.efi").is_file(),"No existing OpenCore configuration")
    require((p/WINDOWS_REL).is_file(),"Windows Boot Manager missing: refuse backup/staging")
    require((p/"BOOT/BOOTx64.efi").is_file(),"UEFI BOOTx64.efi missing")
    safe_tree(p/"OC")
    safe_tree(p/"BOOT")
    return p


def enabled_entries(config,group,key):
    require(isinstance(config.get(group),dict) and isinstance(config[group].get(key),list),
            "Missing "+group+"/"+key+" in OpenCore config")
    return [x for x in config[group][key] if x.get("Enabled",False)]


def inspect(efi,ocvalidate=None):
    efi=source_efi(efi)
    config=plistlib.loads((efi/"OC/config.plist").read_bytes())
    require(isinstance(config,dict),"OpenCore config is not a dictionary")
    enabled=enabled_entries(config,"Kernel","Add")
    names=[x.get("BundlePath","") for x in enabled]
    require(len(names)==len(set(names)),"Duplicate enabled kext path")
    paths=[str(x.get("BundlePath","")) for x in enabled]
    require("Lilu.kext" in paths,"Lilu.kext must be enabled")
    wex=[x for x in paths if x.lower().startswith("whateverxe")]
    if wex: require(paths.index("Lilu.kext")<paths.index(wex[0]),"WhateverXe dependency order invalid")
    issues=[]
    for x in enabled:
        name=x.get("BundlePath","")
        check=(efi/"OC/Kexts"/name/x.get("PlistPath","Contents/Info.plist"))
        if not check.is_file(): issues.append("Missing enabled kext plist: "+name)
        if x.get("ExecutablePath") and not (efi/"OC/Kexts"/name/x["ExecutablePath"]).is_file():
            issues.append("Missing enabled kext executable: "+name)
    for x in enabled_entries(config,"ACPI","Add"):
        if not (efi/"OC/ACPI"/str(x.get("Path",""))).is_file(): issues.append("Missing ACPI file: "+str(x.get("Path","")))
    for x in enabled_entries(config,"UEFI","Drivers"):
        if not (efi/"OC/Drivers"/str(x.get("Path",""))).is_file(): issues.append("Missing UEFI driver: "+str(x.get("Path","")))
    conflicting=sorted(DISALLOWED_KEXTS.intersection(set(paths)))
    if conflicting: issues.append("Review conflicting/experimental enabled kext: "+", ".join(conflicting))
    if "SSDT-DEEPIDLE.aml" in [x.get("Path") for x in enabled_entries(config,"ACPI","Add")]:
        issues.append("Experimental Deep Idle SSDT enabled; not proven safe")
    # Never emit serial, MAC address, ROM, SMBIOS, boot arguments, UUID, or config SHA.
    results={"structure":"pass" if not issues else "review_required",
             "windows_boot_manager_present":True,
             "windows_boot_manager_sha256":digest(efi/WINDOWS_REL),
             "opencore_present":True,
             "enabled_kext_bundle_names":names,
             "enabled_acpi_names":[x.get("Path","") for x in enabled_entries(config,"ACPI","Add")],
             "warnings":issues,
             "ocvalidate":"not_run",
             "private_efi_preserved":True}
    if ocvalidate:
        exe=Path(ocvalidate).resolve(strict=True)
        result=subprocess.run([str(exe),str(efi/"OC/config.plist")],capture_output=True,text=True,timeout=30)
        results["ocvalidate"]="passed" if result.returncode==0 else "failed"
        if result.returncode: issues.append("ocvalidate rejected configuration (see local command output)")
    results["safe_to_certify_boot"]=False  # validation is not boot-testing
    return results


def output_path(source,out):
    p=out.absolute()
    require(not p.exists(),"Output already exists; choose a new path to avoid overwrites")
    require(p!=source and source not in p.parents and p not in source.parents,
            "Refuse output inside/above source private EFI directory")
    require(not p.is_symlink(),"Output symlink refused")
    require(p.parent.exists() and p.parent.is_dir(),"Output parent must already exist")
    return p


def list_hashes(tree):
    return {str(f.relative_to(tree)).replace(os.sep,"/"):digest(f)
            for f in sorted(tree.rglob("*")) if f.is_file()}


def artifact_check():
    data=json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(data["schema_version"]==1,"Unsupported profile manifest")
    info=data["pinned_artifacts"]["WhateverXe-EDP-KeepSoftsleep"]
    p=ROOT/info["path"]
    require(p.is_file() and digest(p)==info["sha256"],"Pinned eDP archive checksum mismatch")
    with zipfile.ZipFile(p) as z:
        require(z.testzip() is None,"eDP archive is corrupt")
    return p,info


def backup(source,out,mode,ack):
    source=source_efi(source)
    expected="BACKUP-PRIVATE-EFI" if mode=="backup" else "PREPARE-OFFLINE-ONLY"
    require(ack==expected,"Explicit --ack "+expected+" required")
    target=output_path(source,Path(out))
    package,info=artifact_check()
    audit=inspect(source)
    require(audit["structure"]=="pass","Review existing EFI errors before preparing a copy")
    # Never create the destination in ESP, or overwrite an existing folder.
    temp=target.parent/(".sl4-private-stage-"+uuid.uuid4().hex)
    try:
        temp.mkdir(mode=0o700)
        (temp/"EFI").mkdir()
        shutil.copytree(source/"OC",temp/"EFI/OC")
        shutil.copytree(source/"BOOT",temp/"EFI/BOOT")
        # Windows BCD can be locked; copy only the stable boot manager for integrity.
        (temp/"EFI/Microsoft/Boot").mkdir(parents=True)
        shutil.copy2(source/WINDOWS_REL,temp/"EFI"/WINDOWS_REL)
        manifest={"format":1,"created":dt.datetime.now(dt.timezone.utc).isoformat(),
                  "mode":mode,"private":True,"windows_bcd_exported":False,
                  "warnings":["PRIVATE EFI: contains SMBIOS identities; NEVER upload this output.",
                              "Windows BCD was not copied; export it separately from Windows if needed.",
                              "Stage is a backup/working copy, NOT a boot-tested system image."],
                  "sha256":list_hashes(temp/"EFI")}
        if mode=="prepare":
            (temp/"postinstall").mkdir()
            shutil.copy2(package,temp/"postinstall"/package.name)
            manifest["extra_artifact_sha256"]={package.name:info["sha256"]}
            manifest["next_steps"]="Validate against current OC 1.0.8; then use individual reversible installers; no automatic ESP write"
        (temp/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
        (temp/PRIVATE_MARKER).write_text("PRIVATE EFI with personal SMBIOS: keep OFF GitHub and file-sharing services.\n",encoding="utf-8")
        require(list_hashes(source/"OC")==list_hashes(temp/"EFI/OC"),"Backup OC bytes differ")
        require(digest(source/WINDOWS_REL)==digest(temp/"EFI"/WINDOWS_REL),"Windows boot manager hash differs")
        temp.rename(target)
    except BaseException:
        if temp.exists(): shutil.rmtree(temp)
        raise
    return {"status":"created_private_local_"+mode,"path":str(target),
            "files":len(manifest["sha256"]),"windows_boot_manager_preserved":True,
            "efi_system_partition_modified":False,"requires_explicit_manual_recovery_test":True}


def verify_backup(path):
    folder=Path(path).resolve(strict=True)
    require(folder.is_dir() and (folder/PRIVATE_MARKER).is_file(),"Not an SL4 private backup")
    manifest=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    require(manifest["private"] is True and manifest["format"]==1,"Unexpected manifest")
    tree=folder/"EFI"
    safe_tree(tree)
    require(manifest["sha256"]==list_hashes(tree),"Backup files missing/modified")
    if "extra_artifact_sha256" in manifest:
        for name,sha in manifest["extra_artifact_sha256"].items():
            require(digest(folder/"postinstall"/name)==sha,"Extra ZIP checksum mismatch")
    return {"status":"backup_integrity_pass","file_count":len(manifest["sha256"]),
            "full_windows_bcd_backup":False,"not_boot_tested":True}


def restore_offline(backup_path,out,ack):
    """Recreate a private recovery copy in a NEW normal directory, never ESP."""
    require(ack=="RESTORE-OFFLINE-COPY","Explicit --ack RESTORE-OFFLINE-COPY required")
    folder=Path(backup_path).resolve(strict=True)
    verify_backup(folder)
    safe_tree(folder/"EFI")
    target=output_path(folder,Path(out))
    temp=target.parent/(".sl4-private-restore-"+uuid.uuid4().hex)
    try:
        temp.mkdir(mode=0o700)
        shutil.copytree(folder/"EFI",temp/"EFI")
        shutil.copy2(folder/"manifest.json",temp/"manifest.json")
        shutil.copy2(folder/PRIVATE_MARKER,temp/PRIVATE_MARKER)
        if (folder/"postinstall").exists():
            shutil.copytree(folder/"postinstall",temp/"postinstall")
        require(verify_backup(temp)["status"]=="backup_integrity_pass","Restored copy checksum mismatch")
        temp.rename(target)
    except BaseException:
        if temp.exists():shutil.rmtree(temp)
        raise
    return {"status":"offline_private_recovery_copy_verified","path":str(target),
            "live_efi_modified":False,"windows_bcd_restored":False,
            "boot_tested":False}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode",choices=["inspect","backup","prepare","verify-backup","verify-pins","restore-offline"])
    ap.add_argument("--source-efi",type=Path)
    ap.add_argument("--backup-path",type=Path)
    ap.add_argument("--out",type=Path)
    ap.add_argument("--ack",default="")
    ap.add_argument("--ocvalidate",type=Path)
    args=ap.parse_args(argv)
    if args.mode=="verify-pins":
        p,meta=artifact_check()
        result={"artifact":str(p.relative_to(ROOT)),"sha256":meta["sha256"],"verified":True}
    elif args.mode=="verify-backup":
        require(args.out is not None,"--out path required")
        result=verify_backup(args.out)
    elif args.mode=="restore-offline":
        require(args.backup_path is not None and args.out is not None,"--backup-path and --out required")
        result=restore_offline(args.backup_path,args.out,args.ack)
    elif args.mode=="inspect":
        require(args.source_efi is not None,"--source-efi path required")
        result=inspect(args.source_efi,args.ocvalidate)
    else:
        require(args.source_efi is not None and args.out is not None,"--source-efi and --out required")
        result=backup(args.source_efi,args.out,args.mode,args.ack)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    try:sys.exit(main())
    except (RuntimeError,OSError,ValueError,KeyError,plistlib.InvalidFileException,subprocess.SubprocessError) as err:
        print("STOP: "+str(err),file=sys.stderr)
        sys.exit(1)
