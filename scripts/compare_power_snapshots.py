#!/usr/bin/env python3
"""Compare two private-free SL4 power snapshots: observations, not EC diagnosis."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def load(path):
    obj=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj,dict) or obj.get("hardware")!="MSHW0250 + MSHW0084":
        raise ValueError("Not a supported SL4 power report")
    probe=obj.get("cpu_cycles_proxy",{})
    if not isinstance(probe,dict):
        raise ValueError("No CPU cycles proxy")
    rounds=probe.get("rounds")
    seconds=probe.get("real_s")
    cpu_time=probe.get("cpu_s")
    freq=probe.get("cycles_per_cpu_second_mhz_proxy")
    if not isinstance(rounds,int) or not isinstance(seconds,(float,int)) or seconds<=0:
        raise ValueError("Invalid cycle probe measurements")
    if not isinstance(cpu_time,(float,int)) or cpu_time<=0:
        raise ValueError("Invalid CPU time")
    if freq is not None and (not isinstance(freq,(float,int)) or freq<=0):
        raise ValueError("Invalid cycles proxy")
    return obj


def compare(before,after):
    x=before["cpu_cycles_proxy"]
    y=after["cpu_cycles_proxy"]
    if x["rounds"]!=y["rounds"]:
        raise ValueError("Different work sizes; cannot directly compare results")
    before_sec=x["real_s"]
    after_sec=y["real_s"]
    if before_sec<=0 or after_sec<=0:
        raise ValueError("Nonpositive benchmark time")
    speedup=before_sec/after_sec
    # The measured test can vary from boot load and thermals. Do not claim
    # causal evidence from clocks or a single observation.
    return {
        "comparison":"SL4 fixed-workload CPU timing",
        "same_workload_rounds":x["rounds"],
        "before_s":before_sec,
        "after_s":after_sec,
        "speedup_factor":round(speedup,2),
        "counter_proxy_before_mhz":x.get("cycles_per_cpu_second_mhz_proxy"),
        "counter_proxy_after_mhz":y.get("cycles_per_cpu_second_mhz_proxy"),
        "cpu_software_limit_before_percent":before.get("pmset_therm",{}).get("CPU_Speed_Limit"),
        "cpu_software_limit_after_percent":after.get("pmset_therm",{}).get("CPU_Speed_Limit"),
        "battery_charge_before":bool(before.get("battery",{}).get("charging")),
        "battery_charge_after":bool(after.get("battery",{}).get("charging")),
        "power_source_before":before.get("power_source"),
        "power_source_after":after.get("power_source"),
        "substantial_speed_recovery_observed":speedup>=2,
        "limitations":"Timing is measured, not a calibrated MHz measurement. No proof of firmware/EC cause, TMP3 benefit or battery-limit causality."
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--before",type=Path,required=True)
    p.add_argument("--after",type=Path,required=True)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    report=compare(load(args.before),load(args.after))
    text=json.dumps(report,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        if args.output.exists():
            raise ValueError("Refusing to overwrite report")
        args.output.write_text(text,encoding="utf-8")
        print("Saved comparison:",args.output)
    else:print(text,end="")


if __name__=="__main__":
    try:main()
    except (OSError,ValueError,KeyError,TypeError) as e:
        print("STOP:",e,file=sys.stderr)
        sys.exit(1)
