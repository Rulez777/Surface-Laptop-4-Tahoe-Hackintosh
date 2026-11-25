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
import install_sl4_sleepwake_macos

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
                self.assertIn("SL4-Tahoe-QuickStart/scripts/install_sl4_rcs_stability.py",names)
                self.assertIn("SL4-Tahoe-QuickStart/scripts/install_sl4_sleepwake_macos.py",names)
                self.assertIn("SL4-Tahoe-QuickStart/experiments/sl4-input/build-bigsurface-sl4-sleepwake.py",names)
                self.assertIn("SL4-Tahoe-QuickStart/experiments/sl4-input/patches/sl4-sleepwake-production.patch",names)
                self.assertIn("SL4-Tahoe-QuickStart/research/SSDT-SL4-LIDWAKE.aml",names)
                self.assertIn("SL4-Tahoe-QuickStart/packages/SL4-TGL-Input-SleepWake-v2-beta.zip",names)
                self.assertIn("SL4-Tahoe-QuickStart/docs/QUICKSTART-RCS.md",names)
                self.assertIn("SL4-Tahoe-QuickStart/research/wex-sl4-rcs-singleport.patch",names)
                self.assertIn("SL4-Tahoe-QuickStart/packages/SL4-Graphics-Performance-0.1.7-beta.zip",names)
                self.assertIn("SL4-Tahoe-QuickStart/packages/SL4-Dolby-APOMac-Profiles-20261123.zip",names)
                self.assertIn("SL4-Tahoe-QuickStart/scripts/install_dolby_macos.py",names)
                self.assertIn("SL4-Tahoe-QuickStart/docs/AUDIO-ALL-IN-ONE.md",names)
                self.assertNotIn("SL4-Tahoe-QuickStart/EFI/OC/config.plist",names)
            with self.assertRaisesRegex(RuntimeError,"exists"):
                build_windows_quickstart_kit.build(out)

    def test_rcs_addon_pinned_and_offline_stage_only(self):
        self.assertTrue(windows_prepare_tahoe.RCS_URL.endswith("/SL4-Graphics-Performance-0.1.7-beta.zip"))
        self.assertEqual(windows_prepare_tahoe.RCS_SHA,
                         "bdbb6aad67ebcfc2185281c5ea8dca267cdd6e3c2aad3371bd701e3b5417880d")
        self.assertIn("choose_automatic_action",
                      (ROOT/"scripts/QuickStart-Mac.command").read_text())
        self.assertNotIn("-wex-sl4-rcs-singleport",enable_xe_macos.STARTUP_ARGS)
        self.assertNotIn("-wex-sl4-rcs-nativequeue-trial",enable_xe_macos.STARTUP_ARGS)
        self.assertIn("-wex-sl4-heap-depth-trial",enable_xe_macos.STARTUP_ARGS)
        self.assertEqual(enable_xe_macos.DMC_PATH,"WhateverXe-SL4-RCS-V017-TRIAL.kext")
        self.assertIn("install_sl4_rcs_stability.py",windows_prepare_tahoe.__file__ and
                      (ROOT/"scripts/windows_prepare_tahoe.py").read_text())

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
        source=ROOT/"packages/SL4-TGL-Input-SleepWake-v2-beta.zip"
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                         build_efi.INPUT_PACKAGE_SHA)
        self.assertEqual(build_efi.INPUT_KEXTS,
                         ("VoodooGPIO","VoodooSerial","VoodooInput","BigSurface","BigSurfaceHIDDriver"))
        files=install_sl4_sleepwake_macos.validate_archive(source)
        self.assertIn("ACPI/SSDT-SL4-LIDWAKE.aml",files)
        self.assertFalse(any("SL4LidGPIOProbe" in x for x in files))
        self.assertEqual(plistlib.loads(files["Kexts/VoodooGPIO.kext/Contents/Info.plist"])["CFBundleVersion"],"1.2.5")

    def test_sleepwake_installer_config_is_minimal_and_diagnostic_free(self):
        cfg={
            "Kernel":{"Add":[
                {"BundlePath":"Lilu.kext","Enabled":True},
                {"BundlePath":"VirtualSMC.kext","Enabled":True},
                {"BundlePath":"VoodooI2C.kext","Enabled":True},
                {"BundlePath":"SMCBatteryManager.kext","Enabled":True},
            ]},
            "ACPI":{"Add":[{"Path":"SSDT-RTC0-SL4.aml","Enabled":True}]},
            "Misc":{"Debug":{"SysReport":True}},
            "NVRAM":{"Add":{"7C436110-AB2A-4BBB-A880-FE41995C9F82":{
                "boot-args":"-igfxdvmt -wex-edp-wake-trace -wex-tgl-edp-keep"
            }}},
        }
        staged,changes=install_sl4_sleepwake_macos.kernel_changes(cfg)
        self.assertFalse(next(x for x in staged["Kernel"]["Add"] if x["BundlePath"]=="VoodooI2C.kext")["Enabled"])
        self.assertFalse(next(x for x in staged["Kernel"]["Add"] if x["BundlePath"]=="SMCBatteryManager.kext")["Enabled"])
        for name in install_sl4_sleepwake_macos.EXPECTED:
            self.assertTrue(next(x for x in staged["Kernel"]["Add"] if x["BundlePath"]==name)["Enabled"])
        self.assertTrue(next(x for x in staged["ACPI"]["Add"] if x["Path"]=="SSDT-SL4-LIDWAKE.aml")["Enabled"])
        self.assertFalse(staged["Misc"]["Debug"]["SysReport"])
        self.assertNotIn("-wex-edp-wake-trace",staged["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"].split())
        self.assertIn("disabled: Misc.Debug.SysReport",changes)
        self.assertTrue(any("diagnostic boot argument" in x for x in changes))

    def test_peripherals_restricted_to_supported_upstreams(self):
        self.assertEqual(len(prepare_sl4_peripherals.RELEASES),8)
        self.assertTrue(all(url.startswith("https://github.com/")
                            and len(sha)==64
                            for url,sha in prepare_sl4_peripherals.RELEASES.values()))

    def test_private_generated_efi_settings_for_graphics(self):
        with tempfile.TemporaryDirectory() as tmp:
            efi=Path(tmp)/"EFI"
            build_efi.restore_seed(efi)
            config=plistlib.loads((efi/"OC/config.plist").read_bytes())
            boot_args=config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"]
            config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"]=boot_args+" -wex-edp-wake-trace -wex-sl4-rcs-singleport -wex-sl4-rcs-nativequeue-trial"
            for part in ("BOOT/BOOTx64.efi","OC/OpenCore.efi"):
                p=efi/part
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(b"synthetic-not-a-real-bootloader")
            for item in ("Lilu.kext","WhateverXe.kext","AMFIAnchor.kext","AMFIAnchorInjector.kext"):
                p=efi/"OC/Kexts"/item/"Contents/Info.plist"
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(b"test")
            build_efi.add_surface_input_pack(efi,config,
                    ROOT/"packages/SL4-TGL-Input-SleepWake-v2-beta.zip")
            self.assertTrue((efi/"OC/ACPI/SSDT-SL4-LIDWAKE.aml").is_file())
            self.assertIn("SSDT-SL4-LIDWAKE.aml",[x["Path"] for x in config["ACPI"]["Add"]])
            self.assertFalse(config["Misc"]["Debug"]["SysReport"])
            staged_boot_args=config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"].split()
            for disabled_flag in ("-wex-edp-wake-trace","-wex-sl4-rcs-singleport","-wex-sl4-rcs-nativequeue-trial"):
                self.assertNotIn(disabled_flag,staged_boot_args)
            self.assertEqual(plistlib.loads((efi/"OC/Kexts/VoodooGPIO.kext/Contents/Info.plist").read_bytes())["CFBundleVersion"],"1.2.5")
            for item in enable_xe_macos.EXTRA_DRIVERS + enable_xe_macos.LEGACY_WIRELESS:
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
            self.assertTrue(all(not next(x for x in staged["Kernel"]["Add"]
                                      if x["BundlePath"]==name)["Enabled"]
                                for name in enable_xe_macos.LEGACY_WIRELESS))
            for flag in ("-btleadv","-btleadvnodupfilter"):
                self.assertIn(flag,staged["NVRAM"]["Add"][enable_xe_macos.GUID]["boot-args"].split())
                self.assertNotIn(flag,before["NVRAM"]["Add"][enable_xe_macos.GUID]["boot-args"].split())
            self.assertIn("SSDT-DEEPIDLE.aml",[x["Path"] for x in staged["ACPI"]["Add"]])
            self.assertIn("SSDT-PNLF.aml",[x["Path"] for x in staged["ACPI"]["Add"]])
            self.assertNotIn("-wex-noaccel",staged["NVRAM"]["Add"][enable_xe_macos.GUID]["boot-args"])
            self.assertIn("-wex-noaccel",before["NVRAM"]["Add"][enable_xe_macos.GUID]["boot-args"])
            staged_args=staged["NVRAM"]["Add"][enable_xe_macos.GUID]["boot-args"].split()
            self.assertNotIn("-wex-sl4-rcs-singleport",staged_args)
            self.assertNotIn("-wex-sl4-rcs-nativequeue-trial",staged_args)
            self.assertIn("-wex-sl4-heap-depth-trial",staged_args)
            self.assertNotIn("-wex-edp-wake-trace",staged_args)
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
