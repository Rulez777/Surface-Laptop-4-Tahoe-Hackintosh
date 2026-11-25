"""Safety constraints for the SL4 lid GPE research and production profile."""
import importlib.util
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]


class LidWakeResearchTests(unittest.TestCase):
    def test_research_only_dsl_is_not_compiled_and_uses_exact_surface_lid_gpe(self):
        src=(ROOT/"research/SSDT-SL4-LIDWAKE.dsl").read_text(encoding="utf-8")
        self.assertIn("RESEARCH ONLY",src)
        self.assertRegex(src,r"Scope\s*\(\\_SB\.LID0\)")
        self.assertRegex(src,r"Method\s*\(_PRW,\s*0,")
        self.assertRegex(src,r"Package\s*\(0x02\)\s*\{\s*0x4B,\s*0x03\s*\}")
        self.assertIn('If (_OSI ("Darwin"))',src)
        self.assertEqual(src.count("Method (_PRW"),1)

    def test_candidate_is_not_in_offline_installer_or_packages(self):
        spec=importlib.util.spec_from_file_location("sl4_research_offline",ROOT/"scripts/build_offline_kit.py")
        tool=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        candidates=tool.files()
        self.assertNotIn("research/SSDT-SL4-LIDWAKE.dsl",candidates)
        self.assertTrue(all(not path.endswith(".dsl") for path in candidates))
        self.assertIn("docs/LINUX-SURFACE-SLEEP-PORT.md",candidates)

    def test_production_gpio_patch_saves_only_supported_pins_and_f11(self):
        patch=(ROOT/"experiments/sl4-input/patches/sl4-sleepwake-production.patch").read_text()
        self.assertIn("if (!shouldSavePin && desc->number != kSurfaceLidWakePin)",patch)
        self.assertIn("if (!intel_pinctrl_should_save(desc->number) && desc->number != kSurfaceLidWakePin)",patch)
        self.assertIn("constexpr unsigned int kSurfaceLidWakePin = 206;",patch)
        self.assertNotIn("if (desc->number == 206)\\n+        if (!shouldSavePin)",patch)
        additions="\\n".join(line[1:] for line in patch.splitlines()
                              if line.startswith("+") and not line.startswith("+++"))
        for token in ("SL4LidGPIOProbe","SL4LidGPEArmStatus","SL4SAMWakeArmed",
                      "GPIO wake up event happened!","SL4SAMWakeGPIO",
                      "Armed SAM wake","Disarmed SAM wake"):
            self.assertNotIn(token,additions)

    def test_sleep_still_marked_unverified_in_public_hardware_profile(self):
        import json
        data=json.loads((ROOT/"data/sl4_profiles.json").read_text(encoding="utf-8"))
        self.assertFalse(data["profiles"][0]["full_system_sleep_verified"])
        self.assertFalse(data["profiles"][0]["certified_for_automatic_esp_installation"])
        self.assertNotIn("research/SSDT-SL4-LIDWAKE.dsl",str(data))


if __name__=="__main__":
    unittest.main()
