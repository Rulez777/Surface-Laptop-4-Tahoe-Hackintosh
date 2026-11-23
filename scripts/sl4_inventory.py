#!/usr/bin/env python3
"""Read-only SL4 hardware inventory and strict compatibility assessment.

Outputs an intentionally redacted report. It does NOT read EFI config, generate
SMBIOS identities, alter firmware, mount ESP, or install drivers.
"""
from __future__ import annotations
import argparse
import json
import platform
import plistlib
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
PROFILES = HERE / "data" / "sl4_profiles.json"


def run(argv, *, timeout=30):
    p = subprocess.run(argv, check=False, capture_output=True, timeout=timeout, text=True)
    if p.returncode:
        raise RuntimeError("Probe failed: " + argv[0] + " (" + str(p.returncode) + ")")
    return p.stdout


def load_profiles(path=PROFILES):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("profiles"), list):
        raise ValueError("Unsupported hardware profile manifest")
    return data


def pci_ids(source):
    found = set()
    for m in re.finditer(r"VEN[_: ]?([0-9a-f]{4}).*?DEV[_: ]?([0-9a-f]{4})", source, re.I):
        found.add((m.group(1)+":"+m.group(2)).lower())
    for m in re.finditer(r"(?<![0-9a-f])([0-9a-f]{4}):([0-9a-f]{4})(?![0-9a-f])", source, re.I):
        found.add((m.group(1)+":"+m.group(2)).lower())
    return sorted(found)


def normalize_inventory(data):
    """Discard all unknown keys, particularly system UUIDs and serials."""
    fields = {
        "platform", "manufacturer", "model", "cpu", "gpu_names", "gpu_pci_ids",
        "acpi_ids", "bios_version", "storage_models", "disk_layout",
        "wifi_names", "audio_names", "display", "os_version",
    }
    clean = {key: data.get(key) for key in sorted(fields)}
    for key in ("gpu_names", "gpu_pci_ids", "acpi_ids", "storage_models", "wifi_names", "audio_names"):
        val = clean.get(key)
        clean[key] = [str(s)[:140] for s in val[:20]] if isinstance(val, list) else []
    for key in ("platform", "manufacturer", "model", "cpu", "bios_version", "display", "os_version"):
        clean[key] = str(clean.get(key) or "")[:170]
    if not isinstance(clean.get("disk_layout"), dict):
        clean["disk_layout"] = {}
    # only publish booleans about the partition map, never mount points or private volumes
    clean["disk_layout"] = {k: bool(clean["disk_layout"].get(k, False)) for k in ("esp_present", "windows_partition_present", "apfs_present")}
    return clean


def windows_inventory():
    script = r'''
$ErrorActionPreference="Stop"
$computer=Get-CimInstance Win32_ComputerSystem
$cpu=Get-CimInstance Win32_Processor | Select-Object -First 1
$gpu=@(Get-CimInstance Win32_VideoController | Select-Object Name,PNPDeviceID)
$bios=Get-CimInstance Win32_BIOS | Select-Object -First 1
$disk=@(Get-CimInstance Win32_DiskDrive | Select-Object Model,InterfaceType)
$net=@(Get-CimInstance Win32_NetworkAdapter | Where-Object { $_.PhysicalAdapter } | Select-Object Name)
$audio=@(Get-CimInstance Win32_SoundDevice | Select-Object Name)
$part=@(Get-Partition -ErrorAction SilentlyContinue | Select-Object GptType,Type)
[pscustomobject]@{
platform="win32"; manufacturer=$computer.Manufacturer; model=$computer.Model;
cpu=$cpu.Name; gpu=$gpu; bios_version=$bios.SMBIOSBIOSVersion;
storage=$disk; wifi=$net; audio=$audio; partitions=$part
} | ConvertTo-Json -Depth 6 -Compress
'''
    raw = json.loads(run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], timeout=60))
    graphics = raw.get("gpu") or []
    if isinstance(graphics, dict): graphics = [graphics]
    disks = raw.get("storage") or []
    if isinstance(disks, dict): disks = [disks]
    nics = raw.get("wifi") or []
    if isinstance(nics, dict): nics = [nics]
    audios = raw.get("audio") or []
    if isinstance(audios, dict): audios = [audios]
    parts = raw.get("partitions") or []
    if isinstance(parts, dict): parts = [parts]
    part_text = " ".join(str(p.get("GptType",""))+" "+str(p.get("Type","")) for p in parts)
    return normalize_inventory({
        "platform":"win32", "manufacturer":raw.get("manufacturer",""), "model":raw.get("model",""),
        "cpu":raw.get("cpu",""), "gpu_names":[str(g.get("Name","")) for g in graphics],
        "gpu_pci_ids":pci_ids(" ".join(str(g.get("PNPDeviceID","")) for g in graphics)),
        "acpi_ids":[], "bios_version":raw.get("bios_version",""),
        "storage_models":[str(d.get("Model","")) for d in disks],
        "wifi_names":[str(n.get("Name","")) for n in nics if "Wi-Fi" in str(n.get("Name","")) or "Wireless" in str(n.get("Name","")) or "AX201" in str(n.get("Name",""))],
        "audio_names":[str(a.get("Name","")) for a in audios],
        "os_version":platform.version(), "display":"",
        "disk_layout":{
            "esp_present":"c12a7328-f81f-11d2-ba4b-00a0c93ec93b" in part_text.lower(),
            "windows_partition_present":"Basic" in part_text or "basic" in part_text,
            "apfs_present":"7c3457ef-0000-11aa-aa11-00306543ecac" in part_text.lower()
        },
    })


def _flatten(obj):
    if isinstance(obj, list):
        for x in obj:
            yield from _flatten(x)
    elif isinstance(obj, dict):
        yield obj
        for x in obj.values():
            yield from _flatten(x)


def mac_inventory():
    machine = json.loads(run(["/usr/sbin/system_profiler", "-json", "SPHardwareDataType", "SPDisplaysDataType",
                              "SPNVMeDataType", "SPAirPortDataType", "SPAudioDataType"], timeout=110))
    disp = machine.get("SPDisplaysDataType") or []
    all_disp = list(_flatten(disp))
    gpuis = [d for d in all_disp if "sppci_model" in d or "spdisplays_device-id" in d]
    gpu_names = [str(g.get("sppci_model","")) for g in gpuis]
    # PCI ID: Intel 8086 is a known *visible* vendor string only for reports where
    # system_profiler identifies the device as Intel. Never assume a PCI ID for other GPUs.
    gpu_pci = ["8086:"+m.group(1).lower() for g in gpuis if "intel" in str(g).lower()
               for m in [re.search(r"0x([0-9a-fA-F]{4})", str(g.get("spdisplays_device-id","")))] if m]
    acpi_raw = run(["/usr/sbin/ioreg", "-p", "IOACPIPlane", "-lw0"], timeout=25)
    acpi = [x for x in ("MSHW0250","MSHW0084") if x in acpi_raw]
    controllers = machine.get("SPNVMeDataType") or []
    models = sorted({str(device.get("device_model") or device.get("_name","")) for controller in controllers
                     for device in controller.get("_items",[]) if device.get("device_model") or device.get("_name")})
    partitions = [item for disk in plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil","list","-plist","internal"], timeout=25)).get("AllDisksAndPartitions",[])
                  for item in disk.get("Partitions",[])]
    kinds = {p.get("Content","") for p in partitions}
    screens = [d for d in all_disp if d.get("_name") and (d.get("spdisplays_resolution") or d.get("spdisplays_pixels"))]
    wireless = list(_flatten(machine.get("SPAirPortDataType") or []))
    audio = list(_flatten(machine.get("SPAudioDataType") or []))
    return normalize_inventory({
        "platform":"darwin",
        "manufacturer":"Microsoft Corporation" if "MSHW0250" in acpi else "unverified",
        "model":"Surface Laptop 4 Intel (ACPI verified)" if set(acpi)=={"MSHW0250","MSHW0084"} else "unverified",
        "cpu":run(["/usr/sbin/sysctl","-n","machdep.cpu.brand_string"]).strip(),
        "gpu_names":gpu_names, "gpu_pci_ids":sorted(set(gpu_pci)),
        "acpi_ids":acpi, "bios_version":"", "storage_models":models,
        "wifi_names":sorted({str(x.get("_name")) for x in wireless if "ax201" in str(x).lower()})[:10],
        "audio_names":sorted({str(x.get("_name")) for x in audio if "alc" in str(x).lower()})[:10],
        "display":str(screens[0].get("spdisplays_resolution") or screens[0].get("spdisplays_pixels")) if screens else "",
        "os_version":run(["/usr/bin/sw_vers","-productVersion"]).strip(),
        "disk_layout":{"esp_present":"EFI" in kinds,"windows_partition_present":"Microsoft Basic Data" in kinds,"apfs_present":"Apple_APFS" in kinds},
    })


def assess(inv, manifest):
    reasons = []
    profiles = manifest["profiles"]
    for candidate in profiles:
        missing = []
        if candidate["manufacturer"].lower() not in inv["manufacturer"].lower():
            missing.append("manufacturer")
        if not all(key.lower() in inv["model"].lower() for key in candidate["model_keywords"]):
            missing.append("model")
        if candidate["cpu_keyword"].lower() not in inv["cpu"].lower():
            missing.append("cpu")
        if candidate["gpu_pci_id"].lower() not in [v.lower() for v in inv["gpu_pci_ids"]]:
            missing.append("gpu_pci_id")
        if inv["platform"]=="darwin" and not all(x in inv["acpi_ids"] for x in candidate["acpi_ids"]):
            missing.append("acpi_ids")
        if missing:
            reasons.append({"profile":candidate["id"],"missing_or_mismatched":missing})
            continue
        storage_ok = any(keyword.lower() in model.lower() for keyword in candidate["tested_storage_keywords"] for model in inv["storage_models"])
        return {"status":"hardware_match_requires_manual_review" if storage_ok else "variant_requires_manual_review",
                "profile":candidate["id"],
                "reason":"Exact CPU/GPU/model IDs match; this is not clean-install or ESP-write certification.",
                "storage_matches_test_machine":storage_ok,
                "automatic_install_allowed":False,
                "full_system_sleep_verified":False}
    return {"status":"unsupported_or_insufficient_evidence","profile":None,
            "reason":"No tested hardware profile matched; fail closed.",
            "missing":reasons, "automatic_install_allowed":False,
            "full_system_sleep_verified":False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixture",type=Path,help="Test only: inspect a JSON inventory, no local hardware probe")
    p.add_argument("--output",type=Path,help="Save a non-secret report; refuses to overwrite")
    args=p.parse_args(argv)
    if args.fixture:
        inv=normalize_inventory(json.loads(args.fixture.read_text(encoding="utf-8")))
    elif sys.platform=="win32":
        inv=windows_inventory()
    elif sys.platform=="darwin":
        inv=mac_inventory()
    else:
        raise RuntimeError("Only Windows and macOS supported; fixture mode is portable")
    data={"inventory":inv,"compatibility":assess(inv,load_profiles())}
    rendered=json.dumps(data,ensure_ascii=False,indent=2)+"\n"
    if args.output:
        if args.output.exists(): raise RuntimeError("Refusing to overwrite report")
        args.output.write_text(rendered,encoding="utf-8")
        print("Read-only report:",args.output)
    else: print(rendered,end="")
    return 0


if __name__=="__main__":
    try: sys.exit(main())
    except (RuntimeError,ValueError,OSError,subprocess.SubprocessError) as ex:
        print("STOP:",ex,file=sys.stderr)
        sys.exit(1)
