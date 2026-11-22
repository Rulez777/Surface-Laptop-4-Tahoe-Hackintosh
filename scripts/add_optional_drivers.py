#!/usr/bin/env python3
"""Stage optional Surface Laptop 4 drivers in a COPY of a personalized OpenCore EFI.

Never touches any EFI System Partition, boot order, or tested EFI.
Downloads selected upstream release archives; additional kext entries start disabled.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import pathlib
import plistlib
import shutil
import subprocess
import sys
import urllib.request
import zipfile

RELEASES = {
    "AppleALC": ("https://github.com/acidanthera/AppleALC/releases/download/1.9.8/AppleALC-1.9.8-RELEASE.zip", ["AppleALC.kext"]),
    "AirportItlwm-Tahoe": ("https://github.com/laobamac/itlwm/releases/download/v2.4.0-alpha/AirportItlwm-Tahoe-v2.4.0-RELEASE-alpha-7204c69.zip", ["AirportItlwm.kext"]),
    "IntelBluetooth": ("https://github.com/OpenIntelWireless/IntelBluetoothFirmware/releases/download/v2.4.0/IntelBluetooth-v2.4.0.zip", ["IntelBluetoothFirmware.kext", "IntelBTPatcher.kext"]),
    "BlueToolFixup": ("https://github.com/acidanthera/BrcmPatchRAM/releases/download/2.7.2/BrcmPatchRAM-2.7.2-RELEASE.zip", ["BlueToolFixup.kext"]),
    "SMCBatteryManager": ("https://github.com/acidanthera/VirtualSMC/releases/download/1.3.8/VirtualSMC-1.3.8-RELEASE.zip", ["SMCBatteryManager.kext"]),
    "VoodooPS2": ("https://github.com/acidanthera/VoodooPS2/releases/download/2.3.7/VoodooPS2Controller-2.3.7-RELEASE.zip", ["VoodooPS2Controller.kext"]),
    "VoodooI2C": ("https://github.com/VoodooI2C/VoodooI2C/releases/download/v2.9.1/VoodooI2C-2.9.1-RELEASE.zip", ["VoodooI2C.kext", "VoodooI2CHID.kext"]),
    "BigSurface": ("https://github.com/Xiashangning/BigSurface/releases/download/v6.5/BigSurface.zip", ["BigSurface.kext"]),
}
# Names to enable with --enable; never enable BigSurface or Voodoo input automatically.
PROFILES = {
    "audio": ["AppleALC.kext"],
    "wifi": ["AirportItlwm.kext"],
    "bluetooth": ["IntelBluetoothFirmware.kext", "BlueToolFixup.kext"],
}
TAHOE_ONLY = {"AirportItlwm.kext"}
# Kexts requiring additional checks, ACPI, hardware matching, or Tahoe compatibility tests.
MANUAL_ONLY = {"BigSurface.kext", "VoodooPS2Controller.kext", "VoodooI2C.kext",
               "VoodooI2CHID.kext", "SMCBatteryManager.kext", "IntelBTPatcher.kext"}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def cached_download(url, cache):
    output = cache / url.rsplit("/", 1)[-1]
    if not output.is_file():
        print("Downloading", url)
        req = urllib.request.Request(url, headers={"User-Agent": "SL4-Optional-Kexts/1.0"})
        with urllib.request.urlopen(req, timeout=180) as response, output.open("wb") as f:
            shutil.copyfileobj(response, f)
    raw = output.read_bytes()
    require(len(raw) > 100 and zipfile.is_zipfile(io.BytesIO(raw)), "Invalid ZIP from " + url)
    return zipfile.ZipFile(io.BytesIO(raw))


def find_files(archive, kext_name):
    # Handle both a release with the kext at root and archives with release folders.
    prefix = kext_name + "/"
    matches = []
    for entry in archive.namelist():
        normal = entry.replace("\\", "/")
        if normal.endswith("/") or normal.startswith("/") or ".." in pathlib.PurePosixPath(normal).parts:
            continue
        if normal.startswith(prefix):
            matches.append((normal[len(prefix):], entry))
        elif "/" + prefix in normal:
            matches.append((normal.split("/" + prefix, 1)[1], entry))
    # If a zip has different Debug/Release variants, prefer RELEASE by sorting parent paths.
    matches.sort(key=lambda x: ("debug" in x[1].lower(), len(x[1])))
    return matches


def unpack_one(archive, name, dst):
    matches = find_files(archive, name)
    if not matches:
        print("NOTICE: upstream release does not contain", name, "- skipped")
        return False
    dest = dst / name
    seen = set()
    for relative, source in matches:
        if not relative or relative in seen:
            continue
        seen.add(relative)
        path = dest.joinpath(*pathlib.PurePosixPath(relative).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(archive.read(source))
    ok = (dest / "Contents/Info.plist").is_file()
    if not ok:
        shutil.rmtree(dest, ignore_errors=True)
        print("NOTICE: no Info.plist in", name, "- skipped")
    else:
        print("Staged:", name)
    return ok


def register(config, folder, name, enabled):
    info = plistlib.loads((folder / name / "Contents/Info.plist").read_bytes())
    executable = info.get("CFBundleExecutable", "")
    binary = "Contents/MacOS/" + executable if executable else ""
    if binary:
        require((folder / name / binary).is_file(), "Missing kext executable " + name + " / " + binary)
    entries = config["Kernel"]["Add"]
    old = next((x for x in entries if x.get("BundlePath") == name), None)
    if old:
        if enabled:
            old["Enabled"] = True
        return
    entry = {
        "Arch": "Any", "BundlePath": name, "Comment": "Optional, not verified on Surface Laptop 4 + Tahoe",
        "Enabled": enabled, "ExecutablePath": binary, "MaxKernel": "25.99.99" if name in TAHOE_ONLY else "",
        "MinKernel": "25.0.0" if name in TAHOE_ONLY else "", "PlistPath": "Contents/Info.plist"
    }
    entries.append(entry)


def main():
    p = argparse.ArgumentParser(description="Build a peripheral-test EFI alongside a known-good boot EFI.")
    p.add_argument("--source", type=pathlib.Path, required=True, help="Path to private, known-good EFI directory")
    p.add_argument("--out", type=pathlib.Path, default=pathlib.Path("EFI-peripherals"))
    p.add_argument("--cache", type=pathlib.Path, default=pathlib.Path(".optional-driver-cache"))
    p.add_argument("--enable", default="", help="Opt-in groups: audio,wifi,bluetooth (experimental)")
    p.add_argument("--ocvalidate", type=pathlib.Path, help="Matching OpenCore 1.0.8 ocvalidate.exe path (optional but strongly recommended)")
    args = p.parse_args()
    enabled_groups = [x.strip() for x in args.enable.split(",") if x.strip()]
    require(all(x in PROFILES for x in enabled_groups), "Allowed groups: audio,wifi,bluetooth. Surface input requires manual ACPI work.")
    enabled_names = {n for g in enabled_groups for n in PROFILES[g]}
    source = args.source.resolve()
    require(source.name.upper() == "EFI" and (source / "OC/config.plist").is_file(), "--source must be a personal EFI directory")
    cfg_in = plistlib.loads((source / "OC/config.plist").read_bytes())
    require(any(a.get("Enabled") and a.get("Path") == "SSDT-RTC0-SL4.aml" for a in cfg_in["ACPI"]["Add"]),
            "Source EFI is missing the Surface RTC0 fix")
    target = args.out.resolve()
    require(not target.exists(), "Output already exists; never overwrite a known-good EFI")
    target.mkdir(parents=True)
    root = target / "EFI"
    shutil.copytree(source, root)
    cache = args.cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    config_path = root / "OC/config.plist"
    config = plistlib.loads(config_path.read_bytes())
    kext_root = root / "OC/Kexts"
    for label, (url, names) in RELEASES.items():
        archive = cached_download(url, cache)
        for name in names:
            if unpack_one(archive, name, kext_root):
                register(config, kext_root, name, name in enabled_names)
    require(all((kext_root / n / "Contents/Info.plist").is_file() for n in enabled_names),
            "One or more requested driver groups missing from upstream releases")
    # Never load WhateverGreen alongside WhateverXe.
    require(not any(x.get("BundlePath") == "WhateverGreen.kext" and x.get("Enabled") for x in config["Kernel"]["Add"]),
            "WhateverGreen conflicts with the working WhateverXe EFI")
    # Keep surface-specific input stacks disabled until there is an appropriate ACPI mapping.
    for x in config["Kernel"]["Add"]:
        if x.get("BundlePath") in MANUAL_ONLY:
            x["Enabled"] = False
    config_path.write_bytes(plistlib.dumps(config, sort_keys=False))
    # Ensure every enabled bundle references real files.
    for x in config["Kernel"]["Add"]:
        if x.get("Enabled"):
            d = kext_root / x["BundlePath"]
            require((d / x["PlistPath"]).is_file(), "Missing Info.plist: " + x["BundlePath"])
            if x.get("ExecutablePath"):
                require((d / x["ExecutablePath"]).is_file(), "Missing executable: " + x["BundlePath"])
    if args.ocvalidate:
        validator = args.ocvalidate.resolve()
        require(validator.is_file(), "ocvalidate binary not found")
        check = subprocess.run([str(validator), str(config_path)], capture_output=True, text=True)
        print(check.stdout, check.stderr)
        require(check.returncode == 0, "ocvalidate failed; do not boot this EFI")
    else:
        print("WARNING: no ocvalidate was run; provide --ocvalidate on Windows before testing")
    print("SUCCESS: experimental copy at", root)
    print("Config SHA256:", hashlib.sha256(config_path.read_bytes()).hexdigest())
    print("Enabled peripheral groups:", ",".join(enabled_groups) or "none")
    print("Keyboard/trackpad/BigSurface remain DISABLED until Surface Laptop 4 Tahoe ACPI and SAM support can be checked.")
    print("Run OpenCore 1.0.8 ocvalidate before every test. Keep the original EFI backed up.")
    print("No internal disk, NVRAM, boot order, or live EFI was changed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR:", str(exc), file=sys.stderr)
        sys.exit(1)
