#!/usr/bin/env python3
"""Offline, system-independent tests for the read-only macOS codec survey."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_codec_macos.py"
spec = importlib.util.spec_from_file_location("sl4_codec", SCRIPT)
codec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(codec)


class CodecSurveyTests(unittest.TestCase):
    def test_fourcc_conversion(self):
        self.assertEqual(codec.codec_name(int.from_bytes(b"av01", "big")), "av01")
        self.assertEqual(codec.codec_name(int.from_bytes(b"vp09", "big")), "vp09")
        self.assertIsNone(codec.codec_name(-1))
        self.assertIsNone(codec.codec_name(2**32))

    def test_invalid_codec_type(self):
        self.assertIsNone(codec.codec_name("avc1"))
        self.assertIsNone(codec.codec_name(0))

    def test_actual_registered_hardware_flag_matters(self):
        rows = [
            {"CodecType": int.from_bytes(b"avc1", "big"),
             "EncoderName": "Apple H.264 (HW)", "IsHardwareAccelerated": True},
            {"CodecType": int.from_bytes(b"hvc1", "big"),
             "EncoderName": "Apple HEVC (SW)"},
            {"CodecType": int.from_bytes(b"vp09", "big"),
             "EncoderName": "VP9 hardware in misleading name"},
            {"CodecType": int.from_bytes(b"av01", "big"),
             "EncoderName": "AV1 software", "IsHardwareAccelerated": False},
        ]
        registry, supported = codec.summarize_encoders(rows)
        self.assertEqual(len(registry), 4)
        self.assertEqual(supported, {
            "H.264": True, "HEVC": False, "VP9": False, "AV1": False
        })

    def test_unregistered_codecs_not_assumed_supported(self):
        registry, supported = codec.summarize_encoders([])
        self.assertEqual(registry, [])
        self.assertTrue(all(flag is False for flag in supported.values()))

    def test_explicit_hardware_flag_for_vp9(self):
        rows = [{"CodecType": int.from_bytes(b"vp09", "big"),
                 "EncoderName": "Test VP9", "IsHardwareAccelerated": True}]
        registry, supported = codec.summarize_encoders(rows)
        self.assertTrue(supported["VP9"])
        self.assertFalse(supported["AV1"])
        self.assertTrue(registry[0]["hardware_advertised"])

    def test_all_in_one_bundles_audit(self):
        root = Path(__file__).resolve().parents[1]
        for relative in ("scripts/build_offline_kit.py",
                         "scripts/build_windows_quickstart_kit.py"):
            self.assertIn("scripts/audit_codec_macos.py",
                          (root / relative).read_text(encoding="utf-8"))
        self.assertIn('"audit_codec_macos.py"',
                      (root / "scripts/windows_prepare_tahoe.py").read_text(encoding="utf-8"))
        self.assertIn('with_name("audit_codec_macos.py")',
                      (root / "scripts/prepare_full_driver_pack.py").read_text(encoding="utf-8"))

    def test_not_mutating_input(self):
        rows = [{"CodecType": int.from_bytes(b"avc1", "big"),
                 "EncoderName": "Test", "IsHardwareAccelerated": True}]
        before = [row.copy() for row in rows]
        codec.summarize_encoders(rows)
        self.assertEqual(rows, before)


if __name__ == "__main__":
    unittest.main()
