#!/usr/bin/env python3
"""Portable eDP package and reversible EFI installer tests. No privileged commands."""
import hashlib
import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest
import zipfile

REPO=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("edp",REPO/"scripts/install_edp_keep_macos.py")
edp=importlib.util.module_from_spec(spec)
spec.loader.exec_module(edp)

class EdpPackageTests(unittest.TestCase):
    def test_zip_integrity(self):
        z=REPO/"packages"/edp.ZIP_NAME
        self.assertTrue(z.is_file())
        with zipfile.ZipFile(z) as archive:
            self.assertIsNone(archive.testzip())
            names=archive.namelist()
            self.assertEqual(len(names),7)
            self.assertFalse(any("config.plist" in x or "SystemUUID" in x for x in names))
            binary=next(x for x in names if x.endswith("/Contents/MacOS/WhateverXe"))
            self.assertEqual(hashlib.sha256(archive.read(binary)).hexdigest(),edp.BINARY_SHA)
            text=next(x for x in names if x.endswith("/install_edp_keep_macos.py"))
            self.assertEqual(archive.read(text),(REPO/"scripts/install_edp_keep_macos.py").read_bytes())
    def test_apply_and_rollback_no_windows_changes(self):
        with tempfile.TemporaryDirectory(prefix="SL4-edp-test-") as td:
            root=Path(td)
            efi=root/"ESP/EFI"
            (efi/"Microsoft/Boot").mkdir(parents=True)
            (efi/"OC/Kexts/WhateverXe.kext/Contents").mkdir(parents=True)
            oldkext=efi/"OC/Kexts/WhateverXe.kext/Contents"
            (oldkext/"Info.plist").write_bytes(plistlib.dumps({
                "CFBundleIdentifier":"org.b00t0x.WhateverXe","CFBundleVersion":"0.8.3"}))
            (oldkext/"MacOS").mkdir()
            (oldkext/"MacOS/WhateverXe").write_bytes(b"SAFE-KNOWN-GOOD")
            win=efi/"Microsoft/Boot/bootmgfw.efi"
            win.write_bytes(b"NOT-TO-BE-EDITED")
            args="npci=0x2000 -allow3d -disablegfxfirmware -igfxdvmt -wex-tgl-no-posh"
            config={"Kernel":{"Add":[{"Enabled":True,"BundlePath":"Lilu.kext"},
                {"Enabled":True,"BundlePath":"WhateverXe.kext","ExecutablePath":"Contents/MacOS/WhateverXe","PlistPath":"Contents/Info.plist"}]},
                "NVRAM":{"Add":{edp.APPLE_GUID:{"boot-args":args}},
                         "Delete":{edp.APPLE_GUID:["boot-args"]}}}
            cp=efi/"OC/config.plist"
            original=plistlib.dumps(config)
            cp.write_bytes(original)
            bundle,validator,temporary=edp.discover_bundle()
            try:
                edp.check_bundle(bundle,validator)
                before_validate, before_mounter, before_euid=edp.validate,edp.MountedEFI,edp.os.geteuid
                class FakeMount:
                    def __init__(self,device):self.device=device
                    def __enter__(self):return efi
                    def __exit__(self,kind,error,tb):return False
                edp.validate=lambda validator,path:plistlib.loads(Path(path).read_bytes())
                edp.MountedEFI=FakeMount
                edp.os.geteuid=lambda:0
                try:
                    saved=root/"user-backups"
                    edp.apply("disk0s1",bundle,validator,saved)
                    self.assertTrue((saved/"latest.json").is_file())
                    current=plistlib.loads(cp.read_bytes())
                    self.assertEqual(current["Kernel"]["Add"][1]["BundlePath"],edp.KEXT_NAME)
                    import json
                    state=json.loads((saved/"latest.json").read_text())
                    self.assertEqual(state["original_kext_name"],"WhateverXe.kext")
                    current_args=current["NVRAM"]["Add"][edp.APPLE_GUID]["boot-args"].split()
                    for flag in edp.FLAGS:self.assertEqual(current_args.count(flag),1)
                    self.assertEqual(win.read_bytes(),b"NOT-TO-BE-EDITED")
                    self.assertEqual((oldkext/"MacOS/WhateverXe").read_bytes(),b"SAFE-KNOWN-GOOD")
                    self.assertEqual(edp.sha(efi/"OC/Kexts"/edp.KEXT_NAME/"Contents/MacOS/WhateverXe"),edp.BINARY_SHA)
                    with self.assertRaisesRegex(RuntimeError,"already recorded"):
                        edp.apply("disk0s1",bundle,validator,saved)
                    edp.rollback("disk0s1",validator,saved)
                    self.assertEqual(cp.read_bytes(),original)
                    self.assertEqual(win.read_bytes(),b"NOT-TO-BE-EDITED")
                finally:
                    edp.validate,edp.MountedEFI,edp.os.geteuid=before_validate,before_mounter,before_euid
            finally:
                if temporary:temporary.cleanup()
    def test_refuses_unaccelerated_configuration(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            contents=root/"OC/Kexts/WhateverXe.kext/Contents"
            contents.mkdir(parents=True)
            (contents/"Info.plist").write_bytes(plistlib.dumps({
                "CFBundleIdentifier":"org.b00t0x.WhateverXe","CFBundleVersion":"0.8.3"}))
            data={"Kernel":{"Add":[{"Enabled":True,"BundlePath":"Lilu.kext"},{"Enabled":True,"BundlePath":"WhateverXe.kext"}]},
                  "NVRAM":{"Add":{edp.APPLE_GUID:{"boot-args":"-wex-noaccel -igfxdvmt -allow3d -disablegfxfirmware"}},
                          "Delete":{edp.APPLE_GUID:["boot-args"]}}}
            with self.assertRaisesRegex(RuntimeError,"Metal must already work"):
                edp.inspect_config(root,data)

if __name__=="__main__":
    unittest.main()
