#!/usr/bin/env python3
"""Safety checks for an offline EFI archive audit. Uses invented fixtures only."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import plistlib
import stat
import tempfile
import unittest
from zipfile import ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sl4_recovery_check", ROOT / "scripts/audit_rcs_recovery_backup.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def cfg(*, kext="WhateverXe.kext", missing=False):
    return {
        "Kernel": {"Add": [
            {"BundlePath": "Lilu.kext", "Enabled": True},
            {"BundlePath": kext, "Enabled": True},
            {"BundlePath": "OtherOld.kext", "Enabled": False},
        ]},
        "ACPI": {"Add": [{"Path": "SSDT-A.aml", "Enabled": True}]},
        "UEFI": {"Drivers": [{"Path": "OpenRuntime.efi", "Enabled": True}]},
        "NVRAM": {"Add": {"DUMMY": {
            "boot-args": "-allow3d custom-secret-string"}
        }},
        "PlatformInfo": {"Generic": {
            "SystemSerialNumber": "SECRET-NOT-TO-BE-EMITTED",
        }},
    }


def create(path, *, config=None, skip=(), extra=None):
    entries = {
        "EFI/Boot/bootx64.efi": b"x",
        "EFI/OC/OpenCore.efi": b"x",
        "EFI/OC/config.plist": plistlib.dumps(config if config is not None else cfg()),
        "EFI/Microsoft/Boot/bootmgfw.efi": b"x",
        "EFI/OC/Kexts/Lilu.kext/Contents/Info.plist": b"x",
        "EFI/OC/Kexts/WhateverXe.kext/Contents/Info.plist": b"x",
        "EFI/OC/ACPI/SSDT-A.aml": b"x",
        "EFI/OC/Drivers/OpenRuntime.efi": b"x",
    }
    for p in skip:
        entries.pop(p, None)
    if extra:
        entries.update(extra)
    with ZipFile(path, "w") as z:
        for n, v in entries.items():
            z.writestr(n, v)


class RecoveryAuditTests(unittest.TestCase):
    def test_minimal_efi_complete_and_not_implicitly_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.zip"
            create(path)
            summary = m.inspect_archive(path)
        self.assertTrue(summary["individual_file_crc_verified"])
        self.assertFalse(summary["selected_rcs_beta"])
        self.assertFalse(summary["bootability_verified"])
        self.assertFalse(summary["safe_to_install_experimental_kernel"])
        self.assertFalse(summary["efi_partition_modified"])
        self.assertEqual(summary["enabled_open_core_entries_resolved"],
                         {"Kernel": 2, "ACPI": 1, "UEFI": 1})
        self.assertNotIn("SECRET-", str(summary))
        self.assertNotIn("custom-secret-string", str(summary))

    def test_missing_windows_boot_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.zip"
            create(path, skip={"EFI/Microsoft/Boot/bootmgfw.efi"})
            with self.assertRaisesRegex(ValueError, "required boot files"):
                m.inspect_archive(path)

    def test_missing_enabled_kext_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.zip"
            create(path, skip={"EFI/OC/Kexts/WhateverXe.kext/Contents/Info.plist"})
            with self.assertRaisesRegex(ValueError, "Kernel"):
                m.inspect_archive(path)

    def test_missing_enabled_uefi_driver_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.zip"
            create(path, skip={"EFI/OC/Drivers/OpenRuntime.efi"})
            with self.assertRaisesRegex(ValueError, "UEFI"):
                m.inspect_archive(path)

    def test_missing_disabled_kext_is_acceptable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.zip"
            create(path)
            self.assertEqual(m.inspect_archive(path)["archive_entries"], 8)

    def test_duplicate_fat_case_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.zip"
            create(path, extra={"EFI/BOOT/BOOTx64.EFI": b"alias"})
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                m.inspect_archive(path)

    def test_zip_traversal_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.zip"
            create(path, extra={"EFI/../../outside": b"pwned"})
            with self.assertRaisesRegex(ValueError, "Unsafe ZIP"):
                m.inspect_archive(path)

    def test_zip_symlink_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.zip"
            create(path)
            with ZipFile(path, "a") as z:
                info = ZipInfo("EFI/SYMLINK")
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                z.writestr(info, "somewhere")
            with self.assertRaisesRegex(ValueError, "Symlinks"):
                m.inspect_archive(path)

    def test_link_to_zip_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.zip"
            create(path)
            linked = Path(tmp) / "link.zip"
            linked.symlink_to(path)
            with self.assertRaisesRegex(ValueError, "not a symlink"):
                m.inspect_archive(linked)

    def test_malicious_oc_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.zip"
            create(path, config=cfg(kext="../escape.kext"))
            with self.assertRaisesRegex(ValueError, "Unsafe path"):
                m.inspect_archive(path)

    def test_selected_rcs_is_reported_without_serials(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.zip"
            create(path, config=cfg(kext="WhateverXe-SL4-RCS-STABILITY.kext"),
                   skip={"EFI/OC/Kexts/WhateverXe.kext/Contents/Info.plist"},
                   extra={"EFI/OC/Kexts/WhateverXe-SL4-RCS-STABILITY.kext/Contents/Info.plist": b"x"})
            summary = m.inspect_archive(path)
        self.assertTrue(summary["selected_rcs_beta"])
        self.assertFalse(summary["safe_to_install_experimental_kernel"])

    def test_original_archive_stays_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.zip"
            create(path)
            before = path.read_bytes()
            m.inspect_archive(path)
            self.assertEqual(before, path.read_bytes())

    def test_no_external_commands_or_partition_edits(self):
        text = (ROOT / "scripts/audit_rcs_recovery_backup.py").read_text()
        for forbidden in ("subprocess", "diskutil", "mount_msdos", "csrutil",
                          "sudo ", "NVRAM write", "os.replace", "write_bytes(",
                          "bootmgfw.exe"):
            self.assertNotIn(forbidden, text)

    def test_shipping_kit_has_backup_auditor(self):
        for file in ("scripts/build_windows_quickstart_kit.py",
                     "scripts/build_offline_kit.py",
                     "scripts/windows_prepare_tahoe.py"):
            text = (ROOT / file).read_text()
            self.assertIn("audit_rcs_recovery_backup.py", text)


if __name__ == "__main__":
    unittest.main()
