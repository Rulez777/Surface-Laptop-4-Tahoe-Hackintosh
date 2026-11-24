#!/usr/bin/env python3
"""Apply the validated compute-hint compatibility change to the original local adapter.
No downloaded/redistributed donor, no changes to SIP, EFI or power policy.
"""
from pathlib import Path
import hashlib, os, stat, subprocess, tempfile, shutil, argparse, sys
LIVE=Path('/Library/GPUBundles/XeCompilerAdapter.bundle/Contents/MacOS/adapter.dylib')
BACKUP=Path('/Library/Application Support/SL4-Graphics-Performance/adapter-original-11609123.dylib')
OLD_SHA='11609123ce5b930aee500736f8bd504cd0280c37654f8e9f353fcc9fc876aff0'
NEW_SHA='50cc0fb84ffc8af995c35fe05e94e0543b8b8e7973edfd541710db93ff5e3b22'
DONOR=Path('/Library/Extensions/AppleIntelTGLGraphics.kext/Contents/MacOS/AppleIntelTGLGraphics')
DONOR_SHA='6c8ab6cce50b9529679ee4fdf5b1c37d091677d945076f41cb4b7f8196c51449'
START,END=0xe0a,0xe4b
OLD=bytes.fromhex('b8 07 00 00 00 80 7c 06 fd 00 75 35 66 2e 0f 1f 84 00 00 00 00 00 80 7c 06 fe 00 75 24 80 7c 06 ff 00 75 1d 48 3d d7 00 00 00 0f 84 39 01 00 00 80 3c 06 00 75 0b 48 83 c0 04 80 7c 06 fd 00 74 d5')
def need(ok,msg):
    if not ok:raise RuntimeError(msg)
def sha(data):return hashlib.sha256(data).hexdigest()
def run(*a):return subprocess.check_output([str(x) for x in a],stderr=subprocess.STDOUT)
def patched(raw):
    need(sha(raw)==OLD_SHA and raw[START:END]==OLD,'Unexpected original adapter')
    b=bytearray();labels={};fixups=[]
    def emit(s):b.extend(bytes.fromhex(s))
    def label(s):labels[s]=START+len(b)
    def j(op,target,n=1):
        emit(op);fixups.append((len(b),n,target));b.extend(b'\0'*n)
    emit('b8 04 00 00 00');label('loop')
    emit('3d 9c 00 00 00');j('75','check')
    emit('81 be 9c 00 00 00 00 04 00 00');j('77',END)
    emit('83 c0 04');label('check')
    emit('3d d7 00 00 00');j('0f 84',0xf73,4)
    emit('80 3c 06 00');j('75',END);emit('ff c0');j('eb','loop')
    for i,n,target in fixups:
        t=labels[target] if isinstance(target,str) else target
        b[i:i+n]=(t-START-i-n).to_bytes(n,'little',signed=True)
    need(len(b)<=len(OLD),'Patch size')
    b.extend(b'\x90'*(len(OLD)-len(b)))
    return raw[:START]+b+raw[END:]
def verify(p):run('/usr/bin/codesign','--verify','--strict',p)
def host():
    need(sys.platform=='darwin' and os.uname().machine=='x86_64','Intel macOS only')
    need(run('/usr/bin/sw_vers','-productVersion').strip()==b'26.7.1','Tahoe 26.7.1 required')
    need(b'i7-1185G7' in run('/usr/sbin/sysctl','-n','machdep.cpu.brand_string'),'Unsupported CPU')
    gpu=run('/usr/sbin/ioreg','-r','-n','IGPU','-lw0').lower()
    need(b'"device-id" = <499a0000>' in gpu and b'"vendor-id" = <86800000>' in gpu,'Unsupported GPU')
    need(DONOR.is_file() and sha(DONOR.read_bytes())==DONOR_SHA,'Different graphics donor')
    need(LIVE.is_file() and not LIVE.is_symlink() and LIVE.stat().st_uid==0 and stat.S_IMODE(LIVE.stat().st_mode)==0o755,'Unexpected live adapter')
    verify(LIVE)
def stage_replace(raw,expected,sign=False):
    fd,path=tempfile.mkstemp(prefix='.sl4-adapter-',suffix='.dylib',dir=LIVE.parent)
    p=Path(path)
    try:
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.chown(p,0,LIVE.stat().st_gid);os.chmod(p,0o755)
        if sign:run('/usr/bin/codesign','--force','--sign','-','--identifier','adapter-compute-hint-trial-55554944f4f3d0fae00737c3bfacae9ee0ab08e9',p)
        verify(p);need(sha(p.read_bytes())==expected,'Candidate SHA mismatch; refusing installation')
        os.replace(p,LIVE)
        verify(LIVE);need(sha(LIVE.read_bytes())==expected,'Installed adapter SHA mismatch')
        run('/bin/sync')
    finally:p.unlink(missing_ok=True)
def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('mode',choices=('check','apply','rollback'));a=a.parse_args()
    host()
    old=LIVE.read_bytes();h=sha(old)
    need(h in (OLD_SHA,NEW_SHA),'Unrecognized compiler adapter; no change')
    if a.mode=='check':
        print('COMPILER_HINT_READY' if h==NEW_SHA else 'COMPILER_HINT_PATCHABLE');return
    need(os.geteuid()==0,'Administrator privileges required')
    if a.mode=='apply':
        if h==NEW_SHA:print('COMPILER_HINT_READY');return
        BACKUP.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        need(not BACKUP.parent.is_symlink() and BACKUP.parent.stat().st_uid==0 and stat.S_IMODE(BACKUP.parent.stat().st_mode)==0o700,'Unsafe backup directory')
        if not BACKUP.exists():
            with BACKUP.open('xb') as f:f.write(old);f.flush();os.fsync(f.fileno())
            os.chmod(BACKUP,0o700)
        need(not BACKUP.is_symlink() and sha(BACKUP.read_bytes())==OLD_SHA,'Original backup mismatch')
        verify(BACKUP)
        try:stage_replace(patched(old),NEW_SHA,sign=True)
        except BaseException:
            if sha(LIVE.read_bytes())==NEW_SHA:stage_replace(old,OLD_SHA)
            raise
        print('COMPILER_HINT_READY',NEW_SHA)
    else:
        if h==OLD_SHA:print('ORIGINAL_ADAPTER_ALREADY_ACTIVE');return
        need(BACKUP.is_file() and not BACKUP.is_symlink() and sha(BACKUP.read_bytes())==OLD_SHA,'Original backup missing or corrupt')
        verify(BACKUP);stage_replace(BACKUP.read_bytes(),OLD_SHA)
        print('ORIGINAL_ADAPTER_RESTORED')
if __name__=='__main__':
    try:main()
    except Exception as e:print('STOP:',e,file=sys.stderr);sys.exit(1)
