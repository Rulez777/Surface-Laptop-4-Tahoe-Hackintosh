#!/usr/bin/env python3
"""Offline validation of native VideoToolbox session probe sources/wrapper."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_codec_hw_probes_macos.py"
spec = importlib.util.spec_from_file_location("sl4_vt_sessions", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class NativeSessionProbeTests(unittest.TestCase):
    def test_known_error_codes(self):
        self.assertEqual(probe.annotated_status(-12906)["name"],
                         "kVTCouldNotFindVideoDecoderErr")
        self.assertEqual(probe.annotated_status(-12913)["name"],
                         "kVTVideoDecoderNotAvailableNowErr")
        self.assertEqual(probe.annotated_status(-12909)["name"],
                         "kVTVideoDecoderBadDataErr")
        self.assertEqual(probe.annotated_status(0)["name"], "noErr")

    def test_annotate_keeps_data_and_no_hardware_claims(self):
        sample = {"codecs": [{"codec": "AV1", "hardware_required_status": -12906,
                              "unrestricted_status": -12906,
                              "hardware_required_session_reported_hw": False}],
                  "real_frame_decode_tested": False}
        result = probe.annotate(sample)
        self.assertFalse(result["real_frame_decode_tested"])
        self.assertFalse(result["codecs"][0]["hardware_required_session_reported_hw"])
        self.assertEqual(result["codecs"][0]["hardware_required_status_detail"]["code"], -12906)

    def test_real_asset_error_annotation(self):
        sample = {"assets": [{"path": "av1.mp4",
                              "require_hardware": {"os_status": -12906},
                              "allow_software": {"os_status": -12906}}]}
        result = probe.annotate(sample)
        self.assertEqual(result["assets"][0]["require_hardware"]["status_detail"]["name"],
                         "kVTCouldNotFindVideoDecoderErr")

    def test_limit_samples(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "clip.mp4"
            file.write_bytes(b"test")
            probe.require_inputs([file])
            with self.assertRaisesRegex(ValueError, "Limit to 12"):
                probe.require_inputs([file] * 13)

    def test_reject_missing_and_invalid_samples(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "unsupported.exe"
            file.write_bytes(b"test")
            with self.assertRaisesRegex(ValueError, "extension"):
                probe.require_inputs([file])
            with self.assertRaisesRegex(ValueError, "normal existing"):
                probe.require_inputs([Path(temp) / "missing.mp4"])

    def test_reject_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "original.mp4"
            file.write_bytes(b"test")
            link = Path(temp) / "link.mp4"
            link.symlink_to(file)
            with self.assertRaisesRegex(ValueError, "normal existing"):
                probe.require_inputs([link])

    def test_compilers_are_fixed_to_vetted_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "binary"
            for source in (probe.SOURCE_BASIC, probe.SOURCE_REAL):
                argv = probe.build_command(source, target)
                self.assertEqual(argv[0], "clang")
                self.assertIn(str(source), argv)
                self.assertIn("-Werror", argv)
            with self.assertRaisesRegex(ValueError, "vetted"):
                probe.build_command(Path(temp) / "unsafe.c", target)

    def test_mac_quickstart_has_readonly_codec_probe(self):
        script = (ROOT / "scripts/QuickStart-Mac.command").read_text(encoding="utf-8")
        self.assertIn("--media-probe)", script)
        self.assertIn('python3 "$base/run_codec_hw_probes_macos.py"', script)
        self.assertIn('python3 "$base/audit_codec_macos.py" --json', script)

    def test_platform_rejects_without_attempted_write(self):
        with mock.patch.object(probe.sys, "platform", "linux"), \
             mock.patch.object(probe, "run", side_effect=AssertionError):
            with self.assertRaisesRegex(RuntimeError, "Only installed macOS"):
                probe.inspect([])

    def test_no_root_or_kernel_writes_in_code(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("TemporaryDirectory", text)
        self.assertIn('"hardware_decode_verified": False', text)
        self.assertIn('"real_frame_decode_tested": False', text)
        for forbidden in ("sudo", "csrutil", "nvram -", "pmset -",
                          "defaults write", "EFI/OC", "LaunchAgents", "chmod 777"):
            self.assertNotIn(forbidden, text)

    def test_reference_baseline_has_no_false_hardware_success(self):
        path = ROOT / "docs/reports/sl4-videotoolbox-hw-session-20261123.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(report["hardware_decode_verified"])
        self.assertFalse(report["device_or_driver_changed"])
        self.assertFalse(report["real_frame_decode_tested"])
        assets = report["results"]["real_asset_probe"]["assets"]
        actual_av1 = next(a for a in assets if a.get("codec_fourcc") == "av01")
        self.assertEqual(actual_av1["require_hardware"]["os_status"], -12906)
        self.assertEqual(actual_av1["allow_software"]["os_status"], -12906)
        for asset in assets:
            self.assertNotIn("/Users/", asset["path"])

    def test_all_in_one_bundles_probe(self):
        paths = (
            "scripts/probe_video_session_macos.c",
            "scripts/probe_real_asset_sessions_macos.m",
            "scripts/run_codec_hw_probes_macos.py",
        )
        for pkg in ("scripts/build_windows_quickstart_kit.py",
                    "scripts/build_offline_kit.py"):
            data = (ROOT / pkg).read_text(encoding="utf-8")
            for path in paths:
                self.assertIn(path, data)
        source = (ROOT / "scripts/windows_prepare_tahoe.py").read_text(encoding="utf-8")
        for path in paths:
            self.assertIn('"' + Path(path).name + '"', source)


if __name__ == "__main__":
    unittest.main()
