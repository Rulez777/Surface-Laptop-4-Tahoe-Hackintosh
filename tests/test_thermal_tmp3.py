#!/usr/bin/env python3
"""Portable unit tests for the optional SL4 TMP3 service; no hardware writes."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

SRC = Path(__file__).resolve().parents[1] / "scripts" / "thermal" / "sl4_tmp3_service.py"
spec = importlib.util.spec_from_file_location("sl4_tmp3_under_test", SRC)
svc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(svc)


class DummySensor:
    def __init__(self, value=None, error=None):
        self.value, self.error, self.closed = value, error, False

    def read(self):
        if self.error is not None:
            raise self.error
        return self.value

    def close(self):
        self.closed = True


class DummyControl:
    def __init__(self):
        self.modes = []

    def set(self, mode):
        self.modes.append(mode)


class DummyGuard:
    def __init__(self, sensor, control):
        self.CpuDie = lambda: sensor
        self.BigSurface = lambda: control


class ThermalServiceTests(unittest.TestCase):
    def test_wake_detector_ignores_normal_elapsed_time(self):
        detector = svc.WakeDetector(100, 50)
        self.assertFalse(detector.detect(105, 55))
        self.assertFalse(detector.detect(125, 75))

    def test_wake_detector_requires_actual_uptime_gap(self):
        detector = svc.WakeDetector(100, 50)
        self.assertTrue(detector.detect(130, 54))
        self.assertFalse(detector.detect(135, 59))

    def test_acceptable_cpu_temp_requests_only_mode_three(self):
        sensor, control = DummySensor(value=47.0), DummyControl()
        with mock.patch.object(svc, "log"):
            self.assertEqual(svc.request_once(DummyGuard(sensor, control)), 47.0)
        self.assertTrue(sensor.closed)
        self.assertEqual(control.modes, [3])

    def test_hot_sensor_rejects_all_profile_requests(self):
        for temperature in (80.0, 94.0, 0.0, 106.0):
            with self.subTest(temperature=temperature):
                sensor, control = DummySensor(value=temperature), DummyControl()
                with self.assertRaises(RuntimeError):
                    svc.request_once(DummyGuard(sensor, control))
                self.assertTrue(sensor.closed)
                self.assertEqual(control.modes, [])

    def test_sensor_error_closes_handle_and_does_not_write(self):
        sensor, control = DummySensor(error=RuntimeError("sensor failed")), DummyControl()
        with self.assertRaisesRegex(RuntimeError, "sensor failed"):
            svc.request_once(DummyGuard(sensor, control))
        self.assertTrue(sensor.closed)
        self.assertEqual(control.modes, [])

    def test_service_installs_only_as_opt_in_daemon(self):
        p = svc.plist_config()
        self.assertEqual(p["Label"], svc.LABEL)
        self.assertTrue(p["RunAtLoad"])
        self.assertEqual(p["ProgramArguments"][-1], "--daemon")
        self.assertFalse(any("EFI" in a for a in p["ProgramArguments"]))
        self.assertEqual(svc.MAX_TEMP, 80.0)


if __name__ == "__main__":
    unittest.main()
