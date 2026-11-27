"""Synthetic macOS SMCProcessor EFI installer tests. No real ESP, EC, or Mac calls."""
import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest
import zipfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("mac_smc", Path(__file__).with_name("install_smcprocessor_macos.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
X64 = bytes.fromhex("cffaedfe07000001") + b"_" * 192


def info(identifier, executable):
    return plistlib.dumps({"CFBundleIdentifier": identifier, "CFBundleVersion": "1.3.8",
                           "CFBundleExecutable": executable,
                           "OSBundleLibraries": {"as.vit9696.VirtualSMC":"1.0.0", "as.vit9696.Lilu":"1.0.0"}})


def setup(root):
    efi = root/"SYS"/"EFI"
    oc = efi/"OC"
    (efi/"Microsoft"/"Boot").mkdir(parents=True)
    (efi/"Microsoft"/"Boot"/"bootmgfw.efi").write_bytes(b"Microsoft")
    (oc/"Kexts"/"VirtualSMC.kext"/"Contents").mkdir(parents=True)
    (oc/"OpenCore.efi").write_bytes(b"OpenCore")
    (oc/"Kexts"/"VirtualSMC.kext"/"Contents"/"Info.plist").write_bytes(info(mod.VIRTUALSMC, "VirtualSMC"))
    entries = [{"BundlePath":name, "Enabled":True, "Arch":"Any", "Comment":"",
                "ExecutablePath":"Contents/MacOS/"+name.split(".")[0],
                "PlistPath":"Contents/Info.plist","MaxKernel":"","MinKernel":""}
               for name in ("Lilu.kext", "VirtualSMC.kext", "BigSurface.kext")]
    config = {"Kernel":{"Add":entries},"NVRAM":{"Add":{mod.GUID:{"boot-args":"npci=0x2000 -igfxdvmt"}}},
              "DeviceProperties":{"Add":{"GPU":{"unchanged":b"HiDPI"}}}}
    (oc/"config.plist").write_bytes(plistlib.dumps(config))
    archive = root/"VirtualSMC-1.3.8-RELEASE.zip"
    with zipfile.ZipFile(archive,"w") as z:
        for name, bundle in ((mod.NAME,mod.BUNDLE), ("VirtualSMC.kext",mod.VIRTUALSMC)):
            exe = name.split(".")[0]
            z.writestr(f"RELEASE/{name}/Contents/Info.plist",info(bundle,exe))
            z.writestr(f"RELEASE/{name}/Contents/MacOS/{exe}",X64)
    return efi, archive


class UnitTests(unittest.TestCase):
    def test_plugin_zip_and_config(self):
        with tempfile.TemporaryDirectory() as t:
            efi,archive = setup(Path(t))
            oc,config,updated,files = mod.inspect(efi,archive)
            self.assertEqual(len(files),2)
            self.assertEqual([x["BundlePath"] for x in updated["Kernel"]["Add"]],
               ["Lilu.kext","VirtualSMC.kext","SMCProcessor.kext","BigSurface.kext"])
            self.assertEqual(plistlib.loads(config.read_bytes())["DeviceProperties"],updated["DeviceProperties"])

    def test_preexisting_kext_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            efi,archive=setup(Path(t))
            (efi/"OC"/"Kexts"/mod.NAME).mkdir()
            with self.assertRaises(RuntimeError):
                mod.inspect(efi,archive)

    def test_invalid_release_version_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            efi,archive=setup(Path(t))
            with zipfile.ZipFile(archive,"w") as z:
                z.writestr(f"{mod.NAME}/Contents/Info.plist",
                     plistlib.dumps({"CFBundleIdentifier":mod.BUNDLE,"CFBundleVersion":"1.3.7","CFBundleExecutable":"SMCProcessor"}))
                z.writestr(f"{mod.NAME}/Contents/MacOS/SMCProcessor",X64)
                z.writestr(f"VirtualSMC.kext/Contents/Info.plist",info(mod.VIRTUALSMC,"VirtualSMC"))
                z.writestr(f"VirtualSMC.kext/Contents/MacOS/VirtualSMC",X64)
            with self.assertRaises(RuntimeError):
                mod.parse_release(archive)

    def test_zip_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            efi,archive=setup(Path(t))
            with zipfile.ZipFile(archive,"a") as z:
                z.writestr("../outside",b"bad")
            with self.assertRaises(RuntimeError):
                mod.parse_release(archive)

    @staticmethod
    def validator(root,success=True):
        v=root/"ocvalidate"
        v.write_text("#!/bin/sh\nexit %d\n" % (0 if success else 1))
        v.chmod(0o755)
        return v

    def test_apply_and_exact_restore(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); efi,archive=setup(root)
            cfg=efi/"OC"/"config.plist"; original=cfg.read_bytes()
            backup=root/"backup"
            with patch.object(mod.os,"geteuid",return_value=0),patch.object(mod,"safe_backup_root",return_value=None):
                mod.apply(efi,archive,backup,self.validator(root), "INSTALL-SMC-SENSOR")
            self.assertTrue((efi/"OC"/"Kexts"/mod.NAME).is_dir())
            self.assertEqual(plistlib.loads(cfg.read_bytes())["DeviceProperties"],
                             plistlib.loads(original)["DeviceProperties"])
            self.assertEqual((efi/"Microsoft"/"Boot"/"bootmgfw.efi").read_bytes(), b"Microsoft")
            saved=next(backup.iterdir())
            with patch.object(mod.os,"geteuid",return_value=0):
                mod.restore(efi,saved,"RESTORE-SMC-SENSOR")
            self.assertEqual(cfg.read_bytes(),original)
            self.assertFalse((efi/"OC"/"Kexts"/mod.NAME).exists())

    def test_ocvalidate_failure_rolls_back(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);efi,archive=setup(root)
            cfg=efi/"OC"/"config.plist";original=cfg.read_bytes()
            with patch.object(mod.os,"geteuid",return_value=0),patch.object(mod,"safe_backup_root",return_value=None):
                with self.assertRaises(RuntimeError):
                    mod.apply(efi,archive,root/"backup",self.validator(root,False),"INSTALL-SMC-SENSOR")
            self.assertEqual(cfg.read_bytes(),original)
            self.assertFalse((efi/"OC"/"Kexts"/mod.NAME).exists())

    def test_refuse_restore_if_config_changed(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);efi,archive=setup(root)
            cfg=efi/"OC"/"config.plist"
            with patch.object(mod.os,"geteuid",return_value=0),patch.object(mod,"safe_backup_root",return_value=None):
                mod.apply(efi,archive,root/"backup",self.validator(root),"INSTALL-SMC-SENSOR")
            cfg.write_bytes(cfg.read_bytes()+b" ")
            saved=next((root/"backup").iterdir())
            with patch.object(mod.os,"geteuid",return_value=0):
                with self.assertRaises(RuntimeError):
                    mod.restore(efi,saved,"RESTORE-SMC-SENSOR")

    def test_reject_wrong_graphics_flags(self):
        with tempfile.TemporaryDirectory() as t:
            efi,archive=setup(Path(t))
            cfgpath=efi/"OC"/"config.plist"
            cfg=plistlib.loads(cfgpath.read_bytes())
            cfg["NVRAM"]["Add"][mod.GUID]["boot-args"]="-wex-noaccel"
            cfgpath.write_bytes(plistlib.dumps(cfg))
            with self.assertRaises(RuntimeError):
                mod.inspect(efi,archive)


if __name__=="__main__":
    unittest.main()
