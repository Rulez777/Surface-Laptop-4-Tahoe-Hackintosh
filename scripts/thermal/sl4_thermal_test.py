#!/usr/bin/env python3
"""Bounded CPU-only SL4 temperature test. No TMP writes and no fan/RPM control.

Do NOT use this as a claim of validated sustained CPU+GPU thermal behavior.
"""
import argparse
import importlib.util
import multiprocessing as mp
import sys
import time
from pathlib import Path

BASE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("guard",BASE/"sl4_thermal_guard.py")
guard=importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def worker(stop, duty):
    while not stop.is_set():
        start=time.monotonic()
        while time.monotonic()-start < duty*0.12 and not stop.is_set():
            _=257*257
        left=0.12-(time.monotonic()-start)
        if left>0: time.sleep(left)


def run(seconds, workers, duty, limit):
    guard.check_hardware()
    sensor=guard.CpuDie()
    stop=mp.Event()
    children=[]
    samples=[]
    reason="completed"
    try:
        start_temp=sensor.read()
        if start_temp>=limit:
            raise RuntimeError("Starting temperature >= limit, refusing load")
        for _ in range(workers):
            proc=mp.Process(target=worker,args=(stop,duty),daemon=True)
            proc.start()
            children.append(proc)
        start=time.monotonic()
        print("Started CPU-only controlled workload; no EC writes; stop at %.1f C"%limit,flush=True)
        while time.monotonic()-start<seconds:
            temp=sensor.read()
            samples.append(temp)
            print("t=%.1fs CPU_die=%.1fC"%(time.monotonic()-start,temp),flush=True)
            if temp>=limit:
                reason="temperature_stop"
                break
            time.sleep(1)
    finally:
        stop.set()
        for p in children:
            p.join(timeout=3)
            if p.is_alive():p.terminate();p.join(timeout=2)
        sensor.close()
    print("RESULT reason=%s samples=%d min=%.1f max=%.1f"%
          (reason,len(samples),min(samples) if samples else -1,max(samples) if samples else -1),flush=True)
    return 0 if reason=="completed" else 2


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seconds",type=int,default=30)
    p.add_argument("--workers",type=int,default=2)
    p.add_argument("--duty",type=float,default=0.6)
    p.add_argument("--limit-c",type=float,default=80.0)
    args=p.parse_args()
    if not (5<=args.seconds<=120 and 1<=args.workers<=4 and 0.1<=args.duty<=0.8 and 65<=args.limit_c<=85):
        raise RuntimeError("Out-of-range test parameters")
    return run(args.seconds,args.workers,args.duty,args.limit_c)


if __name__=="__main__":
    try:sys.exit(main())
    except (RuntimeError,OSError) as e:
        print("STOP:",e,file=sys.stderr)
        sys.exit(1)
