import unittest
from module_cfg80211_ops import EXPECTED, check_table, CONTROL_SYMBOLS, check_control_symbols


class Cfg80211OpsTest(unittest.TestCase):
    def test_stock_layout(self):
        self.assertEqual(check_table(bytes(0x418), EXPECTED)['callbacks_checked'], 65)

    def test_0047_layout_rejected(self):
        old = {o-(16 if o >= 0x1d0 else 0): n for o, n in EXPECTED.items()}
        with self.assertRaises(ValueError):
            check_table(bytes(0x408), old)

    def test_shift_with_padded_size_still_rejected(self):
        old = {o-(16 if o >= 0x1d0 else 0): n for o, n in EXPECTED.items()}
        with self.assertRaises(ValueError):
            check_table(bytes(0x418), old)

    def test_swapped_callbacks_rejected(self):
        rel = dict(EXPECTED)
        rel[0x1f8], rel[0x200] = rel[0x200], rel[0x1f8]
        with self.assertRaises(ValueError):
            check_table(bytes(0x418), rel)

    def test_unexpected_p2p_callback_rejected(self):
        with self.assertRaises(ValueError):
            check_table(bytes(0x418), dict(EXPECTED, **{}) | {0x290: 'unexpected'})

    def test_unrelocated_nonnull_slot_rejected(self):
        table = bytearray(0x418)
        table[0x298] = 1
        with self.assertRaises(ValueError):
            check_table(table, EXPECTED)


class WlanControlTest(unittest.TestCase):
    def test_control_present(self):
        self.assertEqual(check_control_symbols(CONTROL_SYMBOLS)['status'], 'CONTROL_IMPLEMENTATION_PRESENT_ONLY')

    def test_0048_missing_control_rejected(self):
        with self.assertRaisesRegex(ValueError, '/dev/wlan'):
            check_control_symbols(set())

    def test_each_control_callback_required(self):
        for name in CONTROL_SYMBOLS:
            with self.subTest(name=name), self.assertRaises(ValueError):
                check_control_symbols(CONTROL_SYMBOLS - {name})
