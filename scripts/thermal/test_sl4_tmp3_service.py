"""Tests for optional macOS TMP3 startup/wake persistence; no hardware or EFI."""
import importlib.util
import json
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location("sl4_service", Path(__file__).with_name("sl4_tmp3_service.py"))
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class WakeTests(unittest.TestCase):
    def test_normal_time_does_not_trigger_wake(self):
        sensor = service.WakeDetector(100, 50)
        self.assertFalse(sensor.detect(105, 55))
        self.assertFalse(sensor.detect(110, 60))

    def test_suspended_time_triggers_once(self):
        sensor = service.WakeDetector(100, 50)
        self.assertTrue(sensor.detect(250, 56))
        self.assertFalse(sensor.detect(255, 61))

    def test_small_clock_jump_does_not_trigger(self):
        sensor = service.WakeDetector(100, 50)
        self.assertFalse(sensor.detect(114, 55))

    def test_counter_backward_does_not_trigger(self):
        sensor = service.WakeDetector(100, 50)
        self.assertFalse(sensor.detect(150, 40))


class TMPAttemptTests(unittest.TestCase):
    def test_cool_cpu_single_tmp3_request(self):
        guard = MagicMock()
        sensor = guard.CpuDie.return_value
        sensor.read.return_value = 55.0
        self.assertEqual(service.request_once(guard), 55.0)
        guard.BigSurface.return_value.set.assert_called_once_with(3)
        sensor.close.assert_called_once()

    def test_hot_cpu_refuses_ec_write(self):
        guard=MagicMock()
        guard.CpuDie.return_value.read.return_value = 88.0
        with self.assertRaises(RuntimeError):
            service.request_once(guard)
        guard.BigSurface.assert_not_called()
        guard.CpuDie.return_value.close.assert_called_once()

    def test_invalid_cpu_reading_refuses_ec_write(self):
        for temp in (0.0, -4.0, 105.0, 200.0):
            guard=MagicMock()
            guard.CpuDie.return_value.read.return_value = temp
            with self.assertRaises(RuntimeError):
                service.request_once(guard)
            guard.BigSurface.assert_not_called()

    def test_daemon_sends_only_at_start_and_after_wake(self):
        class FakeClock:
            def __init__(self):
                self.up = 500.0
                self.wall = 1000.0
                self.ticks = 0

            def step(self, seconds):
                self.ticks += 1
                self.up += seconds
                self.wall += seconds
                if self.ticks == 5:
                    self.wall += 180  # Suspended interval excluded from uptime.
                if self.ticks >= 12:
                    raise KeyboardInterrupt()

        fake=FakeClock()
        with patch.object(service.os,"geteuid", return_value=0), \
             patch.object(service,"cpu_and_surface_module",return_value=MagicMock()), \
             patch.object(service,"hardware_safety"), \
             patch.object(service,"uptime",side_effect=lambda: fake.up), \
             patch.object(service.time,"time",side_effect=lambda: fake.wall), \
             patch.object(service.time,"sleep",side_effect=fake.step), \
             patch.object(service,"request_once",return_value=54.0) as request:
            with self.assertRaises(KeyboardInterrupt):
                service.run_daemon()
            self.assertEqual(request.call_count,2)

    def test_sensor_failure_does_not_write(self):
        guard=MagicMock()
        guard.CpuDie.return_value.read.side_effect=RuntimeError("missing sensor")
        with self.assertRaises(RuntimeError):
            service.request_once(guard)
        guard.BigSurface.assert_not_called()
        guard.CpuDie.return_value.close.assert_called_once()


class LaunchdTests(unittest.TestCase):
    def test_uses_root_system_launchdaemon(self):
        pl=service.plist_config()
        self.assertTrue(pl["RunAtLoad"] and pl["KeepAlive"])
        self.assertEqual(pl["Label"],"com.rulez777.sl4-tmp3")
        self.assertEqual(pl["ProgramArguments"][-1], "--daemon")
        self.assertNotIn("StartInterval", pl)
        self.assertNotIn("WatchPaths", pl)

    def test_install_then_remove_owned_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            support = t/"Application Support"
            launch = t/"LaunchDaemons"
            src = t/"src"
            support.mkdir()
            launch.mkdir()
            src.mkdir()
            (src/service.SCRIPT_NAME).write_text("service source", encoding="utf-8")
            (src/service.GUARD_NAME).write_text("guard source", encoding="utf-8")
            target = support/"SL4-TMP3"
            pl = launch/"com.rulez777.sl4-tmp3.plist"
            with patch.object(service, "ROOT", target), \
                 patch.object(service, "PLIST", pl), \
                 patch.object(service, "preflight"), \
                 patch.object(service.os, "geteuid", return_value=0), \
                 patch.object(service.os, "chown"), \
                 patch.object(service, "subprocess_launchctl", return_value=MagicMock(returncode=0)) as launchctl:
                service.install("INSTALL-SL4-TMP3",src/service.SCRIPT_NAME)
                self.assertTrue(pl.is_file())
                self.assertTrue((target/service.MANIFEST).is_file())
                self.assertEqual(plistlib.loads(pl.read_bytes())["ProgramArguments"][-2:],
                                 [str(target/service.SCRIPT_NAME), "--daemon"])
                launchctl.assert_called_once_with("bootstrap", "system", str(pl))
                service.remove("REMOVE-SL4-TMP3")
                self.assertFalse(pl.exists())
                self.assertFalse(target.exists())

    def test_reject_preexisting_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"existing.plist"
            path.write_text("unrelated")
            with patch.object(service, "PLIST", path), \
                 patch.object(service.os, "geteuid", return_value=0), \
                 patch.object(service, "preflight") as preflight:
                with self.assertRaisesRegex(RuntimeError,"already exists"):
                    service.install("INSTALL-SL4-TMP3",Path(tmp)/"source.py")
                preflight.assert_not_called()

    def test_remove_rejects_modified_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            t=Path(tmp)
            root=t/"SL4-TMP3";root.mkdir()
            p=t/"launch.plist"
            (root/service.SCRIPT_NAME).write_text("tampered")
            (root/service.GUARD_NAME).write_text("guard")
            (root/service.MANIFEST).write_text(json.dumps({
                "service":service.LABEL, "source_hash":"invalid", "guard_hash":"invalid"}))
            p.write_bytes(plistlib.dumps({"Label":service.LABEL,
                "ProgramArguments":["/usr/bin/python3",str(root/service.SCRIPT_NAME),"--daemon"]}))
            with patch.object(service,"ROOT",root), \
                 patch.object(service,"PLIST",p), \
                 patch.object(service.os,"geteuid",return_value=0), \
                 patch.object(service,"subprocess_launchctl") as launchctl:
                with self.assertRaisesRegex(RuntimeError,"does not match manifest"):
                    service.remove("REMOVE-SL4-TMP3")
                launchctl.assert_not_called()
                self.assertTrue(p.exists())


if __name__ == "__main__":
    unittest.main()
