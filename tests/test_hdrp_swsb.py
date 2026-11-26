import sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import install_hdrp_swsb_macos as h
import build_windows_quickstart_kit as kit
class HDRPTest(unittest.TestCase):
    def test_exact_patch_bytes_and_rejection(self):
        b=bytearray(max(x[0]+len(bytes.fromhex(x[1])) for x in h.PATCHES))
        for off,before,after in h.PATCHES:
            b[off:off+len(bytes.fromhex(before))]=bytes.fromhex(before)
        expected=bytearray(b)
        for off,before,after in h.PATCHES:
            expected[off:off+len(bytes.fromhex(after))]=bytes.fromhex(after)
        with self.assertRaises(RuntimeError):h.patch_igc(b)
        with patch.object(h,"BASE_G",h.sha(b)),patch.object(h,"UNSIGNED_G",h.sha(expected)):
            self.assertEqual(h.patch_igc(b),expected)
            b[h.PATCHES[0][0]]^=1
            with self.assertRaises(RuntimeError):h.patch_igc(b)
    def test_all_three_hash_constants(self):
        b=bytearray(0x2100);old=bytes.fromhex(h.BASE_G);new=bytes.fromhex(h.NEW_G)
        b[0x2020:0x2040]=old[16:]+old[:16];b[0x2060:0x2080]=old
        with patch.object(h,"BASE_A",h.sha(b)):
            a=h.patch_adapter(b)
        self.assertEqual(a[0x2020:0x2040],new[16:]+new[:16])
        self.assertEqual(a[0x2060:0x2080],new)
        self.assertEqual(a[:0x2020],b[:0x2020])
        self.assertEqual(a[0x2040:0x2060],b[0x2040:0x2060])
        self.assertEqual(a[0x2080:],b[0x2080:])
    def test_distribution(self):
        self.assertIn("scripts/install_hdrp_swsb_macos.py",kit.FILES)
        self.assertIn("docs/HDRP-SWSB-FIX.md",kit.FILES)
        for name in ("QuickStart-Mac.command","QuickStart-Windows.ps1","windows_prepare_tahoe.py"):
            self.assertIn("install_hdrp_swsb_macos.py",(ROOT/"scripts"/name).read_text())
        self.assertNotIn("graphicsTracePointEnable",(ROOT/"scripts/install_hdrp_swsb_macos.py").read_text())
if __name__=="__main__":unittest.main()
