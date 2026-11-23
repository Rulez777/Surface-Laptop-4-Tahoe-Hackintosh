#!/usr/bin/env python3
"""Developer-only: generate a complete source diff for tested eDP/GPUREC base.

Upstream checkout is pinned separately. This helper is not required on client
machines, and never reads live EFI, SMBIOS, user identifiers or firmware.
"""
from pathlib import Path
import argparse
import difflib
import hashlib

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--upstream",type=Path,required=True)
    a.add_argument("--tested-base",type=Path,required=True)
    a.add_argument("--output",type=Path,required=True)
    z=a.parse_args()
    assert not z.output.exists()
    components=("WhateverXe","AppleIntelTGLCompat")
    files=set()
    for name in components:
        files.update(str(x.relative_to(z.upstream)) for x in (z.upstream/name).rglob("*") if x.is_file())
        files.update(str(x.relative_to(z.tested_base)) for x in (z.tested_base/name).rglob("*") if x.is_file())
    lines=[]
    for item in sorted(files):
        before=(z.upstream/item).read_text().splitlines(keepends=True) if (z.upstream/item).exists() else []
        after=(z.tested_base/item).read_text().splitlines(keepends=True) if (z.tested_base/item).exists() else []
        if before==after:continue
        lines.extend(difflib.unified_diff(before,after,fromfile=("a/"+item if before else "/dev/null"),tofile=("b/"+item if after else "/dev/null"),n=3))
    blob="".join(lines).encode("utf-8")
    assert len(blob)>3000
    z.output.write_bytes(blob)
    print("SL4 BASE PATCH",len(blob),"bytes",hashlib.sha256(blob).hexdigest())
    print("DIFFED",sorted(files)[:3],"... total candidates",len(files))

if __name__=="__main__":
    main()
