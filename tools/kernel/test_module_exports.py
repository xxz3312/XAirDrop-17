#!/usr/bin/env python3
"""Regression fixture for ELF relocation target lookup (no vendor binaries)."""
from pathlib import Path
import struct
import tempfile
import unittest

from module_exports import exports


def fixture(relocation_name, target=4):
    names = ['', '.shstrtab', '.strtab', '.symtab', '__ksymtab',
             '__kcrctab', relocation_name]
    shstr = b'\0'
    offsets = [0]
    for name in names[1:]:
        offsets.append(len(shstr))
        shstr += name.encode() + b'\0'
    strings = b'\0sample_symbol\0'
    # Relocation points to a section symbol + string addend, not a named symbol.
    symbols = bytes(24) + struct.pack('<IBBHQQ', 0, 3, 0, 2, 0, 0)
    chunks = [b'', shstr, strings, symbols, bytes(12),
              struct.pack('<I', 0x12345678),
              struct.pack('<QQq', 4, (1 << 32) | 261, 1)]
    types = [0, 3, 3, 2, 1, 1, 4]
    links = [0, 0, 0, 2, 0, 0, 3]
    infos = [0, 0, 0, 2, 0, 0, target]
    entries = [0, 0, 0, 24, 0, 0, 24]
    data = bytearray(64)
    sections = []
    for i, chunk in enumerate(chunks):
        while len(data) % 8:
            data.append(0)
        sections.append(struct.pack('<IIQQQQIIQQ', offsets[i], types[i], 0,
                                    0, len(data), len(chunk), links[i],
                                    infos[i], 8, entries[i]))
        data.extend(chunk)
    while len(data) % 8:
        data.append(0)
    shoff = len(data)
    data.extend(b''.join(sections))
    data[:16] = b'\x7fELF\x02\x01\x01' + bytes(9)
    struct.pack_into('<HHIQQQIHHHHHH', data, 16,
                     1, 183, 1, 0, 0, shoff, 0, 64, 0, 0, 64, len(names), 1)
    return data


class ExportRelocationTests(unittest.TestCase):
    def read_fixture(self, name, target=4):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.ko'
            path.write_bytes(fixture(name, target))
            return exports(path)

    def test_combined_android_section(self):
        self.assertEqual(self.read_fixture('.rela__ksymtab'),
                         {'sample_symbol': '0x12345678'})

    def test_section_name_does_not_determine_target(self):
        self.assertEqual(self.read_fixture('.rela_other_spelling'),
                         self.read_fixture('.rela___ksymtab+sample_symbol'))

    def test_wrong_target_is_not_used(self):
        self.assertEqual(self.read_fixture('.rela___ksymtab+sample_symbol', 5), {})


if __name__ == '__main__':
    unittest.main()
