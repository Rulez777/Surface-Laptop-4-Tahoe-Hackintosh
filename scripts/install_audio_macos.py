#!/usr/bin/env python3
"""Install tested Surface Laptop 4 Intel audio on macOS Tahoe.

Realtek ALC274: AppleALC layout 35 + SimpleHDA 1.0.2.
The script edits only EFI/OC and retains a full, private rollback copy.
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
import struct
import subprocess
import sys
import tempfile
import zipfile

RELEASE_URL = ("https://github.com/laobamac/SimpleHDA/releases/download/"
               "v1.0.2/SimpleHDA-Tahoe-v1.0.2-RELEASE.zip")
RELEASE_SHA256 = "4e24a54ea58bc8196c517bd415b263313512832b6e28c455b97e18490a6230f0"
ZIP_ROOT = "SimpleHDA-Tahoe-v1.0.2-RELEASE/SimpleHDA.kext/"
AUDIO_PATH = "PciRoot(0x0)/Pci(0x1F,0x3)"
AUDIO_LAYOUT = 35
KEXT = "SimpleHDA.kext"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def owner_home():
    return Path(pwd.getpwnam(os.environ.get("SUDO_USER") or pwd.getpwuid(os.getuid()).pw_name).pw_dir)


def test_host():
    require(sys.platform == "darwin", "Requires macOS.")
    require(os.uname().machine == "x86_64", "Only Intel hardware is supported.")
    version = subprocess.check_output(["sw_vers", "-productVersion"], text=True).strip()
    require(version.startswith("26."), "Only macOS Tahoe 26 is supported.")
    root = plistlib.loads(subprocess.check_output(["ioreg", "-p", "IOService", "-c", "IOPCIDevice", "-a"]))
    queue = [root]
    found = False
    while queue:
        node = queue.pop()
        queue.extend(node.get("IORegistryEntryChildren", []))
        if node.get("IORegistryEntryName") == "HDEF":
            vendor = node.get("vendor-id", b"")
            device = node.get("device-id", b"")
            if vendor[:2] == b"\x86\x80" and device[:2] == b"\xc8\xa0":
                found = True
                break
    require(found, "Expected Surface Laptop 4 Intel audio controller 8086:A0C8 (HDEF) not found.")


def prepare_config(original):
    config = plistlib.loads(plistlib.dumps(original))
    entries = config["Kernel"]["Add"]
    names = [item["BundlePath"] for item in entries]
    require(names.count("Lilu.kext") == 1 and names.count("AppleALC.kext") == 1,
            "Expected exactly one Lilu and AppleALC entry.")
    lilu_index, alc_index = names.index("Lilu.kext"), names.index("AppleALC.kext")
    require(lilu_index < alc_index and entries[lilu_index]["Enabled"] and entries[alc_index]["Enabled"],
            "Lilu must be enabled before AppleALC.")
    require(KEXT not in names, "SimpleHDA is already configured; no changes made.")
    require(not any(item.get("Enabled") and ("VoodooHDA" in item["BundlePath"] or
                "HDAUniversal" in item["BundlePath"]) for item in entries),
            "Another enabled HDA replacement was found.")
    arguments = config.get("NVRAM", {}).get("Add", {}).get(
        "7C436110-AB2A-4BBB-A880-FE41995C9F82", {}).get("boot-args", "")
    if isinstance(arguments, bytes):
        arguments = arguments.decode("utf-8", errors="replace")
    require(not any(arg.startswith("alcid=") and arg != "alcid=35"
                    for arg in arguments.split()), "Conflicting alcid boot argument.")
    config["Kernel"]["Quirks"]["DisableLinkeditJettison"] = True
    entries.insert(alc_index + 1, {
        "Arch": "x86_64",
        "BundlePath": KEXT,
        "Comment": "Surface Laptop 4 Intel - restore native Tahoe audio",
        "Enabled": True,
        "ExecutablePath": "Contents/MacOS/SimpleHDA",
        "MaxKernel": "25.99.99",
        "MinKernel": "25.0.0",
        "PlistPath": "Contents/Info.plist",
    })
    properties = config.setdefault("DeviceProperties", {}).setdefault("Add", {})
    matches = [path for path in properties if path.lower() == AUDIO_PATH.lower()]
    require(len(matches) <= 1, "Duplicate HDEF device-property paths.")
    selected_path = matches[0] if matches else AUDIO_PATH
    properties.setdefault(selected_path, {})["layout-id"] = struct.pack("<I", AUDIO_LAYOUT)
    return config


def validate_config(path, validator):
    subprocess.run(["plutil", "-lint", str(path)], check=True)
    if validator:
        require(validator.is_file(), "ocvalidate not found: " + str(validator))
        result = subprocess.run([str(validator), str(path)], capture_output=True, text=True)
        print(result.stdout.strip(), result.stderr.strip())
        require(result.returncode == 0, "ocvalidate rejected OpenCore config.")
    else:
        print("WARNING: ocvalidate not supplied; plist syntax and installer invariants checked.")


def efi_root(esp):
    info = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", esp]))
    require(info.get("Content") == "EFI", "Selected volume is not an EFI System Partition.")
    if not info.get("MountPoint"):
        subprocess.run(["diskutil", "mount", esp], check=True)
        info = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", esp]))
    root = Path(info.get("MountPoint") or "")
    require(root.is_dir() and (root / "EFI/OC/OpenCore.efi").is_file(),
            "EFI/OC/OpenCore.efi missing on selected ESP; check --esp.")
    require((root / "EFI/OC/config.plist").is_file(), "OpenCore config.plist missing.")
    return root


def acquire_kext(destination):
    archive = destination / "SimpleHDA-1.0.2-RELEASE.zip"
    if not archive.is_file() or sha256(archive) != RELEASE_SHA256:
        subprocess.run(["curl", "--fail", "--location", "--retry", "3",
                        "--connect-timeout", "15", RELEASE_URL, "--output", str(archive)],
                       check=True)
    require(sha256(archive) == RELEASE_SHA256, "SimpleHDA download SHA-256 mismatch.")
    bundle = destination / KEXT
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if not item.filename.startswith(ZIP_ROOT):
                continue
            relative = item.filename[len(ZIP_ROOT):]
            if not relative:
                continue
            parts = Path(relative).parts
            require(".." not in parts and not Path(relative).is_absolute(), "Unsafe ZIP entry.")
            target = bundle.joinpath(*parts)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(item))
    require((bundle / "Contents/Info.plist").is_file(), "SimpleHDA Info.plist missing.")
    executable = bundle / "Contents/MacOS/SimpleHDA"
    require(executable.is_file(), "SimpleHDA executable missing.")
    executable.chmod(0o755)
    return bundle


def save_config(config, path, validator):
    path.write_bytes(plistlib.dumps(config, sort_keys=False))
    validate_config(path, validator)


def backup_oc(efi, backups, current):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    private = backups / stamp
    private.mkdir(parents=True, exist_ok=False)
    shutil.copytree(current, private / "OC")
    original_hash = sha256(current / "config.plist")
    require(original_hash == sha256(private / "OC/config.plist"), "Backup verification failed.")
    # Duplicate the original OC on the ESP when capacity permits Windows-only recovery.
    bytes_used = sum(p.stat().st_size for p in current.rglob("*") if p.is_file())
    esp_copy = efi / "EFI" / ("OC-SL4-AUDIO-BACKUP-" + stamp)
    if shutil.disk_usage(efi).free > bytes_used + 16 * 1024 * 1024:
        try:
            shutil.copytree(current, esp_copy)
            require(original_hash == sha256(esp_copy / "config.plist"), "ESP backup mismatch.")
        except Exception:
            shutil.rmtree(esp_copy, ignore_errors=True)
            raise
    else:
        esp_copy = None
        print("WARNING: insufficient ESP space for a second copy; private backup is available.")
    (private / "manifest.json").write_text(json.dumps({
        "original_sha256": original_hash, "esp_backup": str(esp_copy) if esp_copy else None,
        "driver": KEXT, "layout_id": AUDIO_LAYOUT,
    }, indent=2), encoding="utf-8")
    print("OpenCore backup:", private)
    if esp_copy:
        print("Windows-accessible backup:", esp_copy)
    return private


def atomic_config_copy(source, dest):
    with tempfile.NamedTemporaryFile(prefix=".sl4-audio-", suffix=".plist",
                                     dir=dest.parent, delete=False) as temp:
        tmp = Path(temp.name)
    try:
        shutil.copy2(source, tmp)
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()


def install(args):
    require(os.geteuid() == 0, "Run apply with sudo.")
    test_host()
    root = efi_root(args.esp)
    oc = root / "EFI/OC"
    config_path = oc / "config.plist"
    require(not (oc / "Kexts" / KEXT).exists(),
            "SimpleHDA already exists on this EFI; stopping to avoid overwriting it.")
    original = plistlib.loads(config_path.read_bytes())
    updated = prepare_config(original)
    backup_root = owner_home() / "Downloads/SL4-AUDIO-BACKUPS"
    backup_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sl4-audio-") as work:
        stage = Path(work)
        bundle = acquire_kext(stage)
        new_file = stage / "config.plist"
        save_config(updated, new_file, args.ocvalidate)
        private = backup_oc(root, backup_root, oc)
        require(sha256(config_path) == sha256(private / "OC/config.plist"),
                "Original config changed during preparation.")
        target_kext = oc / "Kexts" / KEXT
        try:
            shutil.copytree(bundle, target_kext)
            require(sha256(bundle / "Contents/MacOS/SimpleHDA") ==
                    sha256(target_kext / "Contents/MacOS/SimpleHDA"), "Kext copy failed.")
            atomic_config_copy(new_file, config_path)
            require(sha256(config_path) == sha256(new_file), "Config write failed.")
        except BaseException:
            atomic_config_copy(private / "OC/config.plist", config_path)
            shutil.rmtree(target_kext, ignore_errors=True)
            raise
        (backup_root / "LAST_BACKUP").write_text(str(private) + "\n", encoding="utf-8")
    print("SUCCESS: SimpleHDA 1.0.2 and AppleALC layout 35 installed.")
    print("Restart macOS, then check System Settings > Sound.")


def rollback(args):
    require(os.geteuid() == 0, "Run rollback with sudo.")
    root = efi_root(args.esp)
    backups = owner_home() / "Downloads/SL4-AUDIO-BACKUPS"
    pointer = backups / "LAST_BACKUP"
    require(pointer.is_file(), "No recorded audio installation to roll back.")
    private = Path(pointer.read_text(encoding="utf-8").strip())
    require(private.parent == backups and (private / "manifest.json").is_file(),
            "Backup record is invalid.")
    manifest = json.loads((private / "manifest.json").read_text(encoding="utf-8"))
    original = private / "OC/config.plist"
    require(sha256(original) == manifest["original_sha256"], "Backup config checksum mismatch.")
    oc = root / "EFI/OC"
    current = oc / "config.plist"
    config = plistlib.loads(current.read_bytes())
    require(any(x.get("BundlePath") == KEXT and x.get("Enabled")
                for x in config["Kernel"]["Add"]), "SimpleHDA is not active; stopping rollback.")
    # Restore only files this installer changed; leave all other kexts untouched.
    atomic_config_copy(original, current)
    shutil.rmtree(oc / "Kexts" / KEXT)
    print("ROLLBACK COMPLETE: prior config restored; SimpleHDA removed.")
    print("Restart macOS to activate the previous audio configuration.")


def inspect(args):
    test_host()
    require(args.config is not None, "Pass --config PATH for read-only inspection.")
    original = plistlib.loads(args.config.read_bytes())
    updated = prepare_config(original)
    with tempfile.TemporaryDirectory(prefix="sl4-audio-check-") as work:
        target = Path(work) / "config.plist"
        save_config(updated, target, args.ocvalidate)
    print("INSPECT OK: audio configuration is valid; no EFI changes.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "apply", "rollback"))
    parser.add_argument("--esp", default="disk0s1",
                        help="EFI System Partition to mount (default: disk0s1; verify with diskutil list).")
    parser.add_argument("--config", type=Path, help="Existing config.plist for read-only inspect.")
    parser.add_argument("--ocvalidate", type=Path, help="Optional matching OpenCore ocvalidate binary.")
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
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as exc:
        print("FAILED:", exc, file=sys.stderr)
        sys.exit(1)
