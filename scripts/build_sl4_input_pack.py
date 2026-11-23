#!/usr/bin/env python3
"""Package reproducibly built GPL-3 SL4 Surface input kernel drivers.

The source build is in experiments/sl4-input/build-bigsurface-sl4.py, using
pinned upstream GPL repositories + source patches. Never package private EFI
or copy SMBIOS/config.plist from any host.
"""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

NAMES=("VoodooGPIO","VoodooSerial","VoodooInput","BigSurface","BigSurfaceHIDDriver")
EXE_SHA={
 "VoodooGPIO":"2a5985ab5ea62484db8f3826fcbb7968e00b81352ea82ba2b220670f615a65c1",
 "VoodooSerial":"145cb334cddabd6302f449290b50cc682b4a97c9d26902a8cd9df460bb3086c7",
 "VoodooInput":"f772700526394d9a46422ba5b997236140001d8d6384df8658427cc6e30adc6b",
 "BigSurface":"e27c21b6ccc2e8fbecb5bf62222b6e157369e49f666dec1d1803549afeba5dc6",
 "BigSurfaceHIDDriver":"c7c2fa0c91cfe615964758f48fd3f816f179a8ce30d98f302d4482bcd1c2aa09",
}
PACKAGE="SL4-TGL-Input-Working-v1.zip"

def digest(data):
    return hashlib.sha256(data).hexdigest()

def assemble(source,licenses,out):
    if out.exists():raise ValueError("Refusing overwrite "+str(out))
    content={}
    for name in NAMES:
        base=source/(name+".kext")
        for relative in ("Contents/Info.plist","Contents/MacOS/"+name):
            file=base/relative
            if not file.is_file():raise ValueError("Missing compiled kext file "+str(file))
            data=file.read_bytes()
            if relative.endswith("/"+name) and digest(data)!=EXE_SHA[name]:
                raise ValueError("Unrecognized executable for "+name)
            content["Kexts/"+name+".kext/"+relative]=data
    notices={
      "BigSurface-GPL3.txt":licenses/"LICENSE.txt",
      "VoodooGPIO-GPL3.md":licenses/"Dependencies/VoodooGPIO/LICENSE.md",
      "VoodooSerial-GPL3.txt":licenses/"Dependencies/VoodooSerial/LICENSE.txt",
      "BigSurfaceHIDDriver-GPL3.txt":licenses/"Dependencies/BigSurfaceHIDDriver/LICENSE",
    }
    for name,path in notices.items():
        if not path.is_file() or path.stat().st_size<500:raise ValueError("Missing GPL notice: "+str(path))
        content["LICENSES/"+name]=path.read_bytes()
    content["SOURCE.txt"]=(
        "Surface Laptop 4 Intel (i7-1185G7, Tiger Lake) kernel driver build.\n"
        "GPL-3.0-or-later, source and complete, pinned reproducible build steps:\n"
        "https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/blob/main/"
        "experiments/sl4-input/build-bigsurface-sl4.py\n"
        "Upstream https://github.com/Xiashangning/BigSurface commit "
        "82826312a429ede6e6f8441d49de2e2096b69ae4\n"
        "GPIO upstream https://github.com/VoodooI2C/VoodooGPIO commit "
        "d415406ecf25b5e322d3db9a4abab5719106fac1\n"
        "These five kexts alone do not include Windows EFI, personal SMBIOS, or partition data.\n"
    ).encode()
    content["MANIFEST.json"]=(json.dumps({
        "format":1,"hardware":"Surface Laptop 4 Intel i7-1185G7 / 8086:9A49",
        "kexts":list(NAMES),"source_script":"experiments/sl4-input/build-bigsurface-sl4.py",
        "sha256":{key:digest(val) for key,val in sorted(content.items())},
        "private_efi_included":False},indent=2)+"\n").encode()
    out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for key,val in sorted(content.items()):
            info=zipfile.ZipInfo(key,(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o100644<<16)
            z.writestr(info,val)
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        assert set(z.namelist())==set(content)
        assert all(digest(z.read(k))==digest(v) for k,v in content.items())
    print(json.dumps({"asset":out.name,"bytes":out.stat().st_size,
                      "sha256":digest(out.read_bytes()),"files":len(content)},indent=2))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--source",type=Path,required=True)
    ap.add_argument("--license-root",type=Path,required=True)
    x=ap.parse_args()
    assemble(x.source,x.license_root,x.out)

if __name__=="__main__":main()
