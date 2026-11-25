"""End-to-end offline contract tests for the Windows-first RCS + Dolby package."""
from pathlib import Path
import hashlib
import plistlib
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import enable_xe_macos as graphics
import install_dolby_macos as audio
import windows_prepare_tahoe as windows
import build_windows_quickstart_kit as builder
import install_sl4_sleepwake_macos as sleepwake

class AllInOneTests(unittest.TestCase):
    def setUp(self):
        self.rcs=ROOT/"packages/SL4-Graphics-Performance-0.1.7-beta.zip"
        self.dolby=ROOT/"packages/SL4-Dolby-APOMac-Profiles-20261123.zip"
        self.input=ROOT/"packages/SL4-TGL-Input-SleepWake-v2-beta.zip"

    def test_runtimes_are_bundled_and_exactly_pinned(self):
        self.assertEqual(windows.sha(self.rcs),windows.RCS_SHA)
        self.assertEqual(windows.sha(self.dolby),windows.DOLBY_SHA)
        self.assertEqual(builder.sha(self.rcs.read_bytes()),builder.RCS_SHA)
        self.assertEqual(builder.sha(self.dolby.read_bytes()),builder.DOLBY_SHA)
        self.assertEqual(windows.sha(self.input),windows.INPUT_SHA)
        self.assertEqual(builder.sha(self.input.read_bytes()),builder.INPUT_SHA)
        input_files=sleepwake.validate_archive(self.input)
        self.assertIn("ACPI/SSDT-SL4-LIDWAKE.aml",input_files)
        self.assertTrue(windows.checked_rcs_addon(self.rcs).is_file())
        self.assertNotIn("scripts/build_sl4_input_pack.py",builder.FILES)
        self.assertIn("scripts/build_sl4_input_sleepwake_pack.py",builder.FILES)
        for patch in ("research/upstream/voodoogpio-sl4-tgl-lp-sleepwake.patch",
                      "research/upstream/bigsurface-sl4-sam-wake.patch",
                      "research/upstream/voodooserial-sl4-tgl-uart.patch",
                      "research/wex-sl4-rcs-clean-production.patch",
                      "docs/UPSTREAM-DRIVER-REPORTS.md"):
            self.assertIn(patch,builder.FILES)
        self.assertTrue(audio.read_zip(self.dolby))
        for name in ("packages/SL4-Graphics-Performance-0.1.7-beta.zip",
                     "packages/SL4-Dolby-APOMac-Profiles-20261123.zip",
                     "packages/SL4-TGL-Input-SleepWake-v2-beta.zip",
                     "scripts/install_sl4_sleepwake_macos.py",
                     "scripts/install_dolby_macos.py",
                     "scripts/find_internal_esp.py",
                     "docs/AUDIO-ALL-IN-ONE.md"):
            self.assertIn(name,builder.FILES)

    def test_graphics_stage_uses_rcs_not_legacy_dmc_binary(self):
        self.assertEqual(graphics.DMC_PATH,"WhateverXe-SL4-RCS-V017-TRIAL.kext")
        self.assertEqual(graphics.RCS_EXE_SHA,
                         "94669172f4c2a52937b587c5eb3fdb73ff030963397aa094e575d9c4b54863d3")
        self.assertNotIn("-wex-sl4-rcs-singleport",graphics.STARTUP_ARGS)
        self.assertNotIn("-wex-sl4-rcs-nativequeue-trial",graphics.STARTUP_ARGS)
        self.assertIn("-wex-sl4-heap-depth-trial",graphics.STARTUP_ARGS)
        with tempfile.TemporaryDirectory() as tmp:
            t=Path(tmp)
            s0ix=t/"mock-s0ix.zip"
            with zipfile.ZipFile(s0ix,"w") as z:
                z.writestr(graphics.BETA+"payload/S0ixStandby.kext/Contents/MacOS/S0ixStandby",b"fake-runtime")
                z.writestr(graphics.BETA+"payload/SSDT-DEEPIDLE.aml",b"fake-SSDT")
            with mock.patch.object(graphics,"RELEASE_SHA",graphics.sha_file(s0ix)):
                self.assertTrue(graphics.check_release(s0ix,self.rcs))
            efi=t/"EFI"
            (efi/"OC/Kexts").mkdir(parents=True)
            dest=graphics.copy_rcs_kext(self.rcs,efi)
            self.assertEqual(graphics.sha_file(dest/"Contents/MacOS/WhateverXe"),graphics.RCS_EXE_SHA)
            d=plistlib.loads((dest/"Contents/Info.plist").read_bytes())
            self.assertEqual(d["CFBundleIdentifier"],"org.b00t0x.WhateverXe")
            with self.assertRaisesRegex(RuntimeError,"already staged"):
                graphics.copy_rcs_kext(self.rcs,efi)

    def test_clear_speech_has_user_approved_quiet_preamp_and_stereo_convolution(self):
        self.assertEqual(audio.PROFILE,"Surface Laptop 4 - Clear Speech")
        self.assertTrue(audio.UID.startswith("AppleHDAEngineOutput:"))
        with zipfile.ZipFile(self.dolby) as z:
            key=audio.ZIP_PREFIX+audio.PROFILE+"/config.txt"
            b=z.read(key)
            self.assertIn(b"Preamp: -3.0 dB",b)
            self.assertIn(b"Filter: ON PK Fc 2500 Hz Gain 1.88 dB Q 0.70",b)
            transformed=audio.profile_config(b)
            self.assertTrue(transformed.startswith(("Device: "+audio.UID).encode()))
            self.assertEqual(transformed.count(b"Device:"),1)
            self.assertIn(b"Convolution: speaker-correction.wav",transformed)
            wav=z.read(audio.ZIP_PREFIX+audio.PROFILE+"/speaker-correction.wav")
            self.assertEqual(len(wav),32826)  # Stereo 4096-tap 32-bit WAV with extended header
            self.assertEqual(wav[:4],b"RIFF")
        self.assertEqual(audio.APOMAC_DMG_SHA,windows.APOMAC_SHA)

    def test_no_legacy_separate_patch_menu_and_gfx_has_rcs(self):
        s=(ROOT/"scripts/QuickStart-Mac.command").read_text()
        self.assertIn('install_from_usb',s)
        self.assertIn('"$base/enable_xe_macos.py" apply',s)
        self.assertIn('--rcs "$base/$RCS"',s)
        self.assertIn('install_audio',s)
        self.assertIn('"$base/install_dolby_macos.py" apply',s)
        self.assertNotIn("4) Install optional RCS",s)
        self.assertIn("System Audio Recording",s)
        self.assertIn("repair_existing",s)
        installer=(ROOT/"scripts/install_dolby_macos.py").read_text()
        self.assertIn('com.sl4.apomac.autostart',installer)
        self.assertIn('kext', (ROOT/"docs/AUDIO-ALL-IN-ONE.md").read_text().lower())

    def test_coremedia_and_working_sleep_are_preserved_without_power_override(self):
        script=(ROOT/"scripts/QuickStart-Mac.command").read_text()
        self.assertIn("verify_coremedia_h264",script)
        self.assertIn("AllowOnePassMetalScaling:Enabled",script)
        self.assertIn('[[ "$flag" == "false" ]]',script)
        self.assertLess(script.index("verify_coremedia_h264\n    mkdir -p"),
                        script.index('sudo python3 "$base/enable_xe_macos.py" apply'))
        self.assertIn("report_sleep_policy_unchanged",script)
        self.assertIn("/usr/bin/pmset -g custom",script)
        self.assertNotIn("safe_sleep_policy",script)
        self.assertNotIn("/usr/bin/pmset -a",script)
        self.assertNotIn("sleep 0 displaysleep 0",script)
        # Both initial installation and repair must leave the power policy alone.
        self.assertEqual(script.count("    report_sleep_policy_unchanged\n"),1)
        self.assertIn("repair_existing() {",script)
        boot=(ROOT/"scripts/enable_xe_macos.py").read_text()
        self.assertIn("S0ixStandby.kext",boot)
        self.assertIn("SSDT-DEEPIDLE.aml",boot)
        for flag in ("-wex-tgl-edp-keep","-wex-tgl-edp-softsleep",
                     "-wex-sl4-tgl-dmc","-wex-sl4-heap-depth-trial"):
            self.assertIn(flag,graphics.STARTUP_ARGS)
        self.assertNotIn("-wex-edp-wake-trace",graphics.STARTUP_ARGS)
        self.assertNotIn("-wex-sl4-rcs-singleport",graphics.STARTUP_ARGS)
        self.assertNotIn("-wex-sl4-rcs-nativequeue-trial",graphics.STARTUP_ARGS)
        edp=(ROOT/"scripts/install_edp_keep_macos.py").read_text()
        self.assertNotIn("-wex-edp-wake-trace",edp)

    def test_no_power_setting_writes_anywhere_in_core_install_path(self):
        # These run automatically from the CMD-created USB. A new developer
        # must not accidentally reintroduce forced idle-sleep deactivation.
        for name in ("QuickStart-Mac.command","enable_xe_macos.py",
                     "install_dolby_macos.py","windows_prepare_tahoe.py",
                     "QuickStart-Windows.ps1"):
            data=(ROOT/"scripts"/name).read_text().lower()
            self.assertNotIn("sudo /usr/bin/pmset -a",data,name)
            self.assertNotIn("pmset -a sleep",data,name)
            self.assertNotIn("pmset -a displaysleep",data,name)
            self.assertNotIn("sleep 0 displaysleep 0",data,name)

    def test_windows_stage_contains_every_offline_component_and_manifest(self):
        s=(ROOT/"scripts/windows_prepare_tahoe.py").read_text()
        self.assertEqual(s.count('shutil.copy2(rcs,'),2)
        self.assertEqual(s.count('shutil.copy2(apomac,'),2)
        self.assertEqual(s.count('shutil.copy2(dolby,'),2)
        self.assertIn('main_graphics_path',s)
        self.assertIn('speaker_correction_sha256',s)
        self.assertIn('APOMAC_SHA',s)
        self.assertEqual(windows.RCS_SHA,graphics.RCS_RELEASE_SHA)
        self.assertEqual(windows.DOLBY_SHA,audio.AUDIO_SHA)
        self.assertIn('SL4DATA\\SL4-Dolby-APOMac-Profiles-20261123.zip',
                      (ROOT/"scripts/QuickStart-Windows.ps1").read_text())

    def test_windows_repair_stages_every_component_without_a_preinstalled_mac(self):
        from types import SimpleNamespace
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            target=root/"repair"
            cache=root/"cache"
            def fake_fetch(url,dest,expected_sha):
                dest.parent.mkdir(parents=True,exist_ok=True)
                if url==windows.OC_URL:
                    with zipfile.ZipFile(dest,"w") as archive:
                        archive.writestr("Utilities/ocvalidate/ocvalidate",b"test-open-core-validator")
                elif url==windows.RELEASE_URL:
                    with zipfile.ZipFile(dest,"w") as archive:
                        archive.writestr("SL4-S0ix-DMC-0.2.0-beta/install.py",b"placeholder")
                elif url in (windows.GRAPHICS_URL,windows.APOMAC_URL):
                    dest.write_bytes(b"dummy-download-fixture")
                else:
                    raise AssertionError("Unexpected third-party URL: "+url)
                return dest
            with mock.patch.object(windows,"fetch",side_effect=fake_fetch):
                windows.repair_only(SimpleNamespace(out=target,cache=cache,fixture_mode=True))
            data=target/"SL4DATA"
            for filename in (windows.RCS_FILENAME,windows.DOLBY_FILENAME,
                             windows.APOMAC_FILENAME,"enable_xe_macos.py",
                             "find_internal_esp.py","install_dolby_macos.py",
                             "QuickStart-Mac.command","ocvalidate"):
                self.assertTrue((data/filename).is_file(),filename)
            self.assertEqual((data/windows.RCS_FILENAME).read_bytes(),self.rcs.read_bytes())
            self.assertEqual((data/windows.DOLBY_FILENAME).read_bytes(),self.dolby.read_bytes())
            manifest=json.loads((target/"manifest.json").read_text())
            self.assertEqual(manifest["mode"],"existing_tahoe_driver_repair")
            self.assertFalse(manifest["windows_disk_modified"])
            self.assertEqual(manifest["downloads"]["speaker_correction"],audio.AUDIO_SHA)

    def test_reject_unexpected_installer_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            corrupt=Path(tmp)/audio.AUDIO_ARCHIVE
            corrupt.write_bytes(self.dolby.read_bytes()[:-20]+b"bad!")
            with self.assertRaises(RuntimeError):
                audio.read_zip(corrupt)
            with self.assertRaises(RuntimeError):
                windows.checked_rcs_addon(corrupt)

if __name__=="__main__":
    unittest.main()
