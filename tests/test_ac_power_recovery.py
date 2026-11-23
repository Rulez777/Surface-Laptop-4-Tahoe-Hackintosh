#!/usr/bin/env python3
"""Pure state machine tests; no privileged power or EFI writes."""
import importlib.util
import pathlib
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("acretry", ROOT/"scripts/thermal/sl4_ac_retrigger.py")
ac=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ac)


class SourceWatcherTests(unittest.TestCase):
    def test_parse_power_safely(self):
        self.assertEqual(ac.parse_source("Now drawing from 'AC Power'\n -InternalBattery-0 24%; charging"),"ac")
        self.assertEqual(ac.parse_source("Now drawing from 'Battery Power'\n -InternalBattery-0 24%; discharging"),"battery")
        self.assertEqual(ac.parse_source("Invalid power source"),"unknown")
        self.assertEqual(ac.parse_source(""),"unknown")

    def test_stable_ac_reconnect_once(self):
        v=ac.SourceWatcher("battery",0)
        self.assertFalse(v.sample("ac",1))
        self.assertFalse(v.sample("ac",16))
        self.assertTrue(v.sample("ac",31))
        self.assertFalse(v.sample("ac",46))
        self.assertFalse(v.sample("ac",61))
        self.assertFalse(v.sample("battery",76))
        self.assertFalse(v.sample("battery",91))
        self.assertFalse(v.sample("battery",106))
        self.assertFalse(v.sample("ac",121))
        self.assertFalse(v.sample("ac",136))
        self.assertFalse(v.sample("ac",151)) # cooldown
        self.assertFalse(v.sample("battery",300))
        self.assertFalse(v.sample("battery",315))
        self.assertFalse(v.sample("battery",330))
        self.assertFalse(v.sample("ac",346))
        self.assertFalse(v.sample("ac",361))
        self.assertTrue(v.sample("ac",376)) # enough elapsed

    def test_no_request_on_disconnect(self):
        v=ac.SourceWatcher("ac",0)
        for index in (1,2,3,4,5):
            self.assertFalse(v.sample("battery",index))

    def test_transient_flapping_never_triggers(self):
        v=ac.SourceWatcher("battery",0)
        for index in range(1,60):
            self.assertFalse(v.sample("ac" if index%2==0 else "battery", index))

    def test_unknown_breaks_transition(self):
        v=ac.SourceWatcher("battery",0)
        self.assertFalse(v.sample("ac",1))
        self.assertFalse(v.sample("ac",2))
        self.assertFalse(v.sample("unknown",3))
        self.assertFalse(v.sample("ac",4))
        self.assertFalse(v.sample("ac",5))
        self.assertTrue(v.sample("ac",6))

    def test_failed_hardware_preflight_never_restarts(self):
        with patch.object(ac,"acpi_verified", side_effect=RuntimeError("Unsupported")):
            with patch.object(ac,"sh") as sh:
                with self.assertRaisesRegex(RuntimeError,"Unsupported"):
                    ac.restart_existing()
                sh.assert_not_called()

    def test_power_preflight_requires_external_power(self):
        with patch.object(ac,"acpi_verified"):
            with patch.object(ac,"check_original_service"):
                with patch.object(ac,"get_source",return_value="battery"):
                    with self.assertRaisesRegex(RuntimeError,"Adapter no longer connected"):
                        ac.confirm_safe_request()

    def test_install_rejects_wrong_ack(self):
        with self.assertRaisesRegex(RuntimeError,"acknowledgement"):
            ac.install("")

    def test_remove_rejects_wrong_ack(self):
        with self.assertRaisesRegex(RuntimeError,"acknowledgement"):
            ac.remove("")


if __name__=="__main__":
    unittest.main()
