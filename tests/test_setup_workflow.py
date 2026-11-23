#!/usr/bin/env python3
"""Portable tests for private EFI staging and hardware allowlisting."""
import importlib.util
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


setup=load("sl4_setup","scripts/sl4_setup.py")
inventory=load("sl4_inventory","scripts/sl4_inventory.py")


def make_private_efi(root,include_s0ix=False):
    efi=root/"private"/"EFI"
    oc=efi/"OC"
    for folder in ("Kexts/Lilu.kext/Contents/MacOS",
                   "Kexts/WhateverXe.kext/Contents/MacOS","Drivers","ACPI"):
        (oc/folder).mkdir(parents=True,exist_ok=True)
    (efi/"BOOT").mkdir()
    (efi/"Microsoft/Boot").mkdir(parents=True)
    (efi/"BOOT/BOOTx64.efi").write_bytes(b"known-boot")
    (efi/"Microsoft/Boot/bootmgfw.efi").write_bytes(b"MS boot manager")
    (efi/"Microsoft/Boot/BCD").write_bytes(b"LOCKED BCD SHOULD NOT BE COPIED")
    (oc/"OpenCore.efi").write_bytes(b"OC")
    (oc/"Drivers/OpenRuntime.efi").write_bytes(b"runtime")
    (oc/"ACPI/SSDT-RTC0.aml").write_bytes(b"acpi")
    for name in ("Lilu","WhateverXe"):
        (oc/("Kexts/"+name+".kext/Contents/Info.plist")).write_bytes(
            plistlib.dumps({"CFBundleVersion":"1.0"}))
        (oc/("Kexts/"+name+".kext/Contents/MacOS/"+name)).write_bytes(b"kext")
    kernel=[{"Enabled":True,"BundlePath":n+".kext","PlistPath":"Contents/Info.plist",
             "ExecutablePath":"Contents/MacOS/"+n} for n in ("Lilu","WhateverXe")]
    if include_s0ix:
        kernel.append({"Enabled":True,"BundlePath":"S0ixStandby.kext",
                       "PlistPath":"Contents/Info.plist","ExecutablePath":""})
    cfg={"Kernel":{"Add":kernel},"UEFI":{"Drivers":[{"Enabled":True,"Path":"OpenRuntime.efi"}]},
         "ACPI":{"Add":[{"Enabled":True,"Path":"SSDT-RTC0.aml"}]},
         "PlatformInfo":{"Generic":{"SystemSerialNumber":"PRIVATE-ABCDEF","MLB":"PRIVATE-MLB",
                                    "ROM":b"SECRET","SystemUUID":"DO-NOT-PUBLISH"}}}
    (oc/"config.plist").write_bytes(plistlib.dumps(cfg))
    return efi


class SafeSetupTests(unittest.TestCase):
    def test_pins_verified(self):
        p,meta=setup.artifact_check()
        self.assertEqual(setup.digest(p),meta["sha256"])

    def test_private_inspection_never_exposes_smbios(self):
        with tempfile.TemporaryDirectory() as d:
            efi=make_private_efi(Path(d))
            x=setup.inspect(efi)
            s=json.dumps(x)
            self.assertEqual(x["structure"],"pass")
            self.assertNotIn("PRIVATE",s)
            self.assertNotIn("SECRET",s)
            self.assertNotIn("boot-args",s)

    def test_private_backup_preserves_and_verifies(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); efi=make_private_efi(root)
            out=root/"secure-backup"
            original=setup.list_hashes(efi/"OC")
            result=setup.backup(efi,out,"backup","BACKUP-PRIVATE-EFI")
            self.assertFalse(result["efi_system_partition_modified"])
            self.assertEqual(setup.list_hashes(efi/"OC"),original)
            self.assertEqual(setup.list_hashes(out/"EFI/OC"),original)
            self.assertFalse((out/"EFI/Microsoft/Boot/BCD").exists())
            self.assertEqual(setup.verify_backup(out)["status"],"backup_integrity_pass")
            (out/"EFI/OC/OpenCore.efi").write_bytes(b"tampered")
            with self.assertRaisesRegex(RuntimeError,"missing/modified"):
                setup.verify_backup(out)

    def test_stage_never_overwrites_or_changes_source(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); efi=make_private_efi(root)
            out=root/"stage"
            with self.assertRaisesRegex(RuntimeError,"--ack"):
                setup.backup(efi,out,"prepare","")
            self.assertFalse(out.exists())
            x=setup.backup(efi,out,"prepare","PREPARE-OFFLINE-ONLY")
            self.assertIn("created_private_local_prepare",x["status"])
            self.assertEqual(setup.verify_backup(out)["status"],"backup_integrity_pass")
            with self.assertRaisesRegex(RuntimeError,"already exists"):
                setup.backup(efi,out,"prepare","PREPARE-OFFLINE-ONLY")

    def test_offline_restore_is_hash_identical_and_never_writes_source(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); efi=make_private_efi(root)
            backup=root/"private-backup"; restore=root/"restored"
            setup.backup(efi,backup,"backup","BACKUP-PRIVATE-EFI")
            with self.assertRaisesRegex(RuntimeError,"RESTORE-OFFLINE-COPY"):
                setup.restore_offline(backup,restore,"")
            result=setup.restore_offline(backup,restore,"RESTORE-OFFLINE-COPY")
            self.assertFalse(result["live_efi_modified"])
            self.assertEqual(setup.list_hashes(efi/"OC"),setup.list_hashes(restore/"EFI/OC"))
            self.assertEqual(setup.verify_backup(restore)["status"],"backup_integrity_pass")
            with self.assertRaisesRegex(RuntimeError,"already exists"):
                setup.restore_offline(backup,restore,"RESTORE-OFFLINE-COPY")

    def test_detects_unproven_deep_idle(self):
        with tempfile.TemporaryDirectory() as d:
            efi=make_private_efi(Path(d),include_s0ix=True)
            result=setup.inspect(efi)
            self.assertEqual(result["structure"],"review_required")
            self.assertTrue(any("S0ixStandby" in item for item in result["warnings"]))

    def test_source_and_output_restrictions(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); efi=make_private_efi(root)
            with self.assertRaisesRegex(RuntimeError,"not an ESP"):
                setup.source_efi(efi.parent)
            with self.assertRaisesRegex(RuntimeError,"inside/above"):
                setup.output_path(efi,efi/"backup")

    def test_redaction_filters_unknown_identifiers(self):
        result=inventory.normalize_inventory({"platform":"darwin","cpu":"Intel",
              "serial":"C02PRIVATE","username":"secret","gpu_pci_ids":["8086:9a49"],
              "disk_layout":{"esp_present":True,"secret":True}})
        self.assertNotIn("serial",result)
        self.assertNotIn("username",result)
        self.assertNotIn("secret",json.dumps(result))

    def test_pci_id_extraction(self):
        self.assertEqual(inventory.pci_ids("PCI\\VEN_8086&DEV_9A49"),["8086:9a49"])

    def test_profile_match_does_not_authorize_esp_write(self):
        inv=inventory.normalize_inventory({"platform":"darwin",
            "manufacturer":"Microsoft Corporation","model":"Surface Laptop 4 Intel",
            "cpu":"Intel Core i7-1185G7","gpu_pci_ids":["8086:9a49"],
            "acpi_ids":["MSHW0250","MSHW0084"],
            "storage_models":["SAMSUNG MZ9LQ256HBJQ-00000"]})
        x=inventory.assess(inv,inventory.load_profiles())
        self.assertEqual(x["status"],"hardware_match_requires_manual_review")
        self.assertFalse(x["automatic_install_allowed"])
        self.assertFalse(x["full_system_sleep_verified"])

    def test_unsupported_machine_fail_closed(self):
        inv=inventory.normalize_inventory({"platform":"win32","manufacturer":"Dell",
            "model":"Other","cpu":"Intel i7","gpu_pci_ids":["8086:9a49"]})
        self.assertEqual(inventory.assess(inv,inventory.load_profiles())["status"],"unsupported_or_insufficient_evidence")


if __name__=="__main__":
    unittest.main()
