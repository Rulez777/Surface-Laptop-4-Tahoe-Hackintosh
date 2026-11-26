#!/usr/bin/env python3
"""Version-pinned, source-only HDRP compiler fix for the SL4 Tahoe donor.
No kernel/EFI changes, no trace hooks, no redistributed Apple binaries.
"""
import argparse, hashlib, os, stat, subprocess, sys, tempfile
from pathlib import Path
import install_compute_hint_macos as hint

ROOT=Path("/Library/GPUBundles/XeCompilerAdapter.bundle/Contents/MacOS")
BACKUP=Path("/Library/Application Support/SL4-Graphics-Performance/HDRP-SWSB-v1")
BASE_G="a27eaea380aee524a1972927cb44774da1affe0cea93e94c307927f38d41aaf4"
UNSIGNED_G="079b713642779df29333b4e9029b54512b6087f966dd717d3f648241933b2f6f"
NEW_G="2956cf797bf8caebdd62eee75a8644734620576c47c647ae6151d6c284af93ca"
BASE_A="50cc0fb84ffc8af995c35fe05e94e0543b8b8e7973edfd541710db93ff5e3b22"
NEW_A="bf8839038760980476676fa0bab0246819ea0484eb27aa69a9459ad1cc1dbbfd"
PATCHES=((5844211, '662e0f1f8400000000000f1f00', '8b0b3b8c24880000007302eb25'), (5844259, '48630b488b04c8488b00', 'ebce488b04c8488b0090'), (5855537, '662e0f1f8400000000000f1f440000', '413b5e287316909090909090909090'), (5855570, '75ec', '75dd'))
IDENTIFIER="adapter-compute-hint-trial-55554944f4f3d0fae00737c3bfacae9ee0ab08e9"

def need(ok,msg):
    if not ok: raise RuntimeError(msg)
def sha(data): return hashlib.sha256(data).hexdigest()
def run(*args): subprocess.check_call([str(a) for a in args])
def checked(path,expected=None):
    need(path.is_file() and not path.is_symlink(),"Missing or unsafe file: "+str(path))
    raw=path.read_bytes()
    if expected: need(sha(raw)==expected,"Unexpected version: "+str(path))
    return raw
def patch_igc(raw):
    need(sha(raw)==BASE_G,"Unsupported IGC build")
    b=bytearray(raw)
    for off,before,after in PATCHES:
        before,after=bytes.fromhex(before),bytes.fromhex(after)
        need(len(before)==len(after) and raw[off:off+len(before)]==before,"Unexpected instruction bytes")
        b[off:off+len(after)]=after
    need(sha(b)==UNSIGNED_G,"Unexpected patched IGC")
    return bytes(b)
def patch_adapter(raw):
    need(sha(raw)==BASE_A,"Unsupported compute-hint adapter")
    old,new=bytes.fromhex(BASE_G),bytes.fromhex(NEW_G)
    need(raw[0x2020:0x2040]==old[16:]+old[:16] and raw[0x2060:0x2080]==old,"Unexpected SHA constants")
    b=bytearray(raw)
    b[0x2020:0x2040]=new[16:]+new[:16]
    b[0x2060:0x2080]=new
    return bytes(b)
def stage(raw,target,expected,identifier=None):
    fd,name=tempfile.mkstemp(prefix=".sl4-hdrp-",suffix=".dylib",dir=target.parent)
    path=Path(name)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        st=target.stat()
        os.chown(path,st.st_uid,st.st_gid);os.chmod(path,stat.S_IMODE(st.st_mode))
        if identifier: run("/usr/bin/codesign","--force","--sign","-","--identifier",identifier,path)
        run("/usr/bin/codesign","--verify","--strict",path)
        checked(path,expected)
        return path
    except BaseException:
        path.unlink(missing_ok=True);raise
def safe_backup(a,g):
    BACKUP.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    for d in (BACKUP.parent,BACKUP):
        if not d.exists():d.mkdir(mode=0o700)
        need(not d.is_symlink() and d.stat().st_uid==0 and stat.S_IMODE(d.stat().st_mode)==0o700,"Unsafe backup directory")
    for name,raw,h in (("adapter.dylib",a,BASE_A),("libigc-tgl.dylib",g,BASE_G)):
        f=BACKUP/name
        if not f.exists():
            with f.open("xb") as fp:fp.write(raw);fp.flush();os.fsync(fp.fileno())
            f.chmod(0o600)
        checked(f,h)
def swap_pair(a,g,ar,gr,ah,gh,sign=False):
    olda,oldg=checked(a),checked(g)
    staged=[];changed=[]
    try:
        ga=stage(gr,g,gh,"com.apple.libigc" if sign else None);staged.append(ga)
        aa=stage(ar,a,ah,IDENTIFIER if sign else None);staged.append(aa)
        # Stage both and verify before any replacement. Restore on exceptions.
        og=stage(oldg,g,sha(oldg));staged.append(og)
        oa=stage(olda,a,sha(olda));staged.append(oa)
        os.replace(ga,g);changed.append((og,g))
        os.replace(aa,a);changed.append((oa,a))
        checked(a,ah);checked(g,gh);os.sync()
    except BaseException:
        for original,target in reversed(changed):os.replace(original,target)
        os.sync();raise
    finally:
        for path in staged:path.unlink(missing_ok=True)
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode",choices=("check","apply","rollback"))
    mode=ap.parse_args().mode
    hint.host()
    a,g=ROOT/"adapter.dylib",ROOT/"libigc-tgl.dylib"
    ar,gr=checked(a),checked(g)
    pair=(sha(ar),sha(gr))
    ready=(NEW_A,NEW_G)
    if pair==ready:
        run("/usr/bin/codesign","--verify","--strict",g)
        if mode!="rollback":print("HDRP_SWSB_READY");return
    if mode=="check":
        need(pair in ((hint.OLD_SHA,BASE_G),(BASE_A,BASE_G)),"Unsupported compiler pair")
        print("HDRP_SWSB_PATCHABLE");return
    need(os.geteuid()==0,"Administrator privileges required")
    if mode=="rollback":
        need(pair==ready,"Expected installed HDRP pair")
        oa=checked(BACKUP/"adapter.dylib",BASE_A);og=checked(BACKUP/"libigc-tgl.dylib",BASE_G)
        swap_pair(a,g,oa,og,BASE_A,BASE_G);print("HDRP_SWSB_ROLLED_BACK");return
    need(pair in ((hint.OLD_SHA,BASE_G),(BASE_A,BASE_G)),"Unsupported compiler pair")
    if pair[0]==hint.OLD_SHA:
        run(sys.executable,Path(hint.__file__),"apply")
        ar=checked(a,BASE_A)
    safe_backup(ar,gr)
    swap_pair(a,g,patch_adapter(ar),patch_igc(gr),NEW_A,NEW_G,sign=True)
    print("HDRP_SWSB_READY; restart macOS before testing")
if __name__=="__main__":
    try:main()
    except Exception as e:print("STOP:",e,file=sys.stderr);sys.exit(1)
