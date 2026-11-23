#!/usr/bin/env python3
"""Tests for comparing research kext Mach-O bytes without treating UUID as code."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "macho_cmp", ROOT / "scripts/compare_macho_binary_uuids.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fake_macho(uuid: bytes, payload=b"\x90\xc3", *, cpu=0x01000007,
               cmd=0x1b, cmdsize=24, ncmds=1, commandsize=24):
    if len(uuid) != 16:
        raise ValueError("UUID must be sixteen bytes")
    return (struct.pack("<IiiIIIII", 0xfeedfacf, cpu, 3, 0xb,
                        ncmds, commandsize, 0, 0)
            + struct.pack("<II", cmd, cmdsize) + uuid + payload)


class MachOComparisonTests(unittest.TestCase):
    def test_only_linker_uuid_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/"a", Path(tmp)/"b"
            a.write_bytes(fake_macho(b"\x11"*16))
            b.write_bytes(fake_macho(b"\x22"*16))
            r = m.compare(a, b)
            self.assertFalse(r["full_binary_equal"])
            self.assertFalse(r["uuids_equal"])
            self.assertTrue(r["all_non_uuid_bytes_equal"])
            self.assertTrue(r["byte_identical_except_uuid"])
            self.assertFalse("Path" in str(r))
            self.assertTrue(r["read_only"])

    def test_actual_executable_byte_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/"a", Path(tmp)/"b"
            a.write_bytes(fake_macho(b"\x11"*16, payload=b"\x90\xc3"))
            b.write_bytes(fake_macho(b"\x22"*16, payload=b"\xcc\xc3"))
            r = m.compare(a, b)
            self.assertFalse(r["all_non_uuid_bytes_equal"])
            self.assertFalse(r["byte_identical_except_uuid"])

    def test_identical_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/"a", Path(tmp)/"b"
            a.write_bytes(fake_macho(b"\x01"*16))
            b.write_bytes(a.read_bytes())
            r = m.compare(a, b)
            self.assertTrue(r["full_binary_equal"])
            self.assertTrue(r["uuids_equal"])
            self.assertTrue(r["all_non_uuid_bytes_equal"])
            self.assertFalse(r["byte_identical_except_uuid"])

    def test_wrong_cpu_arch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"x"
            p.write_bytes(fake_macho(b"\0"*16, cpu=7))
            with self.assertRaisesRegex(ValueError, "x86_64"):
                m.inspect(p)

    def test_missing_uuid_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"x"
            p.write_bytes(fake_macho(b"\0"*16, cmd=1))
            with self.assertRaisesRegex(ValueError, "LC_UUID"):
                m.inspect(p)

    def test_wrong_uuid_load_command_length_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"x"
            p.write_bytes(fake_macho(b"\0"*16, cmdsize=16))
            with self.assertRaisesRegex(ValueError, "LC_UUID length"):
                m.inspect(p)

    def test_invalid_load_commands_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"x"
            p.write_bytes(fake_macho(b"\0"*16, commandsize=48))
            with self.assertRaisesRegex(ValueError, "commands"):
                m.inspect(p)
            p.write_bytes(fake_macho(b"\0"*16, ncmds=201))
            with self.assertRaisesRegex(ValueError, "commands"):
                m.inspect(p)

    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"x"
            p.write_bytes(fake_macho(b"\0"*16))
            link = Path(tmp)/"link"
            link.symlink_to(p)
            with self.assertRaisesRegex(ValueError, "regular"):
                m.inspect(link)

    def test_no_binary_writes(self):
        text = (ROOT / "scripts/compare_macho_binary_uuids.py").read_text()
        for name in ("subprocess", "sudo ", "diskutil", "write_bytes",
                     "mount", "kextload", "csrutil", "open(", "os.replace"):
            self.assertNotIn(name, text)

    def test_scripts_in_installers(self):
        for path in ("scripts/build_windows_quickstart_kit.py",
                     "scripts/build_offline_kit.py",
                     "scripts/windows_prepare_tahoe.py"):
            self.assertIn("compare_macho_binary_uuids.py",
                          (ROOT / path).read_text())


if __name__ == "__main__":
    unittest.main()
