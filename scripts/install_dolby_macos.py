#!/usr/bin/env python3
"""One-step installation of Surface Laptop 4 speaker correction and APOMac.

Run after Tahoe boots. No changes to EFI, audio kexts, other audio output,
Windows or Steam. macOS must still ask the human to approve system audio capture.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
try:
    import pwd  # macOS only; Win/Linux CI must still import the offline validator
except ImportError:
    pwd=None
import tempfile
import zipfile

AUDIO_ARCHIVE="SL4-Dolby-APOMac-Profiles-20261123.zip"
AUDIO_SHA="ff029e860aec93763dc5fac3032c154a82fc571deb5cc08b5a9ad005907cc013"
APOMAC_DMG="APOMac-0.1.0.dmg"
APOMAC_DMG_SHA="525a6adef1cbad76906d620656c93d7b1da1b3c8d6189b3f12648cfb221006fd"
FIR_SHA="980695d30da4e38"  # Clear Speech left/right IR hash prefix.
ZIP_PREFIX="SL4-Dolby-APOMac-Profiles/"
UID="AppleHDAEngineOutput:1F,3,0,1,1:0"
PROFILE="Surface Laptop 4 - Clear Speech"
APP_ID="com.apomac.app"
NAMES=("Surface Laptop 4 - Clear Speech","Surface Laptop 4 - Dolby Balanced",
       "Surface Laptop 4 - Dolby Detailed","Surface Laptop 4 - Dolby Warm",
       "Surface Laptop 4 - Dolby Voice")
ALLOWED={"MANIFEST.json","README-RU.txt","Install-on-macOS.command"}
for n in NAMES:
    ALLOWED.update((n+"/config.txt",n+"/speaker-correction.wav"))

def require(ok,reason):
    if not ok: raise RuntimeError(reason)

def sha_bytes(data):return hashlib.sha256(data).hexdigest()

def sha_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def read_zip(archive):
    require(archive.is_file() and sha_file(archive)==AUDIO_SHA,
            "Speaker correction archive differs from exact Surface reference")
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None,"Speaker correction ZIP is corrupt")
        names=set(z.namelist())
        require(names=={ZIP_PREFIX+n for n in ALLOWED},
                "Unexpected files or missing profiles in Dolby archive")
        manifest=json.loads(z.read(ZIP_PREFIX+"MANIFEST.json"))
        require(manifest.get("device_id")=="INTELAUDIO FUNC_01 VEN_10EC DEV_0274 SUBSYS_10EC123E",
                "Unexpected Realtek audio device in Dolby manifest")
        require(manifest.get("source_xml_sha256")==
                "0d6eac67b729320fdb563259cbdd08252bf9ef543696d9204b90b82548ddb004",
                "Dolby source provenance mismatch")
        hashes=manifest.get("file_sha256")
        require(isinstance(hashes,dict) and set(hashes)==ALLOWED-{"MANIFEST.json"},
                "Incomplete approved Dolby profile checksum list")
        for name,expected in hashes.items():
            require(sha_bytes(z.read(ZIP_PREFIX+name))==expected,
                    "Dolby profile SHA differs from signed-off Windows extraction: "+name)
        for name in NAMES:
            config=z.read(ZIP_PREFIX+name+"/config.txt").decode("utf-8")
            require(config.startswith("# Surface Laptop 4 Intel") and
                    "Convolution: speaker-correction.wav" in config and
                    "Device:" not in config and "Preamp:" in config,
                    "Unexpected EQ configuration: "+name)
            if name==PROFILE:
                require("Preamp: -3.0 dB" in config and
                        "Filter: ON PK Fc 2500 Hz Gain 1.88 dB Q 0.70" in config,
                        "User-confirmed Clear Speech tuning changed")
                require(sha_bytes(z.read(ZIP_PREFIX+name+"/speaker-correction.wav")).startswith(FIR_SHA),
                        "Clear Speech FIR changed")
    return True

def preflight():
    require(sys.platform=="darwin" and os.uname().machine=="x86_64",
            "Requires macOS Intel Surface laptop")
    v=subprocess.check_output(["/usr/bin/sw_vers","-productVersion"],text=True).strip()
    require(v=="26.7.1","Only exactly tested Tahoe 26.7.1 supported")
    cpu=subprocess.check_output(["/usr/sbin/sysctl","-n","machdep.cpu.brand_string"],text=True)
    require("i7-1185G7" in cpu,"Only tested Surface Laptop 4 Intel i7-1185G7 supported")
    # Verify existing native stereo speakers; no Bluetooth, dock, headphones.
    r=subprocess.check_output(["/usr/sbin/system_profiler","SPAudioDataType"],text=True)
    # When running the Windows-first USB flow, the SimpleHDA kext is not
    # active until the next boot. Stage the exact-UID-bound profile now;
    # first-launch permission and hardware output are verified after reboot.
    if "Output Channels: 2" not in r and "Каналы вывода: 2" not in r:
        print("AUDIO_OUTPUT_PENDING_FIRST_REBOOT: staged but not yet processing")
    return v

def get_user():
    user=os.environ.get("SUDO_USER") or pwd.getpwuid(os.getuid()).pw_name
    require(user not in ("root","_unknown"),"Run from a normal macOS user session")
    p=pwd.getpwnam(user)
    return user,p.pw_uid,p.pw_gid,Path(p.pw_dir)

def owner(path,uid,gid):
    if os.geteuid()==0:
        os.chown(path,uid,gid)
        if path.is_dir():
            for item in path.rglob("*"):
                os.chown(item,uid,gid)

def install_app(dmg):
    require(dmg.is_file() and sha_file(dmg)==APOMAC_DMG_SHA,"Unexpected APOMac release")
    with tempfile.TemporaryDirectory(prefix="sl4-audio-dmg-") as temp:
        mount=Path(temp)/"mount"
        mount.mkdir()
        subprocess.run(["/usr/bin/hdiutil","attach","-readonly","-nobrowse","-mountpoint",
                        str(mount),str(dmg)],check=True,stdout=subprocess.DEVNULL)
        try:
            app=mount/"APOMac.app"
            require(app.is_dir(),"Official APOMac.app not found in verified DMG")
            inf=plistlib.loads((app/"Contents/Info.plist").read_bytes())
            require(inf["CFBundleIdentifier"]==APP_ID,"Unexpected application ID")
            subprocess.run(["/usr/bin/codesign","--verify","--deep","--strict",str(app)],check=True)
            dest=Path("/Applications/APOMac.app")
            if dest.exists():
                require(dest.is_dir() and (dest/"Contents/MacOS/APOMac").is_file() and
                        sha_file(dest/"Contents/MacOS/APOMac")==sha_file(app/"Contents/MacOS/APOMac"),
                        "Existing APOMac has a different binary: not overwriting")
                print("APOMAC_ALREADY_PRESENT: exact version")
            else:
                require(os.geteuid()==0,"Use sudo to install APOMac into /Applications")
                subprocess.run(["/usr/bin/ditto",str(app),str(dest)],check=True)
                subprocess.run(["/usr/bin/codesign","--verify","--deep","--strict",str(dest)],check=True)
                print("INSTALLED_APOMAC",dest)
        finally:
            subprocess.run(["/usr/bin/hdiutil","detach",str(mount)],
                           check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def profile_config(data):
    source=data.decode("utf-8").replace("\r\n","\n").lstrip("\ufeff")
    require(not source.startswith("Device:"),"Already device-scoped source: refuse")
    return ("Device: "+UID+"\n"+source).encode("utf-8")

def install_profiles(bundle,home,uid,gid):
    root=home/"APOMac"
    root.mkdir(parents=True,exist_ok=True)
    owner(root,uid,gid)
    with zipfile.ZipFile(bundle) as z:
        for name in NAMES:
            path=root/name
            expected=profile_config(z.read(ZIP_PREFIX+name+"/config.txt"))
            wav=z.read(ZIP_PREFIX+name+"/speaker-correction.wav")
            if path.exists():
                require(path.is_dir(),"Path occupied by a file: "+str(path))
                current=path/"config.txt"
                sound=path/"speaker-correction.wav"
                if current.is_file() and sound.is_file() and current.read_bytes()==expected and sound.read_bytes()==wav:
                    print("UNCHANGED_PROFILE",name)
                else:
                    print("PRESERVED_USER_EDITED_PROFILE",name)
                continue
            path.mkdir()
            (path/"config.txt").write_bytes(expected)
            (path/"speaker-correction.wav").write_bytes(wav)
            owner(path,uid,gid)
            require(sha_bytes((path/"speaker-correction.wav").read_bytes())==sha_bytes(wav),
                    "Profile copy verification failed")
            print("INSTALLED_PROFILE",name)

def install_login(user,uid,gid,home):
    root=home/"Library/LaunchAgents"
    root.mkdir(parents=True,exist_ok=True)
    p=root/"com.sl4.apomac.autostart.plist"
    config={"Label":"com.sl4.apomac.autostart",
        "ProgramArguments":["/usr/bin/open","-g","-a","/Applications/APOMac.app"],
        "RunAtLoad":True,"KeepAlive":False}
    raw=plistlib.dumps(config)
    if p.exists():
        require(plistlib.loads(p.read_bytes())==config,
                "Different existing APOMac login item: not overwriting")
        print("LOGIN_ITEM_ALREADY_PRESENT")
    else:
        p.write_bytes(raw)
        owner(p,uid,gid)
        print("INSTALLED_LOGIN_ITEM",p)
    # Writes preferences under the interactive user, preserving TCC consent.
    prefix=["/usr/bin/sudo","-u",user] if os.geteuid()==0 else []
    subprocess.run(prefix+["/usr/bin/defaults","write",APP_ID,
                           "selectedProfileName","-string",PROFILE],check=True)
    subprocess.run(prefix+["/usr/bin/defaults","write",APP_ID,
                           "isEnabled","-bool","true"],check=True)
    print("PROFILE_SELECTED",PROFILE)
    print("MACOS_PERMISSION_REQUIRED: approve System Audio Recording on first launch.")
    # Try to load for current login; next login will also start automatically.
    subprocess.run(prefix+["/usr/bin/launchctl","bootstrap",f"gui/{uid}",str(p)],
                   check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(prefix+["/usr/bin/open","-g","-a","/Applications/APOMac.app"],
                   check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("offline-check","check","apply"))
    p.add_argument("--bundle",type=Path,required=True)
    p.add_argument("--apomac-dmg",type=Path)
    a=p.parse_args()
    read_zip(a.bundle)
    if a.mode=="offline-check":
        print("VERIFIED_OFFLINE_DOLBY_ARCHIVE",AUDIO_SHA)
        return
    preflight()
    require(a.apomac_dmg and a.apomac_dmg.is_file() and sha_file(a.apomac_dmg)==APOMAC_DMG_SHA,
            "Pinned APOMac DMG not available")
    user,uid,gid,home=get_user()
    if a.mode=="check":
        print("READY_TO_INSTALL_DOLBY_CLEAR_SPEECH",user)
        return
    require(os.geteuid()==0,"Run with sudo for system application installation")
    install_app(a.apomac_dmg)
    install_profiles(a.bundle,home,uid,gid)
    install_login(user,uid,gid,home)
    print("DONE: permanent audio correction selected; macOS first-use TCC consent still required.")

if __name__=="__main__":
    try: main()
    except Exception as e:
        print("SL4_AUDIO_STOP:",e,file=sys.stderr)
        sys.exit(1)
