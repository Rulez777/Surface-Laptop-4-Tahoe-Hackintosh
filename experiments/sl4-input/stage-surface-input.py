#!/usr/bin/env python3
"""Safely stage experimental Surface Laptop 4 Intel BigSurface HID kexts in OpenCore.

This script intentionally runs from WINDOWS with Python 3 (no Xcode/Python on macOS
needed). It only changes EFI/OC, never EFI/Microsoft, partitions, firmware or NVRAM.

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
PROFILE = "sl4-intel-tigerlake-a0a8"
SYSTEM_GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
IGPU = "PciRoot(0x0)/Pci(0x2,0x0)"


def fail(message: str) -> None:
    raise RuntimeError(message)


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            buf = f.read(1024 * 1024)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def powershell(cmd: str) -> str:
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", cmd],
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def detect_hardware() -> dict[str, str]:
    if os.name != "nt":
        fail("Run the installer from Windows 11 with Python 3; do not stage from a foreign computer")
    model = powershell("(Get-CimInstance Win32_ComputerSystem).Model")
    if "surface laptop 4" not in model.lower():
        fail("Unsupported model: " + model + "; expected Intel Surface Laptop 4")
    ids = powershell("Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPDeviceID -match 'PCI\\\\VEN_8086&DEV_A0A8' } | Select-Object -ExpandProperty PNPDeviceID")
    if not ids:
        fail("Intel Tiger Lake UART PCI 8086:A0A8 was not found in Windows PnP devices")
    return {"model": model, "uart": "8086:A0A8", "profile": PROFILE}


def validate_efi(efi: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path, dict]:
    if efi.name.lower() != "efi":
        fail("--efi must point at the mounted internal EFI directory, e.g. S:\\EFI")
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
        fail("Build artifact not found: " + str(path))
    with zipfile.ZipFile(path) as outer:
        names = outer.namelist()
        nested = [n for n in names if n.lower().endswith(".zip") and not n.startswith("__MACOSX/")]
        if len(nested) == 1 and not any(".kext/" in n for n in names):
            payload = outer.read(nested[0]); actual = zipfile.ZipFile(io.BytesIO(payload))
        else:
            actual = outer
        with actual:
            files: dict[str, bytes] = {}
            members = actual.infolist()
            if len(members) > 2000 or sum(m.file_size for m in members) > 150 * 1024 * 1024:
                fail("Unreasonable archive size or file count")
            for member in members:
                raw = member.filename.replace("\\", "/")
                parts = pathlib.PurePosixPath(raw).parts
                if raw.startswith("/") or ".." in parts or member.file_size > 30 * 1024 * 1024:
                    fail("Untrusted zip member: " + raw)
                if member.is_dir():
                    continue
                if len(parts) < 4 or parts[0] != "out" or parts[1] not in EXPECTED:
                    fail("Unexpected artifact member: " + raw)
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    fail("Artifact may not contain symlinks: " + raw)
                if raw in files:
                    fail("Duplicate artifact path: " + raw)
                files[raw] = actual.read(member)
        for name, bundle_id in EXPECTED.items():
            prefix = "out/" + name + "/Contents/"
            info = prefix + "Info.plist"
            if info not in files:
                fail("Missing kext plist: " + info)
            meta = plistlib.loads(files[info]); actual_id = meta.get("CFBundleIdentifier")
            if actual_id != bundle_id:
                fail("Wrong kext bundle ID " + name + ": " + str(actual_id))
            executable = meta.get("CFBundleExecutable")
            if not executable or prefix + "MacOS/" + executable not in files:
                fail("Missing executable for " + name)
            binary = files[prefix + "MacOS/" + executable]
            if len(binary) < 32 or binary[:8] != bytes.fromhex("cffaedfe07000001"):
                fail("Invalid x86_64 Mach-O executable for " + name)
        serial = plistlib.loads(files["out/VoodooSerial.kext/Contents/Info.plist"])
        pci = serial.get("IOKitPersonalities", {}).get("VoodooUARTController", {}).get("IOPCIMatch", "").lower()
        if "0xa0a88086" not in pci or "0x51a88086" in pci:
            fail("VoodooSerial does not target SL4 Intel UART 8086:A0A8")
        gpio = plistlib.loads(files["out/VoodooGPIO.kext/Contents/Info.plist"])
        personality = gpio.get("IOKitPersonalities", {}).get("VoodooGPIOTigerLakeLP", {})
        matches = personality.get("IONameMatch", [])
        if not {"INT34C5", "INTC1055"}.issubset(set(matches)):
            fail("VoodooGPIO Tiger Lake-LP device match missing")
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
                disabled.append("disabled: " + path)
            item["Enabled"] = False
        retained.append(item)
    new_entries = []
    for name, _bundle_id in KEXTS:
        new_entries.append({"Arch": "Any", "BundlePath": name + ".kext",
                            "Comment": "Experimental Surface Laptop 4 Intel SAM HID",
                            "Enabled": True,
                            "ExecutablePath": "Contents/MacOS/" + name,
                            "MaxKernel": "", "MinKernel": "",
                            "PlistPath": "Contents/Info.plist"})
    for dep in ("Lilu.kext", "VirtualSMC.kext"):
        if not any(x.get("BundlePath") == dep and x.get("Enabled") for x in retained):
            fail("Required enabled dependency missing from Kernel/Add: " + dep)
    cfg["Kernel"]["Add"] = retained + new_entries
    return cfg, disabled + ["enabled: " + n for n in EXPECTED]


def run_validator(exe: pathlib.Path, oc: pathlib.Path) -> None:
    if not exe.is_file():
        fail("Matching OpenCore 1.0.8 ocvalidate.exe is required: " + str(exe))
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
    files = validate_archive(pathlib.Path(args.artifact))
    backup_root = pathlib.Path(args.backup_dir)
    try:
        backup_root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        fail("Cannot create backup location: " + str(e))
    if oc.resolve().is_relative_to(backup_root.resolve()) or backup_root.resolve().is_relative_to(oc.resolve()):
        fail("Backups must not be located inside or above the live OC folder")
    if os.name == "nt" and backup_root.drive.lower() == oc.drive.lower():
        fail("Keep backup on Windows C:, not on the mounted EFI drive")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = backup_root / ("SL4-INPUT-" + stamp)
    backup_oc = backup / "OC"
    shutil.copytree(oc, backup_oc)
    if sha256(path) != sha256(backup_oc / "config.plist"):
        fail("Backup verification failed; OC untouched")
    if args.ack != "STAGE-SL4-INPUT":
        fail("Refusing to modify EFI without --ack STAGE-SL4-INPUT. Backup kept at " + str(backup))
    newcfg, changes = kernel_changes(cfg)
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
            for rel, blob in files.items():
                parts = pathlib.PurePosixPath(rel).parts
                if parts[1] != name:
                    continue
                dest = oc / "Kexts" / pathlib.Path(*parts[1:])
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(blob)
        with tempfile.NamedTemporaryFile(dir=oc, prefix="sl4-input-", suffix=".plist", delete=False) as tf:
            staged = pathlib.Path(tf.name)
            plistlib.dump(newcfg, tf, sort_keys=False)
        os.replace(staged, path)
        run_validator(pathlib.Path(args.ocvalidate), oc)
        for name in EXPECTED:
            info = oc / "Kexts" / name / "Contents" / "Info.plist"
            if info.read_bytes() != files["out/" + name + "/Contents/Info.plist"]:
                fail("Bundle changed during staging: " + name)
    except BaseException:
        print("STAGE FAILED: automatically restoring the full OC directory from backup")
        # Keep the old full OC state intact on C: even if restore errors.
        shutil.rmtree(oc)
        shutil.copytree(backup_oc, oc)
        if sha256(path) != sha256(backup_oc / "config.plist"):
            fail("Automatic recovery verification FAILED; restore full OC manually from " + str(backup_oc))
        print("RESTORED old OC from", backup)
        raise
    manifest = {"backup": str(backup_oc), "profile": PROFILE, "artifact_sha256": sha256(pathlib.Path(args.artifact)),
                "pre_config_sha256": sha256(backup_oc / "config.plist"), "post_config_sha256": sha256(path),
                "changes": changes}
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("STAGED AND VALIDATED. DO NOT DELETE BACKUP:", backup_oc)
    print("No Windows boot files, disk partitions, firmware entries or graphics boot flags changed.")
    print("Test macOS with external keyboard and mouse available; actual HID function unverified.")


def restore(args: argparse.Namespace, oc: pathlib.Path, path: pathlib.Path) -> None:
    if args.ack != "RESTORE-SL4-INPUT":
        fail("Restoring requires explicit --ack RESTORE-SL4-INPUT")
    if not args.backup:
        fail("--backup path to the saved SL4-INPUT-* backup directory is required")
    backup = pathlib.Path(args.backup)
    if os.name == "nt" and backup.drive.lower() == oc.drive.lower():
        fail("Backup on EFI drive is unsafe; refusing restore")
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
    last = backup.parent / ("SL4-INPUT-BEFORE-RESTORE-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
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
    print("Windows EFI, partitions and boot-order unchanged")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("inspect", "apply", "restore"), default="inspect")
    p.add_argument("--efi", type=pathlib.Path, required=True, help="Windows-mounted internal ESP/EFI, e.g. S:\\EFI")
    p.add_argument("--artifact", type=pathlib.Path, help="GitHub Actions downloaded experimental kext artifact ZIP")
    p.add_argument("--backup", type=pathlib.Path, help="Private SL4-INPUT-* backup folder, for restore mode")
    p.add_argument("--backup-dir", type=pathlib.Path, help="Private backup directory on Windows C:")
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
            fail("--backup-dir on Windows system disk required")
        apply(args, oc, path, cfg)
    elif args.mode == "restore":
        restore(args, oc, path)
    else:
        print("READ ONLY: no changes made. Use --mode apply only after successful CI build and hardware review.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, zipfile.BadZipFile, plistlib.InvalidFileException) as exc:
        print("STOP:", exc, file=sys.stderr)
        sys.exit(1)
