import struct
import unittest

from btf_layout import Btf, RecordedLayouts, compare


def fixture(offset=0, bitfield=False):
    strings = b'\0unsigned int\0sample\0value\0'
    integer = struct.pack('<IIII', 1, 1 << 24, 4, 32)
    info = (4 << 24) | 1 | ((1 << 31) if bitfield else 0)
    member_offset = offset | (3 << 24) if bitfield else offset
    record = struct.pack('<IIIIII', 14, info, 4, 21, 1, member_offset)
    types = integer + record
    return struct.pack('<HBBIIIII', 0xeb9f, 1, 0, 24, 0, len(types),
                       len(types), len(strings)) + types + strings


class LayoutTests(unittest.TestCase):
    def test_same_size_but_changed_member_offset_rejected(self):
        a, b = Btf(fixture()), Btf(fixture(offset=8))
        result = compare(a, b, ['sample'])
        self.assertEqual(result['status'], 'REJECT_SELECTED_LAYOUT_DIFFERENCE')
        self.assertEqual(result['types']['sample']['stock'][0]['size'], 4)

    def test_match_is_only_selected_layout_evidence(self):
        result = compare(Btf(fixture()), Btf(fixture()), ['sample'])
        self.assertEqual(result['status'], 'SELECTED_LAYOUTS_MATCH_ONLY')
        self.assertIn('pointer targets', result['limitations'])

    def test_missing_type_is_incomplete(self):
        self.assertEqual(compare(Btf(fixture()), Btf(fixture()), ['absent'])['status'],
                         'INCOMPLETE')

    def test_recorded_metadata_matches_raw_input(self):
        raw = Btf(fixture())
        recorded = RecordedLayouts({'pointer_size': 8, 'source_btf_sha256': raw.sha256,
                                    'types': {'sample': raw.layouts('sample')}})
        self.assertEqual(compare(recorded, raw, ['sample'])['status'],
                         'SELECTED_LAYOUTS_MATCH_ONLY')
        self.assertEqual(compare(recorded, raw, ['unrecorded'])['status'], 'INCOMPLETE')

    def test_bitfield_width_and_offset_decoded(self):
        member = Btf(fixture(offset=5, bitfield=True)).layouts('sample')[0]['members'][0]
        self.assertEqual(member['bit_offset'], 5)
        self.assertEqual(member['bitfield_size'], 3)

    def test_truncated_and_invalid_string_refused(self):
        with self.assertRaises(ValueError):
            Btf(fixture()[:-1])
        data = Btf(fixture())
        with self.assertRaises(ValueError):
            data.string(9999)


if __name__ == '__main__':
    unittest.main()
