"""Regression tests for the fixed-60-MB DVMT profile.

Run from repository root: python -m unittest discover -s tests -p 'test_dvmt60.py'
These are pure config tests; they do not touch hardware, EFI or NVRAM.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from dvmt60 import DVMT_ARG, IGPU_PATH, PROPERTIES, is_ready, stage


class DVMT60Tests(unittest.TestCase):
    def make_config(self):
        return {"DeviceProperties": {"Add": {}}}

    def test_stages_expected_binary_data(self):
        config = self.make_config()
        changed = stage(config)
        self.assertEqual(len(changed), 2)
        self.assertTrue(is_ready(config))
        self.assertEqual(config["DeviceProperties"]["Add"][IGPU_PATH], PROPERTIES)

    def test_idempotent_and_preserves_unrelated_values(self):
        config = self.make_config()
        config["DeviceProperties"]["Add"][IGPU_PATH] = {"AAPL,ig-platform-id": bytes.fromhex("00000000")}
        stage(config)
        self.assertEqual(stage(config), [])
        self.assertIn("AAPL,ig-platform-id", config["DeviceProperties"]["Add"][IGPU_PATH])
        self.assertTrue(is_ready(config))

    def test_rejects_conflicting_value(self):
        config = self.make_config()
        config["DeviceProperties"]["Add"][IGPU_PATH] = {"framebuffer-stolenmem": bytes.fromhex("00000000")}
        with self.assertRaisesRegex(RuntimeError, "Conflicting"):
            stage(config)

    def test_plain_text_is_not_data(self):
        config = self.make_config()
        config["DeviceProperties"]["Add"][IGPU_PATH] = dict(PROPERTIES)
        config["DeviceProperties"]["Add"][IGPU_PATH]["framebuffer-patch-enable"] = "01000000"
        self.assertFalse(is_ready(config))

    def test_expected_flag(self):
        self.assertEqual(DVMT_ARG, "-igfxdvmt")


if __name__ == "__main__":
    unittest.main()
