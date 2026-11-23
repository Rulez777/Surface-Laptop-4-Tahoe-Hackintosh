"""Structural validation of third-party firmware research; no hardware access."""
import importlib.util
import os
from pathlib import Path
import struct
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("dmc_audit",ROOT/"scripts/inspect_tgl_dmc.py")
dmc=importlib.util.module_from_spec(spec);spec.loader.exec_module(dmc)


class DmcParserTests(unittest.TestCase):
    def test_wrong_length_rejected(self):
        with self.assertRaisesRegex(ValueError,"firmware length"):
            dmc.parse(b"bad firmware")

    def test_bad_sha_rejected(self):
        with self.assertRaisesRegex(ValueError,"SHA256"):
            dmc.parse(bytes(dmc.FIRMWARE_LENGTH))

    def test_css_module_type_rejected(self):
        with self.assertRaisesRegex(ValueError,"CSS module"):
            dmc.parse(bytes(dmc.FIRMWARE_LENGTH),check_hash=False)

    def test_wrong_css_header_size_rejected(self):
        data=bytearray(dmc.FIRMWARE_LENGTH)
        struct.pack_into("<I",data,0,9)
        with self.assertRaisesRegex(ValueError,"CSS header"):
            dmc.parse(bytes(data),check_hash=False)

    def test_public_research_only_does_not_bundle_firmware(self):
        source=(ROOT/"scripts/inspect_tgl_dmc.py").read_text()
        generation=(ROOT/"scripts/generate_tgl_dmc_trial_header.py").read_text()
        patch=(ROOT/"research/wex-tgl-dmc-supervised.patch").read_text()
        self.assertNotIn("tgl_dmc_ver2_12.bin.b64",str(ROOT))
        self.assertIn("0x8F03C",patch)
        self.assertIn("-wex-sl4-tgl-dmc",patch)
        self.assertIn("DMC_MMIO_ARRAY_LENGTH = 20",source)
        self.assertIn("DMC",generation)
        self.assertFalse((ROOT/"research/tgl_dmc_ver2_12.bin").exists())
        self.assertFalse((ROOT/"research/kern_sl4_dmc_trial_data.hpp").exists())

    def test_real_dmc_when_external_test_image_explicitly_supplied(self):
        image=os.environ.get("SL4_TGL_DMC_FIRMWARE_FILE")
        if not image:self.skipTest("No private external firmware supplied to portable CI")
        data=Path(image).read_bytes()
        v=dmc.parse(data)
        self.assertEqual(v["dmc"][0]["program_dwords"],4460)
        self.assertEqual(v["dmc"][0]["first_program_dword"],dmc.FIRST_DWORD_MAIN)
        self.assertEqual(v["dmc"][0]["mmio_writes"][5]["value"],"0xc0033200")
        self.assertEqual(v["dmc"][1]["program_dwords"],220)
        self.assertEqual(v["dmc"][0]["payload_end"],v["dmc"][1]["header_offset"])


if __name__=="__main__":
    unittest.main()
