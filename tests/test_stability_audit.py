#!/usr/bin/env python3
"""Portable tests for non-invasive macOS status/driver/crash accounting."""
import importlib.util
from pathlib import Path
import tempfile
import time
import unittest

spec=importlib.util.spec_from_file_location("stability",Path(__file__).resolve().parents[1]/"scripts/sl4_stability_audit_macos.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class StabilityTests(unittest.TestCase):
    def test_kext_version_scoped_to_declared_bundle(self):
        inp="  56  0 0xff 0x31000 as.vit9696.Lilu (1.7.2) <9 7>\n  58 0 org.b00t0x.WhateverXe (0.8.3) xyz"
        self.assertEqual(mod.kext_versions(inp)["as.vit9696.Lilu"],"1.7.2")
        self.assertEqual(mod.kext_versions(inp)["org.b00t0x.WhateverXe"],"0.8.3")

    def test_boot_epoch_only_numeric_sec(self):
        self.assertEqual(mod.boot_epoch("{ sec = 1795394644, usec = 147839 }"),1795394644)
        with self.assertRaisesRegex(RuntimeError,"Cannot parse"):
            mod.boot_epoch("no kernel clock")

    def test_since_boot_is_not_last_24h(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td); x=path/"Kernel-test.gpuRestart"
            x.write_bytes(b"local diagnostic")
            now=time.time()
            old=now-4000
            x.touch()
            import os
            os.utime(x,(old,old))
            d=mod.crash_summary(path,now-3000,now)
            self.assertEqual(d["gpu_reset"]["last_24h"],1)
            self.assertEqual(d["gpu_reset"]["since_current_boot"],0)

    def test_absent_report_folder_yields_zero(self):
        with tempfile.TemporaryDirectory() as td:
            a=mod.crash_summary(Path(td)/"missing",time.time(),time.time())
            self.assertEqual(a["gpu_reset"]["last_24h"],0)


if __name__=="__main__":
    unittest.main()
