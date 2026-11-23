#!/usr/bin/env python3
"""Regression coverage for user-safe, read-only Tiger Lake RCS diagnostics."""
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sl4_rcs_reset_audit", ROOT / "scripts/audit_rcs_gpu_resets_macos.py")
audit_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_mod)

RESET = """Mon Nov 23 23:32:09 2026
Event:               GPU Reset
Date/Time:           Mon Nov 23 23:32:09 2026
Application:         WindowServer
Path:                /Users/secretperson/private/work/hello
OS Version:          Mac OS X Version 26.7.1 (Build 25G241)
Graphics Hardware:   Intel Iris Xe Graphics
Signature:           813
Processing hang for hardware context ID[6]
Scheduler: Host PreemptiveMultiple channels per index
RCS Ring is:\t - busy - in a batch buffer\t <-- Appears hung
CCS Ring is:\t - NOT enabled - idle
BCS Ring is:\t - NOT enabled - idle
VCS0 Ring is:\t - NOT enabled - idle
VCS2 Ring is:\t - NOT enabled - idle
  RING_HEAD   = 0x24e01978  (offset = 0x00001978)
  RING_TAIL   = 0x00001a10
  BB_ADDR     = 0x4302d81d
  Last instruction header executed: 0x7a000204  (IPEHR=0x7a000204)
  - CurrentContextID               : 6
  - LastContextSwitchReason(0x184)  : ELEMENT_SWITCH | WAIT_ON_SEMAPHORE | WAIT_ON_SCANLINE
"""

SECOND = RESET.replace("23:32:09", "17:13:59").replace(
    "WindowServer", "Spectator 3").replace("ID[6]", "ID[355]")
OTHER = RESET.replace("23:32:09", "17:13:45").replace(
    "WindowServer", "Spectator 3").replace(
    "0x7a000204", "0x7b000008").replace(
    "ELEMENT_SWITCH | WAIT_ON_SEMAPHORE | WAIT_ON_SCANLINE",
    "ELEMENT_SWITCH | ACTIVE_TO_IDLE")


class RCSResetAuditTests(unittest.TestCase):
    def test_decode_reference_dump(self):
        result = audit_mod.parse_report(RESET)
        self.assertEqual(result["event_local_time"], "2026-11-23T23:32:09")
        self.assertEqual(result["application"], "WindowServer")
        self.assertEqual(result["last_instruction"], "0x7a000204")
        self.assertEqual(result["rcs"]["status"], "hung")
        self.assertEqual(result["context_id"], "6")
        self.assertEqual(result["rcs_batch_addr"], "0x4302d81d")
        self.assertIn("WAIT_ON_SEMAPHORE", result["last_context_switch_reason"])
        self.assertIn("not proof", result["attribution_limit"])

    def test_untrusted_application_labels_are_sanitized(self):
        tampered = RESET.replace("Application:         WindowServer",
                                 "Application:         /Users/private/unsafe.app")
        record = audit_mod.parse_report(tampered)
        self.assertEqual(record["application"], "<redacted app label>")
        self.assertEqual(audit_mod.sanitized_application("Spectator 3"), "Spectator 3")

    def test_no_secret_paths_or_usernames_in_json(self):
        result = audit_mod.parse_report(RESET)
        text = json.dumps(result)
        self.assertNotIn("secretperson", text)
        self.assertNotIn("/Users/", text)

    def test_not_gpu_reset_discarded(self):
        self.assertIsNone(audit_mod.parse_report(
            RESET.replace("Event:               GPU Reset",
                          "Event:               Shutdown Stall")))
        self.assertIsNone(audit_mod.parse_report(
            RESET.replace("Date/Time:           Mon Nov 23 23:32:09 2026",
                          "Date/Time:           unspecified")))

    def test_parse_file_and_signature_grouping(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for name, contents in enumerate((RESET, SECOND, OTHER), 1):
                (p / f"Kernel_{name:03d}.gpuRestart").write_text(contents)
            result = audit_mod.audit(
                p, since_hours=8, now=datetime(2026, 11, 23, 23, 55),
                hardware=False)
            self.assertEqual(result["gpu_reset_count"], 3)
            self.assertEqual(result["rcs_hang_count"], 3)
            self.assertEqual(
                result["repeated_rcs_signatures"][
                    "0x7a000204|ELEMENT_SWITCH | WAIT_ON_SEMAPHORE | WAIT_ON_SCANLINE"], 2)
            self.assertFalse(result["rcs_patch_stability_proven"])
            self.assertFalse(result["efi_modified"])
            self.assertFalse(result["drivers_modified"])

    def test_filter_uses_event_date_not_file_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "Kernel_old.gpuRestart").write_text(
                RESET.replace("Nov 23", "Nov 18"))
            result = audit_mod.audit(p, since_hours=8,
                                     now=datetime(2026, 11, 23, 23, 55),
                                     hardware=False)
            self.assertEqual(result["gpu_reset_count"], 0)

    def test_skip_symlink_and_large_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Kernel_valid.gpuRestart").write_text(RESET)
            (root / "Kernel_large.gpuRestart").write_bytes(
                b"0" * (audit_mod.MAX_REPORT_BYTES + 1))
            (root / "Kernel_alias.gpuRestart").symlink_to(
                root / "Kernel_valid.gpuRestart")
            events = audit_mod.scan_reports(
                root, 8, datetime(2026, 11, 23, 23, 55))
            self.assertEqual(len(events), 1)

    def test_refuse_unbounded_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "since-hours"):
                audit_mod.scan_reports(Path(tmp), -1, datetime.now())
            with self.assertRaisesRegex(ValueError, "since-hours"):
                audit_mod.scan_reports(Path(tmp), 721, datetime.now())

    def test_parse_recovery_revision2_exact_layout(self):
        words = [2, 3] + [0] * len(audit_mod.RECOVERY_COUNTERS)
        words[2] = 1
        words[3] = 1
        words[4] = 1
        words[9] = 1
        value = audit_mod.decode_recovery_live(
            struct.pack("<26I", *words).hex())
        self.assertEqual(value["revision"], 2)
        self.assertTrue(value["flags"]["gpu_register_recovery"])
        self.assertTrue(value["flags"]["orphan_stamp_fix"])
        self.assertEqual(value["counters"]["resets"], 1)
        self.assertEqual(value["counters"]["sibling_restores"], 1)
        self.assertEqual(value["counters"]["sibling_replays"], 1)
        self.assertIn("not sufficient", value["warning"])

    def test_unknown_recovery_layout_not_false_counts(self):
        self.assertIsNone(audit_mod.decode_recovery_live(None))
        self.assertIsNone(audit_mod.decode_recovery_live("zz"))
        self.assertEqual(audit_mod.decode_recovery_live("00")["status"],
                         "unknown_revision_or_layout")
        words = [3, 1] + [0] * len(audit_mod.RECOVERY_COUNTERS)
        self.assertEqual(audit_mod.decode_recovery_live(
            struct.pack("<26I", *words).hex())["status"],
            "unknown_revision_or_layout")

    def test_registry_properties_and_boot_args_no_leak(self):
        registry = '\n'.join((
            '  |   "TGLGpuRecReady" = Yes',
            '  |   "SL4RCSSinglePortReady" = Yes',
            '  |   "TGLRCSTLBPreparserLive" = <85000000010000000200000003000000>',
            '  |   "TGLGpuRecLive" = <' +
            struct.pack("<26I", *( [2, 3] + [0] * 24 )).hex() + '>',
            '  |   "SystemSerialNumber" = "SHOULD_NEVER_APPEAR"',
        ))
        def mocked_run(command, **_kwargs):
            if command[0].endswith("ioreg"):
                return registry
            return ("boot-args\t-allow3d -wex-sl4-rcs-singleport "
                    "secret=PRIVATE_DO_NOT_OUTPUT")
        with mock.patch.object(audit_mod.sys, "platform", "darwin"), \
             mock.patch.object(audit_mod, "read_command",
                               side_effect=mocked_run):
            state = audit_mod.current_hardware_state()
        self.assertEqual(state["status"], "ok")
        self.assertTrue(state["io_registry_ready"]["SL4RCSSinglePortReady"])
        self.assertTrue(state["boot_flag_enabled"]["-allow3d"])
        self.assertEqual(state["rcs_tlb_preparser"]["write_returns"], 3)
        self.assertNotIn("SystemSerialNumber", json.dumps(state))
        self.assertNotIn("PRIVATE_DO_NOT_OUTPUT", json.dumps(state))

    def test_report_directory_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "ordinary directory"):
                audit_mod.scan_reports(
                    Path(tmp) / "missing", 8, datetime(2026, 11, 23))

    def test_no_actions_to_restart_gpu_or_edit_efi(self):
        source = (ROOT / "scripts/audit_rcs_gpu_resets_macos.py").read_text()
        for command in ("sudo ", "kill -", "launchctl ", "pmset -",
                        "csrutil ", "nvram -", "kextload", "boot-args=",
                        "install -", "mount_efi", "diskutil erase"):
            self.assertNotIn(command, source)

    def test_packaging_and_mac_entry_points(self):
        for filename in ("scripts/build_windows_quickstart_kit.py",
                         "scripts/build_offline_kit.py",
                         "scripts/windows_prepare_tahoe.py"):
            self.assertIn("audit_rcs_gpu_resets_macos.py",
                          (ROOT / filename).read_text(), filename)
        quick = (ROOT / "scripts/QuickStart-Mac.command").read_text()
        self.assertIn("--rcs-audit)", quick)
        self.assertIn('7) python3 "$base/audit_rcs_gpu_resets_macos.py"', quick)


if __name__ == "__main__":
    unittest.main()
