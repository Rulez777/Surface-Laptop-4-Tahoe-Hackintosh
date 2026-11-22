#!/usr/bin/env python3
"""Build a personal OpenCore EFI for Surface Laptop 4 (Intel Tiger Lake).

Downloads pinned releases from original maintainers. Never writes to any disk
partition; output is an ordinary local directory.
"""
import argparse
import base64
import io
import lzma
import pathlib
import plistlib
import re
import shutil
import subprocess
import sys
import urllib.request
import uuid
import zipfile
from dvmt60 import DVMT_ARG, is_ready as dvmt60_ready, stage as stage_dvmt60

HERE = pathlib.Path(__file__).resolve().parent.parent
RELEASES = {
    "OpenCore": "https://github.com/acidanthera/OpenCorePkg/releases/download/1.0.8/OpenCore-1.0.8-RELEASE.zip",
    "Lilu.kext": "https://github.com/acidanthera/Lilu/releases/download/1.7.2/Lilu-1.7.2-RELEASE.zip",
    "VirtualSMC.kext": "https://github.com/acidanthera/VirtualSMC/releases/download/1.3.8/VirtualSMC-1.3.8-RELEASE.zip",
    "WhateverXe.kext": "https://github.com/b00t0x/WhateverXe/releases/download/0.8.3/WhateverXe-0.8.3-RELEASE.zip",
    "AMFIAnchor.kext": "https://github.com/b00t0x/AMFIAnchor/releases/download/0.1.2/AMFIAnchor-0.1.2-Release.zip",
    "USBToolBox.kext": "https://github.com/USBToolBox/kext/releases/download/1.2.0/USBToolBox-1.2.0-RELEASE.zip",
}
HFSPLUS = "https://raw.githubusercontent.com/acidanthera/OcBinaryData/master/Drivers/HfsPlus.efi"
GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def download(url, cache):
    output = cache / url.rsplit("/", 1)[-1]
    if not output.is_file():
        print("Downloading:", url)
        request = urllib.request.Request(url, headers={"User-Agent": "SL4-Tahoe-EFI-Builder/1.0"})
        with urllib.request.urlopen(request, timeout=180) as response, output.open("wb") as file:
            shutil.copyfileobj(response, file)
    require(output.stat().st_size > 64, "Download empty or invalid: " + str(output))
    return output.read_bytes()


def open_zip(name, cache):
    raw = download(RELEASES[name], cache)
    require(zipfile.is_zipfile(io.BytesIO(raw)), "Not a ZIP: " + name)
    return zipfile.ZipFile(io.BytesIO(raw))


def read_zip_suffix(archive, suffix):
    matches = [name for name in archive.namelist() if name.replace("\\", "/").endswith(suffix)]
    require(bool(matches), "Upstream archive missing: " + suffix)
    return archive.read(min(matches, key=len))


def unpack_kext(archive, name, root):
    found = 0
    for member in archive.namelist():
        parts = pathlib.PurePosixPath(member.replace("\\", "/")).parts
        if name not in parts or member.endswith("/"):
            continue
        relative = pathlib.PurePosixPath(*parts[parts.index(name) + 1:]).parts
        require(relative and ".." not in relative, "Invalid kext path: " + member)
        destination = root / name
        for part in relative:
            destination = destination / part
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(archive.read(member))
        found += 1
    require(found > 0 and (root / name / "Contents/Info.plist").is_file(), "Incomplete kext: " + name)
    print("Added:", name)


def restore_seed(root):
    # Binary stream: uint16 path length + UTF-8 path + uint32 content length + content.
    raw = lzma.decompress(base64.b64decode((HERE / "data/seed.lzma.b64").read_text(encoding="ascii")))
    offset = 0
    count = 0
    while offset < len(raw):
        require(offset + 2 <= len(raw), "Truncated seed path header")
        path_size = int.from_bytes(raw[offset:offset + 2], "little")
        offset += 2
        require(0 < path_size < 256 and offset + path_size + 4 <= len(raw), "Invalid seed path")
        relative = pathlib.PurePosixPath(raw[offset:offset + path_size].decode("utf-8"))
        offset += path_size
        length = int.from_bytes(raw[offset:offset + 4], "little")
        offset += 4
        require(offset + length <= len(raw), "Truncated seed content")
        require(not relative.is_absolute() and ".." not in relative.parts, "Unsafe seed path")
        path = root.joinpath(*relative.parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw[offset:offset + length])
        offset += length
        count += 1
    require(count == 6, "Unexpected seed files: " + str(count))


def surface_rtc0(aml):
    require(len(aml) > 36 and aml[:4] == b"SSDT", "Invalid ACPI sample")
    require(int.from_bytes(aml[4:8], "little") == len(aml) and sum(aml) % 256 == 0, "Invalid ACPI checksum")
    body = aml[36:]
    require(1 <= body.count(b"PCI0") <= 4 and b"LPCB" in body and b"RTC0" in body, "Unexpected RTC0 sample path")
    require(bytes.fromhex("41D00B00") in body, "No PNP0B00 in compiled RTC sample")
    patched = bytearray(aml[:36] + body.replace(b"PCI0", b"PC00"))
    patched[9] = 0
    patched[9] = (-sum(patched)) & 255
    require(sum(patched) % 256 == 0, "Patched ACPI checksum failed")
    return bytes(patched)


def validate_tree(root, config):
    for item in config["ACPI"]["Add"]:
        if item["Enabled"]:
            require((root / "OC/ACPI" / item["Path"]).is_file(), "Missing ACPI: " + item["Path"])
    for item in config["UEFI"]["Drivers"]:
        if item["Enabled"]:
            require((root / "OC/Drivers" / item["Path"]).is_file(), "Missing driver: " + item["Path"])
    for item in config["Kernel"]["Add"]:
        if not item["Enabled"]:
            continue
        bundle = root / "OC/Kexts" / item["BundlePath"]
        require((bundle / item["PlistPath"]).is_file(), "Missing kext plist: " + item["BundlePath"])
        if item.get("ExecutablePath"):
            require((bundle / item["ExecutablePath"]).is_file(), "Missing kext executable: " + item["BundlePath"])


def main():
    cli = argparse.ArgumentParser(description="Generate personal Surface Laptop 4 EFI (i7-1185G7)")
    cli.add_argument("--serial", required=True, help="Generate with GenSMBIOS; keep private")
    cli.add_argument("--mlb", required=True, help="Generate with GenSMBIOS; keep private")
    cli.add_argument("--uuid", required=True, help="Generate with GenSMBIOS; keep private")
    cli.add_argument("--rom", required=True, help="Exactly 12 hexadecimal digits; keep private")
    cli.add_argument("--verbose-boot", action="store_true", help="Keep initial diagnostic boot output instead of the default quiet boot")
    cli.add_argument("--dvmt-60", action="store_true", help="Stage tested Surface Iris Xe GGC 0xFEC1 (60 MB) settings; keep -wex-noaccel until Graphics pkg is installed")
    cli.add_argument("--out", type=pathlib.Path, default=pathlib.Path("EFI-output"))
    cli.add_argument("--cache", type=pathlib.Path, default=pathlib.Path(".efi-build-cache"))
    args = cli.parse_args()
    require(re.fullmatch("[A-Za-z0-9]{8,32}", args.serial) is not None, "Invalid serial")
    require(re.fullmatch("[A-Za-z0-9]{8,32}", args.mlb) is not None, "Invalid MLB")
    try:
        uid = str(uuid.UUID(args.uuid)).upper()
        rom = bytes.fromhex(args.rom)
    except ValueError as exc:
        raise RuntimeError("Invalid UUID or ROM") from exc
    require(len(rom) == 6 and any(rom) and uuid.UUID(uid).int, "Invalid ROM/UUID")
    target = args.out.resolve()
    require(not target.exists(), "Output directory already exists: " + str(target))
    cache = args.cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    root = target / "EFI"
    restore_seed(root)
    oc = open_zip("OpenCore", cache)
    for suffix, path in [
        ("X64/EFI/BOOT/BOOTx64.efi", root / "BOOT/BOOTx64.efi"),
        ("X64/EFI/OC/OpenCore.efi", root / "OC/OpenCore.efi"),
        ("X64/EFI/OC/Drivers/OpenRuntime.efi", root / "OC/Drivers/OpenRuntime.efi"),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(read_zip_suffix(oc, suffix))
    rtc = surface_rtc0(read_zip_suffix(oc, "Docs/AcpiSamples/Binaries/SSDT-RTC0.aml"))
    (root / "OC/ACPI/SSDT-RTC0-SL4.aml").write_bytes(rtc)
    (root / "OC/Drivers/HfsPlus.efi").write_bytes(download(HFSPLUS, cache))
    for name in RELEASES:
        if name.endswith(".kext"):
            unpack_kext(open_zip(name, cache), name, root / "OC/Kexts")
    cfg = root / "OC/config.plist"
    settings = plistlib.loads(cfg.read_bytes())
    settings["ACPI"]["Add"].append({"Comment": "Surface Laptop 4 RTC0 at PC00.LPCB", "Enabled": True, "Path": "SSDT-RTC0-SL4.aml"})
    settings["PlatformInfo"]["Generic"].update({"SystemSerialNumber": args.serial, "MLB": args.mlb, "SystemUUID": uid, "ROM": rom})
    if args.dvmt_60:
        for change in stage_dvmt60(settings):
            print("60 MB DVMT:", change)
        boot_args = settings["NVRAM"]["Add"][GUID]["boot-args"].split()
        require("-wex-noaccel" in boot_args, "60 MB DVMT builder output must remain in no-accel mode until Graphics pkg installation")
        if DVMT_ARG not in boot_args:
            boot_args.append(DVMT_ARG)
        settings["NVRAM"]["Add"][GUID]["boot-args"] = " ".join(boot_args)
        require(dvmt60_ready(settings), "DVMT profile validation failed")
        print("60 MB DVMT prepared; -wex-noaccel remains ON until Graphics pkg installation")
    if not args.verbose_boot:
        from quiet_boot import edit as quiet_profile
        quiet_profile(settings)
        print("Quiet boot: no verbose diagnostics, 4-second picker, Ctrl+Enter can select macOS as default")
    cfg.write_bytes(plistlib.dumps(settings, sort_keys=False))
    validate_tree(root, settings)
    try:
        validator = read_zip_suffix(oc, "Utilities/ocvalidate/ocvalidate.exe")
        validator_path = cache / "ocvalidate-1.0.8.exe"
        validator_path.write_bytes(validator)
        if sys.platform == "win32":
            result = subprocess.run([str(validator_path), str(cfg)], capture_output=True, text=True)
            print(result.stdout, result.stderr)
            require(result.returncode == 0, "ocvalidate rejected config")
    except RuntimeError:
        raise
    print("SUCCESS:", root)
    print("PERSONAL EFI GENERATED: fresh builds are NOT independently boot-verified; preserve the working internal EFI.")
    print("Use docs/VALIDATED-METAL-SL4.md for the post-install internal-SSD Metal path.")
    print("Never publish personal SMBIOS data or copy a new build over a working boot EFI without rollback.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("ERROR:", error, file=sys.stderr)
        sys.exit(1)
