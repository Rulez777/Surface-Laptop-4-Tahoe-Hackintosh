#!/usr/bin/env python3
"""Copy the optional kext pack onto an internal OpenCore ESP, disabled by default.

Do not use this on the known-good Kingston rescue USB. The source pack must be
generated from a byte-identical copy of the target EFI. Never alters boot order,
Microsoft EFI/BCD or the existing enabled kernel extensions.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime
import hashlib
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

def require(ok, error):
    if not ok:
        raise RuntimeError(error)

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser(description="Stage all candidate drivers to internal OpenCore, disabled")
    p.add_argument("--internal-efi", required=True, type=Path, help="Windows internal ESP mounted as S:\\EFI")
    p.add_argument("--pack-efi", required=True, type=Path, help="SL4-Driver-Pack/optional-EFI/EFI")
    p.add_argument("--backup-dir", required=True, type=Path, help="Private folder on C: for full OC backup")
    p.add_argument("--ocvalidate", type=Path, help="OpenCore 1.0.8 ocvalidate.exe, strongly recommended")
    p.add_argument("--mode", choices=("inspect", "apply"), default="inspect")
    args = p.parse_args()
    target = Path(os.path.abspath(str(args.internal_efi)))
    pack = Path(os.path.abspath(str(args.pack_efi)))
    backup = Path(os.path.abspath(str(args.backup_dir)))
    require(target.name.upper() == "EFI" and pack.name.upper() == "EFI", "Expected EFI directories")
    require(target != pack and target.anchor.lower() != pack.anchor.lower(), "Pack must live off internal ESP")
    require(target.anchor.lower() != backup.anchor.lower(), "Backup must be off internal ESP")
    current_file, proposed_file = target / "OC/config.plist", pack / "OC/config.plist"
    require(current_file.is_file() and proposed_file.is_file(), "Missing one config.plist")
    require((target / "OC/OpenCore.efi").is_file(), "Internal OpenCore missing")
    require((target / "OC/ACPI/SSDT-RTC0-SL4.aml").is_file(), "Internal RTC0 fix missing")
    current = plistlib.loads(current_file.read_bytes())
    proposed = plistlib.loads(proposed_file.read_bytes())
    active = {x["BundlePath"]: x for x in current["Kernel"]["Add"]}
    revised = copy.deepcopy(proposed)
    new_entries = [x for x in proposed["Kernel"]["Add"] if x["BundlePath"] not in active]
    require(new_entries, "No additional drivers to stage")
    require(not any(x["Enabled"] for x in new_entries), "New kexts must all be disabled")
    revised["Kernel"]["Add"] = [x for x in proposed["Kernel"]["Add"] if x["BundlePath"] in active]
    require(revised == current, "Base EFI settings changed; regenerate pack from the exact internal EFI")
    for name, entry in active.items():
        require(entry == next(x for x in proposed["Kernel"]["Add"] if x["BundlePath"] == name), "Existing entry modified: " + name)
    # All archive candidates, including ones already registered in config.plist.
    # Do not assume an existing Kernel/Add entry implies actual kext files exist.
    candidate_names = (
        "AppleALC.kext", "AirportItlwm.kext", "IntelBluetoothFirmware.kext",
        "IntelBTPatcher.kext", "BlueToolFixup.kext", "SMCBatteryManager.kext",
        "VoodooPS2Controller.kext", "VoodooI2C.kext", "VoodooI2CHID.kext",
        "BigSurface.kext", "NVMeFix.kext", "RestrictEvents.kext",
    )
    proposed_kexts = pack / "OC/Kexts"
    missing = []
    different = []
    matched = []
    for name in candidate_names:
        entries = [x for x in proposed["Kernel"]["Add"] if x["BundlePath"] == name]
        require(len(entries) == 1, "Candidate driver missing or duplicated in packed config: " + name)
        entry = entries[0]
        source = proposed_kexts / name
        require((source / entry["PlistPath"]).is_file(), "Missing staged Info.plist: " + name)
        if entry.get("ExecutablePath"):
            require((source / entry["ExecutablePath"]).is_file(), "Missing staged executable: " + name)
        dest = target / "OC/Kexts" / name
        if not dest.exists():
            missing.append((entry, source))
        else:
            require(dest.is_dir(), "Existing kext path is not a directory: " + name)
            source_files = {str(f.relative_to(source)): digest(f) for f in source.rglob("*") if f.is_file()}
            dest_files = {str(f.relative_to(dest)): digest(f) for f in dest.rglob("*") if f.is_file()}
            if source_files == dest_files:
                matched.append(name)
            else:
                different.append(name)
    require(new_entries or missing, "No new entries or missing kext files to stage")
    total = sum(f.stat().st_size for entry, kext in missing for f in kext.rglob("*") if f.is_file())
    print("Original config SHA256:", digest(current_file))
    print("New disabled config entries:", ", ".join(x["BundlePath"] for x in new_entries) or "none")
    print("Missing kext directories to copy:", ", ".join(x[0]["BundlePath"] for x in missing) or "none")
    print("Already present and byte-identical:", ", ".join(matched) or "none")
    print("Already present with DIFFERENT bytes (PRESERVED):", ", ".join(different) or "none")
    print("Bytes to stage:", total)
    print("Unmodified existing enabled kexts:", sum(x["Enabled"] for x in current["Kernel"]["Add"]))
    if args.mode == "inspect":
        print("INSPECT OK: no files changed")
        return
    require(shutil.disk_usage(str(target)).free > total + 16 * 1024 * 1024, "Not enough free ESP space")
    require(input("Type STAGE-FULL-KEXT-PACK: ") == "STAGE-FULL-KEXT-PACK", "Not confirmed")
    backup.mkdir(parents=True, exist_ok=True)
    saved = backup / ("SL4-before-full-pack-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    saved.mkdir(exist_ok=False)
    shutil.copytree(target / "OC", saved / "OC")
    require(digest(saved / "OC/config.plist") == digest(current_file), "Backup verification failed")
    print("VERIFIED OC BACKUP:", saved)
    installed = []
    try:
        for entry, source in missing:
            dest = target / "OC/Kexts" / entry["BundlePath"]
            # Track destination BEFORE copytree, so a mid-copy failure is cleaned up.
            installed.append(dest)
            shutil.copytree(source, dest)
            for f in source.rglob("*"):
                if f.is_file():
                    dst = dest / f.relative_to(source)
                    require(dst.is_file() and digest(f) == digest(dst), "Kext copy hash mismatch: " + str(dst))
        updated = copy.deepcopy(current)
        updated["Kernel"]["Add"].extend(new_entries)
        output = plistlib.dumps(updated, sort_keys=False)
        with tempfile.NamedTemporaryFile(prefix=".sl4-peripherals-", suffix=".plist", dir=current_file.parent, delete=False) as stream:
            tmp = Path(stream.name)
            stream.write(output)
        try:
            if args.ocvalidate:
                validator = Path(os.path.abspath(str(args.ocvalidate)))
                require(validator.is_file(), "ocvalidate.exe not found")
                check = subprocess.run([str(validator), str(tmp)], capture_output=True, text=True)
                print(check.stdout, check.stderr)
                require(check.returncode == 0, "ocvalidate rejected optional kext config")
            else:
                print("WARNING: ocvalidate skipped; verify before booting")
            require(digest(current_file) == digest(saved / "OC/config.plist"), "Internal config changed during operation")
            os.replace(tmp, current_file)
            print("SUCCESS:", len(new_entries), "new DISABLED config entries;", len(missing), "missing kext folders copied")
            print("WINDOWS EFI, BOOT ORDER, KNOWN GOOD ACTIVE DRIVERS: unchanged")
            print("Rollback: restore backup OC from", saved)
        finally:
            if tmp.exists():
                tmp.unlink()
    except BaseException:
        # Roll back even if a file copy or validation fails.
        shutil.copy2(saved / "OC/config.plist", current_file)
        for dest in installed:
            shutil.rmtree(dest, ignore_errors=True)
        raise

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("STOP:", exc, file=sys.stderr)
        sys.exit(1)
