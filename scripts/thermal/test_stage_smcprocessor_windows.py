"""Synthetic OpenCore ESP tests; no hardware, NVRAM or EFI writes."""
import importlib.util
import pathlib
import plistlib
import tempfile
import unittest
import zipfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("smcinstall", pathlib.Path(__file__).with_name("install_smcprocessor_windows.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
FAKEX64 = bytes.fromhex("cffaedfe07000001") + b"Z" * 150


def plugin_info(bundle, ver="1.3.8", executor=None):
    return plistlib.dumps(dict(CFBundleIdentifier=bundle, CFBundleVersion=ver,
        CFBundleExecutable=executor or bundle.rsplit(".", 1)[-1],
        OSBundleLibraries={"as.vit9696.VirtualSMC": "1.0.0", "as.vit9696.Lilu": "1.0.0"}))


def fixture(tmp):
    efi = tmp/"ESP"/"EFI"
    (efi/"Microsoft"/"Boot").mkdir(parents=True)
    (efi/"Microsoft/Boot/bootmgfw.efi").write_bytes(b"MS")
    oc = efi/"OC"
    (oc/"Kexts"/"VirtualSMC.kext"/"Contents").mkdir(parents=True)
    (oc/"OpenCore.efi").write_bytes(b"OC")
    (oc/"Kexts"/"VirtualSMC.kext"/"Contents"/"Info.plist").write_bytes(plugin_info(m.VSMC_ID))
    entries = [
        {"BundlePath": x, "Enabled": True, "Arch": "Any",
         "PlistPath": "Contents/Info.plist", "ExecutablePath": "Contents/MacOS/" + x.split(".")[0],
         "MaxKernel": "", "MinKernel": "", "Comment": ""}
        for x in ("Lilu.kext", "VirtualSMC.kext", "BigSurface.kext")
    ]
    (oc/"config.plist").write_bytes(plistlib.dumps({"Kernel": {"Add": entries}, "NVRAM": {"Add": {"boot-args": "Metal"}}}))
    archive = tmp/"Official.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for name, bundle in ((m.NAME, m.BUNDLE), ("VirtualSMC.kext", m.VSMC_ID)):
            z.writestr(f"RELEASE/{name}/Contents/Info.plist", plugin_info(bundle))
            z.writestr(f"RELEASE/{name}/Contents/MacOS/" + name.split(".")[0], FAKEX64)
    return efi, archive


class TestInstaller(unittest.TestCase):
    def test_validate_fixture(self):
        with tempfile.TemporaryDirectory() as t:
            efi, archive = fixture(pathlib.Path(t))
            self.assertEqual(len(m.parse_official_zip(archive)), 2)
            oc, path, cfg, new = m.inspect_efi(efi, archive)
            self.assertEqual([i["BundlePath"] for i in new["Kernel"]["Add"]],
                ["Lilu.kext", "VirtualSMC.kext", "SMCProcessor.kext", "BigSurface.kext"])
            self.assertEqual(cfg["NVRAM"], new["NVRAM"])

    def test_wrong_version_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            efi, archive = fixture(pathlib.Path(t))
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("SMCProcessor.kext/Contents/Info.plist", plugin_info(m.BUNDLE, "1.3.7"))
                z.writestr("SMCProcessor.kext/Contents/MacOS/SMCProcessor", FAKEX64)
                z.writestr("VirtualSMC.kext/Contents/Info.plist", plugin_info(m.VSMC_ID))
                z.writestr("VirtualSMC.kext/Contents/MacOS/VirtualSMC", FAKEX64)
            with self.assertRaises(RuntimeError):
                m.parse_official_zip(archive)

    def test_existing_driver_refused(self):
        with tempfile.TemporaryDirectory() as t:
            efi, archive = fixture(pathlib.Path(t))
            (efi/"OC"/"Kexts"/m.NAME).mkdir()
            with self.assertRaises(RuntimeError):
                m.inspect_efi(efi, archive)

    def test_reject_traversal(self):
        with tempfile.TemporaryDirectory() as t:
            _, archive = fixture(pathlib.Path(t))
            with zipfile.ZipFile(archive, "a") as z:
                z.writestr("../trojan", b"abc")
            with self.assertRaises(RuntimeError):
                m.parse_official_zip(archive)


class TestApplyRestore(unittest.TestCase):
    @staticmethod
    def validator(tmp, status):
        f = tmp/"ocvalidate.exe"
        f.write_text("#!/bin/sh\nexit %d\n" % status)
        f.chmod(0o755)
        return f

    def test_install_restore_exact_and_other_kext_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            temp = pathlib.Path(t)
            efi, archive = fixture(temp)
            config = efi/"OC/config.plist"
            baseline = config.read_bytes()
            backup = temp/"backup"
            with patch.object(m, "ensure_backup_location", lambda oc, target: None):
                m.guarded_apply(efi, archive, backup, self.validator(temp, 0), "INSTALL-SMC-SENSOR")
            self.assertNotEqual(config.read_bytes(), baseline)
            self.assertTrue((efi/"OC/Kexts"/m.NAME).exists())
            self.assertEqual(plistlib.loads(config.read_bytes())["NVRAM"]["Add"]["boot-args"], "Metal")
            self.assertEqual((efi/"OC/Kexts/VirtualSMC.kext/Contents/Info.plist").read_bytes(),
                             plugin_info(m.VSMC_ID))
            saved = next(backup.iterdir())
            m.guarded_restore(efi, saved, "RESTORE-SMC-SENSOR")
            self.assertEqual(config.read_bytes(), baseline)
            self.assertFalse((efi/"OC/Kexts"/m.NAME).exists())

    def test_failed_validator_rolls_back(self):
        with tempfile.TemporaryDirectory() as t:
            temp = pathlib.Path(t)
            efi, archive = fixture(temp)
            cfg = efi/"OC/config.plist"
            baseline = cfg.read_bytes()
            with patch.object(m, "ensure_backup_location", lambda oc, target: None):
                with self.assertRaises(RuntimeError):
                    m.guarded_apply(efi, archive, temp/"backup", self.validator(temp, 1), "INSTALL-SMC-SENSOR")
            self.assertEqual(cfg.read_bytes(), baseline)
            self.assertFalse((efi/"OC/Kexts"/m.NAME).exists())

    def test_restore_refuses_modified_config(self):
        with tempfile.TemporaryDirectory() as t:
            temp = pathlib.Path(t)
            efi, archive = fixture(temp)
            with patch.object(m, "ensure_backup_location", lambda oc, target: None):
                m.guarded_apply(efi, archive, temp/"backup", self.validator(temp, 0), "INSTALL-SMC-SENSOR")
            cfg = efi/"OC/config.plist"
            cfg.write_bytes(cfg.read_bytes() + b" ")
            saved = next((temp/"backup").iterdir())
            with self.assertRaises(RuntimeError):
                m.guarded_restore(efi, saved, "RESTORE-SMC-SENSOR")
