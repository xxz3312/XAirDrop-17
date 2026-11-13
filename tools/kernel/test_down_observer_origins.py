"""The historical CDS audit permits only the exact reviewed observer delta."""
import unittest
from mishare_parent_fixture import restore_down_observer


class DownObserverOriginsTests(unittest.TestCase):
    original=('static void mishare_cds_recovery_window(x)\n{\n'
              '     !mishare_runtime_recovery_candidates(wma->psoc) || keep;\n}\n')
    declaration='extern int mishare_wonder_host_down_observe(struct wlan_objmgr_psoc *psoc);\n'
    call='     mishare_wonder_host_down_observe(wma->psoc) ||\n'

    def current(self):
        return self.declaration+self.original.replace('     !mishare_runtime_recovery_candidates',
            self.call+'     !mishare_runtime_recovery_candidates',1)

    def test_original_is_unchanged(self):
        self.assertEqual(restore_down_observer(self.original),self.original)

    def test_exact_known_insertion_is_restored(self):
        self.assertEqual(restore_down_observer(self.current()),self.original)

    def test_partial_or_duplicate_insertion_is_rejected(self):
        for text in [self.current().replace(self.call,''),
                     self.current().replace(self.declaration,''),self.current()+self.call]:
            with self.subTest(text=text),self.assertRaises(ValueError):
                restore_down_observer(text)

    def test_changed_argument_or_position_is_rejected(self):
        for text in [self.current().replace('wma->psoc) ||\n','NULL) ||\n'),
                     self.current().replace(self.call,'')+self.call]:
            with self.subTest(text=text),self.assertRaises(ValueError):
                restore_down_observer(text)

    def test_unrelated_change_is_preserved_for_whole_file_digest(self):
        changed=self.current().replace('keep;','unreviewed;')
        self.assertEqual(restore_down_observer(changed),self.original.replace('keep;','unreviewed;'))
        self.assertNotEqual(restore_down_observer(changed),self.original)
