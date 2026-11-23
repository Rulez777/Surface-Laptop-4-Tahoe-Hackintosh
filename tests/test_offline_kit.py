#!/usr/bin/env python3
"""Unit tests for deterministic offline toolkit (no personal EFI)."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
import zipfile

spec=importlib.util.spec_from_file_location("offline_kit",Path(__file__).resolve().parents[1]/"scripts/build_offline_kit.py")
kit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)


class OfflineKitTests(unittest.TestCase):
    def test_file_allowlist_has_no_personal_efi(self):
        paths=kit.files()
        self.assertNotIn("EFI/OC/config.plist",paths)
        self.assertFalse(any(p.endswith("config.plist") or p.endswith("bootmgfw.efi") for p in paths))
        self.assertTrue(all(p.startswith(("README.md","docs/","scripts/","data/","packages/")) for p in paths))

    def test_two_builds_deterministic_and_verifiable(self):
        with tempfile.TemporaryDirectory() as temp:
            a=Path(temp)/"a.zip";b=Path(temp)/"b.zip"
            result=kit.write_archive(a)
            kit.write_archive(b)
            self.assertEqual(result["sha256"],kit.sha(b.read_bytes()))
            self.assertTrue(kit.verify_archive(a)>20)
            with self.assertRaisesRegex(RuntimeError,"Refusing to overwrite"):
                kit.write_archive(a)

    def test_modified_zip_content_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/"a.zip";kit.write_archive(dest)
            with zipfile.ZipFile(dest,"a") as archive:
                archive.writestr("UNKNOWN-PERSONAL.txt","should not be accepted")
            with self.assertRaisesRegex(RuntimeError,"Unexpected archive member"):
                kit.verify_archive(dest)


if __name__=="__main__":
    unittest.main()
