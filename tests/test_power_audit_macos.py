#!/usr/bin/env python3
"""Read-only power report parsing tests."""
import importlib.util
from pathlib import Path
import unittest

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("power",root/"scripts/audit_power_macos.py")
power=importlib.util.module_from_spec(spec)
spec.loader.exec_module(power)


class PowerAuditTests(unittest.TestCase):
    def test_source_matching_is_exact(self):
        self.assertEqual(power.source_status("Now drawing from 'AC Power'\n -Battery"),"ac")
        self.assertEqual(power.source_status("Now drawing from 'Battery Power'\n"),"battery")
        self.assertEqual(power.source_status("Now drawing from 'AC Powersaving'"),"unknown")

    def test_big_surface_one_not_saver(self):
        self.assertEqual(power.profile('"PerformanceMode" = 1')["registry_label"],"Recommended")
        self.assertEqual(power.profile('"PerformanceMode" = 2')["registry_label"],"Battery Saver")
        self.assertFalse(power.profile('"PerformanceMode" = 3')["verified_ec_effect"])

    def test_private_adapter_details_never_exposed(self):
        raw='"CurrentCapacity" = 1400\n"MaxCapacity" = 5400\n"IsCharging" = Yes\n"ExternalConnected" = Yes\n"AdapterDetails" = {"Watts"=60,"SerialNumber"=999991,"AdapterID"=256}\n"BatteryData" = {"Serial"="PRIVATE999"}'
        result=power.parse_battery(raw)
        self.assertEqual(result["capacity_units"],1400)
        self.assertEqual(result["charger_watts"],60)
        self.assertEqual(result["charging"],True)
        self.assertNotIn("PRIVATE999",str(result))
        self.assertNotIn("999991",str(result))

    def test_therm_limits_do_not_claim_clock_frequency(self):
        inp="CPU_Scheduler_Limit = 100\n CPU_Available_CPUs = 8\n CPU_Speed_Limit = 100"
        self.assertEqual(power.parse_power_limits(inp),{
            "CPU_Scheduler_Limit":100,"CPU_Available_CPUs":8,"CPU_Speed_Limit":100})

    def test_cycle_counter_parsing_is_explicit_proxy(self):
        from unittest.mock import patch
        import subprocess
        record="        1.27 real         1.13 user         0.10 sys\n          2006566792 instructions retired\n           718849943 cycles elapsed\n"
        with patch.object(power.subprocess,"run",return_value=subprocess.CompletedProcess([],0,stdout="",stderr=record)):
            data=power.count_cpu_cycles(250000)
        self.assertEqual(data["rounds"],250000)
        self.assertAlmostEqual(data["cycles_per_cpu_second_mhz_proxy"],584.4,delta=0.3)
        self.assertIn("not",data["notice"].lower())

    def test_cycle_counter_absence_is_not_fabricated(self):
        from unittest.mock import patch
        import subprocess
        record="        1.27 real         1.13 user         0.10 sys\n"
        with patch.object(power.subprocess,"run",return_value=subprocess.CompletedProcess([],0,stdout="",stderr=record)):
            data=power.count_cpu_cycles(250000)
        self.assertIsNone(data["cycles_per_cpu_second_mhz_proxy"])
        self.assertIsNone(data["cycles_elapsed"])

    def test_missing_sensors_fail_closed(self):
        self.assertIsNone(power.read_int("no signal","CurrentCapacity"))
        self.assertIsNone(power.read_boolean("no signal","IsCharging"))
        self.assertEqual(power.profile("no driver")["registry_label"],"unknown")


if __name__=="__main__":
    unittest.main()
