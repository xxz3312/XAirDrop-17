#!/usr/bin/env python3
"""Modpost input provenance and diagnostic verdict boundary checks."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import popsicle_modpost as module


class ModpostTests(unittest.TestCase):
    def test_same_crc_does_not_allow_a_duplicate_export_provider(self):
        known = {'stock_api': '0x12345678'}
        with self.assertRaisesRegex(ValueError, 'Duplicate generated export'):
            module.merge_generated_exports(known, {'stock_api': '0x12345678'})
        self.assertEqual(known, {'stock_api': '0x12345678'})
        module.merge_generated_exports(known, {'private_bridge': '0x87654321'})
        self.assertIn('private_bridge', known)

    def test_unreviewed_protected_list_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'modules.bzl'
            path.write_text('raise RuntimeError("must never execute")\n')
            with self.assertRaisesRegex(ValueError, 'Unreviewed'):
                module.protected_modules(path)

    def test_official_symvers_wrong_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            core = root / 'core.symvers'
            core.write_text('0x12345678 fabricated vmlinux EXPORT_SYMBOL\n')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                module.write_inputs(root, root, core, root / 'absent.json', root / 'vendor.symvers')

    def report(self, layout=None, crc='0x12345678', versions=True):
        expected = {'layout': {'section_size': 1600, 'init_offset': 392, 'exit_offset': 1528},
                    'vermagic': 'target'}
        candidate = {'sha256': 'object', 'modinfo': {'vermagic': ['target']},
                     'versions': {'api': crc} if versions else {}, 'undefined': ['api']}
        with patch.object(module, 'inspect', return_value=candidate), \
             patch.object(module, 'header_layout', return_value=layout or expected['layout']), \
             patch.object(module, 'load', return_value=(b'', [])):
            return module.module_report('candidate.ko', expected, {'api': '0x12345678'})

    def test_metadata_match_does_not_certify_types_or_loading(self):
        result = self.report()
        self.assertEqual(result['status'], 'RECORDS_AND_HEADER_MATCH_ONLY')
        self.assertIn('do not independently validate C declarations', result['limitations'])
        self.assertFalse(result['btf_present'])

    def test_changed_module_header_is_rejected(self):
        self.assertEqual(self.report(layout={'section_size': 1592, 'init_offset': 392,
                                             'exit_offset': 1520})['status'], 'REJECT')

    def test_wrong_crc_or_missing_versions_is_rejected(self):
        self.assertEqual(self.report(crc='0x87654321')['status'], 'REJECT')
        self.assertEqual(self.report(versions=False)['status'], 'REJECT')

    def test_reference_loader_release_rule_does_not_ignore_flags(self):
        expected = {'layout': {'section_size': 1600, 'init_offset': 392, 'exit_offset': 1528},
                    'vermagic': 'stock SMP modversions aarch64'}
        candidate = {'sha256': 'object', 'modinfo': {'vermagic': ['candidate SMP modversions aarch64']},
                     'versions': {'api': '0x12345678'}, 'undefined': ['api']}
        for basic, flags, status in [(True, 'SMP modversions aarch64', 'REVIEW_KERNEL_RELEASE'),
                                     (False, 'SMP modversions aarch64', 'REJECT'),
                                     (True, 'modversions aarch64', 'REJECT')]:
            with self.subTest(basic=basic, flags=flags):
                candidate['modinfo']['vermagic'] = ['candidate ' + flags]
                sections = [{'name': '__versions', 'size': 64}] if basic else []
                with patch.object(module, 'inspect', return_value=candidate), \
                     patch.object(module, 'header_layout', return_value=expected['layout']), \
                     patch.object(module, 'load', return_value=(b'', sections)):
                    result = module.module_report('candidate.ko', expected, {'api': '0x12345678'})
                    self.assertEqual(result['status'], status)

    def test_stock_loader_evidence_still_requires_basic_crcs_and_matching_flags(self):
        expected = {'layout': {'section_size': 1600, 'init_offset': 392, 'exit_offset': 1528},
                    'vermagic': 'stock SMP modversions aarch64'}
        evidence = {'target_vermagic': 'actual-stock SMP modversions aarch64',
                    'kernel_sha256': 'stock-kernel'}
        for basic, flags, crc, status in [
                (True, 'SMP modversions aarch64', '0x12345678', 'RECORDED_LOADER_CHECKS_MATCH_ONLY'),
                (False, 'SMP modversions aarch64', '0x12345678', 'REJECT'),
                (True, 'modversions aarch64', '0x12345678', 'REJECT'),
                (True, 'SMP modversions aarch64', '0x87654321', 'REJECT')]:
            candidate = {'sha256': 'object', 'modinfo': {'vermagic': ['candidate ' + flags]},
                         'versions': {'api': crc}, 'undefined': ['api']}
            sections = [{'name': '__versions', 'size': 64}] if basic else []
            with self.subTest(basic=basic, flags=flags, crc=crc), \
                 patch.object(module, 'inspect', return_value=candidate), \
                 patch.object(module, 'header_layout', return_value=expected['layout']), \
                 patch.object(module, 'load', return_value=(b'', sections)), \
                 patch.object(module, 'stock_loader_evidence', return_value=evidence):
                self.assertEqual(module.module_report('candidate.ko', expected,
                                                     {'api': '0x12345678'})['status'], status)

    def test_recorded_stock_loader_evidence_is_hash_pinned(self):
        import json
        root = Path(__file__).resolve().parents[2]
        expected = json.loads((root / 'kernel/abi/popsicle-stock-module-header.json').read_text())
        self.assertEqual(module.stock_loader_evidence(expected)['caller_vers_byte_offset'], 116)
        expected['loader_evidence']['sha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            module.stock_loader_evidence(expected)


if __name__ == '__main__':
    unittest.main()
