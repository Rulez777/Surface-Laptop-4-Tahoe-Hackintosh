#!/usr/bin/env python3
"""Read-only battery, CPU governor, Surface performance and bounded CPU test.

Never changes macOS power settings, TMP/EC, EFI, Windows or firmware.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time


def run(argv, timeout=25):
    p=subprocess.run(argv,capture_output=True,text=True,timeout=timeout)
    if p.returncode:
        raise RuntimeError("Query failed: "+argv[0]+" "+str(p.returncode))
    return p.stdout


def read_boolean(raw,key):
    m=re.search(r'"'+re.escape(key)+r'"\s*=\s*(Yes|No)',raw)
    return None if not m else m.group(1)=="Yes"


def read_int(raw,key):
    m=re.search(r'"'+re.escape(key)+r'"\s*=\s*(\d+)',raw)
    return None if not m else int(m.group(1))


def source_status(text):
    first=next((x.strip() for x in text.splitlines() if x.strip()),"")
    return ("ac" if first=="Now drawing from 'AC Power'" else
            "battery" if first=="Now drawing from 'Battery Power'" else "unknown")


def parse_battery(text):
    ac=re.search(r'"AdapterDetails"\s*=\s*\{[^}]*"Watts"\s*=\s*(\d+)',text)
    return {"external_connected":read_boolean(text,"ExternalConnected"),
            "charging":read_boolean(text,"IsCharging"),
            "capacity_units":read_int(text,"CurrentCapacity"),
            "max_capacity_units":read_int(text,"MaxCapacity"),
            "charger_watts":int(ac.group(1)) if ac else None}


def parse_power_limits(text):
    state={}
    for key in ("CPU_Scheduler_Limit","CPU_Available_CPUs","CPU_Speed_Limit"):
        m=re.search(r"\b"+re.escape(key)+r"\s*=\s*(\d+)",text)
        state[key]=int(m.group(1)) if m else None
    return state


def profile(text):
    m=re.search(r'"PerformanceMode"\s*=\s*(\d+)',text)
    mode=int(m.group(1)) if m else None
    return {"registry_value":mode,
            "registry_label":{1:"Recommended",2:"Battery Saver",3:"Better Performance",4:"Best Performance"}.get(mode,"unknown"),
            "verified_ec_effect":False}


def sysctl_num(name):
    try:return int(run(["/usr/sbin/sysctl","-n",name],timeout=8).strip())
    except (RuntimeError,ValueError):return None


def cpu_probe(rounds):
    start=time.perf_counter()
    hashlib.pbkdf2_hmac("sha256",b"Surface-Laptop-4",b"performance-probe",rounds)
    return round(time.perf_counter()-start,3)


def count_cpu_cycles(rounds):
    """Use macOS /usr/bin/time -l retired cycles as a frequency *proxy*.

    This is not calibrated APERF/MPERF/powermetrics and should not be treated
    as a direct instantaneous CPU clock reading.
    """
    child='import hashlib;hashlib.pbkdf2_hmac("sha256",b"Surface-Laptop-4",b"performance-probe",'+str(rounds)+')'
    proc=subprocess.run(["/usr/bin/time","-l",sys.executable,"-c",child],
                        capture_output=True,text=True,timeout=40)
    if proc.returncode: raise RuntimeError("Counter probe failed")
    timing=re.search(r"([0-9.]+) real\s+([0-9.]+) user\s+([0-9.]+) sys",proc.stderr)
    cycles=re.search(r"(\d+)\s+cycles elapsed",proc.stderr)
    instructions=re.search(r"(\d+)\s+instructions retired",proc.stderr)
    if not timing: raise RuntimeError("CPU timing data unavailable")
    cpu_s=float(timing.group(2))+float(timing.group(3))
    ticks=int(cycles.group(1)) if cycles else None
    return {"rounds":rounds,"real_s":float(timing.group(1)),
            "cpu_s":round(cpu_s,3),
            "cycles_elapsed":ticks,
            "instructions_retired":int(instructions.group(1)) if instructions else None,
            "cycles_per_cpu_second_mhz_proxy":round(ticks/cpu_s/1e6,1) if ticks and cpu_s>0 else None,
            "notice":"Not a hardware frequency meter. Compares relative progress on THIS machine; root powermetrics required to independently verify frequency."}


def live(rounds=0,cycles_rounds=0):
    if sys.platform!="darwin":
        raise RuntimeError("Only macOS supported")
    acpi=run(["/usr/sbin/ioreg","-p","IOACPIPlane","-lw0"],timeout=25)
    if "MSHW0250" not in acpi or "MSHW0084" not in acpi:
        raise RuntimeError("Unsupported hardware")
    charging=run(["/usr/bin/pmset","-g","batt"])
    therm=run(["/usr/bin/pmset","-g","therm"])
    custom=run(["/usr/bin/pmset","-g","custom"])
    registry=run(["/usr/sbin/ioreg","-r","-c","SurfaceBatteryDriver","-lw0"])
    battery=run(["/usr/sbin/ioreg","-r","-c","AppleSmartBattery","-lw0"])
    limit=read_int(custom,"lowpowermode")
    # Both AC and battery must explicitly be 0; a single match is insufficient.
    lowpower_values=[int(x) for x in re.findall(r"(?m)^\s*lowpowermode\s+(\d+)\s*$",custom)]
    data={
      "observed_at":dt.datetime.now().astimezone().isoformat(timespec="seconds"),
      "hardware":"MSHW0250 + MSHW0084",
      "power_source":source_status(charging),
      "battery":parse_battery(battery),
      "low_power_mode_disabled_on_both_profiles":len(lowpower_values)>=2 and all(x==0 for x in lowpower_values),
      "pmset_therm":parse_power_limits(therm),
      "intel_xcpm":{
          "lpm_enabled":sysctl_num("machdep.xcpm.lpm_enabled"),
          "cpu_thermal_level":sysctl_num("machdep.xcpm.cpu_thermal_level"),
          "gpu_thermal_level":sysctl_num("machdep.xcpm.gpu_thermal_level"),
          "hard_limit_ratio_x100mhz":sysctl_num("machdep.xcpm.hard_plimit_max_100mhz_ratio"),
          "soft_limit_ratio_x100mhz":sysctl_num("machdep.xcpm.soft_plimit_max_100mhz_ratio")
      },
      "bigsurface":profile(registry),
      "actual_cpu_frequency_measured":False,
      "battery_charger_ec_fault_diagnosed":False,
      "safety":"Read-only. hw.cpufrequency is static nominal, not actual clock; XCPM limits are not proof of actual MHz."
    }
    if cycles_rounds:
        data["cpu_cycles_proxy"]=count_cpu_cycles(cycles_rounds)
    if rounds:
        data["cpu_probe"]={"pbkdf2_sha256_rounds":rounds,
                           "elapsed_s":cpu_probe(rounds),
                           "comparison":"compare runs only on this same machine and Python build; not universal score"}
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds",type=int,default=0,help="Optional 50000..500000 CPU-only work")
    parser.add_argument("--cycles",type=int,default=0,help="Optional 50000..500000 CPU-only /usr/bin/time -l counter probe")
    parser.add_argument("--out",type=pathlib.Path)
    args=parser.parse_args()
    if args.rounds!=0 and not 50000<=args.rounds<=500000:
        raise RuntimeError("Benchmark must be 50000..500000 or omitted")
    if args.cycles!=0 and not 50000<=args.cycles<=500000:
        raise RuntimeError("Cycle probe must be 50000..500000 or omitted")
    if args.cycles and args.rounds:raise RuntimeError("Choose one bounded CPU probe")
    result=live(args.rounds,args.cycles)
    raw=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if args.out:
        if args.out.exists():raise RuntimeError("Output path exists; refusing overwrite")
        args.out.write_text(raw,encoding="utf-8")
        print("Read-only power report:",args.out)
    else:
        print(raw,end="")


if __name__=="__main__":
    try:main()
    except (RuntimeError,OSError,ValueError,subprocess.SubprocessError) as exc:
        print("STOP:",exc,file=sys.stderr)
        sys.exit(1)
