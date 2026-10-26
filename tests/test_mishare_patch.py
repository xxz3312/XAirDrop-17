"""Exact-input BLE edits must fail closed on method drift or prior patching."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/mishare'))
from ble_patch import patch_text, VERSION_OLD, VERSION_NEW, OFFSET_OLD, OFFSET_NEW


def fixture():
    return ('.class public final La/u0;\n'
            '.method public final declared-synchronized b(Lcom/xiaomi/sharop/service/AirDropService;)V\n'
            '    const/4 v0, 0x1\n    const/4 v1, 0x0\n    const/16 v2, 0x14\n'
            + VERSION_OLD + '\n' + OFFSET_OLD + '\n    const/16 v3, 0x4c\n.end method\n'
            '.method public unrelated()V\n    return-void\n.end method\n')


class MiShareBleTests(unittest.TestCase):
    def test_only_two_expected_instruction_edits(self):
        original = fixture(); patched = patch_text(original)
        self.assertEqual(patched.replace(VERSION_NEW, VERSION_OLD).replace(OFFSET_NEW, OFFSET_OLD), original)
        self.assertTrue(patched.endswith('.method public unrelated()V\n    return-void\n.end method\n'))

    def test_already_patched_rejected(self):
        with self.assertRaises(ValueError):
            patch_text(patch_text(fixture()))

    def test_duplicate_anchor_rejected(self):
        with self.assertRaises(ValueError):
            patch_text(fixture() + VERSION_OLD)

    def test_register_drift_rejected(self):
        with self.assertRaisesRegex(ValueError, 'semantics'):
            patch_text(fixture().replace('const/4 v0, 0x1', 'const/4 v0, 0x0'))

    def test_anchor_moved_outside_method_rejected(self):
        text = fixture().replace(OFFSET_OLD, '') + OFFSET_OLD
        with self.assertRaisesRegex(ValueError, 'semantics'):
            patch_text(text)


if __name__ == '__main__':
    unittest.main()
