import hashlib
from pathlib import Path
import tempfile
import unittest
from popsicle_transport_audit import audit

class TransportAuditTests(unittest.TestCase):
    def run_case(self,text,**changes):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'profile';p.write_text(text)
            r={'profile_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
               'stock_wlan_sha256':'original-ELF','transport':'PCIE_CNSS',
               'actual_stock_platform_imports':['cnss_wlan_register_driver','cnss_wlan_unregister_driver']}
            r.update(changes);return audit(p,r)
    def test_actual_pcie_evidence(self):
        self.assertEqual(self.run_case('CONFIG_PLD_PCIE_CNSS_FLAG=y\n')['platform_module'],'cnss2')
    def test_wrong_bus_cannot_be_made_applicable_by_label(self):
        with self.assertRaises(ValueError):self.run_case('CONFIG_PLD_IPCI_ICNSS_FLAG=y\n',transport='IPCI_ICNSS')
    def test_ambiguous_bus_is_not_a_pair(self):
        with self.assertRaises(ValueError):self.run_case('CONFIG_PLD_PCIE_CNSS_FLAG=y\nCONFIG_PLD_IPCI_ICNSS_FLAG=y\n')
    def test_changed_profile_requires_fresh_evidence(self):
        with self.assertRaises(ValueError):self.run_case('CONFIG_PLD_PCIE_CNSS_FLAG=y\n',profile_sha256='old-profile')
