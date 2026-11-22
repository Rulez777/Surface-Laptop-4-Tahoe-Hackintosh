#!/usr/bin/env python3
"""Prepare an offline peripheral-driver test bundle for Intel Surface Laptop 4.

No writes to the EFI System Partition, macOS installation, NVRAM or BCD.
Downloads upstream candidates into an isolated directory, without enabling
unverified kernel extensions. The graphics package must be installed in macOS.
"""
import argparse
from datetime import datetime
import hashlib
import json
import zipfile
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import urllib.request

GRAPHICS_URL = "https://github.com/b00t0x/WhateverXe-Graphics/releases/download/v0.4.4/WhateverXe-Graphics-0.4.4.pkg"
GRAPHICS_SHA256 = "f4c2d680a7c52c33a3f038ce6945da0aa2cc044e62b935a52ea046c7c473cfec"
GRAPHICS_SIZE = 95215914
IPTS_URL = "https://github.com/Xiashangning/IPTSDaemon/releases/download/v1.4/IPTSDaemon.zip"
OC_URL = "https://github.com/acidanthera/OpenCorePkg/releases/download/1.0.8/OpenCore-1.0.8-RELEASE.zip"
OC_SHA256 = "2011e8b7216ecb2645d97ea710df965947edd406846e92050b9bc4190be6d27b"
OC_SIZE = 10544084


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def asset_valid(path, expected_size, expected_sha):
    try:
        if not path.is_file() or (expected_size is not None and path.stat().st_size != expected_size):
            return False
        if expected_sha and hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
            return False
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                if archive.testzip() is not None:
                    return False
        return True
    except (OSError, zipfile.BadZipFile, RuntimeError):
        return False


def fetch(url, path, expected_size=None, expected_sha=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not asset_valid(path, expected_size, expected_sha):
        if path.exists():
            print("NOTICE: invalid cached asset, fetching again:", path.name)
        req = urllib.request.Request(url, headers={"User-Agent": "SL4-Tahoe-Driver-Pack/1.0"})
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(prefix=".sl4-", suffix=".part", dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                with urllib.request.urlopen(req, timeout=240) as response:
                    shutil.copyfileobj(response, stream)
            # A temporary .part has no ZIP extension; inspect ZIP by destination type.
            if path.suffix.lower() == ".zip":
                with zipfile.ZipFile(temporary) as archive:
                    require(archive.testzip() is None, "ZIP CRC mismatch: " + path.name)
            require(asset_valid_for_extension(temporary, expected_size, expected_sha),
                    "Pinned size/SHA-256 mismatch for " + path.name)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"file": str(path), "sha256": digest, "bytes": path.stat().st_size, "source": url}


def asset_valid_for_extension(path, expected_size, expected_sha):
    # Used for download temp files, which do not end with .zip.
    return (path.is_file()
            and (expected_size is None or path.stat().st_size == expected_size)
            and (expected_sha is None or hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha))


def main():
    p = argparse.ArgumentParser(description="Get all presently identified Surface Laptop 4 Tahoe driver candidates")
    p.add_argument("--source", type=Path, required=True, help="Existing known-boot private EFI directory, e.g. C:/SL4-personal/EFI")
    p.add_argument("--out", type=Path, default=Path("SL4-Driver-Pack"))
    p.add_argument("--cache", type=Path, default=Path(".optional-driver-cache"))
    args = p.parse_args()
    source = Path(os.path.abspath(str(args.source)))
    require(source.name.upper() == "EFI" and (source / "OC/config.plist").is_file(), "Specify a private, working EFI folder")
    target = Path(os.path.abspath(str(args.out)))
    require(target != source and source not in target.parents, "Output must not be inside the source EFI")
    if target.exists():
        # A previous attempt may have failed while copying a live Windows BCD
        # file. Resume ONLY a recognizable, unfinished output from this script.
        # Preserve the failed EFI copy under a new name rather than deleting it.
        require(target.is_dir() and not target.is_symlink(), "Output is not a normal directory")
        require(not (target / "manifest.json").exists(), "Existing output already finished; choose a new --out")
        allowed = lambda name: name in {"tools", "optional-EFI", "macOS-Installers", "manifest.json.tmp"} or name.startswith("optional-EFI.failed-")
        require(all(allowed(child.name) for child in target.iterdir()), "Unknown files in output; choose a new --out")
        require((target / "tools" / "OpenCore-1.0.8-RELEASE.zip").is_file(),
                "Cannot recognize previous attempt; choose a new --out")
        partial = target / "optional-EFI"
        if partial.exists():
            saved = target / ("optional-EFI.failed-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
            require(not saved.exists(), "Timestamp collision while preserving previous partial output")
            partial.rename(saved)
            print("PRESERVED incomplete driver EFI:", saved)
        print("RESUMING incomplete driver pack:", target)
    else:
        target.mkdir(parents=True)
    tools_dir = target / "tools"
    oc_asset = fetch(OC_URL, tools_dir / "OpenCore-1.0.8-RELEASE.zip", OC_SIZE, OC_SHA256)
    with zipfile.ZipFile(oc_asset["file"]) as oc:
        matches = [name for name in oc.namelist() if name.replace("\\\\", "/").endswith("Utilities/ocvalidate/ocvalidate.exe")]
        require(len(matches) == 1, "OpenCore 1.0.8 ocvalidate.exe missing from official archive")
        validator = tools_dir / "ocvalidate.exe"
        validator.write_bytes(oc.read(matches[0]))
    child = Path(__file__).with_name("add_optional_drivers.py")
    cmd = [sys.executable, str(child), "--source", str(source), "--out", str(target / "optional-EFI"), "--cache", str(args.cache)]
    if sys.platform == "win32":
        cmd += ["--ocvalidate", str(validator)]
    subprocess.run(cmd, check=True)
    graphics_dir = target / "macOS-Installers"
    graphic = fetch(GRAPHICS_URL, graphics_dir / "WhateverXe-Graphics-0.4.4.pkg", GRAPHICS_SIZE, GRAPHICS_SHA256)
    touch = fetch(IPTS_URL, graphics_dir / "IPTSDaemon-v1.4.zip", 1049971)
    # Do not extract/execute daemon: the upstream release only documents older Surface hardware.
    manifest = {
        "machine": "Surface Laptop 4 Intel Core i7-1185G7, Iris Xe 96 EU (8086:9A49)",
        "status": "Driver candidates. Not a complete, validated, working macOS Tahoe hardware configuration.",
        "installed_macOS": "Tahoe 26.7 or newer required for these WhateverXe Graphics releases.",
        "graphics": graphic,
        "touchscreen_daemon_candidate": touch,
        "staged_efi": str(target / "optional-EFI" / "EFI"),
        "opencore_validator": str(validator),
        "opencore_release_sha256": OC_SHA256,
        "warnings": [
            "The EFI is an experimental copy. Optional kext entries are DISABLED by default.",
            "WhateverXe Graphics is a macOS /Library installer, NOT a kext to copy into EFI.",
            "Do not remove -wex-noaccel until the proper graphics package, SIP and AMFI dependencies are verified.",
            "BigSurface 6.5 and IPTSDaemon 1.4 are from 2023, and neither is qualified for Surface Laptop 4 on Tahoe.",
            "Do not combine BigSurface with VoodooI2C and SMCBatteryManager.",
            "Use the original Kingston EFI as a recovery path. Do not replace the working internal EFI blindly.",
        ],
    }
    # Atomic completion marker: interrupted downloads must remain resumable.
    manifest_tmp = target / "manifest.json.tmp"
    manifest_tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.replace(manifest_tmp, target / "manifest.json")
    print("FULL CANDIDATE DRIVER PACK READY:", target)
    print("Graphics and OpenCore ZIP SHA256 verified against official release asset digests.")
    if sys.platform == "win32":
        print("Generated EFI config checked by official OpenCore 1.0.8 ocvalidate.exe.")
    print("No drivers have been installed into macOS or enabled on the internal EFI.")
    print("Read docs/GRAPHICS-ACCELERATION.md before testing.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(1)
