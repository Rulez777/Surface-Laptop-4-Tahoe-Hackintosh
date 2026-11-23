#!/usr/bin/env python3
"""Unit tests for read-only sleep audit parsing, without touching hardware."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

src = Path(__file__).resolve().parents[1]/"scripts"/"audit_sleep_macos.py"
spec = importlib.util.spec_from_file_location("audit_sl4", src)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class SleepAuditTests(unittest.TestCase):
    def test_pmset_profiles_parsed_separately(self):
        inp = "Battery Power:\n sleep 0\n displaysleep 0\n hibernatemode 3\nAC Power:\n sleep 0\n displaysleep 0\n hibernatemode 0\n"
        parsed = audit.power_values(inp)
        self.assertEqual(parsed["Battery Power"]["hibernatemode"], 3)
        self.assertEqual(parsed["AC Power"]["hibernatemode"], 0)

    def test_only_whitelisted_gpu_data(self):
        inp = ' "TGLEDPKeepReady" = Yes\n "TGLEDPKept" = 9\n "SystemUUID" = "secret"\n'
        self.assertEqual(audit.driver_flags(inp), {"TGLEDPKeepReady":"Yes", "TGLEDPKept":9})

    def test_audit_cannot_claim_real_sleep_or_physical_wake(self):
        def fake_command(*args):
            if args[1:3] == ("-g", "custom"):
                return "Battery Power:\n sleep 0\nAC Power:\n sleep 0\n"
            if args[0].endswith("ioreg"):
                return '"TGLEDPKeepReady" = Yes'
            return ""
        with mock.patch.object(audit.sys,"platform","darwin"), mock.patch.object(audit,"command",side_effect=fake_command) as cmd:
            result = audit.audit()
        self.assertTrue(result["automatic_system_sleep_disabled_on_all_profiles"])
        self.assertFalse(result["physical_display_wake_verified_by_script"])
        self.assertFalse(result["true_s3_s0ix_suspend_resume_verified_by_script"])
        calls = [c.args for c in cmd.call_args_list]
        self.assertTrue(all(a[0] in ("/usr/bin/pmset", "/usr/sbin/ioreg") for a in calls))

    def test_non_macos_refuses_to_run(self):
        with mock.patch.object(audit.sys,"platform","linux"):
            with self.assertRaisesRegex(RuntimeError,"macOS required"):
                audit.audit()


if __name__ == "__main__":
    unittest.main()
