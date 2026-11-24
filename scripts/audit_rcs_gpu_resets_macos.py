#!/usr/bin/env python3
"""Read-only Surface Laptop 4 Intel GPU reset / RCS regression audit.

Parses locally recorded .gpuRestart reports and optionally reads current
IORegistry and boot-arg *feature flags*. Never changes graphics, EFI, files,
sleep, display, NVRAM, kexts, or running processes. Does NOT prove causal
attribution or stable recovery from a kernel GPU reset.

Example: python3 scripts/audit_rcs_gpu_resets_macos.py --since-hours 12 --json
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import subprocess
import sys

DEFAULT_DIR = Path("/Library/Logs/DiagnosticReports")
MAX_REPORT_BYTES = 512 * 1024
MAX_REPORTS = 300
BOOT_FLAGS = (
    "-allow3d", "-disablegfxfirmware", "-wex-tgl-no-posh",
    "-wex-tgl-gpurec", "-wex-tgl-stampfix",
    "-wex-sl4-rcs-singleport", "-wex-sl4-rcs-nativequeue-trial", "-wex-sl4-tgl-dmc",
    "-wex-tgl-edp-keep", "-wex-tgl-edp-softsleep",
    "-wex-tgl-nomc", "-wex-tgl-gpurec-halt",
)
READY_KEYS = (
    "SL4RCSSinglePortReady", "SL4RCSNativeQueueTrialReady", "TGLGpuRecReady", "TGLStampFixReady",
    "TGLRCSTLBPreparserReady", "SL4DMCLocalInitVerified",
    "SL4DMCLocalWakeHookReady", "TGLNoPOSHReady",
)
RECOVERY_COUNTERS = (
    "resets", "sibling_restores", "sibling_replays", "own_fixes",
    "kick_skips", "extras_fixes", "last_rcu", "last_status",
    "sibling_not_ready", "list_invalid", "stamp_fixes",
    "stamp_last", "stamp_declined", "whitelist_fixes",
    "pre_fix_rcu", "pre_fix_reads", "pocs_before", "pocs_after",
    "pocs88_before", "pocs88_after", "sibling_resubmits",
    "sibling_halts", "halt_not_ready", "sibling_resumes",
)
MONTHS = {x: i + 1 for i, x in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def match(pattern: str, raw: str, *, flags=0):
    found = re.search(pattern, raw, flags=flags)
    return found.group(1).strip() if found else None


def parse_report_date(raw):
    # The ASCII report header is locale-invariant despite Russian macOS UI.
    value = match(r"(?m)^Date/Time:\s*(?:\w{3}\s+)?"
                  r"(\w{3}\s+\d+\s+\d\d:\d\d:\d\d\s+\d{4})\s*$", raw)
    if value is None:
        return None
    parts = value.split()
    if len(parts) != 4 or parts[0] not in MONTHS:
        return None
    try:
        hour, minute, second = (int(x) for x in parts[2].split(":"))
        return datetime(int(parts[3]), MONTHS[parts[0]], int(parts[1]),
                        hour, minute, second)
    except (ValueError, OverflowError):
        return None


def sanitized_application(raw):
    """Treat report application names as untrusted labels, never as file paths."""
    if raw is None:
        return None
    if "/" in raw or "\\" in raw or len(raw) > 80:
        return "<redacted app label>"
    return re.sub(r"[^A-Za-z0-9._ ()+-]", "?", raw)


def parse_report(raw: str) -> dict | None:
    if match(r"(?m)^Event:\s*(.+)$", raw) != "GPU Reset":
        return None
    when = parse_report_date(raw)
    if when is None:
        return None
    ring = match(r"(?m)^RCS Ring is:\s*\n?\s*([^\r\n]+)", raw)
    other = {
        name: match(r"(?m)^"+label+r"\s+is:\s*\n?\s*([^\r\n]+)", raw)
        for name, label in (
            ("ccs", "CCS Ring"), ("vcs0", "VCS0 Ring"),
            ("vcs2", "VCS2 Ring"), ("bcs", "BCS Ring"))
    }
    status = "hung" if ring and "Appears hung" in ring else "unclassified"
    return {
        "event_local_time": when.isoformat(timespec="seconds"),
        "application": sanitized_application(match(r"(?m)^Application:\s*(.+)$", raw)),
        "signature": match(r"(?m)^Signature:\s*(\d+)", raw),
        "graphics_hardware": match(r"(?m)^Graphics Hardware:\s*(.+)$", raw),
        "os_version": match(r"(?m)^OS Version:\s*(.+)$", raw),
        "scheduler": match(r"(?m)^\s*Scheduler:\s*(.+)$", raw),
        "context_id": match(r"Processing hang for hardware context ID\[(\d+)\]", raw),
        "rcs": {"status": status, "raw": ring},
        "other_engines": other,
        "last_instruction": match(
            r"Last instruction header executed:\s*(0x[0-9a-fA-F]+)", raw),
        "last_context_switch_reason": match(
            r"LastContextSwitchReason\(0x[0-9a-fA-F]+\)\s*:\s*([^\r\n]+)", raw),
        "rcs_ring_head": match(r"RING_HEAD\s*=\s*(0x[0-9a-fA-F]+)", raw),
        "rcs_ring_tail": match(r"RING_TAIL\s*=\s*(0x[0-9a-fA-F]+)", raw),
        "rcs_batch_addr": match(r"BB_ADDR\s*=\s*(0x[0-9a-fA-F]+)", raw),
        "attribution_limit": "Application field is an event label, not proof of submitter or cause",
    }


def scan_reports(directory: Path, since_hours: float, now: datetime) -> list[dict]:
    if not 0 < since_hours <= 720:
        raise ValueError("--since-hours must be >0 and <=720")
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("Report directory must be an ordinary directory")
    cutoff = now - timedelta(hours=since_hours)
    report_paths = sorted(directory.glob("Kernel_*.gpuRestart"))
    # Refuse large directories rather than silently sampling or sorting by mtime.
    if len(report_paths) > MAX_REPORTS:
        raise RuntimeError("Report directory contains too many GPU reset files")
    results = []
    for path in report_paths:
        if path.is_symlink() or not path.is_file():
            continue
        if path.stat().st_size > MAX_REPORT_BYTES:
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeError):
            continue
        entry = parse_report(raw)
        if not entry:
            continue
        when = datetime.fromisoformat(entry["event_local_time"])
        if not cutoff <= when <= now + timedelta(minutes=5):
            continue
        # Avoid leaking an account name or device name from report filenames:
        # only include content-defined, public GPU metadata.
        results.append(entry)
    return sorted(results, key=lambda x: x["event_local_time"])


def read_command(argv, timeout=12):
    result = subprocess.run(argv, capture_output=True, text=True,
                            timeout=timeout, check=False)
    if result.returncode != 0:
        return None
    return result.stdout


def decode_recovery_live(hex_value: str | None) -> dict | None:
    if not hex_value:
        return None
    try:
        data = bytes.fromhex(hex_value)
    except ValueError:
        return None
    if len(data) != 104:  # Revision 2: 26 little-endian 32-bit words.
        return {"status": "unknown_revision_or_layout", "length": len(data)}
    import struct
    words = struct.unpack("<26I", data)
    if words[0] != 2:
        return {"status": "unknown_revision_or_layout", "revision": words[0]}
    result = dict(zip(RECOVERY_COUNTERS, words[2:]))
    return {
        "status": "decoded",
        "revision": words[0],
        "flags": {"gpu_register_recovery": bool(words[1] & 1),
                  "orphan_stamp_fix": bool(words[1] & 2),
                  "sibling_halt": bool(words[1] & 4)},
        "counters": result,
        "warning": ("Counters are cumulative for the current boot; reset counts"
                    " are not sufficient proof of end-to-end display recovery"),
    }


def decode_rcs_hook_telemetry(hex_value: str | None) -> dict | None:
    """Decode opt-in v0.1.1 *candidate* hook usage telemetry, if present.

    Missing means the reference Surface has the stock v0.1.0 RCS patch.
    This is NOT GPU-reset telemetry and does not imply successful scheduling.
    """
    if not hex_value:
        return None
    try:
        import struct
        data = bytes.fromhex(hex_value)
    except ValueError:
        return None
    # Exact v1, v2 and v4 telemetry lengths. v4 never stores a scheduler pointer.
    expected_revisions = {28: 1, 48: 2, 52: 4, 56: 5}
    if len(data) not in expected_revisions:
        return {"status": "unknown_revision_or_layout", "length": len(data)}
    fields = struct.unpack("<" + str(len(data)//4) + "I", data)
    if (fields[0] != expected_revisions[len(data)]
            or fields[6] not in (0, 1)
            or (fields[0] == 5 and fields[13] not in (0, 1))):
        return {"status": "unknown_revision_or_layout",
                "revision": fields[0]}
    counters = {
        "dequeue_calls": fields[1],
        "eval_wait_calls": fields[2],
        "preempt_suppressed": fields[3],
        "deferred_port0": fields[4],
        "rejected_port1": fields[5],
    }
    if fields[0] in (2, 4, 5):
        counters.update({
            "deferred_occupied_port": fields[7],
            "deferred_not_ready": fields[8],
            "native_dequeue_calls": fields[9],
            "native_eval_wait_calls": fields[10],
            "other_port_busy_wait_rejections": fields[11],
        })
    if fields[0] in (4, 5):
        counters["native_update_options_calls"] = fields[12]
    return {
        "status": "decoded",
        "revision": fields[0],
        "active": bool(fields[6]),
        "native_queue_trial": bool(fields[13]) if fields[0] == 5 else False,
        "counters": counters,
        "warning": ("Counters are opt-in and cumulative since boot; "
                    "hook activity alone does not prove GPU stability. "
                    "Concurrent snapshots need not have internally equal sums."),
    }


def current_hardware_state():
    if sys.platform != "darwin":
        return {"status": "not_macos"}
    out = read_command(["/usr/sbin/ioreg", "-p", "IOService", "-l",
                        "-w0", "-n", "IOService"], timeout=20)
    if out is None:
        return {"status": "ioreg_unavailable"}
    props = {}
    for key in READY_KEYS:
        value = match(r'"'+re.escape(key)+r'"\s*=\s*(Yes|No)', out)
        props[key] = (value == "Yes") if value is not None else None
    live = match(r'"TGLGpuRecLive"\s*=\s*<([0-9a-fA-F]+)>', out)
    prep = match(r'"TGLRCSTLBPreparserLive"\s*=\s*<([0-9a-fA-F]+)>', out)
    rcs_hooks = match(r'"SL4RCSHookTelemetryLive"\s*=\s*<([0-9a-fA-F]+)>', out)
    preparser = None
    if prep is not None:
        try:
            import struct
            data = bytes.fromhex(prep)
            if len(data) == 16:
                marker, reservations, submissions, returns = struct.unpack(
                    "<4I", data)
                preparser = {"marker": marker, "reservations": reservations,
                             "write_entries": submissions, "write_returns": returns}
        except ValueError:
            pass
    boot_arg_text = read_command(["/usr/sbin/nvram", "-p"], timeout=8)
    flag_states = {}
    if boot_arg_text is not None:
        args = match(r"(?m)^boot-args\s+([^\r\n]*)", boot_arg_text)
        if args is not None:
            enabled = set(args.split())
            flag_states = {name: (name in enabled) for name in BOOT_FLAGS}
    # Never return full IORegistry/NVRAM logs: may contain SMBIOS or serials.
    return {"status": "ok", "boot_flag_enabled": flag_states,
            "io_registry_ready": props, "recovery": decode_recovery_live(live),
            "rcs_tlb_preparser": preparser,
            "rcs_scheduler_hooks": decode_rcs_hook_telemetry(rcs_hooks)}


def audit(directory, *, since_hours, now=None, hardware=True):
    if now is None:
        now = datetime.now()
    events = scan_reports(Path(directory), since_hours, now)
    current = current_hardware_state() if hardware else {"status": "not_checked"}
    hung = [x for x in events if x["rcs"]["status"] == "hung"]
    repeated = {}
    for item in hung:
        signature = (item["last_instruction"] or "unknown",
                     item["last_context_switch_reason"] or "unknown")
        label = "|".join(signature)
        repeated[label] = repeated.get(label, 0) + 1
    ready = current.get("io_registry_ready", {})
    single = ready.get("SL4RCSSinglePortReady")
    native = ready.get("SL4RCSNativeQueueTrialReady")
    is_loaded = True if single is True or native is True else (False if single is False or native is False else None)
    return {
        "read_only": True, "efi_modified": False, "drivers_modified": False,
        "window_hours": since_hours, "checked_at_local": now.isoformat(timespec="seconds"),
        "gpu_reset_count": len(events), "rcs_hang_count": len(hung),
        "repeated_rcs_signatures": repeated,
        "rcs_patch_active_now": is_loaded,
        "rcs_mode": "native_queue_trial" if native is True else ("single_port" if single is True else "not_confirmed"),
        "rcs_patch_stability_proven": False,
        "events": events,
        "current_boot_state": current,
        "interpretation": (
            "RCS hang(s) observed; patch activation alone does not prevent GPU reset."
            if hung else "No recorded RCS GPU resets in window; absence is not stability proof."
        ),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--since-hours", type=float, default=24)
    p.add_argument("--reports-dir", type=Path, default=DEFAULT_DIR)
    p.add_argument("--no-hardware", action="store_true", help="Offline fixtures, no system calls")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    try:
        result = audit(args.reports_dir, since_hours=args.since_hours,
                       hardware=not args.no_hardware)
        if args.json:
            print(json.dumps(result, sort_keys=True, indent=2))
        else:
            print("RCS GPU RESET AUDIT — READ ONLY")
            print(f"Window: last {result['window_hours']} hours; "
                  f"GPU resets: {result['gpu_reset_count']}; "
                  f"RCS hangs: {result['rcs_hang_count']}")
            for ev in result["events"]:
                print(f"{ev['event_local_time']} {ev['application']} "
                      f"RCS={ev['rcs']['status']} IPEHR={ev['last_instruction']} "
                      f"reason={ev['last_context_switch_reason']}")
            print("RCS PATCH ACTIVE NOW:", result["rcs_patch_active_now"])
            hook = result["current_boot_state"].get("rcs_scheduler_hooks")
            if hook and hook.get("status") == "decoded":
                print("OPTIONAL RCS SCHEDULER HOOK COUNTERS:", hook["counters"])
            else:
                print("OPTIONAL RCS SCHEDULER HOOK COUNTERS: unavailable (old RCS build)")
            recovery = result["current_boot_state"].get("recovery")
            if recovery and recovery.get("status") == "decoded":
                print("GPU RECOVERY COUNTERS:", recovery["counters"])
            print(result["interpretation"])
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print("RCS_AUDIT_ERROR:", error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
