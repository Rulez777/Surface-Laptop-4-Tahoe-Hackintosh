#!/usr/bin/env python3
"""Install the tested Surface Laptop 4 Intel brightness fix on macOS Tahoe.

Installs or updates SSDT-PNLF.aml and its ACPI/Add Enabled flag only.
The tested WhateverXe 0.8.3 profile uses PNLF _UID 19 rather than 14.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import pwd
import shutil
import stat
import subprocess
import sys
import tempfile

PNLF = "SSDT-PNLF.aml"
KNOWN_PATH = b"_SB_PC00GFX0"
ACPI_UID14 = b"_UID\x0a\x0e"
ACPI_UID19 = b"_UID\x0a\x13"
# Original 126-byte Surface SSDT-PNLF, UID 14; no personal identifiers.
# UID 19 is derived by patch_pnlf(), with a corrected ACPI checksum.
ORIGINAL_PNLF_UID14 = bytes.fromhex(
    "535344547e000000025c535552460000504e4c460000000001000000494e544c"
    "12122520a01400155c2f035f53425f504330304746583006001044045c2f03"
    "5f53425f50433030474658305b8231504e4c46085f4849440d4150503030"
    "303200085f4349440d6261636b6c6967687400085f5549440a0e085f5354"
    "410a0b"
)


def check(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def home():
    username = os.environ.get("SUDO_USER") or pwd.getpwuid(os.getuid()).pw_name
    return Path(pwd.getpwnam(username).pw_dir)


def verify_host():
    check(sys.platform == "darwin" and os.uname().machine == "x86_64",
          "Requires Intel macOS.")
    version = subprocess.check_output(["sw_vers", "-productVersion"], text=True).strip()
    check(version.startswith("26."), "Only macOS Tahoe 26.x is supported.")
    registry = plistlib.loads(subprocess.check_output([
        "ioreg", "-p", "IOService", "-c", "IOPCIDevice", "-a"]))
    nodes = [registry]
    found = False
    while nodes:
        node = nodes.pop()
        nodes.extend(node.get("IORegistryEntryChildren", []))
        if (node.get("IORegistryEntryName") == "IGPU"
                and node.get("vendor-id", b"")[:2] == b"\x86\x80"
                and node.get("device-id", b"")[:2] == b"\x49\x9a"):
            found = True
            break
    check(found, "Expected Surface Intel Iris Xe 8086:9A49 not found.")
    acpi = subprocess.check_output(["ioreg", "-p", "IOACPIPlane", "-lw0"],
                                   text=True)
    check("MSHW0084" in acpi and "MSHW0250" in acpi,
          "Surface Laptop 4 Intel ACPI identifiers not found.")


def pnl_uid(table):
    check(len(table) == 126 and table[:4] == b"SSDT",
          "Unrecognized SSDT-PNLF build; refusing to patch.")
    check(int.from_bytes(table[4:8], "little") == len(table)
          and sum(table) % 256 == 0, "Invalid ACPI length or checksum.")
    check(KNOWN_PATH in table and b"APP0002" in table
          and b"backlight" in table and table.count(b"PNLF") >= 1,
          "Not the known Surface Laptop 4 PNLF table.")
    count14, count19 = table.count(ACPI_UID14), table.count(ACPI_UID19)
    check(count14 + count19 == 1, "Unknown or ambiguous PNLF UID.")
    return 14 if count14 else 19


def patch_pnlf(table):
    before_uid = pnl_uid(table)
    if before_uid == 19:
        return table
    updated = bytearray(table)
    pos = updated.index(ACPI_UID14) + len(ACPI_UID14) - 1
    updated[pos] = 19
    updated[9] = (updated[9] - 5) & 255
    result = bytes(updated)
    check(pnl_uid(result) == 19, "Patched ACPI table failed verification.")
    changes = [i for i, (a, b) in enumerate(zip(table, result)) if a != b]
    check(changes == [9, pos], "Unexpected changes outside checksum and UID.")
    return result


def updated_config(original, allow_missing=False):
    config = plistlib.loads(plistlib.dumps(original, sort_keys=False))
    check(config.get("PlatformInfo", {}).get("Generic", {}).get("SystemProductName")
          == "MacBookPro16,2", "Unexpected SMBIOS.")
    matches = [entry for entry in config["ACPI"]["Add"]
               if entry.get("Path") == PNLF]
    check(len(matches) <= 1, "Duplicate SSDT-PNLF ACPI entries.")
    if not matches:
        check(allow_missing, "A unique SSDT-PNLF ACPI entry is required.")
        config["ACPI"]["Add"].append({
            "Comment": "Surface Laptop 4 Intel backlight, PNLF UID 19",
            "Enabled": True, "Path": PNLF
        })
        return config, True
    was_enabled = bool(matches[0]["Enabled"])
    matches[0]["Enabled"] = True
    return config, not was_enabled


def verify_config(path, validator):
    result = subprocess.run(["plutil", "-lint", str(path)],
                            text=True, capture_output=True)
    check(result.returncode == 0, "Invalid config.plist: " + result.stdout + result.stderr)
    if validator is not None:
        check(validator.is_file(), "ocvalidate not found: " + str(validator))
        result = subprocess.run([str(validator), str(path)],
                                text=True, capture_output=True)
        check(result.returncode == 0, "ocvalidate failed: " + result.stdout + result.stderr)


def mount_esp(esp):
    info = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", esp]))
    check(info.get("Content") == "EFI", "Selected disk is not an EFI partition.")
    if not info.get("MountPoint"):
        subprocess.run(["diskutil", "mount", esp], check=True)
        info = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", esp]))
    root = Path(info.get("MountPoint") or "/nonexistent")
    check((root / "EFI/OC/OpenCore.efi").is_file(),
          "OpenCore not present on this EFI; verify --esp.")
    check((root / "EFI/Microsoft/Boot/bootmgfw.efi").is_file(),
          "Windows Boot Manager missing; stopping to avoid altering the wrong EFI.")
    return root / "EFI"


def select_validator(args):
    return args.ocvalidate


def stage_config(original, config_path, validator):
    with tempfile.TemporaryDirectory(prefix="sl4-pnlf-check-") as work:
        staged = Path(work) / "config.plist"
        staged.write_bytes(plistlib.dumps(original, sort_keys=False))
        verify_config(staged, validator)
        return staged.read_bytes()


def atomic_write(path, data):
    temporary = path.with_name("." + path.name + ".sl4-pnlf-new")
    check(not temporary.exists(), "Pending temporary file exists: " + str(temporary))
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    try:
        temporary.write_bytes(data)
        temporary.chmod(mode)
        check(temporary.read_bytes() == data, "Staged file verification failed.")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def verified_backup(efi, backup_root, oc, old_cfg, old_pnlf):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = backup_root / stamp
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copytree(oc, backup / "OC")
    check((backup / "OC/config.plist").read_bytes() == old_cfg
          and ((backup / "OC/ACPI" / PNLF).read_bytes() == old_pnlf
               if old_pnlf is not None else
               not (backup / "OC/ACPI" / PNLF).exists()),
          "Private OpenCore backup verification failed.")
    total = sum(p.stat().st_size for p in oc.rglob("*") if p.is_file())
    check(shutil.disk_usage(efi).free > total + 16 * 1024 * 1024,
          "EFI lacks space for a Windows-accessible OpenCore rollback copy.")
    esp_backup = efi / ("OC-SL4-BRIGHTNESS-BACKUP-" + stamp)
    shutil.copytree(oc, esp_backup)
    check((esp_backup / "config.plist").read_bytes() == old_cfg
          and ((esp_backup / "ACPI" / PNLF).read_bytes() == old_pnlf
               if old_pnlf is not None else
               not (esp_backup / "ACPI" / PNLF).exists()),
          "EFI OpenCore backup verification failed.")
    return backup, esp_backup


def install(args):
    check(os.geteuid() == 0, "Use sudo for apply.")
    verify_host()
    efi = mount_esp(args.esp)
    oc = efi / "OC"
    config_path, aml_path = oc / "config.plist", oc / "ACPI" / PNLF
    check(config_path.is_file(), "OpenCore config.plist is missing.")
    before_cfg = config_path.read_bytes()
    before_aml = aml_path.read_bytes() if aml_path.is_file() else None
    after_aml = patch_pnlf(before_aml if before_aml is not None
                           else ORIGINAL_PNLF_UID14)
    cfg, enable_pnlf = updated_config(plistlib.loads(before_cfg), allow_missing=True)
    after_cfg = (stage_config(cfg, config_path, select_validator(args))
                 if enable_pnlf else before_cfg)
    if not enable_pnlf:
        # Validate the existing config, without rewriting its personalized fields.
        verify_config(config_path, select_validator(args))
    if after_cfg == before_cfg and after_aml == before_aml:
        print("ALREADY CONFIGURED: PNLF UID 19 is enabled. No changes made.")
        return
    backups = home() / "Downloads/SL4-BRIGHTNESS-BACKUPS"
    backups.mkdir(parents=True, exist_ok=True)
    backup, esp_backup = verified_backup(efi, backups, oc, before_cfg, before_aml)
    record = {
        "before_config": sha(before_cfg), "after_config": sha(after_cfg),
        "before_aml": sha(before_aml) if before_aml is not None else None,
        "after_aml": sha(after_aml), "aml_existed": before_aml is not None,
        "config_changed": after_cfg != before_cfg,
        "esp_backup": str(esp_backup)
    }
    (backup / "manifest.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    try:
        check(config_path.read_bytes() == before_cfg
              and (aml_path.read_bytes() == before_aml if before_aml is not None
                   else not aml_path.exists()), "EFI files changed during backup.")
        if after_aml != before_aml:
            atomic_write(aml_path, after_aml)
        if after_cfg != before_cfg:
            atomic_write(config_path, after_cfg)
        check(sha(aml_path.read_bytes()) == record["after_aml"]
              and sha(config_path.read_bytes()) == record["after_config"],
              "Written files failed verification.")
    except BaseException:
        if before_aml is None:
            if aml_path.exists():
                aml_path.unlink()
        elif aml_path.read_bytes() != before_aml:
            atomic_write(aml_path, before_aml)
        if config_path.read_bytes() != before_cfg:
            atomic_write(config_path, before_cfg)
        raise
    (backups / "LATEST").write_text(str(backup) + "\n", encoding="utf-8")
    print("SUCCESS: persistent PNLF UID 19 and enabled OpenCore entry.")
    print("Full OpenCore backup:", backup)
    print("Windows-accessible backup:", esp_backup)
    print("Restart macOS; verify Settings > Displays > Brightness.")


def rollback(args):
    check(os.geteuid() == 0, "Use sudo for rollback.")
    backups = home() / "Downloads/SL4-BRIGHTNESS-BACKUPS"
    pointer = backups / "LATEST"
    check(pointer.is_file(), "No brightness backup found.")
    backup = Path(pointer.read_text(encoding="utf-8").strip())
    check(backup.parent == backups and (backup / "manifest.json").is_file(),
          "Unrecognized backup.")
    record = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    source_cfg = (backup / "OC/config.plist").read_bytes()
    source_aml_path = backup / "OC/ACPI" / PNLF
    source_aml = source_aml_path.read_bytes() if record["aml_existed"] else None
    check(sha(source_cfg) == record["before_config"]
          and (sha(source_aml) == record["before_aml"] if source_aml is not None
               else not source_aml_path.exists()), "Backup checksum mismatch.")
    efi = mount_esp(args.esp)
    config_path, aml_path = efi / "OC/config.plist", efi / "OC/ACPI" / PNLF
    check(sha(config_path.read_bytes()) == record["after_config"]
          and sha(aml_path.read_bytes()) == record["after_aml"],
          "Current EFI changed since the brightness installation. Manual merge required.")
    if record["config_changed"]:
        atomic_write(config_path, source_cfg)
    if source_aml is None:
        aml_path.unlink()
    elif source_aml != aml_path.read_bytes():
        atomic_write(aml_path, source_aml)
    print("ROLLBACK COMPLETE. Restart macOS to restore the previous backlight configuration.")


def inspect(args):
    verify_host()
    efi = mount_esp(args.esp)
    oc = efi / "OC"
    aml_path = oc / "ACPI" / PNLF
    before_aml = aml_path.read_bytes() if aml_path.is_file() else None
    config_path = oc / "config.plist"
    updated, enables = updated_config(plistlib.loads(config_path.read_bytes()),
                                      allow_missing=True)
    after_cfg = stage_config(updated, config_path, select_validator(args))
    source = before_aml if before_aml is not None else ORIGINAL_PNLF_UID14
    check(pnl_uid(patch_pnlf(source)) == 19, "PNLF validation failed.")
    print("INSPECT OK: PNLF UID =", pnl_uid(before_aml) if before_aml else "absent",
          "; requires UID patch =", before_aml is None or pnl_uid(before_aml) != 19,
          "; requires enable =", enables,
          "; config verified =", len(after_cfg) > 0)
    print("No files changed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "apply", "rollback"))
    parser.add_argument("--esp", default="disk0s1",
                        help="EFI System Partition; verify via diskutil list (default: disk0s1).")
    parser.add_argument("--ocvalidate", type=Path,
                        help="Optional matching OpenCore ocvalidate binary.")
    args = parser.parse_args()
    if args.mode == "apply":
        install(args)
    elif args.mode == "rollback":
        rollback(args)
    else:
        inspect(args)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print("FAILED:", exc, file=sys.stderr)
        sys.exit(1)
