"""Unit tests for comparing full battery/AC cycle benchmarks."""
import importlib.util
from pathlib import Path
import unittest

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("compare_power",root/"scripts/compare_power_snapshots.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)


def fixture(seconds,rounds=250000,freq=580,source="ac"):
    return {
        "hardware":"MSHW0250 + MSHW0084",
        "power_source":source,
        "battery":{"charging":False},
        "pmset_therm":{"CPU_Speed_Limit":100},
        "cpu_cycles_proxy":{"rounds":rounds,"real_s":seconds,"cpu_s":seconds,
                             "cycles_per_cpu_second_mhz_proxy":freq}
    }


class ComparePowerTests(unittest.TestCase):
    def test_success_after_reboot_is_observation_not_causal_claim(self):
        r=mod.compare(fixture(1.18),fixture(0.21,freq=3200))
        self.assertTrue(r["substantial_speed_recovery_observed"])
        self.assertAlmostEqual(r["speedup_factor"],5.62,places=2)
        self.assertIn("No proof",r["limitations"])

    def test_minor_change_not_recovery(self):
        self.assertFalse(mod.compare(fixture(1.18),fixture(1.15))["substantial_speed_recovery_observed"])

    def test_reject_incompatible_rounds(self):
        with self.assertRaisesRegex(ValueError,"Different work sizes"):
            mod.compare(fixture(1.0),fixture(0.3,rounds=500000))

    def test_validate_missing_frequency_counter_is_optional(self):
        r=mod.compare(fixture(1.1),fixture(0.2,freq=None))
        self.assertIsNone(r["counter_proxy_after_mhz"])


if __name__=="__main__":
    unittest.main()
