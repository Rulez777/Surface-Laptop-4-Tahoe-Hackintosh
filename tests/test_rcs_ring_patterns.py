#!/usr/bin/env python3
"""CPU-only parser tests, including evidence bounding/privacy."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sl4_ring_audit", ROOT/"scripts/audit_rcs_ring_patterns_macos.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

REPORT = """Event: GPU Reset
Last instruction header executed: 0x7a000204
Private user name: REJECT-SECRET-NAME
Dumping RCS ring buffer contents:
-----------------------------------
Offset       Value
------------------------
0x000017e8 : 0x00000000
0x000017ec : 0x7a000204
0x000017f0 : 0x50107021
0x000017f4 : 0x40000000
0x000017f8 : 0x02800101
0x000017fc : 0x7a000004
0x00001800 : 0x02800100

Dumping BCS ring buffer contents:
Offset       Value
------------------------
0x00000010 : 0x7a000204
0x00000014 : 0xdeadbeef
"""


class RCSRingPatternTests(unittest.TestCase):
    def test_opcode_counts_are_rcs_only(self):
        r = m.summarize(REPORT)
        self.assertEqual(r["rcs_dword_count"], 7)
        self.assertEqual(r["known_opcodes"]["pipe_control_0x7a000204"], 1)
        self.assertEqual(r["known_opcodes"]["mi_arbitration_disable"], 1)
        self.assertEqual(r["known_opcodes"]["mi_arbitration_enable"], 1)
        self.assertEqual(r["pipe_control_0x7a000204_flags"], {"0x50107021": 1})
        self.assertTrue(r["arbitration_disable_enable_counts_equal"])
        self.assertEqual(r["reported_ipehr"], "0x7a000204")

    def test_not_a_gpu_reset_ignored(self):
        self.assertIsNone(m.summarize(
            REPORT.replace("Event: GPU Reset", "Event: Shutdown Stall")))

    def test_missing_ring_keeps_report_but_no_false_data(self):
        report = REPORT.replace("Dumping RCS ring buffer contents:",
                                "Other ring:")
        result = m.summarize(report)
        self.assertFalse(result["rcs_dump_available"])
        self.assertEqual(result["rcs_dword_count"], 0)

    def test_do_not_publish_gpu_memory_addresses_or_secrets(self):
        result = str(m.summarize(REPORT))
        self.assertNotIn("40000000", result)
        self.assertNotIn("REJECT-SECRET-NAME", result)
        self.assertNotIn("deadbeef", result)
        self.assertNotIn("/Users/", result)

    def test_reject_unbounded_rcs_words(self):
        line = "0x00000001 : 0x7a000204\n"
        raw = REPORT[:REPORT.index("Dumping RCS ring buffer contents:")]
        raw += "Dumping RCS ring buffer contents:\n" + line*2049
        with self.assertRaisesRegex(ValueError, "Excessive RCS"):
            m.summarize(raw)

    def test_sorted_local_filename_and_no_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p/"Kernel_2026-11-23-233209_Serialized.gpuRestart").write_text(REPORT)
            (p/"Kernel_2026-11-23-171359_Serialized.gpuRestart").write_text(REPORT)
            (p/"Kernel_2026-11-23-171345_Serialized.gpuRestart").write_text(
                REPORT.replace("Event: GPU Reset", "Event: Sleep Wake"))
            result = m.compare(p)
            self.assertEqual(result["gpu_reset_reports_analysed"], 2)
            self.assertFalse(result["stability_fix_proven"])
            self.assertTrue(result["read_only"])
            self.assertFalse(result["efi_modified"])
            self.assertFalse(result["driver_modified"])
            self.assertEqual(result["records"][0]["event_local"],
                             "2026-11-23T17:13:59")

    def test_reject_symlink_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root/"src"
            folder.mkdir()
            alias = root/"alias"
            alias.symlink_to(folder)
            with self.assertRaisesRegex(ValueError, "ordinary"):
                m.compare(alias)

    def test_kit_packaging_and_no_kernel_changes(self):
        for name in ("scripts/build_offline_kit.py",
                     "scripts/build_windows_quickstart_kit.py",
                     "scripts/windows_prepare_tahoe.py"):
            self.assertIn("audit_rcs_ring_patterns_macos.py",
                          (ROOT / name).read_text(encoding="utf-8"))
        code = (ROOT / "scripts/audit_rcs_ring_patterns_macos.py").read_text()
        for dangerous in ("sudo ", "diskutil ", "mount ", "kextload",
                          "csrutil ", "nvram -", "os.replace", "write_bytes("):
            self.assertNotIn(dangerous, code)


if __name__ == "__main__":
    unittest.main()
