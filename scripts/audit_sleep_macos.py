#!/usr/bin/env python3
"""Read-only SL4 display/system sleep audit. Never changes power/EFI state."""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

FLAGS = ("TGLEDPKeepReady", "TGLSoftSleepReady", "TGLGpuRecReady",
         "TGLStampFixReady", "TGLWakeTraceReady", "TGLEDPKept")


def command(*argv):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=25, check=False)
    if result.returncode:
        raise RuntimeError("Read-only command failed: " + " ".join(argv) + " (exit " + str(result.returncode) + ")")
    return result.stdout


def power_values(output):
    """Parse only AC/battery numeric pmset keys; ignore per-host identifiers."""
    result, active = {}, None
    for line in output.splitlines():
        if line in ("AC Power:", "Battery Power:"):
            active = line[:-1]
            result[active] = {}
        elif active:
            m = re.match(r"^\s*(sleep|displaysleep|hibernatemode|standby|powernap|lowpowermode)\s+(\d+)\s*$", line)
            if m:
                result[active][m.group(1)] = int(m.group(2))
    return result


def driver_flags(output):
    """Return only whitelisted WhateverXe flag values, not private registry data."""
    found = {}
    for line in output.splitlines():
        m = re.search(r'"(' + '|'.join(FLAGS) + r')"\s*=\s*(Yes|No|\d+)', line)
        if m:
            found[m.group(1)] = int(m.group(2)) if m.group(2).isdigit() else m.group(2)
    return found


def sleep_events(output):
    interesting = ("Entering Sleep", "Wake from", "DarkWake", "Sleep/Wakes since boot")
    return [re.sub(r"\s+", " ", line).strip()[:260] for line in output.splitlines()
            if any(fragment in line for fragment in interesting)][-20:]


def assertion_summary(output):
    values = {}
    for name in ("PreventUserIdleDisplaySleep", "PreventUserIdleSystemSleep", "PreventSystemSleep"):
        match = re.search(r"^\s*" + name + r"\s+(\d+)\s*$", output, re.MULTILINE)
        if match:
            values[name] = int(match.group(1))
    return values


def audit():
    if sys.platform != "darwin":
        raise RuntimeError("macOS required; no changes performed")
    settings = power_values(command("/usr/bin/pmset", "-g", "custom"))
    flags = driver_flags(command("/usr/sbin/ioreg", "-lw0"))
    assertions = assertion_summary(command("/usr/bin/pmset", "-g", "assertions"))
    events = sleep_events(command("/usr/bin/pmset", "-g", "log"))
    return {
        "date_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "power_settings": settings,
        "power_assertions": assertions,
        "edp_driver_flags": flags,
        "recent_power_events": events,
        "automatic_system_sleep_disabled_on_all_profiles": bool(settings) and all(
            x.get("sleep") == 0 for x in settings.values()),
        "physical_display_wake_verified_by_script": False,
        "true_s3_s0ix_suspend_resume_verified_by_script": False,
        "warning": "Read-only registry/log snapshot. Physical screen wake and real S3/S0ix resume require independent testing; flags alone cannot prove either.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write JSON to an explicit local path; default stdout")
    args = parser.parse_args()
    data = json.dumps(audit(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise RuntimeError("Refusing to overwrite existing report: " + str(args.output))
        args.output.write_text(data, encoding="utf-8")
        print("Read-only audit saved: " + str(args.output))
    else:
        print(data, end="")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print("AUDIT STOP: " + str(exc), file=sys.stderr)
        sys.exit(1)
