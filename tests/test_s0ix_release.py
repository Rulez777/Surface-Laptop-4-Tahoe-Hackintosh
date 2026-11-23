"""Public S0ix release integrity and synthetic OpenCore staging tests.

Does not access an actual ESP, machine configuration or real SMBIOS.
Run with SL4_RELEASE_ZIP=/.../SL4-S0ix-DMC-0.2.0-beta.zip to exercise real payload.
"""
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PKG=Path(os.environ["SL4_RELEASE_ZIP"]) if os.environ.get("SL4_RELEASE_ZIP") else None
PUBLIC_EDP=ROOT/"packages/SL4-WEX-0.8.3-EDP-KeepSoftSleep.zip"

def load(path):
    spec=importlib.util.spec_from_file_location("sl4_s0ix_release_tested",path)
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

class S0ixReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="sl4-s0ix-test-")
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        if PKG:
            with zipfile.ZipFile(PKG) as z:
                self.assertIsNone(z.testzip())
                z.extractall(self.base)
            self.inst=self.base/"SL4-S0ix-DMC-0.2.0-beta"
            self.m=load(self.inst/"install.py")
        else:
            self.inst=ROOT
            self.m=load(ROOT/"scripts/install_sl4_s0ix_release.py")
        self.efi=self.base/"synthetic"/"EFI"
        oc=self.efi/"OC"
        oc.mkdir(parents=True)
        (oc/"Kexts").mkdir()
        (oc/"ACPI").mkdir()
        (self.efi/"Microsoft/Boot").mkdir(parents=True)
        (self.efi/"Microsoft/Boot/bootmgfw.efi").write_bytes(b"synthetic-WBM")
        (oc/"OpenCore.efi").write_bytes(b"synthetic-OC")
        # The public eDP package contains a non-personal WEX kext.
        with zipfile.ZipFile(PUBLIC_EDP) as z:
            binaries=[n for n in z.namelist() if n.endswith("/WhateverXe.kext/Contents/MacOS/WhateverXe")]
            self.assertEqual(len(binaries),1)
            prefix=binaries[0].split("/WhateverXe.kext/Contents/MacOS/WhateverXe")[0]
            kext=oc/"Kexts/WhateverXe-SL4-EDP-KeepSoftSleep.kext"
            for name in z.namelist():
                if not name.startswith(prefix+"/WhateverXe.kext/") or name.endswith("/"):continue
                parts=name[len(prefix+"/WhateverXe.kext/"):].split("/")
                out=kext.joinpath(*parts)
                out.parent.mkdir(parents=True,exist_ok=True)
                out.write_bytes(z.read(name))
        self.assertEqual(self.m.hash_file(kext/"Contents/MacOS/WhateverXe"),
                         self.m.BASE_WEX_SHA)
        self.cfg=oc/"config.plist"
        self.config={
            "PlatformInfo":{"Generic":{"SystemProductName":"MacBookPro16,2"}},
            "Kernel":{"Emulate":{"Cpuid1Data":bytes.fromhex("e5060700")+bytes(12)},
                      "Add":[{"BundlePath":"Lilu.kext","Enabled":True},
                             {"BundlePath":kext.name,"Enabled":True,
                              "PlistPath":"Contents/Info.plist",
                              "ExecutablePath":"Contents/MacOS/WhateverXe"}]},
            "ACPI":{"Add":[]},
            "NVRAM":{"Add":{self.m.NV_GUID:
                {"boot-args":"-allow3d -disablegfxfirmware -igfxdvmt -wex-tgl-gpurec -wex-tgl-edp-keep -wex-tgl-edp-softsleep"}},
                      "Delete":{self.m.NV_GUID:["boot-args"]}}}
        self.cfg.write_bytes(plistlib.dumps(self.config))
        self.initial_config=self.m.hash_file(self.cfg)
        self.windows=self.m.hash_file(self.efi/"Microsoft/Boot/bootmgfw.efi")

    def test_install_preflight_on_synthetic_efi(self):
        raw,obj,pos,args,state=self.m.current_config(self.efi)
        self.assertEqual(state,"edp_ready")
        with mock.patch.object(self.m,"validate_config",return_value=None):
            changed=self.m.build_config(raw,pos,args)
        newer=plistlib.loads(changed)
        self.assertEqual(newer["Kernel"]["Add"][pos]["BundlePath"],self.m.WEX_TARGET)
        self.assertEqual(newer["Kernel"]["Add"][-1]["BundlePath"],"S0ixStandby.kext")
        self.assertEqual(newer["ACPI"]["Add"][-1]["Path"],"SSDT-DEEPIDLE.aml")
        self.assertIn(self.m.BOOT_ARG,newer["NVRAM"]["Add"][self.m.NV_GUID]["boot-args"].split())

    def test_bad_hardware_settings_fail_closed(self):
        self.config["PlatformInfo"]["Generic"]["SystemProductName"]="MacBookPro18,1"
        self.cfg.write_bytes(plistlib.dumps(self.config))
        with self.assertRaisesRegex(RuntimeError,"SMBIOS"):
            self.m.current_config(self.efi)

    def test_s0ix_duplicate_rejected(self):
        raw,obj,pos,args,_=self.m.current_config(self.efi)
        obj["Kernel"]["Add"].append({"BundlePath":"S0ixStandby.kext","Enabled":True})
        raw=plistlib.dumps(obj)
        with mock.patch.object(self.m,"validate_config",return_value=None):
            with self.assertRaisesRegex(RuntimeError,"S0ixStandby already"):
                self.m.build_config(raw,pos,args)

    @unittest.skipUnless(PKG and PKG.is_file(),"Published package path not supplied")
    def test_release_integrity(self):
        self.m.validate_assets()
        p=self.inst/"MANIFEST.json"
        m=json.loads(p.read_text())
        self.assertTrue(m["no_private_efi"])
        self.assertFalse(m["auto_idle_sleep_enabled_by_installer"])
        self.assertFalse(m["clean_install"])
        self.assertEqual(m["one_machine_rtc_wake_tests"],[8,71])
        for name,expected in m["sha256"].items():
            self.assertEqual(self.m.hash_file(self.inst/name),expected)
        self.assertFalse(any("config.plist" in x or "bootmgfw" in x
                             for x in m["sha256"]))

    @unittest.skipUnless(PKG and PKG.is_file(),"Published package path not supplied")
    def test_apply_and_rollback_without_real_efi(self):
        root=self.base/"private-backups"
        self.assertFalse(root.exists())
        root.mkdir(parents=True)
        @contextlib.contextmanager
        def fake_esp(_):
            yield self.efi
        patchers=[
            mock.patch.object(self.m.os,"geteuid",return_value=0),
            mock.patch.object(self.m,"mount_esp",side_effect=fake_esp),
            mock.patch.object(self.m,"mac_preflight",return_value=True),
            mock.patch.object(self.m,"validate_config",return_value=None),
            mock.patch.object(self.m,"backup_home",return_value=root),
        ]
        for patch in patchers:
            patch.start()
            self.addCleanup(patch.stop)
        self.m.apply("disk0s1")
        obj=plistlib.loads(self.cfg.read_bytes())
        w=[x["BundlePath"] for x in obj["Kernel"]["Add"]
           if x.get("Enabled") and "WhateverXe" in x.get("BundlePath","")]
        self.assertEqual(w,[self.m.WEX_TARGET])
        self.assertTrue((self.efi/"OC/Kexts"/self.m.WEX_TARGET).exists())
        self.assertTrue((self.efi/"OC/Kexts/WhateverXe-SL4-EDP-KeepSoftSleep.kext").exists())
        self.assertEqual(self.windows,self.m.hash_file(self.efi/"Microsoft/Boot/bootmgfw.efi"))
        self.m.rollback("disk0s1")
        self.assertEqual(self.initial_config,self.m.hash_file(self.cfg))
        self.assertEqual(self.windows,self.m.hash_file(self.efi/"Microsoft/Boot/bootmgfw.efi"))
        self.assertFalse((root/"latest.json").exists())

if __name__=="__main__":
    unittest.main()
