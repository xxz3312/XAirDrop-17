"""Real ELF fixtures must reject the old shifted callback table."""
from pathlib import Path
import struct
import tempfile
import unittest

from module_mac80211_ops import audit


def fixture(shift=0, missing_wake=False, assigned=False, bad_relocation=False):
    names = ['', '.shstrtab', '.strtab', '.symtab', '.rodata', '.rela.rodata', '.modinfo']
    shstr = b'\0'; offsets = [0]
    for name in names[1:]:
        offsets.append(len(shstr)); shstr += name.encode() + b'\0'
    strings = b'\0'; no = {}
    for name in ['wonder_mac80211_ops', 'callback', 'ieee80211_emulate_add_chanctx',
                 'ieee80211_emulate_remove_chanctx', 'ieee80211_emulate_change_chanctx']:
        no[name] = len(strings); strings += name.encode() + b'\0'
    symbols = bytes(24) + struct.pack('<IBBHQQ', no['wonder_mac80211_ops'], 1, 0, 4, 0, 1000)
    for name in list(no)[1:]:
        symbols += struct.pack('<IBBHQQ', no[name], 0x12, 0, 0, 0, 0)
    entries = [(offset, 2) for offset in [0, 8, 16, 0x30, 0x40, 0x48, 0x80]]
    if not missing_wake:
        entries.append((0x2f0, 2))
    entries += [(0x250 + shift, 3), (0x258 + shift, 4), (0x260 + shift, 5)]
    if assigned:
        entries.append((0x268, 2))
    rel = b''.join(struct.pack('<QQq', off, (sym << 32) | (261 if bad_relocation else 257), 0)
                   for off, sym in entries)
    chunks = [b'', shstr, strings, symbols, bytes(1000), rel, b'name=wonder\0']
    types = [0, 3, 3, 2, 1, 4, 1]
    links = [0, 0, 0, 2, 0, 3, 0]
    infos = [0, 0, 0, 2, 0, 4, 0]
    sizes = [0, 0, 0, 24, 0, 24, 0]
    data = bytearray(64); sections = []
    for i, chunk in enumerate(chunks):
        while len(data) % 8:
            data.append(0)
        sections.append(struct.pack('<IIQQQQIIQQ', offsets[i], types[i], 0, 0,
                                    len(data), len(chunk), links[i], infos[i], 8, sizes[i]))
        data.extend(chunk)
    while len(data) % 8:
        data.append(0)
    shoff = len(data); data.extend(b''.join(sections))
    data[:16] = b'\x7fELF\x02\x01\x01' + bytes(9)
    struct.pack_into('<HHIQQQIHHHHHH', data, 16, 1, 183, 1, 0, 0, shoff,
                     0, 64, 0, 0, 64, len(names), 1)
    return data


class AllocatorOpsTests(unittest.TestCase):
    def check(self, **kwargs):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'wonder.ko'
            path.write_bytes(fixture(**kwargs))
            return audit(path)

    def test_correct_linked_slots(self):
        self.assertEqual(self.check()['status'], 'ALLOCATOR_TABLE_OFFSETS_MATCH_ONLY')

    def test_actual_old_sixteen_byte_shift_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Wrong callback relocation'):
            self.check(shift=-16)

    def test_missing_mandatory_callback_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Missing mandatory'):
            self.check(missing_wake=True)

    def test_assign_callback_is_rejected_on_emulation_path(self):
        with self.assertRaisesRegex(ValueError, 'Unexpected assign'):
            self.check(assigned=True)

    def test_non_pointer_relocations_cannot_pass(self):
        with self.assertRaisesRegex(ValueError, 'R_AARCH64_ABS64'):
            self.check(bad_relocation=True)


if __name__ == '__main__':
    unittest.main()
