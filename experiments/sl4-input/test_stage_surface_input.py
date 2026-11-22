"""Safe synthetic tests for the Surface Laptop 4 Intel Windows EFI stager.

Pure temporary fixtures; never accesses real EFI/registry/hardware.
"""
from __future__ import annotations
import argparse
import importlib.util
import os
import pathlib
import plistlib
import tempfile
import unittest
import zipfile

SRC = pathlib.Path(__file__).with_name('stage-surface-input.py')
spec = importlib.util.spec_from_file_location('sl4_input', SRC)
sut = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sut)


class StageTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory(prefix='sl4-input-tests-')
        root = pathlib.Path(self.root.name)
        self.efi = root / 'EFI'
        self.oc = self.efi / 'OC'
        (self.efi / 'Microsoft/Boot').mkdir(parents=True)
        (self.efi / 'Microsoft/Boot/bootmgfw.efi').write_bytes(b'WINDOWS EFI PRESERVED')
        (self.oc / 'Kexts').mkdir(parents=True)
        (self.oc / 'OpenCore.efi').write_bytes(b'OPENCORE PRESERVED')
        self.config = self.oc / 'config.plist'
        bootargs = 'npci=0x2000 -allow3d -disablegfxfirmware -igfxdvmt'
        existing = [{'Arch': 'Any', 'BundlePath': x, 'Comment': '', 'Enabled': True,
                     'ExecutablePath': 'Contents/MacOS/X', 'MaxKernel': '', 'MinKernel': '',
                     'PlistPath': 'Contents/Info.plist'}
                    for x in ('Lilu.kext', 'VirtualSMC.kext', 'SMCBatteryManager.kext',
                              'VoodooI2C.kext/Contents/PlugIns/VoodooInput.kext')]
        cfg = {
            'ACPI': {'Add': []}, 'DeviceProperties': {'Add': {sut.IGPU: {
                'framebuffer-patch-enable': bytes.fromhex('01000000'),
                'framebuffer-stolenmem': bytes.fromhex('0000C003')}}},
            'Kernel': {'Add': existing}, 'NVRAM': {'Add': {sut.SYSTEM_GUID: {'boot-args': bootargs}}}}
        self.config.write_bytes(plistlib.dumps(cfg))
        self.original_bytes = self.config.read_bytes()
        self.artifact = root / 'artifact.zip'
        self.make_artifact()
        self.validator = root / 'ocvalidate'
        self.validator.write_text('#!/bin/sh\necho "No issues found"\n')
        self.validator.chmod(0o755)
        self.args = argparse.Namespace(artifact=self.artifact, backup_dir=root / 'backups',
                                       ocvalidate=self.validator, ack='STAGE-SL4-INPUT')

    def tearDown(self):
        self.root.cleanup()

    def make_artifact(self):
        data = {}
        for name, bundle_id in sut.EXPECTED.items():
            executable = name[:-5]
            payload = {'CFBundleIdentifier': bundle_id, 'CFBundleExecutable': executable}
            if executable == 'VoodooSerial':
                payload['IOKitPersonalities'] = {'VoodooUARTController': {'IOPCIMatch': '0x34a88086 0xa0a88086'}}
            if executable == 'VoodooGPIO':
                payload['IOKitPersonalities'] = {'VoodooGPIOTigerLakeLP': {'IONameMatch': ['INT34C5', 'INTC1055']}}
            data['out/' + name + '/Contents/Info.plist'] = plistlib.dumps(payload)
            data['out/' + name + '/Contents/MacOS/' + executable] = bytes.fromhex('cffaedfe07000001') + bytes(24)
        with zipfile.ZipFile(self.artifact, 'w', compression=zipfile.ZIP_DEFLATED) as f:
            for name, content in data.items():
                f.writestr(name, content)

    def test_archive_and_efi_readonly(self):
        files = sut.validate_archive(self.artifact)
        self.assertEqual(len(files), 10)
        self.assertEqual(sut.validate_efi(self.efi)[0], self.oc)

    def test_apply_restore_and_preserve_metal_windows(self):
        _, path, cfg = sut.validate_efi(self.efi)
        sut.apply(self.args, self.oc, path, cfg)
        self.assertEqual((self.efi / 'Microsoft/Boot/bootmgfw.efi').read_bytes(), b'WINDOWS EFI PRESERVED')
        modified = plistlib.loads(path.read_bytes())
        self.assertEqual(modified['NVRAM'], cfg['NVRAM'])
        self.assertEqual(modified['DeviceProperties'], cfg['DeviceProperties'])
        additions = modified['Kernel']['Add']
        self.assertEqual([x['BundlePath'] for x in additions[-5:]], [name+'.kext' for name, _ in sut.KEXTS])
        self.assertFalse(next(x['Enabled'] for x in additions if x['BundlePath'] == 'SMCBatteryManager.kext'))
        self.assertFalse(next(x['Enabled'] for x in additions if x['BundlePath'].startswith('VoodooI2C.')))
        backup = next((self.args.backup_dir).glob('SL4-INPUT-2*'))
        rollback = argparse.Namespace(ack='RESTORE-SL4-INPUT', backup=backup)
        sut.restore(rollback, self.oc, path)
        self.assertEqual(self.config.read_bytes(), self.original_bytes)
        self.assertEqual((self.oc / 'OpenCore.efi').read_bytes(), b'OPENCORE PRESERVED')
        self.assertEqual((self.efi / 'Microsoft/Boot/bootmgfw.efi').read_bytes(), b'WINDOWS EFI PRESERVED')

    def test_unsupported_build_rejected(self):
        self.make_artifact()
        with zipfile.ZipFile(self.artifact, 'a') as f:
            f.writestr('EFI/Microsoft/Boot/bootmgfw.efi', b'ATTACK')
        with self.assertRaisesRegex(RuntimeError, 'Unexpected artifact member'):
            sut.validate_archive(self.artifact)

    def test_acceleration_guard(self):
        cfg = plistlib.loads(self.config.read_bytes())
        cfg['NVRAM']['Add'][sut.SYSTEM_GUID]['boot-args'] = '-wex-noaccel'
        self.config.write_bytes(plistlib.dumps(cfg))
        with self.assertRaisesRegex(RuntimeError, 'Metal 2'):
            sut.validate_efi(self.efi)

    def test_bad_binary_rejected(self):
        with zipfile.ZipFile(self.artifact, 'a') as f:
            f.writestr('out/VoodooSerial.kext/Contents/MacOS/VoodooSerial', b'BAD BINARY')
        with self.assertRaisesRegex(RuntimeError, 'Duplicate artifact path'):
            sut.validate_archive(self.artifact)


if __name__ == '__main__':
    unittest.main()
