#!/usr/bin/env python3
"""Switch a known-working Surface Laptop 4 EFI to a quiet OpenCore boot picker.

Only modifies EFI/OC/config.plist after backing up. Does not edit bootloaders,
ACPI, kexts, partitions, BCD, UEFI boot entries, or personal SMBIOS values.
"""
import argparse
import hashlib
import os
import pathlib
import plistlib
import subprocess
import sys
import tempfile
from datetime import datetime

GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
DEBUG_ARGS = {"-v", "keepsyms=1", "debug=0x100"}


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def edit(cfg):
    changes = []
    boot = cfg["Misc"]["Boot"]
    debug = cfg["Misc"]["Debug"]
    sec = cfg["Misc"]["Security"]
    nvram = cfg["NVRAM"]["Add"][GUID]
    need(cfg["UEFI"]["Quirks"]["RequestBootVarRouting"] is True, "RequestBootVarRouting must remain enabled")
    need(any(x.get("Enabled") and x.get("Path") == "SSDT-RTC0-SL4.aml" for x in cfg["ACPI"]["Add"]),
         "Working Surface RTC0 ACPI entry missing")
    need(sec.get("ScanPolicy") == 0, "ScanPolicy differs from working configuration")
    for obj, key, value in (
        (boot, "ShowPicker", True),
        (boot, "PickerMode", "Builtin"),
        (boot, "Timeout", 4),
        (boot, "HideAuxiliary", True),
        (sec, "AllowSetDefault", True),
        (debug, "Target", 0),
        (debug, "AppleDebug", False),
        (debug, "ApplePanic", False),
        (debug, "DisplayLevel", 0),
    ):
        if obj[key] != value:
            changes.append("%s: %r -> %r" % (key, obj[key], value))
            obj[key] = value
    oldargs = nvram.get("boot-args", "")
    need(isinstance(oldargs, str), "boot-args is not text")
    newargs = " ".join(x for x in oldargs.split() if x not in DEBUG_ARGS)
    if newargs != oldargs:
        changes.append("boot-args: diagnostic flags removed (all graphics, NVMe and USB flags kept)")
        nvram["boot-args"] = newargs
    return changes


def main():
    p = argparse.ArgumentParser(description="Quiet Surface Laptop 4 OpenCore")
    p.add_argument("--mode", choices=("inspect", "apply", "restore"), required=True)
    p.add_argument("--efi", type=pathlib.Path, required=True, help="Path to existing working EFI folder, e.g. D:\\EFI")
    p.add_argument("--backup-dir", type=pathlib.Path, help="For apply: directory on Windows C:, outside EFI")
    p.add_argument("--backup", type=pathlib.Path, help="For restore: backup config.plist")
    p.add_argument("--ocvalidate", type=pathlib.Path, help="Matching OpenCore 1.0.8 ocvalidate.exe")
    args = p.parse_args()
    # On Windows, mountvol /S exposes ESP via an unusual volume mount point.
    # pathlib.resolve(strict=True) can raise WinError 3 on this mount even when
    # ordinary file I/O works. Use a lexical absolute path and check files below.
    root = pathlib.Path(os.path.abspath(os.fspath(args.efi)))
    need(root.name.upper() == "EFI", "--efi must be an EFI folder")
    need(root.is_dir(), "EFI folder is not accessible: " + str(root))
    plist = root / "OC" / "config.plist"
    need(plist.is_file() and (root / "OC/OpenCore.efi").is_file(), "OpenCore EFI missing")
    need((root / "OC/ACPI/SSDT-RTC0-SL4.aml").is_file(), "Surface RTC0 SSDT not found")
    before = plist.read_bytes()
    cfg = plistlib.loads(before)
    if args.mode == "restore":
        need(args.backup is not None, "--backup needed for restore")
        src = args.backup.resolve(strict=True)
        need(src.is_file() and src.name == "config.plist" and src != plist, "Invalid backup path")
        after = src.read_bytes()
        plistlib.loads(after)
        print("Current SHA256:", sha(before))
        print("Backup SHA256: ", sha(after))
        need(input("Type RESTORE-SL4-PICKER: ") == "RESTORE-SL4-PICKER", "Not confirmed")
    else:
        changes = edit(cfg)
        after = plistlib.dumps(cfg, sort_keys=False)
        print("Current SHA256:", sha(before))
        print("Quiet SHA256:  ", sha(after))
        for change in changes:
            print("CHANGE:", change)
        if args.mode == "inspect":
            print("INSPECT OK: no changes")
            return
        if not changes:
            print("Already in quiet profile: nothing changed")
            return
        need(args.backup_dir is not None, "--backup-dir on a different disk is required")
        backup_dir = args.backup_dir.expanduser().resolve()
        need(backup_dir != root and root not in backup_dir.parents, "Backup must not be inside EFI")
        backup_dir.mkdir(parents=True, exist_ok=True)
        need(input("Type APPLY-SL4-QUIET: ") == "APPLY-SL4-QUIET", "Not confirmed")

    handle, name = tempfile.mkstemp(prefix=".oc-quiet-", suffix=".plist", dir=plist.parent)
    os.close(handle)
    temp = pathlib.Path(name)
    try:
        temp.write_bytes(after)
        plistlib.loads(temp.read_bytes())
        if args.ocvalidate:
            v = args.ocvalidate.resolve(strict=True)
            result = subprocess.run([str(v), str(temp)], capture_output=True, text=True)
            print(result.stdout, result.stderr)
            need(result.returncode == 0, "OpenCore ocvalidate rejected the new config")
        elif args.mode == "apply":
            print("WARNING: ocvalidate not supplied (recommended version: OpenCore 1.0.8)")
        need(plist.read_bytes() == before, "EFI changed during verification")
        if args.mode == "apply":
            backup = backup_dir / ("SL4-OC-before-quiet-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
            backup.mkdir(exist_ok=False)
            file = backup / "config.plist"
            file.write_bytes(before)
            need(file.read_bytes() == before, "Backup verification failed")
            print("VERIFIED private backup:", file)
        os.replace(temp, plist)
        need(plist.read_bytes() == after, "Written config differs from verified config")
        print("SUCCESS: config.plist only, SHA256", sha(after))
        print("EFI drivers/ACPI, Windows Boot Manager, partitions and boot order unchanged.")
    finally:
        if temp.exists():
            temp.unlink()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("STOP:", exc, file=sys.stderr)
        sys.exit(1)
