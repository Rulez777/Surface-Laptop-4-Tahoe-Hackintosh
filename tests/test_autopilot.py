"""Autopilot CMD, macOS first boot and Windows resume regression tests."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import auto_verify_first_boot_macos as verifier
import build_windows_quickstart_kit as bundle

class AutoFlowTests(unittest.TestCase):
    def test_windows_cmd_launches_auto_by_default_and_requires_usb_confirmation(self):
        cmd=(ROOT/"QuickStart.cmd").read_text()
        script=(ROOT/"scripts/QuickStart-Windows.ps1").read_text()
        self.assertIn('set "SL4_MODE=Auto"',cmd)
        self.assertIn('if /I "%~1"=="advanced" set "SL4_MODE=Menu"',cmd)
        self.assertIn("Prepare-Installation -AutoUSB",script)
        self.assertIn("Find-Verified-MacReadyUSB",script)
        self.assertIn("Stage-Internal-OpenCore",script)
        self.assertIn("QuickStart-Advanced.cmd",bundle.FILES)
        self.assertIn("Write-USB -folder $out -number $number",script)
        self.assertIn("ERASE USB $number",script)
        self.assertIn("$disk.BusType -ne 'USB'",script)
        self.assertIn("$disk.IsBoot",script)
        self.assertIn("$disk.IsSystem",script)
        self.assertIn("Get-FileHash -LiteralPath $kext",script)
        self.assertIn("Get-FileHash -LiteralPath $conf",script)

    def test_macos_helper_selects_hardware_mode_without_manual_menu(self):
        script=(ROOT/"scripts/QuickStart-Mac.command").read_text()
        for name in ("choose_automatic_action","repair_existing","install_from_usb",
                     "graphics_loaded","rcs_ready","usb_efi_ready","arm_postboot_check",
                     "sudo -v","--menu) show_advanced_menu","verify_coremedia_h264"):
            self.assertIn(name,script)
        self.assertNotIn("sudo /usr/bin/pmset -a",script)
        self.assertNotIn("sleep 0 displaysleep 0",script)

    def test_login_verifier_requires_actual_acceleration_and_leaves_efi_alone(self):
        s=(ROOT/"scripts/auto_verify_first_boot_macos.py").read_text()
        for name in ("SL4RCSNativeQueueTrialReady","SL4HeapDepthTrialReady","SL4DMCLocalInitVerified",
                     "TGLEDPKeepReady","TGLSoftSleepReady","IOPMDeepIdleSupported",
                     "Metal Support: Metal 2","com.labrouss.S0ixStandby",
                     "AllowOnePassMetalScaling","Surface Laptop 4 - Clear Speech",
                     "pmset","AppleHDAEngineOutput:1F,3,0,1,1:0"):
            self.assertIn(name,s)
        self.assertNotIn("sudo /usr/bin/pmset",s)
        self.assertNotIn("bcdedit",s)
        self.assertNotIn("tccutil",s)

    def test_verifier_creates_marker_only_if_checks_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            usb=base/"SL4DATA"
            usb.mkdir()
            example={"schema":1,"stage":"verified_accelerated_tahoe_boot",
                     "macos":"26.7.1","power_policy_modified":False,
                     "usb_oc_config_sha256":"0"*64}
            with mock.patch.object(verifier,"inspected",return_value=example):
                with mock.patch.object(Path,"home",return_value=base):
                    verifier.check(usb)
            marker=usb/"SL4-AUTO-READY.json"
            self.assertTrue(marker.exists())
            self.assertEqual(json.loads(marker.read_text())["stage"],"verified_accelerated_tahoe_boot")
            self.assertTrue((base/"Library/Application Support/SL4-Autopilot/verified.json").exists())
            marker.unlink()
            with mock.patch.object(verifier,"inspected",side_effect=RuntimeError("GPU not ready")):
                with mock.patch.object(Path,"home",return_value=base):
                    with self.assertRaisesRegex(RuntimeError,"GPU not ready"):
                        verifier.check(usb)
            self.assertFalse(marker.exists())

    def test_windows_stage_includes_verifier_and_integrated_drivers(self):
        self.assertIn("scripts/auto_verify_first_boot_macos.py",bundle.FILES)
        self.assertIn("docs/AUTOPILOT.md",bundle.FILES)
        self.assertIn("packages/SL4-Graphics-Performance-0.1.7-beta.zip",bundle.FILES)
        self.assertIn("packages/SL4-Dolby-APOMac-Profiles-20261123.zip",bundle.FILES)
        stage=(ROOT/"scripts/windows_prepare_tahoe.py").read_text()
        self.assertIn("auto_verify_first_boot_macos.py",stage)
        self.assertIn("macos_autopilot_first_boot_check",stage)
        self.assertIn("manual_os_recovery_install_still_required",stage)

if __name__=="__main__":
    unittest.main()
