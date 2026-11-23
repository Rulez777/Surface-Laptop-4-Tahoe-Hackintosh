#!/usr/bin/env python3
"""Offline safety tests for optional signed Firefox AV1/VP9 software fallback."""
import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/install_media_fallback_macos.py"
spec = importlib.util.spec_from_file_location("sl4_media_fallback", SCRIPT)
fallback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fallback)


class SoftwareMediaFallbackTests(unittest.TestCase):
    def test_trusted_domains(self):
        for url in (
            "https://download.mozilla.org/?product=firefox-latest&os=osx&lang=en-US",
            "https://download-installer.cdn.mozilla.net/pub/firefox/releases/stable/Firefox.dmg",
        ):
            self.assertTrue(fallback.trusted_download(url))
        for url in (
            "http://download.mozilla.org/Firefox.dmg",
            "https://download.mozilla.org.evil.invalid/file.dmg",
            "https://example.com/file.dmg",
            "file:///tmp/Firefox.dmg",
            "https://mozilla.net.example.com/Firefox.dmg",
        ):
            self.assertFalse(fallback.trusted_download(url))

    def test_absent_browser_check_is_readonly(self):
        with tempfile.TemporaryDirectory() as t:
            with mock.patch.object(fallback, "target_path", return_value=Path(t) / "Firefox.app"):
                with mock.patch.object(fallback, "download_official", side_effect=AssertionError):
                    report = fallback.status()
                self.assertFalse(report["installed"])
                self.assertFalse(report["gpu_av1_vp9_unlocked"])
                self.assertEqual(list(Path(t).iterdir()), [])

    def test_existing_browser_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "Firefox.app"
            path.mkdir()
            sample = {"version": "160.0.1"}
            with mock.patch.object(fallback, "target_path", return_value=path), \
                 mock.patch.object(fallback, "verify_publisher_signature", return_value=sample), \
                 mock.patch.object(fallback, "download_official", side_effect=AssertionError), \
                 mock.patch.object(fallback.sys, "platform", "darwin"):
                report = fallback.install()
                self.assertTrue(report["installed"])
                self.assertEqual(report["app"], sample)
                self.assertFalse(report["gpu_av1_vp9_unlocked"])

    def test_bad_existing_browser_never_overwritten(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "Firefox.app"
            path.mkdir()
            with mock.patch.object(fallback, "target_path", return_value=path), \
                 mock.patch.object(fallback, "verify_publisher_signature",
                                   side_effect=RuntimeError("unknown publisher")), \
                 mock.patch.object(fallback, "download_official", side_effect=AssertionError), \
                 mock.patch.object(fallback.sys, "platform", "darwin"):
                with self.assertRaisesRegex(RuntimeError, "unknown publisher"):
                    fallback.install()

    def test_reject_wrong_bundle_identity(self):
        with tempfile.TemporaryDirectory() as t:
            app = Path(t) / "Firefox.app"
            (app / "Contents").mkdir(parents=True)
            (app / "Contents/Info.plist").write_bytes(plistlib.dumps(
                {"CFBundleIdentifier": "com.evil.browser"}
            ))
            with self.assertRaisesRegex(RuntimeError, "Unexpected app bundle identifier"):
                fallback.verify_publisher_signature(app)

    def test_reject_wrong_developer_id_and_unnotarized(self):
        with tempfile.TemporaryDirectory() as t:
            app = Path(t) / "Firefox.app"
            (app / "Contents").mkdir(parents=True)
            (app / "Contents/Info.plist").write_bytes(plistlib.dumps(
                {"CFBundleIdentifier": fallback.BUNDLE_ID}
            ))
            with mock.patch.object(fallback, "run", return_value="TeamIdentifier=UNKNOWN"):
                with self.assertRaisesRegex(RuntimeError, "Publisher signature"):
                    fallback.verify_publisher_signature(app)
            real_identity = (
                f"Identifier={fallback.BUNDLE_ID}\nTeamIdentifier={fallback.TEAM}\n"
                f"Authority=Developer ID Application: Mozilla Corporation ({fallback.TEAM})"
            )
            def fake_run(*args, **kwargs):
                if "-dv" in args:
                    return real_identity
                if "--assess" in args:
                    return "source=Developer ID"  # not notarized
                return ""
            with mock.patch.object(fallback, "run", side_effect=fake_run):
                with self.assertRaisesRegex(RuntimeError, "not accepted as notarized"):
                    fallback.verify_publisher_signature(app)

    def test_is_opt_in_and_never_modifies_gpu(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('group.add_argument("--install"', source)
        self.assertIn('group.add_argument("--check"', source)
        for dangerous in ("csrutil", "pmset -", "nvram -", "/Library/GPUBundles",
                          "defaults write", "sudo", "EFI/OC"):
            self.assertNotIn(dangerous, source)
        for path in ("scripts/build_offline_kit.py",
                     "scripts/build_windows_quickstart_kit.py",
                     "scripts/windows_prepare_tahoe.py"):
            self.assertIn("install_media_fallback_macos.py",
                          (ROOT / path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
