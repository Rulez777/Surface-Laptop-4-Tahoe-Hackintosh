#!/usr/bin/env python3
"""Unit tests for the Surface Laptop 4 Tahoe audio installer."""
import copy
import importlib.util
import os
from pathlib import Path
import plistlib
import struct
import unittest

SCRIPT = Path(os.environ.get(
    "SL4_AUDIO_SCRIPT",
    Path(__file__).resolve().parents[1] / "scripts/install_audio_macos.py",
))
spec = importlib.util.spec_from_file_location("sl4_audio", str(SCRIPT))
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


class AudioConfigTests(unittest.TestCase):
    def setUp(self):
        self.original = {
            "Kernel": {
                "Add": [
                    {"BundlePath": "Lilu.kext", "Enabled": True},
                    {"BundlePath": "AppleALC.kext", "Enabled": True},
                    {"BundlePath": "VirtualSMC.kext", "Enabled": True},
                ],
                "Quirks": {"DisableLinkeditJettison": False},
            },
            "DeviceProperties": {"Add": {
                "PciRoot(0x0)/Pci(0x2,0x0)": {"AAPL,ig-platform-id": b"\x00" * 4},
            }},
            "NVRAM": {"Add": {
                "7C436110-AB2A-4BBB-A880-FE41995C9F82": {
                    "boot-args": "npci=0x2000 -igfxdvmt",
                },
            }},
            "PlatformInfo": {"Generic": {"SystemProductName": "MacBookPro16,2"}},
        }

    def test_audio_injection_and_independent_copy(self):
        before = copy.deepcopy(self.original)
        result = audio.prepare_config(self.original)
        self.assertEqual(self.original, before)
        self.assertEqual([entry["BundlePath"] for entry in result["Kernel"]["Add"]],
                         ["Lilu.kext", "AppleALC.kext", "SimpleHDA.kext", "VirtualSMC.kext"])
        self.assertTrue(result["Kernel"]["Quirks"]["DisableLinkeditJettison"])
        self.assertEqual(result["DeviceProperties"]["Add"][audio.AUDIO_PATH]["layout-id"],
                         struct.pack("<I", 35))
        self.assertEqual(result["NVRAM"], before["NVRAM"])
        self.assertEqual(result["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"],
                         before["DeviceProperties"]["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"])
        self.assertEqual(result["Kernel"]["Add"][2]["MaxKernel"], "25.99.99")
        self.assertEqual(plistlib.loads(plistlib.dumps(result)), result)

    def test_uses_existing_audio_path_case_insensitively(self):
        key = "PciRoot(0x0)/Pci(0x1f,0x3)"
        self.original["DeviceProperties"]["Add"][key] = {"layout-id": struct.pack("<I", 7)}
        result = audio.prepare_config(self.original)
        self.assertEqual(result["DeviceProperties"]["Add"][key]["layout-id"], struct.pack("<I", 35))
        self.assertNotIn(audio.AUDIO_PATH, result["DeviceProperties"]["Add"])

    def test_rejects_conflicting_alcid(self):
        self.original["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"] = "alcid=7"
        with self.assertRaisesRegex(RuntimeError, "Conflicting alcid"):
            audio.prepare_config(self.original)

    def test_rejects_missing_applealc(self):
        self.original["Kernel"]["Add"].pop(1)
        with self.assertRaisesRegex(RuntimeError, "Lilu and AppleALC"):
            audio.prepare_config(self.original)

    def test_rejects_wrong_dependency_order(self):
        self.original["Kernel"]["Add"][0], self.original["Kernel"]["Add"][1] = (
            self.original["Kernel"]["Add"][1], self.original["Kernel"]["Add"][0])
        with self.assertRaisesRegex(RuntimeError, "Lilu must be enabled"):
            audio.prepare_config(self.original)

    def test_does_not_readd_simplehda(self):
        result = audio.prepare_config(self.original)
        with self.assertRaisesRegex(RuntimeError, "already configured"):
            audio.prepare_config(result)

    def test_rejects_voodoohda(self):
        self.original["Kernel"]["Add"].append({"BundlePath": "VoodooHDA.kext", "Enabled": True})
        with self.assertRaisesRegex(RuntimeError, "HDA replacement"):
            audio.prepare_config(self.original)


if __name__ == "__main__":
    unittest.main()
