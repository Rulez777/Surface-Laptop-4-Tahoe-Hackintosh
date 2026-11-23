#!/usr/bin/env python3
"""Read-only EFI recovery archive integrity and structural readiness check.

Never opens, mounts or writes the actual EFI partition. Archive paths and
boot-args/SMBIOS/serial values are not included in output. NOT a boot test.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import plistlib
import stat
import sys
from zipfile import BadZipFile, ZipFile

MAX_MEMBERS = 6000
MAX_UNCOMPRESSED = 3 * 1024**3
MAX_MEMBER = 650 * 1024**2
MAX_CONFIG = 1024 * 1024
REQUIRED = (
    "EFI/Boot/bootx64.efi",
    "EFI/OC/OpenCore.efi",
    "EFI/OC/config.plist",
    "EFI/Microsoft/Boot/bootmgfw.efi",
)


def has_archive_member(paths: set[str], entry: str) -> bool:
    # Case-insensitive lookup reflects the FAT filesystem, while rejects
    # duplicate aliases below prevent ambiguous extraction.
    return entry.lower() in paths


def checked_config(z: ZipFile):
    raw = z.read("EFI/OC/config.plist")
    if len(raw) > MAX_CONFIG:
        raise ValueError("OpenCore config exceeds size limit")
    config = plistlib.loads(raw)
    if not isinstance(config, dict):
        raise ValueError("OpenCore configuration is not a dictionary")
    return config


def referenced_enabled(config, group: str):
    if group == "Kernel":
        entries = config["Kernel"]["Add"]
        field = "BundlePath"
        prefix = "EFI/OC/Kexts/"
        suffix = "/Contents/Info.plist"
    elif group == "ACPI":
        entries = config["ACPI"]["Add"]
        field = "Path"
        prefix = "EFI/OC/ACPI/"
        suffix = ""
    elif group == "UEFI":
        entries = config["UEFI"]["Drivers"]
        field = "Path"
        prefix = "EFI/OC/Drivers/"
        suffix = ""
    else:
        raise ValueError("Invalid OpenCore group")
    if not isinstance(entries, list) or len(entries) > 200:
        raise ValueError("Unexpected OpenCore entry list")
    result = []
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("Unexpected OpenCore list member")
        if item.get("Enabled", True) is not True:
            continue
        name = item.get(field)
        if not isinstance(name, str) or not name:
            raise ValueError("OpenCore entry has no valid filename")
        entry = PurePosixPath(name)
        if entry.is_absolute() or ".." in entry.parts or "\\" in name:
            raise ValueError("Unsafe path in OpenCore configuration")
        result.append(prefix + name + suffix)
    return result


def inspect_archive(archive: Path) -> dict:
    if archive.is_symlink() or not archive.is_file():
        raise ValueError("Archive must be a regular local file, not a symlink")
    if archive.stat().st_size > 1024 * 1024**2:
        raise ValueError("Recovery ZIP exceeds input limit")
    with ZipFile(archive) as z:
        members = z.infolist()
        if not 4 <= len(members) <= MAX_MEMBERS:
            raise ValueError("Invalid number of recovery ZIP members")
        paths = set()
        size = 0
        for m in members:
            n = m.filename
            path = PurePosixPath(n)
            if (path.is_absolute() or ".." in path.parts or not n or
                    "\\" in n or len(n) > 340 or n.startswith("./")):
                raise ValueError("Unsafe ZIP path")
            if m.file_size > MAX_MEMBER:
                raise ValueError("Archive has an excessive member")
            size += m.file_size
            if size > MAX_UNCOMPRESSED:
                raise ValueError("Archive uncompressed size exceeds limit")
            low = n.rstrip("/").lower()
            if low in paths:
                raise ValueError("Duplicate ZIP entry ignoring FAT case")
            paths.add(low)
            kind = (m.external_attr >> 16) & 0o170000
            if kind == stat.S_IFLNK:
                raise ValueError("Symlinks not permitted in recovery archive")
        missing = [p for p in REQUIRED if not has_archive_member(paths, p)]
        if missing:
            raise ValueError("Recovery archive is missing required boot files")
        config = checked_config(z)
        enabled = {}
        for group in ("Kernel", "ACPI", "UEFI"):
            refs = referenced_enabled(config, group)
            unresolved = [p for p in refs if not has_archive_member(paths, p)]
            if unresolved:
                raise ValueError("Missing enabled OpenCore component in "+group)
            enabled[group] = len(refs)
        kernels = config["Kernel"]["Add"]
        active_rcs = any(
            x.get("Enabled") is True and
            "RCS-STABILITY" in str(x.get("BundlePath", ""))
            for x in kernels if isinstance(x, dict))
        if not z.testzip() is None:
            raise ValueError("Corrupt ZIP entry (CRC mismatch)")
        win_count = sum(x.startswith("efi/microsoft/") for x in paths)
        return {
            "status": "structure_verified_not_boot_tested",
            "archive_read_only": True,
            "efi_partition_mounted": False,
            "efi_partition_modified": False,
            "windows_partition_modified": False,
            "individual_file_crc_verified": True,
            "has_open_core_efi": True,
            "has_windows_boot_manager": True,
            "has_bootx64": True,
            "enabled_open_core_entries_resolved": enabled,
            "selected_rcs_beta": active_rcs,
            "archive_entries": len(paths),
            "windows_files_preserved": win_count,
            "bootability_verified": False,
            "safe_to_install_experimental_kernel": False,
            "scope_limit": (
                "Valid ZIP content does not prove external bootability. "
                "Independent recovery entry, installed-ESP backup, "
                "rollback procedure and physical boot test are mandatory."
            ),
        }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        print(json.dumps(inspect_archive(args.archive), indent=2, sort_keys=True))
        return 0
    except (BadZipFile, KeyError, TypeError, OSError, ValueError,
            plistlib.InvalidFileException) as err:
        # Emit a generic error, not untrusted paths or secret config contents.
        print("RCS_BACKUP_AUDIT_FAILED:", type(err).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
