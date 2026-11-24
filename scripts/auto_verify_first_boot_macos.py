#!/usr/bin/env python3
"""Surface first-boot verification and Windows handoff (no root/disk changes).

The installer creates a per-user LaunchAgent. On successful accelerated Tahoe
login, it writes a non-secret, read-only-verification marker to the SL4DATA
partition so Windows QuickStart can offer safe internal OpenCore staging.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

VERSION=1
AGENT="com.sl4.autoverify"
RCS_FILE="WhateverXe-SL4-RCS-V017-TRIAL.kext/Contents/MacOS/WhateverXe"
RCS_SHA="94669172f4c2a52937b587c5eb3fdb73ff030963397aa094e575d9c4b54863d3"
READY_FILE="SL4-AUTO-READY.json"
FLAGS=("SL4RCSNativeQueueTrialReady","SL4HeapDepthTrialReady","SL4DMCLocalInitVerified","TGLEDPKeepReady",
       "TGLSoftSleepReady","IOPMDeepIdleSupported")

def insist(ok,message):
    if not ok:
        raise RuntimeError(message)

def run(*args):
    return subprocess.check_output(args,text=True,stderr=subprocess.STDOUT)

def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):
            h.update(b)
    return h.hexdigest()

def preflight():
    insist(sys.platform=="darwin" and os.uname().machine=="x86_64","requires Intel Tahoe")
    insist(run("/usr/bin/sw_vers","-productVersion").strip()=="26.7.1",
           "requires byte-tested macOS Tahoe 26.7.1")
    insist("i7-1185G7" in run("/usr/sbin/sysctl","-n","machdep.cpu.brand_string"),
           "requires matching Surface Laptop 4 CPU")

def inspected(source):
    preflight()
    insist(source.is_dir() and source.name=="SL4DATA" and source==Path("/Volumes/SL4DATA"),
           "refusing non-SL4DATA boot media")
    oc=Path("/Volumes/MACOS-OC/EFI/OC")
    insist((oc/"config.plist").is_file(),"Windows-prepared USB OC not mounted")
    kext=oc/"Kexts"/RCS_FILE
    insist(kext.is_file() and sha(kext)==RCS_SHA,"accelerated USB RCS kext differs from tested driver")
    config=plistlib.loads((oc/"config.plist").read_bytes())
    kernel=config["Kernel"]["Add"]
    enabled=[p["BundlePath"] for p in kernel if p.get("Enabled")]
    insist(enabled.count("WhateverXe-SL4-RCS-V017-TRIAL.kext")==1 and
           enabled.count("S0ixStandby.kext")==1,"missing tested RCS+S0ix combination in EFI")
    args=" ".join(v.get("boot-args","") for v in config["NVRAM"]["Add"].values())
    for flag in ("-wex-sl4-rcs-singleport","-wex-sl4-rcs-nativequeue-trial","-wex-sl4-heap-depth-trial","-wex-tgl-edp-softsleep"):
        insist(flag in args,"boot-arg missing "+flag)
    props=run("/usr/sbin/ioreg","-p","IOService","-l","-w0")
    for f in FLAGS:
        insist('"'+f+'" = Yes' in props,"not active yet: "+f)
    insist("Metal Support: Metal 2" in run("/usr/sbin/system_profiler","SPDisplaysDataType"),
           "Intel Metal2 acceleration not yet active")
    kexts=run("/usr/bin/kmutil","showloaded")
    insist("org.b00t0x.WhateverXe" in kexts and "com.labrouss.S0ixStandby" in kexts,
           "GPU/S0ix not both loaded")
    adapter=Path("/Library/GPUBundles/XeCompilerAdapter.bundle/Contents/MacOS/adapter.dylib")
    insist(adapter.is_file() and sha(adapter)=="50cc0fb84ffc8af995c35fe05e94e0543b8b8e7973edfd541710db93ff5e3b22",
           "compute hint patch not installed")
    insist("1DAD98CE-CD44-3CA8-9BEE-CE65F3B47DBF" in kexts,"wrong active v0.1.7 UUID")
    core=Path("/Library/Preferences/FeatureFlags/Domain/CoreMedia.plist")
    insist(core.is_file() and
           plistlib.loads(core.read_bytes()).get("AllowOnePassMetalScaling",{}).get("Enabled") is False,
           "YouTube CoreMedia compatibility flag is not active")
    user=Path.home()
    profile=user/"APOMac/Surface Laptop 4 - Clear Speech/config.txt"
    insist(profile.is_file() and "Preamp: -3.0 dB" in profile.read_text() and
           "Device: AppleHDAEngineOutput:1F,3,0,1,1:0" in profile.read_text(),
           "original Dolby Clear Speech not configured")
    insist(Path("/Applications/APOMac.app/Contents/MacOS/APOMac").is_file(),
           "APOMac is not installed")
    # Audit power policy without altering it.
    policy=run("/usr/bin/pmset","-g","custom")
    insist("Battery Power:" in policy and "AC Power:" in policy,
           "power policy cannot be inspected")
    return {
        "schema":VERSION,
        "stage":"verified_accelerated_tahoe_boot",
        "profile":"Surface Laptop 4 Intel i7-1185G7 Iris Xe 8086:9A49",
        "macos":"26.7.1",
        "integrated_rcs_sha256":RCS_SHA,
        "heap_depth_patch_ready":True,
        "compute_hint_patch_ready":True,
        "usb_oc_config_sha256":sha(oc/"config.plist"),
        "macos_metal2":True,
        "s0ix_deep_idle_driver_loaded":True,
        "edp_panel_wake_hooks_ready":True,
        "coremedia_h264_hevc_fix":True,
        "dolby_clear_speech_installed":True,
        "audio_capture_user_consent_unverified":True,
        "power_policy_modified":False,
        "windows_efi_modified":False,
        "checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

def check(source):
    result=inspected(source)
    userdir=Path.home()/"Library/Application Support/SL4-Autopilot"
    userdir.mkdir(parents=True,exist_ok=True)
    local=userdir/"verified.json"
    local.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    os.chmod(local,0o600)
    marker=source/READY_FILE
    if marker.exists():
        current=json.loads(marker.read_text())
        insist(current.get("schema")==VERSION and
               current.get("stage")=="verified_accelerated_tahoe_boot",
               "another installer marker already exists; not overwriting")
    marker.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("READY_FOR_WINDOWS_INTERNAL_BOOT",marker)
    print("Open QuickStart.cmd in Windows again with this USB inserted; it will detect this verified stage.")

def install(source):
    preflight()
    insist(source.is_dir() and source.name=="SL4DATA" and source==Path("/Volumes/SL4DATA"),
           "must run from mounted USB /Volumes/SL4DATA")
    insist(os.geteuid()!=0,"Install login verification as the actual macOS user, not root")
    dst=Path.home()/"Library/Application Support/SL4-Autopilot"
    dst.mkdir(parents=True,exist_ok=True)
    runner=dst/"auto_verify_first_boot_macos.py"
    current=Path(__file__).resolve()
    if runner.exists():
        insist(runner.read_bytes()==current.read_bytes(),"existing auto-verifier modified, not overwriting")
    else:
        shutil.copy2(current,runner)
    launch=Path.home()/"Library/LaunchAgents"
    launch.mkdir(parents=True,exist_ok=True)
    path=launch/(AGENT+".plist")
    value={
        "Label":AGENT,
        "ProgramArguments":["/usr/bin/python3",str(runner),"check","--source",str(source)],
        "RunAtLoad":True,
        "KeepAlive":False,
        "StandardOutPath":str(dst/"verification.log"),
        "StandardErrorPath":str(dst/"verification-errors.log"),
    }
    data=plistlib.dumps(value)
    if path.exists():
        insist(plistlib.loads(path.read_bytes())==value,
               "different existing first-boot agent, not overwriting")
    else:
        path.write_bytes(data)
    print("VERIFICATION_AGENT_INSTALLED",path)
    print("At next macOS login the agent verifies active RCS + sleep hooks + video + Dolby; only then it writes a readiness marker.")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("install","check"))
    p.add_argument("--source",type=Path,required=True)
    a=p.parse_args()
    if a.mode=="install":install(a.source.resolve())
    else:check(a.source.resolve())

if __name__=="__main__":
    try:main()
    except Exception as e:
        print("SL4_POSTBOOT_NOT_READY:",e,file=sys.stderr)
        sys.exit(1)
