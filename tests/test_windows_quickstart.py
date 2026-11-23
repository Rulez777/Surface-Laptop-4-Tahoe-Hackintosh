"""Safety and offline functional checks for the Windows-first Tahoe workflow."""
from pathlib import Path
import importlib.util
import json
import plistlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import build_efi
import quiet_boot
import enable_xe_macos
import windows_prepare_tahoe
import build_windows_quickstart_kit
import prepare_sl4_peripherals

class WindowsQuickStartTests(unittest.TestCase):
    def test_installer_archive_self_verifies_without_private_efi(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/"SL4-Tahoe-Windows-QuickStart.zip"
            obj=build_windows_quickstart_kit.build(out)
            self.assertGreater(obj["files"],24)
            self.assertEqual(build_windows_quickstart_kit.verify(out),len(build_windows_quickstart_kit.FILES))
            import zipfile
            with zipfile.ZipFile(out) as z:
                names=z.namelist()
                self.assertIn("SL4-Tahoe-QuickStart/QuickStart.cmd",names)
                self.assertIn("SL4-Tahoe-QuickStart/scripts/QuickStart-Windows.ps1",names)
                self.assertIn("SL4-Tahoe-QuickStart/scripts/xe_acceleration.py",names)
                self.assertNotIn("SL4-Tahoe-QuickStart/EFI/OC/config.plist",names)
            with self.assertRaisesRegex(RuntimeError,"exists"):
                build_windows_quickstart_kit.build(out)

    def test_new_usb_shows_recovery_without_space(self):
        # Verify both regular (quiet) and diagnostic (verbose) installer paths.
        for quiet in (False, True):
            with self.subTest(quiet=quiet), tempfile.TemporaryDirectory() as temp:
                efi = Path(temp)/"EFI"
                build_efi.restore_seed(efi)
                cfg = plistlib.loads((efi/"OC/config.plist").read_bytes())
                cfg["ACPI"]["Add"].append({"Enabled":True, "Path":"SSDT-RTC0-SL4.aml"})
                if quiet:
                    quiet_boot.edit(cfg)
                    self.assertTrue(cfg["Misc"]["Boot"]["HideAuxiliary"])
                build_efi.configure_installer_picker(cfg)
                boot = cfg["Misc"]["Boot"]
                self.assertTrue(boot["ShowPicker"])
                self.assertFalse(boot["HideAuxiliary"])
                self.assertEqual(boot["Timeout"], 15)
                self.assertEqual(cfg["Misc"]["Security"]["ScanPolicy"], 0)

    def test_known_input_archive_integrity(self):
        import hashlib
        source=ROOT/"packages/SL4-TGL-Input-Working-v1.zip"
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                         build_efi.INPUT_PACKAGE_SHA)
        self.assertEqual(build_efi.INPUT_KEXTS,
                         ("VoodooGPIO","VoodooSerial","VoodooInput","BigSurface","BigSurfaceHIDDriver"))

    def test_peripherals_restricted_to_supported_upstreams(self):
        self.assertEqual(len(prepare_sl4_peripherals.RELEASES),6)
        self.assertTrue(all(url.startswith("https://github.com/")
                            and len(sha)==64
                            for url,sha in prepare_sl4_peripherals.RELEASES.values()))

    def test_private_generated_efi_settings_for_graphics(self):
        with tempfile.TemporaryDirectory() as tmp:
            efi=Path(tmp)/"EFI"
            build_efi.restore_seed(efi)
            config=plistlib.loads((efi/"OC/config.plist").read_bytes())
            for part in ("BOOT/BOOTx64.efi","OC/OpenCore.efi"):
                p=efi/part
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(b"synthetic-not-a-real-bootloader")
            for item in ("Lilu.kext","WhateverXe.kext","AMFIAnchor.kext","AMFIAnchorInjector.kext"):
                p=efi/"OC/Kexts"/item/"Contents/Info.plist"
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(b"test")
            build_efi.add_surface_input_pack(efi,config,
                    ROOT/"packages/SL4-TGL-Input-Working-v1.zip")
            for item in enable_xe_macos.EXTRA_DRIVERS:
                config["Kernel"]["Add"].append({
                    "Arch":"x86_64","BundlePath":item,"Enabled":False,
                    "ExecutablePath":"Contents/MacOS/"+item[:-5],
                    "PlistPath":"Contents/Info.plist","MinKernel":"","MaxKernel":""})
                p=efi/"OC/Kexts"/item/"Contents/Info.plist"
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(b"test")
            config["ACPI"]["Add"].append({"Enabled":True,"Path":"SSDT-RTC0-SL4.aml"})
            boot=config["NVRAM"]["Add"][enable_xe_macos.GUID]
            boot["boot-args"]+=" -igfxdvmt"
            original=plistlib.dumps(config)
            staged=plistlib.loads(enable_xe_macos.make_active(original,efi))
            before=plistlib.loads(original)
            self.assertNotEqual(original,plistlib.dumps(staged))
            self.assertTrue(next(x for x in staged["Kernel"]["Add"]
                                 if x["BundlePath"]==enable_xe_macos.DMC_PATH)["Enabled"])
            self.assertFalse(next(x for x in staged["Kernel"]["Add"]
                                 if x["BundlePath"]=="WhateverXe.kext")["Enabled"])
            self.assertTrue(all(next(x for x in staged["Kernel"]["Add"]
                                      if x["BundlePath"]==name)["Enabled"]
                                for name in enable_xe_macos.EXTRA_DRIVERS))
            self.assertIn("SSDT-DEEPIDLE.aml",[x["Path"] for x in staged["ACPI"]["Add"]])
            self.assertIn("SSDT-PNLF.aml",[x["Path"] for x in staged["ACPI"]["Add"]])
            self.assertNotIn("-wex-noaccel",staged["NVRAM"]["Add"][enable_xe_macos.GUID]["boot-args"])
            self.assertIn("-wex-noaccel",before["NVRAM"]["Add"][enable_xe_macos.GUID]["boot-args"])
            with self.assertRaisesRegex(RuntimeError,"Missing or duplicate initial"):
                enable_xe_macos.make_active(plistlib.dumps({
                    **config,"Kernel":{**config["Kernel"],
                                     "Add":[x for x in config["Kernel"]["Add"] if x["BundlePath"]!="WhateverXe.kext"]}}),efi)

    def test_python_dependency_bootstrap_is_pinned(self):
        ps=(ROOT/"scripts/QuickStart-Windows.ps1").read_text(encoding="utf-8")
        self.assertIn("python-3.12.10-amd64.exe",ps)
        self.assertIn("67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb",ps)
        self.assertIn("Clear-Disk",ps)
        self.assertIn('ERASE USB $number',ps)
        self.assertLess(ps.index('ERASE USB $number'),ps.index('Clear-Disk'))
        self.assertIn("Get-Disk -Number $number",ps)
        self.assertIn("BusType -ne 'USB'",ps)
        self.assertIn("macOS Base System (External)",ps)
        self.assertIn("press Space",ps)

if __name__=="__main__":
    unittest.main()
