#!/usr/bin/env python3
"""macOS-only SMCProcessor 1.3.8 installer for Surface Laptop 4 Intel / Tahoe.

Only EFI/OC/config.plist and new EFI/OC/Kexts/SMCProcessor.kext are changed.
No modifications to existing BigSurface, VirtualSMC, graphics, Windows EFI,
partitions, NVRAM, firmware, boot order, or system kext directories.
Inspect is read-only. Apply requires full verified OC backup and ocvalidate.
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
VIRTUALSMC = "as.vit9696.VirtualSMC"
VERSION = "1.3.8"
INFO = "Contents/Info.plist"
EXE = "Contents/MacOS/SMCProcessor"
GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"


def need(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def sha_data(data):
    return hashlib.sha256(data).hexdigest()


def verify_device():
    need(sys.platform == "darwin", "Run on installed macOS Tahoe")
    acpi = subprocess.check_output(["/usr/sbin/ioreg", "-p", "IOACPIPlane", "-lw0"], text=True, timeout=30)
    need("MSHW0250" in acpi and "MSHW0084" in acpi, "Not Surface Laptop 4 Intel ACPI MSHW0250/MSHW0084")


def resolve_internal_efi():
    """Reject external/mismatched ESP; do not guess volume name."""
    data = plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil", "info", "-plist", "disk0s1"], timeout=20))
    need(data.get("DeviceIdentifier") == "disk0s1" and data.get("Internal") is True,
         "disk0s1 is not the expected internal EFI system partition")
    mount = data.get("MountPoint")
    need(isinstance(mount, str) and mount, "Internal ESP not mounted; use diskutil mount disk0s1")
    root = Path(mount).resolve()
    efi = root / "EFI"
    need((efi/"Microsoft"/"Boot"/"bootmgfw.efi").is_file(), "Windows Boot Manager not found on this ESP")
    need((efi/"OC"/"OpenCore.efi").is_file(), "OpenCore.efi missing from internal ESP")
    return efi


def parse_release(archive):
    """Extract only the expected plugin; reject duplicate paths and symlinks."""
    need(archive.is_file() and zipfile.is_zipfile(archive), "VirtualSMC 1.3.8 release ZIP unavailable")
    bundles = {NAME: {}, "VirtualSMC.kext": {}}
    with zipfile.ZipFile(archive) as z:
        info = z.infolist()
        need(len(info) < 5000 and sum(x.file_size for x in info) < 180*1024*1024, "Unreasonable archive size")
        for item in info:
            raw = item.filename.replace("\\", "/")
            parts = PurePosixPath(raw).parts
            need(not raw.startswith("/") and ".." not in parts, "Unsafe archive path")
            if item.is_dir():
                continue
            need(item.file_size < 30*1024*1024 and (item.external_attr >> 16) & 0o170000 != 0o120000,
                 "Unexpected ZIP entry type/size")
            for bundle in bundles:
                if bundle in parts:
                    idx = parts.index(bundle)
                    rel = "/".join(parts[idx+1:])
                    need(rel.startswith("Contents/") and rel not in bundles[bundle],
                         "Duplicated or unsafe kext member: " + raw)
                    bundles[bundle][rel] = z.read(item)
        for bundle, identifier in ((NAME, BUNDLE), ("VirtualSMC.kext", VIRTUALSMC)):
            files = bundles[bundle]
            need(INFO in files, "Official release bundle missing Info.plist: " + bundle)
            meta = plistlib.loads(files[INFO])
            need(meta.get("CFBundleIdentifier") == identifier and meta.get("CFBundleVersion") == VERSION,
                 "Mismatched VirtualSMC release plugin " + bundle)
            exe = "Contents/MacOS/" + meta.get("CFBundleExecutable", "")
            need(exe in files and len(files[exe]) > 128 and
                 (files[exe][:8] == bytes.fromhex("cffaedfe07000001") or
                  files[exe][:4] in (b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca")),
                 "Missing x86_64 Mach-O in " + bundle)
        deps = plistlib.loads(bundles[NAME][INFO]).get("OSBundleLibraries", {})
        need("as.vit9696.VirtualSMC" in deps and "as.vit9696.Lilu" in deps,
             "SMCProcessor dependency list incomplete")
    return bundles[NAME]


def inspect(efi, archive):
    oc = efi/"OC"
    cfgpath = oc/"config.plist"
    need(cfgpath.is_file(), "OpenCore config.plist missing")
    cfg = plistlib.loads(cfgpath.read_bytes())
    entries = cfg.get("Kernel", {}).get("Add")
    need(isinstance(entries, list), "OpenCore Kernel/Add is missing")
    for bundle in ("Lilu.kext", "VirtualSMC.kext", "BigSurface.kext"):
        items = [(index, x) for index,x in enumerate(entries) if x.get("BundlePath") == bundle]
        need(len(items) == 1 and items[0][1].get("Enabled") is True, "Required enabled kext missing: " + bundle)
    index_lilu = next(i for i,x in enumerate(entries) if x.get("BundlePath") == "Lilu.kext")
    index_vsmc = next(i for i,x in enumerate(entries) if x.get("BundlePath") == "VirtualSMC.kext")
    need(index_lilu < index_vsmc, "Unexpected Lilu / VirtualSMC order")
    need(not (oc/"Kexts"/NAME).exists() and not any(NAME in x.get("BundlePath","") for x in entries),
         "SMCProcessor already present; refusing replace")
    existing = plistlib.loads((oc/"Kexts"/"VirtualSMC.kext"/INFO).read_bytes())
    need(existing.get("CFBundleIdentifier") == VIRTUALSMC and existing.get("CFBundleVersion") == VERSION,
         "Installed VirtualSMC must be 1.3.8; existing kext will not be replaced")
    args = cfg.get("NVRAM", {}).get("Add", {}).get(GUID, {}).get("boot-args", "")
    need(isinstance(args,str) and "-igfxdvmt" in args.split() and "-wex-noaccel" not in args.split(),
         "Existing Metal 2 boot configuration differs; no changes made")
    plugin = parse_release(archive)
    updated = copy.deepcopy(cfg)
    updated["Kernel"]["Add"].insert(index_vsmc + 1, {
        "Arch":"Any", "BundlePath":NAME, "Comment":"Surface Laptop 4 Intel CPU die sensor",
        "Enabled":True, "ExecutablePath":EXE, "MaxKernel":"", "MinKernel":"", "PlistPath":INFO})
    need(len(updated["Kernel"]["Add"]) == len(entries)+1, "Unexpected Kernel/Add change")
    return oc, cfgpath, updated, plugin


def safe_backup_root(efi, root):
    path = root.resolve()
    need(efi.resolve() not in path.parents and path != efi.resolve(), "Backup must not be on EFI")
    need(path != Path("/") and not root.is_symlink(), "Unsafe backup directory")
    # A backup belongs on macOS storage. A mounted external disk is not required.
    need(str(path).startswith("/Users/") and "/Downloads/" in str(path) + "/",
         "Use a private macOS home Downloads folder for OC backups")


def apply(efi, archive, backup_root, validator, ack):
    need(ack == "INSTALL-SMC-SENSOR", "Apply requires --ack INSTALL-SMC-SENSOR")
    need(os.geteuid() == 0, "Apply requires sudo")
    need(validator.is_file() and os.access(validator, os.X_OK) and validator.name == "ocvalidate",
         "macOS OpenCore 1.0.8 ocvalidate binary required")
    oc, config, updated, files = inspect(efi, archive)
    safe_backup_root(efi, backup_root)
    need(os.access(oc, os.W_OK), "ESP mounted read-only")
    need(shutil.disk_usage(oc).free > sum(len(blob) for blob in files.values())+16*1024*1024,
         "Not enough EFI free space")
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = backup_root/("SL4-SMC-"+stamp)
    shutil.copytree(oc, backup/"OC")
    original_hash = sha256(config)
    need(sha256(backup/"OC"/"config.plist") == original_hash, "OC backup verification failed")
    # A secondary recovery plist on the existing ESP, accessible without APFS.
    rescue = efi/("SL4-SMC-ROLLBACK-"+stamp+".plist")
    need(not rescue.exists(), "Rollback config path collision")
    shutil.copy2(backup/"OC"/"config.plist", rescue)
    need(sha256(rescue) == original_hash, "EFI rollback config verification failed")
    print("VERIFIED FULL OC BACKUP:", backup/"OC")
    print("EFI ROLLBACK CONFIG:", rescue)
    target = oc/"Kexts"/NAME
    temporary = oc/"Kexts"/(".sl4-smc-stage-"+stamp)
    temp_cfg = None
    try:
        temporary.mkdir()
        for rel, data in files.items():
            dst = temporary.joinpath(*PurePosixPath(rel).parts)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            need(sha256(dst) == sha_data(data), "SMCProcessor copy verification failed")
        temporary.rename(target)
        with tempfile.NamedTemporaryFile(dir=oc, prefix=".sl4-smc-", suffix=".plist", delete=False) as fd:
            temp_cfg = Path(fd.name)
            fd.write(plistlib.dumps(updated, sort_keys=False))
        result = subprocess.run([str(validator),str(temp_cfg)], capture_output=True, text=True, timeout=40)
        print(result.stdout.strip(), result.stderr.strip())
        need(result.returncode == 0, "OpenCore 1.0.8 ocvalidate rejected config")
        need(sha256(config) == original_hash, "Live config changed during staging")
        os.replace(temp_cfg,config)
        manifest = {
            "pre": original_hash, "post":sha256(config), "backup":str(backup),
            "new_info":sha256(target/INFO), "new_exe":sha256(target/EXE),
            "archive":sha256(archive), "rescue":str(rescue), "scope":"SMCProcessor only"}
        (backup/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        print("STAGED AND VALIDATED: SMCProcessor 1.3.8 enabled; reboot and run --probe")
    except BaseException:
        print("INSTALL FAILED: restoring original config; removing only staged SMCProcessor")
        shutil.copy2(backup/"OC"/"config.plist",config)
        if target.exists():
            shutil.rmtree(target)
        if temporary.exists():
            shutil.rmtree(temporary)
        need(sha256(config)==original_hash,"Automatic rollback failed; full OC backup retained")
        raise
    finally:
        if temp_cfg and temp_cfg.exists():
            temp_cfg.unlink()


def restore(efi, backup, ack):
    need(ack == "RESTORE-SMC-SENSOR", "Restore requires --ack RESTORE-SMC-SENSOR")
    need(os.geteuid() == 0, "Restore requires sudo")
    manifest_file = backup/"manifest.json"
    need(manifest_file.is_file(), "Backup manifest missing")
    info = json.loads(manifest_file.read_text(encoding="utf-8"))
    oc = efi/"OC"
    config = oc/"config.plist"
    target = oc/"Kexts"/NAME
    need(sha256(config) == info.get("post"), "EFI config changed since install; refusing overwrite")
    need(target.is_dir() and sha256(target/INFO) == info.get("new_info") and
         sha256(target/EXE) == info.get("new_exe"), "SMCProcessor files differ; refusing deletion")
    original = backup/"OC"/"config.plist"
    need(original.is_file() and sha256(original)==info.get("pre"), "Backup config failed hash verification")
    rescue = backup.parent/("SL4-SMC-BEFORE-RESTORE-"+dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    shutil.copytree(oc,rescue/"OC")
    need(sha256(rescue/"OC"/"config.plist")==info.get("post"),"Pre-restore backup failed")
    try:
        shutil.copy2(original,config)
        need(sha256(config)==info["pre"],"Restored original config invalid")
        shutil.rmtree(target)
    except BaseException:
        shutil.copy2(rescue/"OC"/"config.plist",config)
        raise
    print("RESTORED original OpenCore config and removed ONLY SMCProcessor")
    print("Pre-restore complete OC copy:",rescue/"OC")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("inspect","apply","restore"), default="inspect")
    p.add_argument("--archive", type=Path, help="Official VirtualSMC-1.3.8-RELEASE.zip")
    p.add_argument("--ocvalidate", type=Path, help="OpenCore 1.0.8 native macOS validator")
    p.add_argument("--backup-dir", type=Path, help="Full OC backup in macOS home Downloads")
    p.add_argument("--backup", type=Path, help="Exact SL4-SMC-* folder for restore")
    p.add_argument("--ack", default="")
    options = p.parse_args()
    verify_device()
    efi = resolve_internal_efi()
    print("INTERNAL ESP:",efi)
    if options.mode == "restore":
        need(options.backup is not None, "--backup required for restore")
        restore(efi,options.backup,options.ack)
        return
    need(options.archive is not None, "--archive required")
    archive=options.archive.expanduser().resolve()
    oc, config, proposed, plugin = inspect(efi,archive)
    print("SMCProcessor 1.3.8:", len(plugin), "files; original config SHA256:",sha256(config))
    print("VirtualSMC, BigSurface and Metal 2 preserved; no Windows or EFI boot changes")
    if options.mode == "inspect":
        print("INSPECT PASS: read-only; no EFI files changed")
        return
    need(options.ocvalidate is not None and options.backup_dir is not None, "Apply requires --ocvalidate and --backup-dir")
    apply(efi,archive,options.backup_dir.expanduser(),options.ocvalidate.expanduser(),options.ack)


if __name__=="__main__":
    try:
        main()
    except (RuntimeError,OSError,ValueError,plistlib.InvalidFileException,zipfile.BadZipFile,
            subprocess.SubprocessError) as error:
        print("STOP:",error,file=sys.stderr)
        sys.exit(1)
