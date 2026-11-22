#!/usr/bin/env python3
"""Prepare an offline peripheral-driver test bundle for Intel Surface Laptop 4.

No writes to the EFI System Partition, macOS installation, NVRAM or BCD.
Downloads upstream candidates into an isolated directory, without enabling
unverified kernel extensions. The graphics package must be installed in macOS.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

GRAPHICS_URL = "https://github.com/b00t0x/WhateverXe-Graphics/releases/download/v0.4.4/WhateverXe-Graphics-0.4.4.pkg"
GRAPHICS_SHA256 = "f4c2d680a7c52c33a3f038ce6945da0aa2cc044e62b935a52ea046c7c473cfec"
GRAPHICS_SIZE = 95215914
IPTS_URL = "https://github.com/Xiashangning/IPTSDaemon/releases/download/v1.4/IPTSDaemon.zip"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def fetch(url, path, expected_size=None, expected_sha=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        req = urllib.request.Request(url, headers={"User-Agent": "SL4-Tahoe-Driver-Pack/1.0"})
        with urllib.request.urlopen(req, timeout=240) as response, path.open("wb") as stream:
            import shutil
            shutil.copyfileobj(response, stream)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_size is not None:
        require(path.stat().st_size == expected_size, "Unexpected download size for " + path.name)
    if expected_sha is not None:
        require(digest == expected_sha, "SHA256 mismatch for " + path.name)
    return {"file": str(path), "sha256": digest, "bytes": path.stat().st_size, "source": url}


def main():
    p = argparse.ArgumentParser(description="Get all presently identified Surface Laptop 4 Tahoe driver candidates")
    p.add_argument("--source", type=Path, required=True, help="Existing known-boot private EFI directory, e.g. C:/SL4-personal/EFI")
    p.add_argument("--out", type=Path, default=Path("SL4-Driver-Pack"))
    p.add_argument("--cache", type=Path, default=Path(".optional-driver-cache"))
    args = p.parse_args()
    source = Path(os.path.abspath(str(args.source)))
    require(source.name.upper() == "EFI" and (source / "OC/config.plist").is_file(), "Specify a private, working EFI folder")
    target = Path(os.path.abspath(str(args.out)))
    require(not target.exists(), "Output exists; refusing to overwrite: " + str(target))
    require(target != source and source not in target.parents, "Output must not be inside the source EFI")
    target.mkdir(parents=True)
    child = Path(__file__).with_name("add_optional_drivers.py")
    subprocess.run([sys.executable, str(child), "--source", str(source), "--out", str(target / "optional-EFI"), "--cache", str(args.cache)], check=True)
    graphics_dir = target / "macOS-Installers"
    graphic = fetch(GRAPHICS_URL, graphics_dir / "WhateverXe-Graphics-0.4.4.pkg", GRAPHICS_SIZE, GRAPHICS_SHA256)
    touch = fetch(IPTS_URL, graphics_dir / "IPTSDaemon-v1.4.zip")
    # Do not extract/execute daemon: the upstream release only documents older Surface hardware.
    manifest = {
        "machine": "Surface Laptop 4 Intel Core i7-1185G7, Iris Xe 96 EU (8086:9A49)",
        "status": "Driver candidates. Not a complete, validated, working macOS Tahoe hardware configuration.",
        "installed_macOS": "Tahoe 26.7 or newer required for these WhateverXe Graphics releases.",
        "graphics": graphic,
        "touchscreen_daemon_candidate": touch,
        "staged_efi": str(target / "optional-EFI" / "EFI"),
        "warnings": [
            "The EFI is an experimental copy. Optional kext entries are DISABLED by default.",
            "WhateverXe Graphics is a macOS /Library installer, NOT a kext to copy into EFI.",
            "Do not remove -wex-noaccel until the proper graphics package, SIP and AMFI dependencies are verified.",
            "BigSurface 6.5 and IPTSDaemon 1.4 are from 2023, and neither is qualified for Surface Laptop 4 on Tahoe.",
            "Do not combine BigSurface with VoodooI2C and SMCBatteryManager.",
            "Use the original Kingston EFI as a recovery path. Do not replace the working internal EFI blindly.",
        ],
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("FULL CANDIDATE DRIVER PACK READY:", target)
    print("Graphics SHA256 verified against the official v0.4.4 GitHub release asset digest.")
    print("No drivers have been installed into macOS or enabled on the internal EFI.")
    print("Read docs/GRAPHICS-ACCELERATION.md before testing.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(1)
