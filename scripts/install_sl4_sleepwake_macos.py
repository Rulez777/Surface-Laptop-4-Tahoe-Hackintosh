#!/usr/bin/env python3
"""Safely install the pinned Surface Laptop 4 input + lid/SAM sleep-wake profile in OpenCore.

macOS installer for the public, hash-pinned SL4-TGL-Input-SleepWake-v2-beta.zip.
It changes only EFI/OC, never EFI/Microsoft, partitions, firmware or NVRAM.

Only Intel Surface Laptop 4 with UART PCI 8086:A0A8 are supported. A successful
staging operation does not imply the experimental kexts actually work on Tahoe.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import os
import pathlib
import plistlib
import shutil
import subprocess
import struct
import sys
import tempfile
import zipfile

KEXTS = (
    ("VoodooGPIO", "org.coolstar.VoodooGPIO"),
    ("VoodooSerial", "com.xavier.VoodooSerial"),
    ("VoodooInput", "me.kishorprins.VoodooInput"),
    ("BigSurface", "com.xavier.BigSurface"),
    ("BigSurfaceHIDDriver", "com.xavier.BigSurfaceHIDDriver"),
)
EXPECTED = {k + ".kext": bundle_id for k, bundle_id in KEXTS}
PROFILE = "sl4-intel-tigerlake-a0a8-sleepwake-v2"
SYSTEM_GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
IGPU = "PciRoot(0x0)/Pci(0x2,0x0)"


def fail(message: str) -> None:
    raise RuntimeError(message)


def efi_anchor(oc: pathlib.Path) -> pathlib.Path:
    return oc.parent.parent


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            buf = f.read(1024 * 1024)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def normalized_macho_digest(data: bytes) -> str:
    blob = bytearray(data)
    if blob[:4] not in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf"):
        fail("Input package contains a non-64-bit Mach-O executable")
    ncmds = struct.unpack_from("<I", blob, 16)[0]
    offset = 32
    for _ in range(ncmds):
        command, size = struct.unpack_from("<II", blob, offset)
        if size < 8 or offset + size > len(blob):
            fail("Malformed Mach-O load command in input package")
        if command == 0x1B:
            if size < 24:
                fail("Malformed Mach-O LC_UUID in input package")
            blob[offset + 8:offset + 24] = bytes(16)
            return hashlib.sha256(blob).hexdigest()
        offset += size
    fail("Input package Mach-O LC_UUID missing")


def detect_hardware() -> dict[str, str]:
    if sys.platform != "darwin":
        fail("Run only on the target Surface Laptop 4 from macOS (dry-run tests may mock this function)")
    acpi = subprocess.check_output(["/usr/sbin/ioreg", "-p", "IOACPIPlane", "-lw0"], text=True)
    if not all(x in acpi for x in ('MSHW0084', 'MSHW0250', 'UA00', 'GPI0')):
        fail("Expected Surface Laptop 4 Intel ACPI profile (MSHW0084, MSHW0250, UA00, GPI0) not found")
    pcis = subprocess.check_output(["/usr/sbin/ioreg", "-p", "IOService", "-lw0"], text=True)
    if 'a8a00000' not in pcis.lower():
        fail("Intel UART PCI device-id A0A8 not found in IORegistry; refusing this profile")
    return {"model": "Surface Laptop 4 Intel (ACPI MSHW0250)", "uart": "8086:A0A8", "profile": PROFILE}


def check_internal_esp(efi: pathlib.Path) -> None:
    if sys.platform != 'darwin':
        fail("Internal EFI verification requires macOS")
    details = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','disk0s1']))
    mountpoint = details.get('MountPoint')
    if (details.get('DeviceIdentifier') != 'disk0s1' or details.get('Internal') is not True
            or not mountpoint or (pathlib.Path(mountpoint)/'EFI').resolve() != efi.resolve()):
        fail("Expected internal disk0s1 ESP path differs from --efi. No files changed")


def validate_efi(efi: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path, dict]:
    if efi.name.lower() != "efi":
        fail("--efi must point at the mounted internal EFI directory, e.g. S:\\EFI")
    check_internal_esp(efi)
    if not (efi / "Microsoft" / "Boot" / "bootmgfw.efi").is_file():
        fail("Microsoft Boot Manager missing: refusing to modify an unverified ESP")
    oc = efi / "OC"
    path = oc / "config.plist"
    if not path.is_file() or not (oc / "OpenCore.efi").is_file():
        fail("OpenCore.efi or config.plist missing from EFI/OC")
    with path.open("rb") as f:
        cfg = plistlib.load(f)
    if not isinstance(cfg, dict):
        fail("OpenCore config is not a dict")
    for k in ("ACPI", "DeviceProperties", "Kernel", "NVRAM"):
        if not isinstance(cfg.get(k), dict):
            fail("Missing OpenCore config section: " + k)
    kernel = cfg["Kernel"].get("Add")
    if not isinstance(kernel, list):
        fail("Missing Kernel/Add list")
    props = cfg["DeviceProperties"].get("Add", {}).get(IGPU, {})
    flag = cfg["NVRAM"].get("Add", {}).get(SYSTEM_GUID, {}).get("boot-args", "")
    if not isinstance(flag, str) or "-wex-noaccel" in flag.split():
        fail("Working Metal 2 boot args not found; this input experiment cannot switch graphics modes")
    if "-igfxdvmt" not in flag.split():
        fail("DVMT 60 MB working boot-args have changed; stop and inspect instead")
    required = {"framebuffer-patch-enable": bytes.fromhex("01000000"),
                "framebuffer-stolenmem": bytes.fromhex("0000C003")}
    if not isinstance(props, dict) or any(props.get(k) != v for k, v in required.items()):
        fail("Working 60 MB DVMT properties missing; preserve verified Metal 2 state")
    return oc, path, cfg


def validate_archive(path: pathlib.Path) -> dict[str, bytes]:
    if not path.is_file():
        fail("Sleep/wake artifact not found: " + str(path))
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 2000 or sum(x.file_size for x in members) > 150 * 1024 * 1024:
            fail("Unreasonable archive size or file count")
        files: dict[str, bytes] = {}
        for member in members:
            raw = member.filename.replace("\\", "/")
            parts = pathlib.PurePosixPath(raw).parts
            if raw.startswith("/") or ".." in parts or member.file_size > 30 * 1024 * 1024:
                fail("Untrusted zip member: " + raw)
            if member.is_dir():
                continue
            if not (raw.startswith("Kexts/") or raw.startswith("ACPI/") or
                    raw in {"MANIFEST.json", "SOURCE.txt"} or raw.startswith("LICENSES/")):
                fail("Unexpected package member: " + raw)
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                fail("Package may not contain symlinks: " + raw)
            if raw in files:
                fail("Duplicate package path: " + raw)
            files[raw] = archive.read(member)
    if "MANIFEST.json" not in files:
        fail("Missing package manifest")
    manifest = json.loads(files["MANIFEST.json"])
    if manifest.get("release") != "SL4-TGL-Input-SleepWake-v2-beta" or manifest.get("private_efi_included") is not False:
        fail("Unexpected or private package identity")
    features = manifest.get("features", {})
    if features.get("diagnostic_probe_timer") is not False or features.get("diagnostic_ioregistry_telemetry") is not False:
        fail("Refusing a package containing temporary diagnostic probes")
    for member, expected in manifest.get("sha256", {}).items():
        if member not in files or hashlib.sha256(files[member]).hexdigest() != expected:
            fail("Package checksum mismatch: " + member)
    normalized = manifest.get("normalized_macho_sha256", {})
    if set(normalized) != {name for name, _ in KEXTS}:
        fail("Missing normalized executable hashes in package manifest")
    for name, _bundle_id in KEXTS:
        executable = files.get("Kexts/" + name + ".kext/Contents/MacOS/" + name)
        if executable is None or normalized_macho_digest(executable) != normalized[name]:
            fail("Normalized executable hash mismatch: " + name)
    for name, bundle_id in KEXTS:
        prefix = "Kexts/" + name + ".kext/Contents/"
        info_path = prefix + "Info.plist"
        if info_path not in files:
            fail("Missing kext plist: " + info_path)
        meta = plistlib.loads(files[info_path])
        if meta.get("CFBundleIdentifier") != bundle_id:
            fail("Wrong kext bundle ID " + name)
        executable = meta.get("CFBundleExecutable")
        binary_path = prefix + "MacOS/" + str(executable)
        if not executable or binary_path not in files:
            fail("Missing executable for " + name)
        binary = files[binary_path]
        if len(binary) < 32 or binary[:8] != bytes.fromhex("cffaedfe07000001"):
            fail("Invalid x86_64 Mach-O executable for " + name)
        if name == "VoodooGPIO" and meta.get("CFBundleVersion") != "1.2.5":
            fail("Expected production VoodooGPIO 1.2.5")
        if name == "BigSurface":
            if meta.get("CFBundleVersion") != "1.2.1":
                fail("Expected BigSurface 1.2.1")
            if meta.get("IOKitPersonalities", {}).get("Surface Serial Hub", {}).get("SL4SAMWakeEnabled") is not True:
                fail("SAM wake personality not enabled")
    serial = plistlib.loads(files["Kexts/VoodooSerial.kext/Contents/Info.plist"])
    pci = serial.get("IOKitPersonalities", {}).get("VoodooUARTController", {}).get("IOPCIMatch", "").lower()
    if "0xa0a88086" not in pci or "0x51a88086" in pci:
        fail("VoodooSerial does not target SL4 Intel UART 8086:A0A8")
    gpio = plistlib.loads(files["Kexts/VoodooGPIO.kext/Contents/Info.plist"])
    personality = gpio.get("IOKitPersonalities", {}).get("VoodooGPIOTigerLakeLP", {})
    if not {"INT34C5", "INTC1055"}.issubset(set(personality.get("IONameMatch", []))):
        fail("VoodooGPIO Tiger Lake-LP device match missing")
    aml_path = "ACPI/SSDT-SL4-LIDWAKE.aml"
    if aml_path not in files:
        fail("Missing SSDT-SL4-LIDWAKE.aml")
    aml = files[aml_path]
    if len(aml) != 100 or sum(aml) % 256 or hashlib.sha256(aml).hexdigest() != "96efe9f179bbf62b9d30c2742f6d5be303d0c78b5f569b31c562e0035903aefb":
        fail("Invalid or unrecognized SL4 lid-wake SSDT")
    return files


def kernel_changes(cfg: dict) -> tuple[dict, list[str]]:
    original = cfg["Kernel"]["Add"]
    disabled, retained = [], []
    new_names = set(EXPECTED)
    for item in original:
        path = item.get("BundlePath", "")
        root = path.split("/", 1)[0]
        if root in new_names:
            disabled.append("replaced existing entry: " + path)
            continue
        if (root.startswith("VoodooI2C") or root in {"SMCBatteryManager.kext", "SMCLightSensor.kext"}
                or "/VoodooGPIO.kext" in path or "/VoodooInput.kext" in path):
            if item.get("Enabled"):
                disabled.append("disabled conflicting input driver: " + path)
            item["Enabled"] = False
        retained.append(item)
    new_entries = []
    for name, _bundle_id in KEXTS:
        new_entries.append({
            "Arch": "x86_64", "BundlePath": name + ".kext",
            "Comment": "Surface Laptop 4 Intel input and sleep/wake",
            "Enabled": True, "ExecutablePath": "Contents/MacOS/" + name,
            "MaxKernel": "", "MinKernel": "", "PlistPath": "Contents/Info.plist"
        })
    for dep in ("Lilu.kext", "VirtualSMC.kext"):
        if not any(x.get("BundlePath") == dep and x.get("Enabled") for x in retained):
            fail("Required enabled dependency missing from Kernel/Add: " + dep)
    cfg["Kernel"]["Add"] = retained + new_entries

    boot = cfg.get("NVRAM", {}).get("Add", {}).get(SYSTEM_GUID, {})
    boot_args = boot.get("boot-args", "")
    if isinstance(boot_args, bytes):
        decoded = boot_args.decode("utf-8", errors="strict")
        cleaned = " ".join(x for x in decoded.split() if x != "-wex-edp-wake-trace")
        if cleaned != decoded:
            boot["boot-args"] = cleaned.encode("utf-8")
            disabled.append("disabled temporary diagnostic boot argument: -wex-edp-wake-trace")
    elif isinstance(boot_args, str):
        cleaned = " ".join(x for x in boot_args.split() if x != "-wex-edp-wake-trace")
        if cleaned != boot_args:
            boot["boot-args"] = cleaned
            disabled.append("disabled temporary diagnostic boot argument: -wex-edp-wake-trace")
    elif boot_args:
        fail("Unsupported NVRAM boot-args type; refusing to alter it")

    acpi_add = cfg["ACPI"]["Add"]
    acpi_add[:] = [x for x in acpi_add if x.get("Path") != "SSDT-SL4-LIDWAKE.aml"]
    acpi_add.append({
        "Enabled": True, "Comment": "Surface Laptop 4 lid wake GPE 0x4B",
        "Path": "SSDT-SL4-LIDWAKE.aml"
    })
    cfg.setdefault("Misc", {}).setdefault("Debug", {})["SysReport"] = False
    return cfg, disabled + ["enabled: " + n for n in EXPECTED] + ["enabled: SSDT-SL4-LIDWAKE.aml", "disabled: Misc.Debug.SysReport"]


def run_validator(exe: pathlib.Path, oc: pathlib.Path) -> None:
    if not exe.is_file():
        fail("Matching OpenCore 1.0.8 macOS ocvalidate is required: " + str(exe))
    r = subprocess.run([str(exe), str(oc / "config.plist")],
                       text=True, capture_output=True)
    print(r.stdout.strip()); print(r.stderr.strip())
    if r.returncode:
        fail("ocvalidate rejected the staged config; OC will be restored from backup")


def apply(args: argparse.Namespace, oc: pathlib.Path, path: pathlib.Path, cfg: dict) -> None:
    if not args.artifact:
        fail("--artifact is required in apply mode")
    if not args.ocvalidate:
        fail("--ocvalidate for OpenCore 1.0.8 is mandatory")
    artifact = pathlib.Path(args.artifact)
    files = validate_archive(artifact)
    if not os.access(oc, os.W_OK):
        fail("ESP is not writable: remount disk0s1 read/write before apply; no changes made")
    backup_root = pathlib.Path(args.backup_dir)
    backup_root.mkdir(parents=True, exist_ok=True)
    if oc.resolve().is_relative_to(backup_root.resolve()) or backup_root.resolve().is_relative_to(oc.resolve()):
        fail("Backups must not be located inside or above the live OC folder")
    if os.path.commonpath([str(backup_root.resolve()), str(efi_anchor(oc).resolve())]) == str(efi_anchor(oc).resolve()):
        fail("Keep backups on macOS APFS, not on the mounted ESP")

    # Idempotent no-op when the exact release is already installed.
    try:
        installed_gpio = plistlib.loads((oc / "Kexts/VoodooGPIO.kext/Contents/Info.plist").read_bytes())
        installed_big = plistlib.loads((oc / "Kexts/BigSurface.kext/Contents/Info.plist").read_bytes())
        acpi_enabled = any(x.get("Path") == "SSDT-SL4-LIDWAKE.aml" and x.get("Enabled") for x in cfg["ACPI"]["Add"])
        aml_ok = sha256(oc / "ACPI/SSDT-SL4-LIDWAKE.aml") == hashlib.sha256(files["ACPI/SSDT-SL4-LIDWAKE.aml"]).hexdigest()
        boot_args = cfg.get("NVRAM", {}).get("Add", {}).get(SYSTEM_GUID, {}).get("boot-args", "")
        trace_absent = "-wex-edp-wake-trace" not in (boot_args.decode("utf-8") if isinstance(boot_args, bytes) else str(boot_args)).split()
        sysreport_off = cfg.get("Misc", {}).get("Debug", {}).get("SysReport") is False
        bundles_exact = all(
            (oc / "Kexts" / pathlib.Path(rel[len("Kexts/"):])).is_file()
            and sha256(oc / "Kexts" / pathlib.Path(rel[len("Kexts/"):])) == hashlib.sha256(blob).hexdigest()
            for rel, blob in files.items() if rel.startswith("Kexts/")
        )
        if (installed_gpio.get("CFBundleVersion") == "1.2.5" and installed_big.get("CFBundleVersion") == "1.2.1"
                and acpi_enabled and aml_ok and bundles_exact and trace_absent and sysreport_off):
            print("EXACT SL4 sleep/wake production profile already installed; no files changed.")
            return
    except (OSError, plistlib.InvalidFileException):
        pass

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = backup_root / ("SL4-SLEEPWAKE-" + stamp)
    backup_oc = backup / "OC"
    shutil.copytree(oc, backup_oc)
    if sha256(path) != sha256(backup_oc / "config.plist"):
        fail("Backup verification failed; OC untouched")
    if args.ack != "STAGE-SL4-SLEEPWAKE":
        fail("Refusing to modify EFI without --ack STAGE-SL4-SLEEPWAKE. Backup kept at " + str(backup))
    newcfg, changes = kernel_changes(cfg)
    rescue = efi_anchor(oc) / "EFI" / ("SL4-SLEEPWAKE-ROLLBACK-" + stamp + ".plist")
    if rescue.exists():
        fail("ESP rollback plist already exists; OC unchanged: " + str(rescue))
    shutil.copy2(backup_oc / "config.plist", rescue)
    if sha256(rescue) != sha256(backup_oc / "config.plist"):
        fail("ESP rollback plist verification failed; OC unchanged")
    print("ROLLBACK PLIST FOR WINDOWS:", rescue)
    print("Backup verified:", backup_oc)
    for change in changes:
        print(" ", change)
    try:
        for name in EXPECTED:
            target = oc / "Kexts" / name
            if target.exists():
                if not target.is_dir() or target.is_symlink():
                    fail("Refusing non-directory existing bundle: " + str(target))
                shutil.rmtree(target)
            prefix = "Kexts/" + name + ".kext/"
            for rel, blob in files.items():
                if rel.startswith(prefix):
                    dest = oc / "Kexts" / pathlib.Path(rel[len("Kexts/"):])
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(blob)
                    if "/Contents/MacOS/" in str(dest):
                        dest.chmod(0o755)
        aml_dest = oc / "ACPI/SSDT-SL4-LIDWAKE.aml"
        aml_dest.parent.mkdir(parents=True, exist_ok=True)
        aml_dest.write_bytes(files["ACPI/SSDT-SL4-LIDWAKE.aml"])
        with tempfile.NamedTemporaryFile(dir=oc, prefix="sl4-sleepwake-", suffix=".plist", delete=False) as tf:
            staged = pathlib.Path(tf.name)
            plistlib.dump(newcfg, tf, sort_keys=False)
        os.replace(staged, path)
        run_validator(pathlib.Path(args.ocvalidate), oc)
        for name in EXPECTED:
            prefix = "Kexts/" + name + ".kext/Contents/"
            info = oc / "Kexts" / name / "Contents/Info.plist"
            if info.read_bytes() != files[prefix + "Info.plist"]:
                fail("Bundle changed during staging: " + name)
        if sha256(aml_dest) != hashlib.sha256(files["ACPI/SSDT-SL4-LIDWAKE.aml"]).hexdigest():
            fail("Staged lid-wake SSDT failed verification")
    except BaseException:
        print("STAGE FAILED: automatically restoring the full OC directory from backup")
        shutil.rmtree(oc)
        shutil.copytree(backup_oc, oc)
        if sha256(path) != sha256(backup_oc / "config.plist"):
            fail("Automatic recovery verification FAILED; restore full OC manually from " + str(backup_oc))
        print("RESTORED old OC from", backup)
        raise
    manifest = {
        "backup": str(backup_oc), "profile": PROFILE,
        "artifact_sha256": sha256(artifact),
        "pre_config_sha256": sha256(backup_oc / "config.plist"),
        "post_config_sha256": sha256(path), "changes": changes
    }
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("STAGED AND VALIDATED. DO NOT DELETE BACKUP:", backup_oc)
    print("No Microsoft EFI files, disk partitions, firmware entries or graphics boot flags changed.")
    print("Keyboard/trackpad SAM wake is included but not yet physically validated.")


def restore(args: argparse.Namespace, oc: pathlib.Path, path: pathlib.Path) -> None:
    if args.ack != "RESTORE-SL4-SLEEPWAKE":
        fail("Restoring requires explicit --ack RESTORE-SL4-SLEEPWAKE")
    if not args.backup:
        fail("--backup path to the saved SL4-SLEEPWAKE-* backup directory is required")
    backup = pathlib.Path(args.backup)
    if os.path.commonpath([str(backup.resolve()), str(efi_anchor(oc).resolve())]) == str(efi_anchor(oc).resolve()):
        fail("Backup on the EFI drive is unsafe; refusing restore")
    manifest_path, saved_oc = backup / "manifest.json", backup / "OC"
    if not manifest_path.is_file() or not (saved_oc / "config.plist").is_file():
        fail("Valid backup manifest and OC/config.plist not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("profile") != PROFILE:
        fail("Unsupported backup profile")
    if sha256(saved_oc / "config.plist") != manifest.get("pre_config_sha256"):
        fail("Backup config has changed; refusing to restore")
    if sha256(path) != manifest.get("post_config_sha256"):
        fail("Current config differs from the staged version. Stop: do not overwrite newer changes")
    # Never delete the live OC before preserving its *entire* current contents off ESP.
    last = backup.parent / ("SL4-SLEEPWAKE-BEFORE-RESTORE-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    shutil.copytree(oc, last / "OC")
    if sha256(path) != sha256(last / "OC" / "config.plist"):
        fail("Pre-restore backup verification failed; old OC retained")
    try:
        shutil.rmtree(oc)
        shutil.copytree(saved_oc, oc)
        if sha256(path) != manifest["pre_config_sha256"]:
            fail("Restored OC config failed verification")
    except BaseException:
        print("RESTORE FAILED; attempting to put the pre-restore OC back")
        if oc.exists():
            shutil.rmtree(oc)
        shutil.copytree(last / "OC", oc)
        raise
    print("ORIGINAL OC RESTORED. Pre-restore snapshot:", last)
    print("Microsoft EFI, partitions and boot-order unchanged")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("inspect", "apply", "restore"), default="inspect")
    p.add_argument("--efi", type=pathlib.Path, required=True, help="mounted internal ESP/EFI, e.g. /Volumes/SYSTEM/EFI")
    p.add_argument("--artifact", type=pathlib.Path, help="Locally built pinned five-kext + lid-wake SSDT ZIP")
    p.add_argument("--backup", type=pathlib.Path, help="Private SL4-SLEEPWAKE-* backup folder, for restore mode")
    p.add_argument("--backup-dir", type=pathlib.Path, help="Private backup directory on macOS APFS ~/Downloads")
    p.add_argument("--ocvalidate", type=pathlib.Path, help="Matching OpenCore 1.0.8 ocvalidate.exe")
    p.add_argument("--ack", type=str, default="", help="Explicit apply acknowledgement")
    args = p.parse_args()
    hw = detect_hardware()
    oc, path, cfg = validate_efi(args.efi)
    print("Detected:", hw)
    print("Internal ESP:", args.efi, "OpenCore:", oc)
    print("Current config SHA256:", sha256(path))
    if args.artifact:
        print("Artifact SHA256:", sha256(args.artifact))
        files = validate_archive(args.artifact)
        print("Verified experimental kexts:", ", ".join(EXPECTED), "(%d files)" % len(files))
    if args.mode == "apply":
        if not args.backup_dir:
            fail("--backup-dir on macOS APFS required")
        apply(args, oc, path, cfg)
    elif args.mode == "restore":
        restore(args, oc, path)
    else:
        print("READ ONLY: no changes made. Use --mode apply only on the supported Surface Laptop 4 after review.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, zipfile.BadZipFile, plistlib.InvalidFileException) as exc:
        print("STOP:", exc, file=sys.stderr)
        sys.exit(1)
