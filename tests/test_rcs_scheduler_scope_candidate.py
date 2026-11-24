#!/usr/bin/env python3
"""Source-only RCS scheduler scope regression checks; not a real GPU simulator.

Verifies the proposed v0.1.3 guard, its reproducible patch chain and a
bounded behavioral reference model. It does not claim the new kernel kext
compiles, boots or resolves a graphics reset on hardware.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCHES = (
    "wex-sl4-rcs-singleport.patch",
    "wex-sl4-rcs-hook-telemetry-v0.1.1.patch",
    "wex-sl4-rcs-queue-reasons-v0.1.2.patch",
    "wex-sl4-rcs-scheduler-scope-v0.1.3.patch",
)
HEADER = Path("WhateverXe/kern_sl4_rcs_singleport.hpp")


class ScopeModel:
    """Minimal logical model of the proposed guard, NOT the donor ABI."""
    def __init__(self):
        self.target = None
        self.generic_seen = 0
        self.rcs_scoped = 0
        self.other_or_unknown = 0

    def remember_verified_rcs(self, scheduler):
        if scheduler is not None:
            self.target = scheduler

    def update_options(self, scheduler, native_flags, live=True):
        # Base class updateOptions ALWAYS runs first.
        result = native_flags
        if not live:
            return result
        self.generic_seen += 1
        if scheduler is not None and self.target is not None and scheduler == self.target:
            result &= ~4
            self.rcs_scoped += 1
        else:
            self.other_or_unknown += 1
        return result


def reconstruct(patches):
    with tempfile.TemporaryDirectory(prefix="sl4-rcs-scope-") as temp:
        root = Path(temp)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True,
                       capture_output=True)
        for n in patches:
            p = ROOT / "research" / n
            for args in (["git", "apply", "--check"],
                         ["git", "apply"]):
                subprocess.run(args + ["--include=" + HEADER.as_posix(), str(p)],
                               cwd=root, check=True, capture_output=True)
        return (root / HEADER).read_text(encoding="utf-8")


class RcsSchedulerScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = reconstruct(PATCHES[:-1])
        cls.after = reconstruct(PATCHES)

    def test_original_generic_scheduler_mutation_is_proven_from_source(self):
        self.assertIn(
            'if(live() && isKernelPtr(that))\n        static_cast<uint8_t *>(that)[0x0c] &= ~0x04u;',
            self.before)
        self.assertNotIn("knownRcsScheduler", self.before)

    def test_new_generic_hook_only_mutates_identity_matched_scheduler(self):
        hook = self.after.split("static void wrapUpdateOptions(void *that) {", 1)[1].split(
            "static void wrapAllowPreemption(void *that)", 1)[0]
        self.assertIn("FunctionCast(wrapUpdateOptions,orgUpdateOptions)(that);", hook)
        self.assertLess(
            hook.index("FunctionCast(wrapUpdateOptions,orgUpdateOptions)(that);"),
            hook.index("target==reinterpret_cast<uintptr_t>(that)"))
        self.assertIn("if(!enabled || !isKernelPtr(that)) return;", hook)
        self.assertIn("if(target && target==reinterpret_cast<uintptr_t>(that)) {", hook)
        self.assertEqual(hook.count("static_cast<uint8_t *>(that)[0x0c]&=~0x04u;"), 1)
        self.assertIn("unrelatedOrUnknownUpdateOptions", hook)
        self.assertNotIn("if(live() && isKernelPtr(that))\n        static_cast", hook)

    def test_target_capture_is_limited_to_rcs_typed_callbacks(self):
        self.assertEqual(self.after.count("rememberRcsScheduler(scheduler);"), 2)
        p = self.after.index("static void disablePreempt(void *that)")
        q = self.after.index("static void wrapUpdateOptions(void *that)")
        text = self.after[p:q]
        self.assertIn("if(!isKernelPtr(c28) || c28[0]!=0) return; // RCS only", text)
        self.assertIn("rememberRcsScheduler(scheduler);", text)
        self.assertIn("static volatile uintptr_t knownRcsScheduler = 0;", self.after)

    def test_pointers_not_exposed_in_serialized_telemetry(self):
        s = self.after.split("static bool telemetrySerialize",1)[1].split("static bool live()",1)[0]
        self.assertNotIn("knownRcsScheduler", s)
        self.assertIn("uint32_t values[15]", s)
        self.assertIn("__atomic_load_n(&observedUpdateOptions", s)
        self.assertIn("__atomic_load_n(&scopedRcsUpdateOptions", s)
        self.assertIn("__atomic_load_n(&unrelatedOrUnknownUpdateOptions", s)
        self.assertIn("        3,", s)
        self.assertNotIn("reinterpret_cast<uintptr_t>", s)

    def test_reconstructed_patch_does_not_change_dequeue_conditions(self):
        for start, end in (
            ("static void wrapDequeue", "static uint64_t wrapEvalWait"),
            ("static uint64_t wrapEvalWait", "// Exact signatures")):
            self.assertEqual(self.before.split(start,1)[1].split(end,1)[0],
                             self.after.split(start,1)[1].split(end,1)[0])

    def test_unknown_scheduler_retains_native_options(self):
        model=ScopeModel()
        self.assertEqual(model.update_options(0x111, 0x7), 0x7)
        self.assertEqual(model.rcs_scoped, 0)
        self.assertEqual(model.other_or_unknown, 1)

    def test_only_identified_rcs_scheduler_is_changed(self):
        model=ScopeModel()
        model.remember_verified_rcs(0x12345678)
        self.assertEqual(model.update_options(0x87654321, 0x7), 0x7)
        self.assertEqual(model.update_options(0x12345678, 0x7), 0x3)
        self.assertEqual(model.generic_seen, 2)
        self.assertEqual(model.rcs_scoped, 1)
        self.assertEqual(model.other_or_unknown, 1)

    @unittest.expectedFailure
    def test_stale_rcs_scheduler_pointer_reuse_must_not_affect_media(self):
        """Known unresolved safety gate, deliberately exposed by the model.

        If the render scheduler at address A is destroyed at sleep/reset
        and later a media scheduler reuses address A, mere pointer equality
        cannot safely distinguish the object. Until lifetime handling is
        proven, this kernel patch is not approved for installation.
        """
        model = ScopeModel()
        model.remember_verified_rcs(0x1000)
        # Simulate RCS teardown followed by media object reuse of address.
        self.assertEqual(model.update_options(0x1000, 0x7), 0x7)

    def test_inactive_patch_does_not_change_scheduler_flags(self):
        model=ScopeModel()
        model.remember_verified_rcs(7)
        self.assertEqual(model.update_options(7, 0x7, live=False), 0x7)
        self.assertEqual(model.generic_seen, 0)

    def test_experimental_kernel_binary_not_in_installers(self):
        source=(ROOT/"scripts/build_windows_quickstart_kit.py").read_text(encoding="utf-8")
        offline=(ROOT/"scripts/build_offline_kit.py").read_text(encoding="utf-8")
        for s in (source,offline):
            self.assertNotIn("wex-sl4-rcs-scheduler-scope-v0.1.3.patch", s)

    def test_no_kernel_changes_or_unsafe_hardware_actions(self):
        patch=(ROOT/"research"/PATCHES[-1]).read_text(encoding="utf-8")
        self.assertNotIn("kern_xe.cpp", patch)
        self.assertNotIn("boot-args", patch)
        self.assertNotIn("csrutil", patch)
        self.assertNotIn("pmset", patch)
        self.assertNotIn("Contents/MacOS/WhateverXe", patch)


if __name__ == "__main__":
    unittest.main()
