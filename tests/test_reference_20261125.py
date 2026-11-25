import hashlib,sys,plistlib,unittest,zipfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import install_reference_20261125 as r
class ReferenceTests(unittest.TestCase):
    def test_exact_public_package(self):
        b,i=r.bundle(ROOT/"packages"/r.ARCHIVE)
        self.assertEqual(hashlib.sha256(b).hexdigest(),r.BIN_SHA)
        self.assertEqual(plistlib.loads(i)["CFBundleVersion"],"0.8.5")
        with zipfile.ZipFile(ROOT/"packages"/r.ARCHIVE) as z:
            for n in z.namelist():
                self.assertNotIn("config.plist",n.lower())
                self.assertNotIn("bootmgfw",n.lower())
            self.assertIn("source/WhateverXe/kern_sl4_rapl_cap.hpp",z.namelist())
    def test_preserve_non_graphics_configuration(self):
        c={"Kernel":{"Add":[{"Enabled":True,"BundlePath":"Lilu.kext"},{"Enabled":True,"BundlePath":r.TARGET}]},"NVRAM":{"Add":{r.base.GUID:{"boot-args":"-allow3d -wex-sl4-tgl-dmc -wex-sl4-heap-depth-trial -wex-sl4-rcs-singleport -btleadvnodupfilter"}},"Delete":{r.base.GUID:["boot-args"]}},"PlatformInfo":{"Generic":{"SystemSerialNumber":"fixture"}}}
        n=plistlib.loads(r.candidate(plistlib.dumps(c)))
        self.assertEqual(n["PlatformInfo"],c["PlatformInfo"])
        self.assertEqual(n["Kernel"],c["Kernel"])
        args=n["NVRAM"]["Add"][r.base.GUID]["boot-args"].split()
        self.assertIn("-btleadvnodupfilter",args)
        self.assertNotIn("-wex-sl4-rcs-singleport",args)
        for f in r.NEW_FLAGS:self.assertEqual(args.count(f),1)
        c["Kernel"]["Add"].append({"Enabled":True,"BundlePath":"WhateverXe.kext"})
        with self.assertRaises(RuntimeError):r.candidate(plistlib.dumps(c))
if __name__=="__main__":unittest.main()
