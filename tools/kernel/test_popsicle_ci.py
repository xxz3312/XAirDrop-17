#!/usr/bin/env python3
"""CNSS diagnostic reports must distinguish name coverage from compatibility."""
import gzip
import hashlib
import json
from pathlib import Path
import unittest

from popsicle_ci import REPO, cnss_audit


class CiTests(unittest.TestCase):
    def test_missing_provider_blocks(self):
        result = cnss_audit({'undefined': ['cnss_new'], 'sha256': 'object'},
                            {'exports': {'cnss_old': '0x12345678'}})
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['missing'], ['cnss_new'])

    def test_name_match_is_not_abi_pass(self):
        result = cnss_audit({'undefined': ['cnss_old'], 'sha256': 'object'},
                            {'exports': {'cnss_old': '0x12345678'}})
        self.assertEqual(result['status'], 'NAME_COVERAGE_ONLY')

    def test_audit_scope_is_explicit(self):
        result = cnss_audit({'undefined': ['unresolved_other_vendor_api'], 'sha256': 'object'},
                            {'exports': {}})
        self.assertEqual(result['required_cnss_symbols'], 0)
        self.assertIn('full dependency', result['limitations'])

    def test_tracked_config_is_exact_recorded_input(self):
        raw = gzip.decompress((REPO / 'kernel/configs/popsicle-stock.config.gz').read_bytes())
        expected = json.loads((REPO / 'kernel/configs/popsicle-stock.json').read_text())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), expected['config_sha256'])

    def test_stock_cnss_table_preserves_known_blocker(self):
        table = json.loads((REPO / 'kernel/abi/popsicle-stock-cnss-exports.json').read_text())
        self.assertNotIn('cnss_get_wlan_tsf_gpio', table['exports'])
        self.assertEqual(len(table['providers']), 4)


if __name__ == '__main__':
    unittest.main()
