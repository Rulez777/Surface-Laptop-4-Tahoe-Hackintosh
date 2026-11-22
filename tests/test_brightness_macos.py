#!/usr/bin/env python3
"""Isolated PNLF patch tests: no EFI or boot disk access."""
import importlib.util
import os
from pathlib import Path
import plistlib
import unittest

SOURCE = Path(os.environ.get(
    "SL4_BRIGHTNESS_SCRIPT",
    Path(__file__).resolve().parents[1] / "scripts/install_brightness_macos.py"
))
spec = importlib.util.spec_from_file_location("sl4_brightness", str(SOURCE))
bright = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bright)

# Verified 126-byte SL4 SSDT-PNLF structure, with no personal machine data.
AML14 = bytes.fromhex(
    "535344547e000000025c535552460000504e4c460000000001000000494e544c"
    "12122520a01400155c2f035f53425f504330304746583006001044045c2f03"
    "5f53425f50433030474658305b8231504e4c46085f4849440d4150503030"
    "303200085f4349440d6261636b6c6967687400085f5549440a0e085f5354"
    "410a0b"
)


def config(enabled=True):
    return {
        "PlatformInfo": {"Generic": {"SystemProductName": "MacBookPro16,2"}},
        "ACPI": {"Add": [
            {"Path": "SSDT-PLUG.aml", "Enabled": True},
            {"Path": "SSDT-PNLF.aml", "Enabled": enabled},
        ]},
        "Kernel": {"Add": [{"BundlePath": "Lilu.kext", "Enabled": True}]},
    }


class BrightnessTests(unittest.TestCase):
    def test_fixture(self):
        self.assertEqual(len(AML14), 126)
        self.assertEqual(sum(AML14) % 256, 0)
        self.assertEqual(bright.pnl_uid(AML14), 14)

    def test_uid_patch_is_exactly_two_bytes(self):
        patched = bright.patch_pnlf(AML14)
        self.assertEqual(bright.pnl_uid(patched), 19)
        self.assertEqual(sum(patched) % 256, 0)
        changed = [i for i, (a, b) in enumerate(zip(AML14, patched)) if a != b]
        self.assertEqual(changed, [9, 118])
        self.assertEqual(patched[118], 19)

    def test_idempotence(self):
        patched = bright.patch_pnlf(AML14)
        self.assertEqual(bright.patch_pnlf(patched), patched)

    def test_bad_checksum_rejected(self):
        changed = bytearray(AML14)
        changed[-1] ^= 1
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            bright.patch_pnlf(bytes(changed))

    def test_unknown_firmware_table_rejected(self):
        changed = bytearray(AML14)
        changed[4] += 1
        with self.assertRaisesRegex(RuntimeError, "length or checksum"):
            bright.patch_pnlf(bytes(changed))

    def test_enabled_flag_noop(self):
        old = config(enabled=True)
        new, toggle = bright.updated_config(old)
        self.assertFalse(toggle)
        self.assertEqual(new, old)
        self.assertIsNot(new, old)

    def test_disabled_flag_enabled(self):
        old = config(enabled=False)
        new, toggle = bright.updated_config(old)
        self.assertTrue(toggle)
        self.assertTrue(new["ACPI"]["Add"][1]["Enabled"])
        self.assertFalse(old["ACPI"]["Add"][1]["Enabled"])
        self.assertEqual(new["Kernel"], old["Kernel"])
        self.assertEqual(plistlib.loads(plistlib.dumps(new)), new)

    def test_missing_or_duplicate_pnlf_rejected(self):
        for items in ([], [{"Path": "SSDT-PNLF.aml", "Enabled": False}] * 2):
            old = config()
            old["ACPI"]["Add"] = items
            with self.assertRaisesRegex(RuntimeError, "unique"):
                bright.updated_config(old)

    def test_wrong_smbios_rejected(self):
        old = config()
        old["PlatformInfo"]["Generic"]["SystemProductName"] = "iMac19,1"
        with self.assertRaisesRegex(RuntimeError, "SMBIOS"):
            bright.updated_config(old)


if __name__ == "__main__":
    unittest.main()
