"""RCS release tests: source signatures, personal EFI safety, apply/rollback and ZIP integrity."""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import plistlib
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("sl4_rcs",ROOT/"scripts/install_sl4_rcs_stability.py")
rcs=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rcs)
PKG=Path(os.environ["SL4_RCS_RELEASE_ZIP"]) if os.environ.get("SL4_RCS_RELEASE_ZIP") else None

class RCSTests(unittest.TestCase):
    def test_own_patch_guards_and_baseline(self):
        source=(ROOT/"research/wex-sl4-rcs-singleport.patch").read_text()
        for item in ("0x3d5d0","0x3b971","SL4RCSSinglePortReady",
                     "-wex-sl4-rcs-singleport","wrapAllowPreemption",
                     "wrapEvalWait","wrapDequeue","0x9A49"):
            self.assertIn(item,source)
        self.assertNotIn("kextstat -l",source)

    def test_bundle_has_no_private_efi(self):
        if not PKG:
            self.skipTest("requires real compiled distribution ZIP")
        self.assertTrue(PKG.is_file())
        with zipfile.ZipFile(PKG) as z:
            self.assertIsNone(z.testzip())
            pre=rcs.RELEASE+"/"
            m=json.loads(z.read(pre+"MANIFEST.json"))
            self.assertTrue(m["no_private_efi"])
            self.assertFalse(m["game_stability_fully_verified"])
            self.assertEqual(m["synthetic_metal_command_buffers"],400000)
            for name,sha in m["sha256"].items():
                self.assertEqual(hashlib.sha256(z.read(pre+name)).hexdigest(),sha)
                self.assertNotIn("config.plist",name.lower())
                self.assertNotIn("bootmgfw",name.lower())
                self.assertNotIn("SMBIOS",name)
            self.assertEqual(m["sha256"]["payload/"+rcs.TARGET+"/Contents/MacOS/WhateverXe"],rcs.WEX_SHA)

    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.base=Path(self.t.name)
        self.efi=self.base/"disk"/"EFI"
        oc=self.efi/"OC"
        (oc/"Kexts").mkdir(parents=True)
        (self.efi/"Microsoft/Boot").mkdir(parents=True)
        (self.efi/"Microsoft/Boot/bootmgfw.efi").write_bytes(b"not-a-real-windows-efi")
        self.before_win=rcs.digest(self.efi/"Microsoft/Boot/bootmgfw.efi")
        old=oc/"Kexts/WhateverXe-Previous.kext/Contents"
        (old/"MacOS").mkdir(parents=True)
        (old/"MacOS/WhateverXe").write_bytes(b"old-tested-graphics")
        (old/"Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier":rcs.KEXT_ID,"CFBundleVersion":"0.8.3"}))
        self.config={
            "Kernel":{"Add":[{"Enabled":True,"BundlePath":"Lilu.kext"},
                             {"Enabled":True,"BundlePath":"WhateverXe-Previous.kext",
                              "PlistPath":"Contents/Info.plist","ExecutablePath":"Contents/MacOS/WhateverXe"}]},
            "NVRAM":{"Add":{rcs.UUID:{"boot-args":"-allow3d -wex-tgl-gpurec -wex-tgl-stampfix -wex-sl4-tgl-dmc"}},
                     "Delete":{rcs.UUID:["boot-args"]}}
        }
        (oc/"config.plist").write_bytes(plistlib.dumps(self.config))
        self.before_config=rcs.digest(oc/"config.plist")
        self.bundle=self.base/"bundle"
        src=self.bundle/"payload"/rcs.TARGET/"Contents"
        (src/"MacOS").mkdir(parents=True)
        (src/"MacOS/WhateverXe").write_bytes(b"RCS-test-only-kext-data")
        (src/"Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier":rcs.KEXT_ID,"CFBundleVersion":"0.8.3"}))
        self.backups=self.base/"backups"

    @contextmanager
    def fake_mount(self,esp):
        self.assertEqual(esp,"disk0s1")
        yield self.efi

    def test_apply_and_rollback_never_touch_windows(self):
        patches=[
            mock.patch.object(rcs,"preflight_hardware",return_value=None),
            mock.patch.object(rcs,"mounted_esp",side_effect=self.fake_mount),
            mock.patch.object(rcs,"validate",return_value=None),
            mock.patch.object(rcs,"state_home",return_value=self.backups),
            mock.patch.object(rcs.os,"geteuid",return_value=0),
            mock.patch.object(rcs,"HERE",self.bundle),
            mock.patch.object(rcs,"WEX_SHA",rcs.digest(self.bundle/"payload"/rcs.TARGET/"Contents/MacOS/WhateverXe")),
        ]
        with patches[0],patches[1],patches[2],patches[3],patches[4],patches[5],patches[6]:
            rcs.check("disk0s1",self.base/"validator")
            rcs.apply("disk0s1",self.base/"validator")
            d=plistlib.loads((self.efi/"OC/config.plist").read_bytes())
            self.assertEqual(d["Kernel"]["Add"][1]["BundlePath"],rcs.TARGET)
            self.assertIn(rcs.FLAG,d["NVRAM"]["Add"][rcs.UUID]["boot-args"])
            self.assertEqual(self.before_win,rcs.digest(self.efi/"Microsoft/Boot/bootmgfw.efi"))
            self.assertTrue((self.efi/"OC/Kexts/WhateverXe-Previous.kext").is_dir())
            self.assertTrue((self.backups/"latest.json").is_file())
            rcs.rollback("disk0s1",self.base/"validator")
            self.assertEqual(self.before_config,rcs.digest(self.efi/"OC/config.plist"))
            self.assertEqual(self.before_win,rcs.digest(self.efi/"Microsoft/Boot/bootmgfw.efi"))
            self.assertFalse((self.backups/"latest.json").exists())
            self.assertTrue((self.efi/"OC/Kexts"/rcs.TARGET).exists())

    def test_wrong_source_dmc_args_fail_closed(self):
        self.config["NVRAM"]["Add"][rcs.UUID]["boot-args"]="-allow3d -wex-tgl-gpurec"
        (self.efi/"OC/config.plist").write_bytes(plistlib.dumps(self.config))
        with self.assertRaisesRegex(RuntimeError,"DMC/3D"):
            rcs.cfg_inspect(self.efi)

if __name__=="__main__":unittest.main()
