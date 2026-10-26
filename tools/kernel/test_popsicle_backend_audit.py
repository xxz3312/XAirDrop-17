"""Do not infer a usable radio backend from monitor support or log strings."""
from pathlib import Path
import tempfile
import unittest

from popsicle_backend_audit import NATIVE, REQUIRED, inventory, identifiers


class BackendInventoryTests(unittest.TestCase):
    def source(self, add_required=False, monitor_tx=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        files = {}
        for path, names in list(NATIVE.values()) + (list(REQUIRED.values()) if add_required else []):
            files.setdefault(path, []).extend(names)
        for path, names in files.items():
            dest = root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text('\n'.join(n + ';' for n in set(names)))
        main = root / NATIVE['adapter_lifecycle'][0]
        with main.open('a') as f:
            f.write('\nstatic const struct net_device_ops wlan_mon_drv_ops = {\n')
            if monitor_tx:
                f.write('.ndo_start_xmit = tx,\n')
            f.write('};\n')
        return root

    def test_baseline_monitor_rx_is_not_backend_success(self):
        report = inventory(self.source())
        self.assertEqual(report['status'], 'SOURCE_PORT_REQUIRED')
        self.assertEqual(len(report['missing_source_plumbing']), len(REQUIRED))
        self.assertFalse(report['monitor_netdev_has_start_xmit'])
        self.assertIsNone(report['radio_usable'])

    def test_even_all_identifiers_require_review(self):
        report = inventory(self.source(add_required=True, monitor_tx=True))
        self.assertEqual(report['missing_source_plumbing'], [])
        self.assertEqual(report['status'], 'SOURCE_IDENTIFIERS_PRESENT_REVIEW_REQUIRED')
        self.assertIsNone(report['radio_usable'])
        self.assertEqual(report['firmware_passthru_support'], 'UNVERIFIED')

    def test_comments_and_strings_cannot_supply_missing_implementation(self):
        self.assertEqual(identifiers('/* QDF_PASSTHRU_MODE */\n"QDF_PASSTHRU_MODE"',
                                     ['QDF_PASSTHRU_MODE']), {'QDF_PASSTHRU_MODE': False})

    def test_monitor_tx_is_reported_without_inventing_capabilities(self):
        report = inventory(self.source(monitor_tx=True))
        self.assertTrue(report['monitor_netdev_has_start_xmit'])
        self.assertEqual(report['status'], 'SOURCE_PORT_REQUIRED')

    def test_native_source_drift_stops_inventory(self):
        root = self.source()
        (root / NATIVE['management_tx'][0]).write_text('/* deleted */')
        with self.assertRaisesRegex(ValueError, 'anchors changed'):
            inventory(root)
