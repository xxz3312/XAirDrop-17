import copy
import unittest

from stock_cnss_audit import audit, LEGACY, CHECKED, LIVE


class StockCNSSAuditTests(unittest.TestCase):
    def setUp(self):
        exports = {n: {'crc': '0x12345678'} for n in LEGACY | {'cnss_power_up'}}
        self.stock = {'firmware': 'captured', 'modules': [{'name': 'cnss2', 'exports': exports}]}
        self.module = {'undefined': sorted(exports),
                       'versions': {n: r['crc'] for n, r in exports.items()},
                       'modinfo': {'depends': ['cnss2,opairshare_wonder_provider']}}

    def rejected(self, module):
        self.assertEqual(audit(module, self.stock)['status'], 'STOCK_CNSS2_IMPORTS_REJECTED')

    def test_legacy_surface_matches_without_runtime_certification(self):
        report = audit(self.module, self.stock)
        self.assertEqual(report['status'], 'STOCK_CNSS2_IMPORTS_MATCH_ONLY')
        self.assertFalse(report['runtime_certified'])

    def test_optional_or_version_only_checked_reference_still_rejected(self):
        for name in CHECKED | LIVE:
            for field in ['undefined', 'versions']:
                module = copy.deepcopy(self.module)
                if field == 'undefined':
                    module[field].append(name)
                else:
                    module[field][name] = '0x12345678'
                self.rejected(module)

    def test_missing_registration_or_unregistration_rejected(self):
        for name in LEGACY:
            module = copy.deepcopy(self.module)
            module['undefined'].remove(name)
            self.rejected(module)

    def test_missing_or_changed_crc_including_non_registration_import(self):
        for name in self.module['undefined']:
            for value in [None, '0x00000000']:
                module = copy.deepcopy(self.module)
                if value is None:
                    del module['versions'][name]
                else:
                    module['versions'][name] = value
                self.rejected(module)

    def test_unknown_cnss_extension_rejected(self):
        module = copy.deepcopy(self.module)
        module['undefined'].append('cnss_future_private_extension')
        self.rejected(module)

    def test_captured_cnss_utils_is_not_misclassified_as_cnss2(self):
        self.stock['modules'].append({'name': 'cnss_utils', 'exports': {
            'cnss_utils_get_wlan_mac_address': {'crc': '0x11111111'}}})
        self.module['undefined'].append('cnss_utils_get_wlan_mac_address')
        self.module['versions']['cnss_utils_get_wlan_mac_address'] = '0x11111111'
        report = audit(self.module, self.stock)
        self.assertEqual(report['status'], 'STOCK_CNSS2_IMPORTS_MATCH_ONLY')
        self.assertNotIn('cnss_utils_get_wlan_mac_address', report['cnss2_imports'])

    def test_required_dependency_records_cannot_be_omitted(self):
        for dep in ['cnss2', 'opairshare_wonder_provider', '']:
            module = copy.deepcopy(self.module)
            module['modinfo']['depends'] = [dep]
            self.rejected(module)

    def test_ambiguous_stock_capture_rejected(self):
        self.stock['modules'] *= 2
        with self.assertRaises(ValueError):
            audit(self.module, self.stock)
