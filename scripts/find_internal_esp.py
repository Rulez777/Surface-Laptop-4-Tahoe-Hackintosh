#!/usr/bin/env python3
"""Find exactly one internal Windows+macOS ESP; no writes, no auto-mount."""
import plistlib
import re
import subprocess
import sys

def find():
    data=plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil","list","-plist"]))
    matches=[]
    for item in data["AllDisksAndPartitions"]:
        parts=item.get("Partitions",[])
        names={x.get("Content") for x in parts}
        if not {"EFI","Microsoft Basic Data","Apple_APFS"}.issubset(names):
            continue
        for part in parts:
            if part.get("Content")!="EFI":continue
            dev=part.get("DeviceIdentifier","")
            if not re.fullmatch(r"disk[0-9]+s[0-9]+",dev):continue
            details=plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil","info","-plist",dev]))
            if (details.get("DeviceIdentifier")==dev and details.get("Internal") and
                not details.get("Removable") and
                details.get("Content")=="EFI" and
                250_000_000<=details.get("TotalSize",0)<=350_000_000):
                matches.append(dev)
    if len(matches)!=1:raise RuntimeError("Expected exactly one verified internal Surface EFI, found "+repr(matches))
    return matches[0]

if __name__=="__main__":
    try: print(find())
    except Exception as error:
        print("NO_UNIQUE_INTERNAL_ESP:",error,file=sys.stderr)
        sys.exit(1)
