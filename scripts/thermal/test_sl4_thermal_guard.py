"""Synthetic SL4 temperature monitoring tests: no hardware access."""
import ctypes
import importlib.util
import pathlib
import sys
import unittest
from unittest.mock import patch, MagicMock

src = pathlib.Path(__file__).with_name("sl4_thermal_guard.py")
spec = importlib.util.spec_from_file_location("sl4_guard", src)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ThermalGuardTests(unittest.TestCase):
    def test_apple_smc_abi(self):
        self.assertEqual(ctypes.sizeof(mod.Data), 80)

    def test_readonly_temperature_labels(self):
        self.assertEqual(mod.temperature_status(59), "below 80 C")
        self.assertIn("ELEVATED", mod.temperature_status(80))
        self.assertIn("ELEVATED", mod.temperature_status(88))
        self.assertIn("HIGH", mod.temperature_status(90))
        self.assertIn("HIGH", mod.temperature_status(98))

    def test_impossible_reading_rejected(self):
        for reading in (0, -5, 106, 200):
            with self.assertRaises(RuntimeError):
                mod.temperature_status(reading)

    def test_smc_missing_cpu_key(self):
        self.assertIn("SMCProcessor.kext", mod.smc_error(0x84, "TC0D"))
        self.assertIn("not found", mod.smc_error(0x84, "TC0D"))

    def test_smc_other_error(self):
        self.assertIn("not readable", mod.smc_error(0x85, "TC0D"))
        self.assertIn("rejected request", mod.smc_error(0x8B, "TC0D"))

    def test_no_battery_sensor(self):
        self.assertIn(b"TC0D", mod.CpuDie.read.__code__.co_consts)
        self.assertNotIn(b"TC0P", mod.CpuDie.read.__code__.co_consts)

    def test_automatic_write_refused_before_hardware_access(self):
        with patch.object(sys,"argv",["guard.py","--control"]), \
             patch.object(mod,"check_hardware") as hardware, \
             patch.object(mod,"BigSurface") as sender:
            with self.assertRaisesRegex(RuntimeError, "DISABLED"):
                mod.main()
            hardware.assert_not_called()
            sender.assert_not_called()

    def test_manual_mode_requires_ack(self):
        with patch.object(sys,"argv",["guard.py","--set-profile","3"]), \
             patch.object(mod,"check_hardware") as hardware, \
             patch.object(mod,"BigSurface") as sender:
            with self.assertRaisesRegex(RuntimeError, "requires --ack"):
                mod.main()
            hardware.assert_not_called()
            sender.assert_not_called()

    def test_manual_mode_requires_root(self):
        with patch.object(sys,"argv",["guard.py","--set-profile","3","--ack","SET-TMP-3-NOT-FAN-RPM"]), \
             patch.object(mod.os,"geteuid", return_value=501), \
             patch.object(mod,"BigSurface") as sender:
            with self.assertRaisesRegex(RuntimeError, "requires sudo"):
                mod.main()
            sender.assert_not_called()

    def test_manual_mode_refuses_hot_cpu(self):
        sensor = MagicMock()
        sensor.read.return_value = 88.0
        with patch.object(sys,"argv",["guard.py","--set-profile","3","--ack","SET-TMP-3-NOT-FAN-RPM"]), \
             patch.object(mod.os,"geteuid", return_value=0), \
             patch.object(mod,"check_hardware"), \
             patch.object(mod,"CpuDie", return_value=sensor), \
             patch.object(mod,"BigSurface") as sender:
            with self.assertRaisesRegex(RuntimeError, "refuse to raise"):
                mod.main()
            sender.assert_not_called()
            sensor.close.assert_called_once()

    def test_manual_mode_sends_only_three(self):
        sensor = MagicMock()
        sensor.read.return_value = 58.0
        with patch.object(sys,"argv",["guard.py","--set-profile","3","--ack","SET-TMP-3-NOT-FAN-RPM"]), \
             patch.object(mod.os,"geteuid", return_value=0), \
             patch.object(mod,"check_hardware"), \
             patch.object(mod,"CpuDie", return_value=sensor), \
             patch.object(mod,"BigSurface") as backend:
            mod.main()
            backend.return_value.set.assert_called_once_with(3)
            sensor.close.assert_called_once()

    def test_monitor_never_sends_ec_command(self):
        sensor = MagicMock()
        sensor.read.side_effect = [59.0,88.0,64.0]
        with patch.object(sys,"argv",["guard.py","--monitor","--samples","3"]), \
             patch.object(mod,"check_hardware"), \
             patch.object(mod,"CpuDie", return_value=sensor), \
             patch.object(mod,"BigSurface") as backend, \
             patch.object(mod.time,"sleep"):
            mod.main()
            backend.assert_not_called()
            self.assertEqual(sensor.read.call_count,3)

    def test_monitor_stops_on_repeated_sensor_failures(self):
        sensor=MagicMock()
        sensor.read.side_effect = [59.0, RuntimeError("bad"),RuntimeError("bad"),RuntimeError("bad")]
        with patch.object(sys,"argv",["guard.py","--monitor","--samples","5"]), \
             patch.object(mod,"check_hardware"), \
             patch.object(mod,"CpuDie", return_value=sensor), \
             patch.object(mod,"BigSurface") as backend, \
             patch.object(mod.time,"sleep"):
            with self.assertRaisesRegex(RuntimeError, "monitoring stopped"):
                mod.main()
            backend.assert_not_called()


if __name__ == "__main__":
    unittest.main()
