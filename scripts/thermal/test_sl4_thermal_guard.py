"""Synthetic tests. No macOS IOKit, fan, TMP, EFI or firmware calls."""
import ctypes
import importlib.util
import pathlib
import unittest

src = pathlib.Path(__file__).with_name("sl4_thermal_guard.py")
spec = importlib.util.spec_from_file_location("sl4_guard", src)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ThermalPolicyTests(unittest.TestCase):
    def test_apple_smc_structure_has_expected_size(self):
        self.assertEqual(ctypes.sizeof(mod.Data), 80)

    def test_normal_cool(self):
        p = mod.Policy()
        self.assertEqual(p.select(55.0, 0), 3)
        self.assertEqual(p.select(70.0, 5), 3)

    def test_single_hot_sample_does_not_trigger(self):
        p = mod.Policy()
        self.assertEqual(p.select(80, 0), 3)
        self.assertEqual(p.select(79, 5), 3)

    def test_two_hot_samples_request_tmp_not_rpm(self):
        p = mod.Policy()
        self.assertEqual(p.select(80, 0), 3)
        self.assertEqual(p.select(81, 5), 4)
        self.assertEqual(p.state, "hot")

    def test_hysteresis_and_sixty_second_cooldown(self):
        p = mod.Policy()
        p.select(80, 0)
        p.select(81, 5)
        self.assertEqual(p.select(75, 10), 4)
        self.assertEqual(p.select(71, 20), 4)
        self.assertEqual(p.select(71, 79), 4)
        self.assertEqual(p.select(71, 80), 3)

    def test_critical_mode_recommended_not_battery_saver(self):
        p = mod.Policy()
        self.assertEqual(p.select(90, 0), 1)
        self.assertEqual(p.select(86, 5), 1)
        self.assertEqual(p.select(71, 10), 1)
        self.assertEqual(p.select(71, 70), 3)

    def test_impossible_temperature_rejected(self):
        p = mod.Policy()
        for temp in (0, -20, 106, 200):
            with self.assertRaises(RuntimeError):
                p.select(temp, 1)

    def test_battery_is_not_sensor_source(self):
        self.assertEqual(mod.CpuDie.read.__name__, "read")
        self.assertNotIn(b"TC0P", mod.CpuDie.read.__code__.co_consts)
        self.assertIn(b"TC0D", mod.CpuDie.read.__code__.co_consts)


if __name__ == "__main__":
    unittest.main()
