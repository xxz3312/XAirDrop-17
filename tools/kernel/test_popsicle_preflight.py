#!/usr/bin/env python3
"""Audit decision regressions: incomplete evidence must never pass as complete."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from popsicle_preflight import audit


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.table = Path(self.temp.name) / 'vmlinux.symvers'
        self.table.write_text('0x12345678 sample vmlinux EXPORT_SYMBOL\n')
        self.stock = {
            'sha256': 'stock',
            'modinfo': {'name': ['qca_cld3_peach_v2'], 'vermagic': ['6.12 target']},
            'versions': {'sample': '0x12345678'}, 'undefined': ['sample'],
        }
        self.candidate = deepcopy(self.stock)
        self.candidate['sha256'] = 'candidate'

    def run_audit(self, dependencies=()):
        inputs = {'stock': self.stock, 'candidate': self.candidate,
                  'dependency': deepcopy(self.stock)}
        with patch('popsicle_preflight.inspect', side_effect=lambda path: inputs[path]):
            return audit('stock', dependencies, [self.table], 'candidate')

    def test_matching_crcs_remain_evidence_only(self):
        self.assertEqual(self.run_audit()['status'], 'ABI_EVIDENCE_ONLY')

    def test_candidate_new_import_must_be_resolved(self):
        self.candidate['versions']['new_interface'] = '0x01020304'
        self.candidate['undefined'].append('new_interface')
        report = self.run_audit()
        self.assertEqual(report['status'], 'INCOMPLETE')
        self.assertEqual(report['candidate']['missing'], ['new_interface'])

    def test_unversioned_undefined_import_is_incomplete(self):
        self.candidate['undefined'].append('unversioned_interface')
        self.assertEqual(self.run_audit()['status'], 'INCOMPLETE')

    def test_candidate_without_versions_is_rejected(self):
        self.candidate['versions'] = {}
        self.assertEqual(self.run_audit()['status'], 'REJECT')

    def test_wrong_module_or_vermagic_is_rejected(self):
        for field in ('name', 'vermagic'):
            with self.subTest(field=field):
                self.candidate = deepcopy(self.stock)
                self.candidate['modinfo'][field] = ['wrong']
                self.assertEqual(self.run_audit()['status'], 'REJECT')

    def test_real_export_conflict_is_rejected(self):
        with patch('popsicle_preflight.exports', return_value={'sample': '0x87654321'}):
            self.assertEqual(self.run_audit(['dependency'])['status'], 'REJECT')

    def test_candidate_crc_mismatch_is_rejected(self):
        self.candidate['versions']['sample'] = '0x87654321'
        self.assertEqual(self.run_audit()['status'], 'REJECT')


if __name__ == '__main__':
    unittest.main()
