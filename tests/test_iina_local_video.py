#!/usr/bin/env python3
"""Platform-independent tests of notarized IINA software playback fallback."""
import importlib.util
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def import_module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


installer = import_module("sl4_iina_installer", "scripts/install_local_video_player_macos.py")
probe = import_module("sl4_iina_probe", "scripts/test_local_video_player_macos.py")


class IINALocalVideoTests(unittest.TestCase):
    def test_release_is_pinned(self):
        self.assertEqual(installer.VERSION, "1.5.1")
        self.assertEqual(len(installer.DOWNLOAD_SHA256), 64)
        self.assertEqual(installer.DOWNLOAD_SIZE, 113092405)
        self.assertIn("iina/iina/releases/download/v1.5.1/", installer.DOWNLOAD)

    def test_reject_untrusted_download_hosts(self):
        self.assertTrue(installer.url_allowed(installer.DOWNLOAD))
        self.assertTrue(installer.url_allowed(
            "https://release-assets.githubusercontent.com/downloads/file"))
        for candidate in (
            "http://github.com/iina/iina/releases",
            "https://github.com.evil.invalid/file",
            "https://evil.invalid/IINA.dmg",
            "file:///tmp/IINA.dmg",
            "https://user:pass@github.com/file",
        ):
            self.assertFalse(installer.url_allowed(candidate))

    def test_check_missing_app_is_readonly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "IINA.app"
            with mock.patch.object(installer, "app_path", return_value=path), \
                 mock.patch.object(installer, "download_pinned", side_effect=AssertionError):
                report = installer.check()
                self.assertFalse(report["installed"])
                self.assertFalse(report["intel_av1_vp9_hardware_unlocked"])
                self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_never_replace_existing_signed_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "IINA.app"
            path.mkdir()
            with mock.patch.object(installer.sys, "platform", "darwin"), \
                 mock.patch.object(installer, "app_path", return_value=path), \
                 mock.patch.object(installer, "verify_app",
                                   return_value={"version": "1.5.1"}), \
                 mock.patch.object(installer, "download_pinned", side_effect=AssertionError):
                report = installer.install()
                self.assertTrue(report["installed"])
                self.assertFalse(report["intel_av1_vp9_hardware_unlocked"])

    def test_reject_tampered_existing_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "IINA.app"
            path.mkdir()
            with mock.patch.object(installer.sys, "platform", "darwin"), \
                 mock.patch.object(installer, "app_path", return_value=path), \
                 mock.patch.object(installer, "verify_app",
                                   side_effect=RuntimeError("publisher mismatch")), \
                 mock.patch.object(installer, "download_pinned", side_effect=AssertionError):
                with self.assertRaisesRegex(RuntimeError, "publisher mismatch"):
                    installer.install()

    def test_bundle_identity_must_be_official(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "IINA.app"
            (p / "Contents").mkdir(parents=True)
            (p / "Contents/Info.plist").write_bytes(plistlib.dumps({
                "CFBundleIdentifier": "com.fake.iina"
            }))
            with self.assertRaisesRegex(RuntimeError, "identifier mismatch"):
                installer.verify_app(p)

    def test_decode_summary_parsing(self):
        sample = Path("/tmp/sample-av1.mp4")
        msg = ("FILE_LOADED CODEC=Alliance for Open Media AV1 SIZE=1920x1080\n"
               "RESULT codec=Alliance for Open Media AV1 dimensions=1920x1080 "
               "file_loaded=1 eof=1 end_error=0 decoder_dropped=-1 "
               "hardware_decode=no\n")
        result = probe.parse_result(msg, sample)
        self.assertEqual(result["codec"], "Alliance for Open Media AV1")
        self.assertTrue(result["software_decoded_to_eof"])
        self.assertFalse(result["frame_count_measured"])
        self.assertEqual(result["hardware_acceleration"], "disabled")
        self.assertEqual(result["width"], 1920)

    def test_failed_decode_is_not_marked_successful(self):
        sample = Path("/tmp/sample-vp9.webm")
        msg = ("RESULT codec=Google VP9 dimensions=1920x1080 "
               "file_loaded=1 eof=0 end_error=-12 decoder_dropped=-1 "
               "hardware_decode=no\n")
        result = probe.parse_result(msg, sample)
        self.assertFalse(result["software_decoded_to_eof"])

    def test_bad_or_nonlocal_input_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "video.mp4"
            path.write_bytes(b"content")
            probe.validate_files([path])
            with self.assertRaisesRegex(ValueError, "between 1 and 12"):
                probe.validate_files([])
            with self.assertRaisesRegex(ValueError, "between 1 and 12"):
                probe.validate_files([path] * 13)
            link = Path(tmp) / "alias.mp4"
            link.symlink_to(path)
            with self.assertRaisesRegex(ValueError, "ordinary local file"):
                probe.validate_files([link])

    def test_reference_report_is_explicitly_software(self):
        report = json.loads((ROOT / "docs/reports/sl4-iina-software-playback-20261123.json")
                            .read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "pass")
        self.assertFalse(report["hardware_decode_verified"])
        self.assertFalse(report["video_rendered_on_screen"])
        self.assertFalse(report["driver_or_efi_changed"])
        self.assertEqual({x["filename"] for x in report["files"]},
                         {"av1-1080.mp4", "vp9-1080.webm"})
        self.assertTrue(all(x["software_decoded_to_eof"] for x in report["files"]))
        self.assertTrue(all(x["frame_count_measured"] is False for x in report["files"]))

    def test_not_a_gpu_patch(self):
        for p in ("scripts/install_local_video_player_macos.py",
                  "scripts/test_local_video_player_macos.py",
                  "scripts/iina_libmpv_decode_probe.c"):
            content = (ROOT / p).read_text(encoding="utf-8")
            for forbidden in ("sudo ", "csrutil ", "nvram -", "pmset -",
                              "defaults write", "EFI/OC", "kextload "):
                self.assertNotIn(forbidden, content)
        source = (ROOT / "scripts/iina_libmpv_decode_probe.c").read_text()
        self.assertIn('{"vo","null"}', source)
        self.assertIn('{"hwdec","no"}', source)

    def test_all_in_one_kit_references_helper(self):
        for p in ("scripts/build_windows_quickstart_kit.py",
                  "scripts/build_offline_kit.py",
                  "scripts/windows_prepare_tahoe.py"):
            source = (ROOT / p).read_text(encoding="utf-8")
            for name in ("install_local_video_player_macos.py",
                         "iina_libmpv_decode_probe.c",
                         "test_local_video_player_macos.py"):
                self.assertIn(name, source, (p, name))
        quick = (ROOT / "scripts/QuickStart-Mac.command").read_text(encoding="utf-8")
        self.assertIn("--media-local-player)", quick)
        self.assertIn("install_local_video_player_macos.py", quick)


if __name__ == "__main__":
    unittest.main()
