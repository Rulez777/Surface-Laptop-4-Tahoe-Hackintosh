#!/usr/bin/env python3
"""Offline tests: video readiness does not modify macOS or EFI."""
import copy
import importlib.util
import os
from pathlib import Path
import unittest

SCRIPT = Path(os.environ.get(
    "SL4_VIDEO_SCRIPT",
    Path(__file__).resolve().parents[1] / "scripts/verify_video_macos.py"))
spec = importlib.util.spec_from_file_location("sl4_video", str(SCRIPT))
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)

BASE = {
    "macOS": "26.7.1",
    "Lilu_loaded": True,
    "WhateverXe_loaded": True,
    "WhateverXe_Graphics_common_pkg": "0.4.4",
    "WhateverXe_Graphics_tahoe_pkg": "0.4.4",
    "CoreMedia_AllowOnePassMetalScaling": False,
    "Metal_2_reported": True,
    "video_hardware_decoders_advertised": {
        "H.264": True, "HEVC": True, "VP9": False, "AV1": False,
    },
    "browser_video_playback": "Not measured here.",
}

class VideoReadinessTests(unittest.TestCase):
    def test_tested_profile_ready(self):
        self.assertTrue(video.ready(BASE))

    def test_no_mutation(self):
        source = copy.deepcopy(BASE)
        video.ready(source)
        self.assertEqual(source, BASE)

    def test_requires_graphics_package(self):
        for key in ("WhateverXe_Graphics_common_pkg", "WhateverXe_Graphics_tahoe_pkg"):
            state = copy.deepcopy(BASE)
            state[key] = "0.4.2"
            self.assertFalse(video.ready(state))

    def test_requires_coremedia_flag(self):
        for value in (True, None):
            state = copy.deepcopy(BASE)
            state["CoreMedia_AllowOnePassMetalScaling"] = value
            self.assertFalse(video.ready(state))

    def test_requires_h264_advertisement(self):
        state = copy.deepcopy(BASE)
        state["video_hardware_decoders_advertised"]["H.264"] = False
        self.assertFalse(video.ready(state))

    def test_vp9_av1_are_not_required(self):
        state = copy.deepcopy(BASE)
        state["video_hardware_decoders_advertised"]["VP9"] = True
        state["video_hardware_decoders_advertised"]["AV1"] = True
        self.assertTrue(video.ready(state))

    def test_unknown_os_rejected(self):
        state = copy.deepcopy(BASE)
        state["macOS"] = "15.8.2"
        self.assertFalse(video.ready(state))

    def test_requires_loaded_driver_and_metal(self):
        for key in ("Lilu_loaded", "WhateverXe_loaded", "Metal_2_reported"):
            state = copy.deepcopy(BASE)
            state[key] = False
            self.assertFalse(video.ready(state))


if __name__ == "__main__":
    unittest.main()
