#!/usr/bin/env python3
"""Bounded read-only comparison of RCS command opcodes from Intel gpuRestart reports.

Only counts known opcodes and extracts PIPE_CONTROL flags. GPU addresses,
private application labels, serials and raw command buffers are never emitted.
Neither opcode presence nor a matching PIPE_CONTROL IPEHR proves causation.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re
import sys

REPORT_SIZE_LIMIT = 512 * 1024
MAX_REPORTS = 200
RCS_HEADER = "Dumping RCS ring buffer contents:"
DW_LINE = re.compile(r"^0x([0-9a-fA-F]{8})\s*:\s*0x([0-9a-fA-F]{8})\s*$")
EVENT = re.compile(r"(?m)^Event:\s*GPU Reset\s*$")
IPEHR = re.compile(r"(?m)Last instruction header executed:\s*(0x[0-9a-fA-F]+)")
DATE = re.compile(r"^Kernel_(\d{4}-\d\d-\d\d-\d{6})_.*\.gpuRestart$")
OPCODES = {
    0x7A000204: "pipe_control_0x7a000204",
    0x7A000004: "pipe_control_0x7a000004",
    0x02800101: "mi_arbitration_disable",
    0x02800100: "mi_arbitration_enable",
}


def extract_rcs_words(raw: str):
    p = raw.find(RCS_HEADER)
    if p == -1:
        return []
    lines = raw[p + len(RCS_HEADER):].splitlines()
    words = []
    started = False
    for line in lines:
        m = DW_LINE.fullmatch(line.strip())
        if m:
            started = True
            if len(words) >= 2048:
                raise ValueError("Excessive RCS dump word count")
            words.append((int(m.group(1), 16), int(m.group(2), 16)))
        elif started:
            break
    return words


def summarize(raw: str):
    if not EVENT.search(raw):
        return None
    m = IPEHR.search(raw)
    words = extract_rcs_words(raw)
    values = [w[1] for w in words]
    count = Counter(values)
    pc_flags = Counter(
        f"0x{values[i+1]:08x}" for i, v in enumerate(values[:-1])
        if v == 0x7A000204
    )
    disable = count[0x02800101]
    enable = count[0x02800100]
    return {
        "reported_ipehr": m.group(1).lower() if m else None,
        "rcs_dump_available": bool(words),
        "rcs_dword_count": len(words),
        "known_opcodes": {name: count[key] for key, name in OPCODES.items()},
        "pipe_control_0x7a000204_flags": dict(sorted(pc_flags.items())),
        "arbitration_disable_enable_counts_equal": disable == enable,
        "interpretation_limit": (
            "Counts show observed command words, not which instruction "
            "caused a wait, whether arb pairs are balanced over the full "
            "ring or whether hardware returned from a GPU reset."
        ),
    }


def compare(directory: Path, *, limit=MAX_REPORTS):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Use an ordinary directory of reports")
    paths = sorted(directory.glob("Kernel_*.gpuRestart"))
    if len(paths) > limit or limit > MAX_REPORTS:
        raise ValueError("Too many GPU reset reports")
    items = []
    for path in paths:
        if path.is_symlink() or not path.is_file():
            continue
        m = DATE.fullmatch(path.name)
        if not m or path.stat().st_size > REPORT_SIZE_LIMIT:
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        result = summarize(raw)
        if result is not None:
            # Report an ISO time derived only from a constrained filename.
            stamp = datetime.strptime(m.group(1), "%Y-%m-%d-%H%M%S")
            result["event_local"] = stamp.isoformat(timespec="seconds")
            items.append(result)
    return {
        "read_only": True,
        "driver_modified": False,
        "efi_modified": False,
        "records": items,
        "gpu_reset_reports_analysed": len(items),
        "stability_fix_proven": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reports-dir", type=Path,
                   default=Path("/Library/Logs/DiagnosticReports"))
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    try:
        r = compare(args.reports_dir)
        if args.json:
            print(json.dumps(r, indent=2, sort_keys=True))
        else:
            for event in r["records"]:
                print(event["event_local"],
                      "IPEHR", event["reported_ipehr"],
                      "RCS words", event["rcs_dword_count"],
                      "known opcodes", event["known_opcodes"],
                      "PIPE_CONTROL flags", event["pipe_control_0x7a000204_flags"])
            print("COMPARED", len(r["records"]), "GPU RESET REPORTS; NO MODIFICATIONS")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print("RCS_RING_AUDIT_ERROR:", type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
