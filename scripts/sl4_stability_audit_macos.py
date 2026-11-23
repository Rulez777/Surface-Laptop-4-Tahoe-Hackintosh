#!/usr/bin/env python3
"""Non-invasive macOS Surface Laptop 4 stability snapshot.

All reported facts are software observations. No input, physical audio/video,
display backlight, Windows boot, or true system suspend is certified by this.
"""
from __future__ import annotations
import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time

REQUIRED={"as.vit9696.Lilu":"1.7.2",
          "org.b00t0x.WhateverXe":"0.8.3",
          "as.vit9696.VirtualSMC":"1.3.8",
          "as.vit9696.SMCProcessor":"1.3.8",
          "as.vit9696.AppleALC":"1.9.8",
          "cn.laobamac.SimpleHDA":"1.0.2",
          "com.xavier.BigSurface":"1.2.0",
          "com.xavier.BigSurfaceHIDDriver":"1.0.0"}
CRASH_TYPES={"gpu_reset":(".gpuRestart",),"kernel_panic":(".panic",),
             "windowserver_crash":("WindowServer",)}


def run(*args,timeout=35):
    p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if p.returncode: raise RuntimeError("Probe failed: "+str(args[0]))
    return p.stdout


def kext_versions(output):
    found={}
    for line in output.splitlines():
        match=re.search(r"\b([\w.-]+)\s+\((\d+(?:\.\d+){1,3})\)",line)
        if match:
            found[match.group(1)]=match.group(2)
    return found


def crash_summary(folder,boot_ts,now_ts):
    totals={key:{"last_24h":0,"since_current_boot":0} for key in CRASH_TYPES}
    if not folder.exists():return totals
    for file in folder.iterdir():
        if not file.is_file():continue
        try: modified=file.stat().st_mtime
        except OSError:continue
        for key,markers in CRASH_TYPES.items():
            if any(marker in file.name for marker in markers):
                if modified>=now_ts-86400:totals[key]["last_24h"]+=1
                if modified>=boot_ts:totals[key]["since_current_boot"]+=1
                break
    return totals


def boot_epoch(output):
    match=re.search(r"sec = (\d+)",output)
    if not match:raise RuntimeError("Cannot parse kernel boot epoch")
    return int(match.group(1))


def live_summary():
    if sys.platform!="darwin":raise RuntimeError("macOS required")
    os_version=run("/usr/bin/sw_vers","-productVersion").strip()
    gpu=run("/usr/sbin/system_profiler","SPDisplaysDataType",timeout=40)
    audio=run("/usr/sbin/system_profiler","SPAudioDataType",timeout=40)
    net=run("/usr/sbin/networksetup","-listallhardwareports")
    kexts=kext_versions(run("/usr/bin/kmutil","showloaded"))
    flags_raw=run("/usr/sbin/ioreg","-lw0")
    pm=run("/usr/bin/pmset","-g","custom")
    battery=run("/usr/bin/pmset","-g","batt")
    boot=boot_epoch(run("/usr/sbin/sysctl","-n","kern.boottime"))
    flags={}
    for name in ("TGLEDPKeepReady","TGLSoftSleepReady","TGLGpuRecReady","TGLEDPKept"):
        m=re.search(r'"'+name+r'"\s*=\s*(Yes|No|\d+)',flags_raw)
        if m: flags[name]=int(m.group(1)) if m.group(1).isdigit() else m.group(1)
    editions={k:{"loaded":k in kexts,"version":kexts.get(k,""),
                  "expected":version,"expected_version_loaded":kexts.get(k)==version}
              for k,version in REQUIRED.items()}
    asleep=bool(re.findall(r"^\s*sleep\s+0\s*$",pm,re.M)) and len(re.findall(r"^\s*sleep\s+0\s*$",pm,re.M))>=2
    pct=re.search(r"(\d{1,3})%",battery)
    now=time.time()
    crashes=crash_summary(Path("/Library/Logs/DiagnosticReports"),boot,now)
    return {
        "timestamp_local":dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "platform":"macOS","os_version":os_version,
        "graphics":{"intel_iris_xe_detected":"Intel Iris Xe Graphics" in gpu,
                    "metal2_reported":"Metal Support: Metal 2" in gpu,
                    "internal_display_online_reported":"Online: Yes" in gpu,
                    "edp_driver_flags":flags,
                    "physical_panel_wake_verified":False},
        "audio":{"default_input_present":"Default Input Device: Yes" in audio,
                 "default_output_present":"Default Output Device: Yes" in audio,
                 "actual_recording_playback_tested":False},
        "network":{"wifi_hardware_port_present":"Hardware Port: Wi-Fi" in net,
                   "actual_connection_tested":False},
        "drivers":editions,
        "battery":{"current_power_source":"AC" if "AC Power" in battery else "Battery" if "Battery Power" in battery else "unknown",
                   "charge_percent":int(pct.group(1)) if pct else None,
                   "endurance_verified":False},
        "sleep":{"idle_system_sleep_disabled_both_profiles":asleep,
                 "true_s3_s0ix_resume_verified":False},
        "crash_counts":crashes,
        "manual_checks_required":["Windows cold boot / dual boot","physical display wake and lid",
            "audio playback and microphone record","3.5 mm headphones","Bluetooth transfer",
            "Wi-Fi network use","dock/external monitor","keyboard and trackpad input",
            "full battery discharge/charging","real S3/S0ix resume"],
        "safety":"read-only inspection; driver and crash counters do not prove overall physical stability"
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    summary=live_summary()
    s=json.dumps(summary,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        if args.output.exists():raise RuntimeError("Output exists; refusing overwrite")
        args.output.write_text(s,encoding="utf-8")
        print("Saved:",args.output)
    else:print(s,end="")
    return 0


if __name__=="__main__":
    try:sys.exit(main())
    except (RuntimeError,OSError,subprocess.SubprocessError) as e:
        print("STOP:",e,file=sys.stderr)
        sys.exit(1)
