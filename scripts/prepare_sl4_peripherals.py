#!/usr/bin/env python3
"""Add pinned SL4 Tahoe wireless, audio and telemetry kexts to a new personal EFI.

Downloaded directly from maintainers, with fixed SHA256 of complete releases.
For initial Apple Recovery these optional drivers are STAGED INACTIVE. The
post-install metal/profile assistant enables them once installed Tahoe boots.
No disk mounts, EFI writes outside supplied private staging directory, or BCD.
"""
from __future__ import annotations
import hashlib
import io
import pathlib
import plistlib
import urllib.request
import zipfile

RELEASES = {
 "ForbiddenItlwm.kext": ("https://github.com/retropineaple/ForbiddenItlwm/releases/download/v0.7.0-alpha.3/ForbiddenItlwm-0.7.0-alpha.3-Tahoe.zip","f1c2bd5e99ab94fff4c11eae8dd31f2269bb782a8b961d561e6a1c648d5bce4a"),
 "BTLEAdvFixup.kext": ("https://github.com/retropineaple/ForbiddenItlwm/releases/download/v0.7.0-alpha.3/BTLEAdvFixup-0.9.7-Tahoe.zip","aea22f311c7b60c16186e938870a0ce960aac24bf456ac4657edff08baef935e"),
 "AppleALC.kext": ("https://github.com/acidanthera/AppleALC/releases/download/1.9.8/AppleALC-1.9.8-RELEASE.zip","d4d36cd2da7863cf7cbfcb0892d45c08457f4f4ddd065a073dd010e46bd63bcb"),
 "SimpleHDA.kext": ("https://github.com/laobamac/SimpleHDA/releases/download/v1.0.2/SimpleHDA-Tahoe-v1.0.2-RELEASE.zip","4e24a54ea58bc8196c517bd415b263313512832b6e28c455b97e18490a6230f0"),
 "AirportItlwm.kext": ("https://github.com/laobamac/itlwm/releases/download/v2.4.0-alpha/AirportItlwm-Tahoe-v2.4.0-RELEASE-alpha-7204c69.zip","a5d098e6752592435c021aa6e8d08c64ee6aab9f2786660a6c72d7af1218fcf9"),
 "IntelBluetoothFirmware.kext": ("https://github.com/lshbluesky/IntelBluetoothFirmware/releases/download/v2.5.3/IntelBluetooth-2.5.3-RELEASE.zip","8ae1cad6edf39f524bf5a106b88a2ddfd27744c12612f631b451d4017ff8b70b"),
 "IntelBTPatcher.kext": ("https://github.com/lshbluesky/IntelBluetoothFirmware/releases/download/v2.5.3/IntelBluetooth-2.5.3-RELEASE.zip","8ae1cad6edf39f524bf5a106b88a2ddfd27744c12612f631b451d4017ff8b70b"),
 "BlueToolFixup.kext": ("https://github.com/acidanthera/BrcmPatchRAM/releases/download/2.7.2/BrcmPatchRAM-2.7.2-RELEASE.zip","e1c1c55347526d031a8ae2fdd1f52efa3019161e497fb38e1cfa809752f8af21"),
}

def require(valid,why):
    if not valid:raise RuntimeError(why)

def extract(z, name,root):
    dest=root/"OC/Kexts"/name
    require(not dest.exists(),"Refusing duplicate existing kext: "+name)
    count=0
    for filename in z.namelist():
        if filename.endswith("/"):continue
        parts=pathlib.PurePosixPath(filename.replace("\\","/")).parts
        if name not in parts:continue
        index=parts.index(name)
        tail=parts[index+1:]
        require(tail and ".." not in tail,"Unsafe upstream zip member "+filename)
        target=dest.joinpath(*tail)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(z.read(filename))
        count+=1
    require(count>0 and (dest/"Contents/Info.plist").is_file() and
            (dest/"Contents/MacOS"/name.replace(".kext","")).is_file(),
            "Upstream driver bundle missing required executable: "+name)
    return dest

def prepared_zip(cache, url, expected):
    out=cache/url.rsplit("/",1)[-1]
    if not out.exists():
        request=urllib.request.Request(url,headers={"User-Agent":"SL4-Tahoe-QuickStart/1"})
        partial=out.with_name(out.name+".partial")
        require(not partial.exists(),"Previous partial download exists: "+str(partial))
        with urllib.request.urlopen(request,timeout=160) as stream,partial.open("xb") as f:
            import shutil
            shutil.copyfileobj(stream,f)
        require(hashlib.sha256(partial.read_bytes()).hexdigest()==expected,
                "Driver checksum mismatch: "+url)
        partial.replace(out)
    require(hashlib.sha256(out.read_bytes()).hexdigest()==expected,
            "Cached driver differs from pinned release: "+out.name)
    require(zipfile.is_zipfile(out),"Downloaded driver not a zip")
    return zipfile.ZipFile(out)

def add(efi,config,cache,virtual_smc):
    cache.mkdir(parents=True,exist_ok=True)
    require((efi/"OC/config.plist").is_file(),"EFI config missing")
    names=[x.get("BundlePath") for x in config["Kernel"]["Add"]]
    order=["AppleALC.kext","SimpleHDA.kext","AirportItlwm.kext",
           "IntelBluetoothFirmware.kext","IntelBTPatcher.kext","BlueToolFixup.kext",
           "BTLEAdvFixup.kext","ForbiddenItlwm.kext","SMCProcessor.kext"]
    require(not any(x in names for x in order),"Peripherals already present")
    for name in order:
        if name=="SMCProcessor.kext":
            extract(virtual_smc,name,efi)
        else:
            url,sha=RELEASES[name]
            with prepared_zip(cache,url,sha) as release:
                extract(release,name,efi)
        entry={"Arch":"x86_64","BundlePath":name,
               "Comment":"SL4 Tahoe working peripheral driver (enable after install)",
               "Enabled":False,"ExecutablePath":"Contents/MacOS/"+name[:-5],
               "MaxKernel":"","MinKernel":"","PlistPath":"Contents/Info.plist"}
        if name in ("AirportItlwm.kext","BTLEAdvFixup.kext","ForbiddenItlwm.kext"):
            entry.update(MinKernel="25.0.0",MaxKernel="25.99.99")
        elif name=="BlueToolFixup.kext":
            entry["MinKernel"]="21.0.0"
        config["Kernel"]["Add"].append(entry)
    print("PERIPHERALS STAGED:",", ".join(order)," (initially disabled for Recovery)")
    return order

if __name__=="__main__":
    raise SystemExit("Import and run add() from build_efi.py")
