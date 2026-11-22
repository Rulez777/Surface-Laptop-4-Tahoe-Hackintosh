#!/usr/bin/env python3
"""Guarded Tiger Lake Xe acceleration transition for Surface Laptop 4.

Never installs macOS packages, changes partitions or BCD, or touches a USB
unless the user explicitly points --efi to that USB. No vendor ids or SMBIOS
identifiers are modified or logged.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile

APPLE_GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
SIP_WEX = bytes.fromhex("03080000")
CORE_KEXTS = ("Lilu.kext", "WhateverXe.kext", "AMFIAnchor.kext", "AMFIAnchorInjector.kext")
REQUIRED_ARGS = ("-allow3d", "-disablegfxfirmware")
DISABLE_FLAG = "-wex-noaccel"


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def kext_index(entries, name):
    hits = [i for i, item in enumerate(entries) if item.get("BundlePath") == name and item.get("Enabled")]
    require(len(hits) == 1, "Required enabled kext missing or duplicated: " + name)
    return hits[0]


def preflight(root, cfg):
    require((root / "OC/OpenCore.efi").is_file(), "Missing OpenCore.efi")
    require((root / "OC/ACPI/SSDT-RTC0-SL4.aml").is_file(), "Surface-specific RTC0 AML missing")
    require(any(x.get("Enabled") and x.get("Path") == "SSDT-RTC0-SL4.aml" for x in cfg["ACPI"]["Add"]), "Surface RTC0 disabled")
    require(cfg["UEFI"]["Quirks"]["RequestBootVarRouting"] is True, "Unexpected boot variable routing")
    kexts = cfg["Kernel"]["Add"]
    indices = {k: kext_index(kexts, k) for k in CORE_KEXTS}
    require(indices["Lilu.kext"] < indices["WhateverXe.kext"], "Lilu must load before WhateverXe")
    require(indices["Lilu.kext"] < indices["AMFIAnchor.kext"] < indices["AMFIAnchorInjector.kext"], "Incorrect AMFIAnchor loading order")
    require(not any(x.get("Enabled") and x.get("BundlePath") == "WhateverGreen.kext" for x in kexts), "WhateverGreen conflicts with WhateverXe")
    for name in CORE_KEXTS:
        path = root / "OC/Kexts" / name / "Contents/Info.plist"
        require(path.is_file(), "Missing required kext file: " + str(path))
    boot = cfg["NVRAM"]["Add"][APPLE_GUID].get("boot-args", "")
    require(isinstance(boot, str), "boot-args is not a string")
    nvram = cfg["NVRAM"]["Add"][APPLE_GUID]
    sip = nvram.get("csr-active-config")
    require(isinstance(sip, (bytes, bytearray)), "csr-active-config must be Data, not a string")
    return boot.split(), bytes(sip)


def write_config(root, before, after, backup_root, validator, label):
    require(backup_root is not None, "--backup-dir on C: is required for writes")
    backup_root = Path(os.path.abspath(os.fspath(backup_root)))
    require(backup_root.anchor.lower() != root.anchor.lower(), "Backups must be on a separate drive from the ESP")
    backup_root.mkdir(parents=True, exist_ok=True)
    cfg = root / "OC/config.plist"
    handle, tmp_name = tempfile.mkstemp(prefix=".sl4-xe-", suffix=".plist", dir=cfg.parent)
    os.close(handle)
    temp = Path(tmp_name)
    try:
        temp.write_bytes(after)
        plistlib.loads(temp.read_bytes())
        if validator:
            cmd = [str(validator), str(temp)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(result.stdout, result.stderr)
            require(result.returncode == 0, "ocvalidate failed; existing EFI unchanged")
        else:
            print("WARNING: ocvalidate not supplied; matching OpenCore 1.0.8 is strongly recommended.")
        require(cfg.read_bytes() == before, "config.plist changed during preparation")
        backup = backup_root / ("SL4-XE-" + label + "-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        backup.mkdir(exist_ok=False)
        backup_file = backup / "config.plist"
        backup_file.write_bytes(before)
        require(backup_file.read_bytes() == before, "Private backup failed")
        print("BACKUP:", backup_file)
        os.replace(temp, cfg)
        require(cfg.read_bytes() == after, "Written config failed verification")
        print("SUCCESS:", label, "config.plist SHA256", hashlib.sha256(after).hexdigest())
        print("Internal boot files, RTC0, Microsoft Boot Manager and partitions unchanged.")
    finally:
        if temp.exists():
            temp.unlink()


def main():
    p = argparse.ArgumentParser(description="Safely prepare/enable WhateverXe acceleration on a private EFI")
    p.add_argument("--efi", required=True, type=Path, help="Path to internal EFI, e.g. S:\\EFI")
    p.add_argument("--mode", choices=("inspect", "prepare", "enable", "restore"), default="inspect")
    p.add_argument("--backup-dir", type=Path, help="Private backups on C:")
    p.add_argument("--backup", type=Path, help="Known-good config.plist for restore")
    p.add_argument("--ocvalidate", type=Path, help="OpenCore 1.0.8 ocvalidate.exe")
    args = p.parse_args()
    root = Path(os.path.abspath(os.fspath(args.efi)))
    require(root.name.upper() == "EFI", "Expected EFI folder, not bare ESP root")
    config_path = root / "OC/config.plist"
    require(config_path.is_file(), "EFI config.plist missing: " + str(config_path))
    before = config_path.read_bytes()
    cfg = plistlib.loads(before)
    before_hash = hashlib.sha256(before).hexdigest()
    print("CONFIG SHA256:", before_hash)
    if args.mode == "restore":
        require(args.backup is not None, "--backup needed for restore")
        backed = Path(os.path.abspath(os.fspath(args.backup)))
        require(backed.is_file() and backed != config_path, "Invalid backup")
        after = backed.read_bytes()
        plistlib.loads(after)
        print("RESTORE SOURCE SHA256:", hashlib.sha256(after).hexdigest())
        require(input("Type RESTORE-XE-EFI: ") == "RESTORE-XE-EFI", "Not confirmed")
        write_config(root, before, after, args.backup_dir, args.ocvalidate, "restore")
        return
    flags, sip = preflight(root, cfg)
    print("SIP Data: 0x" + sip.hex())
    print("Graphics: ", "NO ACCEL (-wex-noaccel)" if DISABLE_FLAG in flags else "ACCEL FLAG NOT DISABLED")
    print("Required boot flags:", {a: (a in flags) for a in REQUIRED_ARGS})
    if args.mode == "inspect":
        print("INSPECT OK: no changes")
        return
    new_flags = flags[:]
    nv = cfg["NVRAM"]["Add"][APPLE_GUID]
    if args.mode == "prepare":
        require(DISABLE_FLAG in flags, "Prepare expects safe no-accel config; boot first with current EFI")
        print("NOTICE: SIP 0x803 is less restrictive than full macOS SIP; required by WhateverXe Graphics.")
        if sip != SIP_WEX:
            nv["csr-active-config"] = SIP_WEX
            print("CHANGE: csr-active-config -> Data 03080000")
        for arg in REQUIRED_ARGS:
            if arg not in new_flags:
                new_flags.append(arg)
                print("ADD boot-arg:", arg)
        print("PRESERVED: -wex-noaccel (until Graphics pkg has been installed into Tahoe)")
    else:
        require(sip == SIP_WEX, "SIP must be Data 03080000; run --mode prepare first and reboot")
        require(all(x in flags for x in REQUIRED_ARGS), "Required WEX boot arguments missing; run --mode prepare")
        require(DISABLE_FLAG in flags, "Already enabled, no -wex-noaccel flag found")
        print("CRITICAL: WhateverXe Graphics 0.4.4 must have been installed successfully in Tahoe 26.7+.")
        require(input("Type GRAPHICS-0.4.4-INSTALLED to confirm the pkg installation: ") == "GRAPHICS-0.4.4-INSTALLED", "Not confirmed")
        new_flags = [x for x in flags if x != DISABLE_FLAG]
        print("CHANGE: remove -wex-noaccel")
    nv["boot-args"] = " ".join(new_flags)
    after = plistlib.dumps(cfg, sort_keys=False)
    if before == after:
        print("ALREADY PREPARED: no write needed")
        return
    prompt = "PREPARE-XE-EFI" if args.mode == "prepare" else "ENABLE-XE-ACCEL"
    require(input("Type " + prompt + " to write internal EFI config: ") == prompt, "Not confirmed")
    write_config(root, before, after, args.backup_dir, args.ocvalidate, args.mode)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("STOP:", exc, file=sys.stderr)
        sys.exit(1)
