"""Offline regression tests: no real ESP, boot manager, or network access."""
import hashlib
import importlib.util
import io
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_zip():
    data = io.BytesIO()
    info = plistlib.dumps({"CFBundleExecutable": "New"})
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("RELEASE/New.kext/Contents/Info.plist", info)
        archive.writestr("RELEASE/New.kext/Contents/MacOS/New", b"test-binary")
    return data.getvalue()


class DriverPackSafety(unittest.TestCase):
    def test_prepare_recovers_invalid_cached_zip_atomically(self):
        prepare = load("prepare_full_driver_pack")
        raw = sample_zip()
        sha = hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "test.zip"
            target.write_bytes(b"partial-download")
            with patch.object(prepare.urllib.request, "urlopen", return_value=io.BytesIO(raw)) as urlopen:
                info = prepare.fetch("https://example.test/test.zip", target, len(raw), sha)
            self.assertEqual(urlopen.call_count, 1)
            self.assertEqual(info["sha256"], sha)
            self.assertEqual(target.read_bytes(), raw)
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), ["test.zip"])

    def test_prepare_rejects_bad_release_digest_without_replacing_cache(self):
        prepare = load("prepare_full_driver_pack")
        raw = sample_zip()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "test.zip"
            with patch.object(prepare.urllib.request, "urlopen", return_value=io.BytesIO(raw)):
                with self.assertRaises(RuntimeError):
                    prepare.fetch("https://example.test/test.zip", target, len(raw), "0" * 64)
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_optional_preserves_original_active_kext_and_avoids_bcd(self):
        optional = load("add_optional_drivers")
        raw = sample_zip()
        sha = hashlib.sha256(raw).hexdigest()
        url = "https://example.test/New.zip"
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "private" / "EFI"
            kexts = source / "OC" / "Kexts"
            old = kexts / "AppleALC.kext"
            (old / "Contents" / "MacOS").mkdir(parents=True)
            (old / "Contents" / "Info.plist").write_bytes(plistlib.dumps({"CFBundleExecutable": "AppleALC"}))
            (old / "Contents" / "MacOS" / "AppleALC").write_bytes(b"my-working-active-driver")
            config = {
                "ACPI": {"Add": [{"Enabled": True, "Path": "SSDT-RTC0-SL4.aml"}]},
                "Kernel": {"Add": [{
                    "BundlePath": "AppleALC.kext", "Enabled": True,
                    "PlistPath": "Contents/Info.plist",
                    "ExecutablePath": "Contents/MacOS/AppleALC",
                }]},
            }
            (source / "OC" / "config.plist").write_bytes(plistlib.dumps(config))
            (source / "Microsoft" / "Boot").mkdir(parents=True)
            (source / "Microsoft" / "Boot" / "BCD").write_bytes(b"locked-BCD")
            target = base / "staged"
            with patch.dict(optional.RELEASES, {
                "AppleALC": ("https://example.test/Old.zip", ["AppleALC.kext"]),
                "New": (url, ["New.kext"]),
            }, clear=True), patch.dict(optional.ASSET_INTEGRITY, {
                "New.zip": (len(raw), sha)
            }, clear=True), patch.object(optional.urllib.request, "urlopen", return_value=io.BytesIO(raw)) as fetcher, patch.object(sys, "argv", [
                "add_optional_drivers.py", "--source", str(source), "--out", str(target), "--cache", str(base / "cache")
            ]):
                optional.main()
            self.assertEqual(fetcher.call_count, 1)
            self.assertEqual((target / "EFI" / "OC" / "Kexts" / "AppleALC.kext" / "Contents" / "MacOS" / "AppleALC").read_bytes(), b"my-working-active-driver")
            self.assertFalse((target / "EFI" / "Microsoft").exists())
            staged_config = plistlib.loads((target / "EFI" / "OC" / "config.plist").read_bytes())
            entries = {x["BundlePath"]: x for x in staged_config["Kernel"]["Add"]}
            self.assertTrue(entries["AppleALC.kext"]["Enabled"])
            self.assertFalse(entries["New.kext"]["Enabled"])

    def make_xe(self, base, boot="-wex-noaccel", sip=b"\\x00" * 4):
        xe = load("xe_acceleration")
        root = base / "EFI"
        (root / "OC" / "ACPI").mkdir(parents=True)
        (root / "OC" / "OpenCore.efi").write_bytes(b"test")
        (root / "OC" / "ACPI" / "SSDT-RTC0-SL4.aml").write_bytes(b"test")
        for name in xe.CORE_KEXTS:
            p = root / "OC" / "Kexts" / name / "Contents"
            p.mkdir(parents=True)
            (p / "Info.plist").write_bytes(b"test")
        config = {
            "ACPI": {"Add": [{"Enabled": True, "Path": "SSDT-RTC0-SL4.aml"}]},
            "Kernel": {"Add": [{"Enabled": True, "BundlePath": name} for name in xe.CORE_KEXTS]},
            "UEFI": {"Quirks": {"RequestBootVarRouting": True}},
            "NVRAM": {"Add": {xe.APPLE_GUID: {"boot-args": boot, "csr-active-config": sip}}, "Delete": {}},
        }
        (root / "OC" / "config.plist").write_bytes(plistlib.dumps(config))
        return xe, root

    def test_xe_prepare_sets_effective_nvram_delete_without_removing_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            xe, root = self.make_xe(base)
            args = ["xe_acceleration.py", "--efi", str(root), "--mode", "prepare",
                    "--backup-dir", str(base / "backups"), "--ocvalidate", str(base / "validator.exe")]
            with patch.object(sys, "argv", args), patch("builtins.input", return_value="PREPARE-XE-EFI"), patch.object(xe, "write_config") as writer:
                xe.main()
            after = plistlib.loads(writer.call_args.args[2])
            self.assertEqual(after["NVRAM"]["Add"][xe.APPLE_GUID]["csr-active-config"], xe.SIP_WEX)
            self.assertEqual(after["NVRAM"]["Delete"][xe.APPLE_GUID], ["boot-args", "csr-active-config"])
            flags = after["NVRAM"]["Add"][xe.APPLE_GUID]["boot-args"].split()
            self.assertIn("-wex-noaccel", flags)
            self.assertIn("-allow3d", flags)
            self.assertIn("-disablegfxfirmware", flags)

    def test_xe_enable_refuses_stale_nvram_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            xe, root = self.make_xe(base, "-wex-noaccel -allow3d -disablegfxfirmware", b"\\x03\\x08\\x00\\x00")
            args = ["xe_acceleration.py", "--efi", str(root), "--mode", "enable"]
            with patch.object(sys, "argv", args):
                with self.assertRaisesRegex(RuntimeError, "NVRAM/Delete missing"):
                    xe.main()


if __name__ == "__main__":
    unittest.main()
