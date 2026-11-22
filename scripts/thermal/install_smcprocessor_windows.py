#!/usr/bin/env python3
"""Surface Laptop 4 Intel: guarded OpenCore SMCProcessor 1.3.8 install/rollback.

Windows 11 only; requires official VirtualSMC-1.3.8-RELEASE.zip and OpenCore
1.0.8 ocvalidate.exe. Does NOT alter Microsoft EFI, graphics, BigSurface or
existing kexts. Inspect is read-only; apply creates a verified full OC backup.
"""
from __future__ import annotations
import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import shutil
import subprocess
import sys
import tempfile
import zipfile

NAME = "SMCProcessor.kext"
BUNDLE = "as.vit9696.SMCProcessor"
VSMC_ID = "as.vit9696.VirtualSMC"
VERSION = "1.3.8"
INFO = "Contents/Info.plist"
EXEC = "Contents/MacOS/SMCProcessor"
MODELS = ("Surface Laptop 4",)
EXPECTED = ("Lilu.kext", "VirtualSMC.kext", "BigSurface.kext")


def check(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest_bytes(content):
    return hashlib.sha256(content).hexdigest()


def sha256(path):
    sha = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def ps(script):
    return subprocess.check_output(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], text=True, timeout=30).strip()


def verify_hardware():
    check(sys.platform == "win32", "Run from Windows 11, not macOS or WSL")
    name = ps("(Get-CimInstance Win32_ComputerSystem).Model")
    check(any(m.lower() in name.lower() for m in MODELS), "Unsupported system: " + name)
    serial = ps("Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPDeviceID -match 'VEN_8086&DEV_A0A8' } | Select-Object -ExpandProperty PNPDeviceID")
    check("VEN_8086&DEV_A0A8" in serial.upper(), "SL4 Intel 8086:A0A8 UART not found")


def check_macho(blob):
    # MH_MAGIC_64 x86_64 or universal Mach-O (x86_64 slice checked by OC at boot).
    return (len(blob) > 128 and (blob[:8] == bytes.fromhex("cffaedfe07000001") or blob[:4] in (b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca")))


def parse_official_zip(path):
    """No extraction to ESP. Accept only exact expected bundles in the archive."""
    check(path.is_file() and zipfile.is_zipfile(path), "Official VirtualSMC release ZIP missing/invalid: " + str(path))
    bundles = {NAME: {}, "VirtualSMC.kext": {}}
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        check(len(members) < 5000 and sum(x.file_size for x in members) < 180 * 1024 * 1024, "Unreasonable ZIP size")
        for member in members:
            raw = member.filename.replace("\\", "/")
            parts = PurePosixPath(raw).parts
            check(not raw.startswith("/") and ".." not in parts, "Unsafe ZIP entry: " + raw)
            if member.is_dir():
                continue
            check(member.file_size < 30 * 1024 * 1024, "Overlarge ZIP entry")
            check((member.external_attr >> 16) & 0o170000 != 0o120000, "ZIP symlink forbidden: " + raw)
            for bundle in bundles:
                if bundle not in parts:
                    continue
                idx = parts.index(bundle)
                rel = "/".join(parts[idx+1:])
                check(rel.startswith("Contents/") and rel not in bundles[bundle], "Invalid or duplicate kext file: " + raw)
                bundles[bundle][rel] = archive.read(member)
        for name, expected_id in [(NAME, BUNDLE), ("VirtualSMC.kext", VSMC_ID)]:
            d = bundles[name]
            check(INFO in d, "Release missing " + name + " Info.plist")
            info = plistlib.loads(d[INFO])
            check(info.get("CFBundleIdentifier") == expected_id and info.get("CFBundleVersion") == VERSION,
                  "Incorrect release identifier/version: " + name)
            exe = "Contents/MacOS/" + info.get("CFBundleExecutable", "")
            check(exe in d and check_macho(d[exe]), "Expected x86_64 binary missing: " + name)
        deps = plistlib.loads(bundles[NAME][INFO]).get("OSBundleLibraries", {})
        check("as.vit9696.VirtualSMC" in deps and "as.vit9696.Lilu" in deps, "Release plugin dependencies missing")
    return bundles[NAME]


def inspect_efi(efi, artifact):
    check(efi.name.upper() == "EFI" and efi.is_dir(), "--efi must be mounted S:\\EFI")
    check((efi/"Microsoft/Boot/bootmgfw.efi").is_file(), "Windows Boot Manager missing: not the expected internal ESP")
    oc = efi/"OC"
    cfgpath = oc/"config.plist"
    check(cfgpath.is_file() and (oc/"OpenCore.efi").is_file(), "OpenCore files missing")
    cfg = plistlib.loads(cfgpath.read_bytes())
    entries = cfg.get("Kernel", {}).get("Add", [])
    check(isinstance(entries, list), "Kernel/Add missing")
    for bundle in EXPECTED:
        matches = [(i, item) for i,item in enumerate(entries) if item.get("BundlePath")==bundle]
        check(len(matches)==1 and matches[0][1].get("Enabled") is True, "Expected loaded kext not enabled: " + bundle)
    lilu = next(i for i,x in enumerate(entries) if x["BundlePath"]=="Lilu.kext")
    vsmc = next(i for i,x in enumerate(entries) if x["BundlePath"]=="VirtualSMC.kext")
    check(lilu < vsmc, "Lilu must precede VirtualSMC")
    check(not any(NAME in x.get("BundlePath", "") for x in entries), "SMCProcessor entry already present: manual review required")
    check(not (oc/"Kexts"/NAME).exists(), "Existing SMCProcessor directory: refusing overwrite")
    vsmc_meta = plistlib.loads((oc/"Kexts/VirtualSMC.kext"/INFO).read_bytes())
    check(vsmc_meta.get("CFBundleIdentifier")==VSMC_ID and vsmc_meta.get("CFBundleVersion")==VERSION,
          "Installed VirtualSMC is not the expected 1.3.8 release")
    copy_cfg = copy.deepcopy(cfg)
    entry = {"Arch":"Any", "BundlePath":NAME, "Comment":"Surface Laptop 4 Intel CPU die sensor", "Enabled":True,
             "ExecutablePath":EXEC, "MaxKernel":"", "MinKernel":"", "PlistPath":INFO}
    copy_cfg["Kernel"]["Add"].insert(vsmc+1, entry)
    check(all(x==y for x,y in zip(entries[:vsmc+1], copy_cfg["Kernel"]["Add"][:vsmc+1])), "Existing kext entries changed")
    return oc, cfgpath, cfg, copy_cfg


def ensure_backup_location(oc, target):
    check(str(target).lower().startswith("c:\\"), "Backups must be on Windows C:, not EFI")
    check(os.path.normcase(str(oc.resolve())) not in os.path.normcase(str(target.resolve())), "Backup overlaps EFI")


def guarded_apply(efi, archive, backup_dir, validator, ack):
    check(ack == "INSTALL-SMC-SENSOR", "Apply requires --ack INSTALL-SMC-SENSOR")
    oc, cfgpath, current, updated = inspect_efi(efi, archive)
    plugin = parse_official_zip(archive)
    check(validator.is_file() and validator.name.lower()=="ocvalidate.exe", "OpenCore 1.0.8 ocvalidate.exe is required")
    ensure_backup_location(oc, backup_dir)
    required_bytes = sum(len(x) for x in plugin.values())
    check(shutil.disk_usage(oc).free > required_bytes + 16 * 1024 * 1024, "ESP free space insufficient")
    backup_dir.mkdir(parents=True, exist_ok=True)
    saved = backup_dir/("SL4-SMC-"+dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    check(not saved.exists(), "Backup path collision")
    shutil.copytree(oc, saved/"OC")
    pre_hash = sha256(cfgpath)
    check(sha256(saved/"OC/config.plist")==pre_hash, "OC backup config hash mismatch")
    print("VERIFIED FULL OC BACKUP:", saved)
    plugin_target = oc/"Kexts"/NAME
    staged = None
    try:
        plugin_target.mkdir()
        for rel, data in plugin.items():
            path = plugin_target.joinpath(*PurePosixPath(rel).parts)
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data)
            check(sha256(path)==digest_bytes(data), "Plugin copy failed verification: " + rel)
        with tempfile.NamedTemporaryFile(dir=oc, prefix=".sl4-smc-", suffix=".plist", delete=False) as fd:
            staged = Path(fd.name)
            fd.write(plistlib.dumps(updated, sort_keys=False))
        validated = subprocess.run([str(validator),str(staged)],capture_output=True,text=True,timeout=40)
        print(validated.stdout.strip(), validated.stderr.strip())
        check(validated.returncode==0, "ocvalidate rejected staged Kernel/Add")
        check(sha256(cfgpath)==pre_hash, "Another process changed config during staging")
        os.replace(staged,cfgpath)
        manifest = {"pre_config":pre_hash,"post_config":sha256(cfgpath),
                    "plugin_info":sha256(plugin_target/INFO),"plugin_exe":sha256(plugin_target/EXEC),
                    "archive":sha256(archive),"backup":str(saved),"scope":"SMCProcessor.kext only"}
        (saved/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        print("STAGED AND VALIDATED: SMCProcessor 1.3.8 enabled after VirtualSMC")
        print("COMPLETE ROLLBACK BACKUP:", saved)
        print("Reboot macOS; check kmutil for SMCProcessor and TC0D with sl4_thermal_guard.py --probe")
    except BaseException:
        print("INSTALL ERROR: restoring original config and deleting ONLY newly staged SMCProcessor")
        shutil.copy2(saved/"OC/config.plist", cfgpath)
        if plugin_target.exists():
            shutil.rmtree(plugin_target)
        raise
    finally:
        if staged and staged.exists():
            staged.unlink()


def guarded_restore(efi, backup, ack):
    check(ack == "RESTORE-SMC-SENSOR", "Restore requires --ack RESTORE-SMC-SENSOR")
    check(efi.name.upper()=="EFI" and (efi/"Microsoft/Boot/bootmgfw.efi").is_file(), "Not internal EFI")
    oc = efi/"OC"
    manifest_file = backup/"manifest.json"
    check(manifest_file.is_file() and (backup/"OC/config.plist").is_file(), "Backup manifest/config missing")
    m = json.loads(manifest_file.read_text(encoding="utf-8"))
    current_cfg = oc/"config.plist"
    target = oc/"Kexts"/NAME
    check(sha256(current_cfg)==m.get("post_config"), "Current config changed since installation: refuse destructive restore")
    check(target.is_dir() and sha256(target/INFO)==m.get("plugin_info") and sha256(target/EXEC)==m.get("plugin_exe"),
          "SMCProcessor directory differs: refuse restore")
    check(sha256(backup/"OC/config.plist")==m.get("pre_config"), "Backup config damaged")
    shutil.copy2(backup/"OC/config.plist",current_cfg)
    check(sha256(current_cfg)==m["pre_config"], "Cannot verify restored config")
    shutil.rmtree(target)
    print("RESTORED prior config and removed only SMCProcessor; Microsoft EFI/BigSurface/Metal unchanged")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode",choices=("inspect","apply","restore"),default="inspect")
    p.add_argument("--efi",type=Path,required=True)
    p.add_argument("--archive",type=Path)
    p.add_argument("--backup-dir",type=Path)
    p.add_argument("--backup",type=Path)
    p.add_argument("--ocvalidate",type=Path)
    p.add_argument("--ack",default="")
    args=p.parse_args()
    verify_hardware()
    efi=Path(os.path.abspath(str(args.efi)))
    if args.mode=="restore":
        check(args.backup is not None, "--backup required")
        guarded_restore(efi, args.backup, args.ack)
    else:
        check(args.archive is not None, "--archive required")
        archive=Path(os.path.abspath(str(args.archive)))
        oc,cfgpath,original,updated=inspect_efi(efi,archive)
        plugin=parse_official_zip(archive)
        print("HARDWARE/EFI: Surface Laptop 4 Intel, Windows Boot Manager, VirtualSMC 1.3.8, BigSurface")
        print("OFFICIAL RELEASE:",archive,"SHA256:",sha256(archive))
        print("SMCProcessor files:",len(plugin),"Config SHA256:",sha256(cfgpath))
        print("CONFIG ACTION: add one enabled SMCProcessor.kext after VirtualSMC; NO other changes")
        if args.mode=="inspect":
            print("INSPECT PASS: internal EFI untouched")
        else:
            check(args.backup_dir is not None and args.ocvalidate is not None, "--backup-dir and --ocvalidate required")
            guarded_apply(efi,archive,args.backup_dir,args.ocvalidate,args.ack)


if __name__=="__main__":
    try:
        main()
    except (RuntimeError,OSError,ValueError,zipfile.BadZipFile,subprocess.SubprocessError,plistlib.InvalidFileException) as exc:
        print("STOP:",exc,file=sys.stderr)
        sys.exit(1)
