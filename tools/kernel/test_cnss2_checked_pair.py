import copy
import unittest
from cnss2_checked_pair import check_export_surface

REQUIRED='cnss_wlan_unregister_driver_checked_v1'

class CNSS2ExportSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.stock={'native':{'crc':'0x12345678','export_type':'EXPORT_SYMBOL','namespace':''}}
        self.actual=copy.deepcopy(self.stock)
        self.actual[REQUIRED]={'crc':'0x87654321','export_type':'EXPORT_SYMBOL','namespace':''}
    def test_matching_old_surface_with_checked_extension(self):
        self.assertTrue(check_export_surface(self.stock,self.actual,REQUIRED)['match'])
    def test_crc_difference_is_not_waived(self):
        self.actual['native']['crc']='0x00000000'
        self.assertIn('native',check_export_surface(self.stock,self.actual,REQUIRED)['changed'])
    def test_license_and_namespace_are_part_of_old_contract(self):
        for field,value in [('export_type','EXPORT_SYMBOL_GPL'),('namespace','OTHER')]:
            with self.subTest(field=field):
                changed=copy.deepcopy(self.actual);changed['native'][field]=value
                self.assertFalse(check_export_surface(self.stock,changed,REQUIRED)['match'])
    def test_missing_old_export_and_unexpected_export_are_rejected(self):
        del self.actual['native'];self.actual['unexpected']=self.stock['native']
        r=check_export_surface(self.stock,self.actual,REQUIRED)
        self.assertFalse(r['match']);self.assertEqual(r['missing'],['native']);self.assertEqual(r['unexpected_extra'],['unexpected'])
    def test_missing_or_incompatible_checked_extension_is_rejected(self):
        for changed in [{k:v for k,v in self.actual.items() if k!=REQUIRED},
                        dict(self.actual,**{REQUIRED:{'crc':'0x87654321','export_type':'EXPORT_SYMBOL_GPL','namespace':''}})]:
            self.assertFalse(check_export_surface(self.stock,changed,REQUIRED)['match'])
