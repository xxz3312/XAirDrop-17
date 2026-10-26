"""ELF wrappers and string names must not become firmware capability claims."""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/kernel'))
from firmware_image_audit import firmware_info, firmware_elf


def image(machine=40, payload=b'fixture', size=None):
    data = bytearray(84 + len(payload))
    data[:16] = b'\x7fELF\x01\x01\x01' + b'\0' * 9
    struct.pack_into('<HHIIIIIHHHHHH', data, 16, 2, machine, 1, 0x1000, 52, 0, 0, 52, 32, 1, 0, 0, 0)
    struct.pack_into('<IIIIIIII', data, 52, 1, 84, 0x1000, 0x1000, len(payload) if size is None else size, len(payload), 5, 4)
    data[84:] = payload
    return bytes(data)


class FirmwareImageTests(unittest.TestCase):
    def test_embedded_dsp_is_found_without_certifying_support(self):
        inner = image(164, b'QC_IMAGE_VERSION_STRING=fixture\0PASSTHRU\0')
        blob = image(payload=b'outer')
        blob += b'\0' * (256 - len(blob)) + inner
        report = firmware_info(blob)
        self.assertEqual([(x['offset'], x['machine']) for x in report['elf_images']], [(0, 40), (256, 164)])
        self.assertEqual(report['passthru_support'], 'UNVERIFIED')
        self.assertFalse(report['active_image_confirmed'])
        self.assertEqual(report['version_strings'][0]['text'], 'QC_IMAGE_VERSION_STRING=fixture')

    def test_magic_inside_data_is_rejected(self):
        result = firmware_info(image(payload=b'hello\x7fELF2not-a-header'))
        self.assertEqual(len(result['elf_images']), 1)
        self.assertEqual(len(result['rejected_magic']), 1)

    def test_truncated_program_and_segment_tables_rejected(self):
        with self.assertRaises(ValueError):
            firmware_elf(image()[:60], 0)
        with self.assertRaises(ValueError):
            firmware_elf(image(size=4096), 0)

    def test_plain_strings_are_not_an_elf(self):
        with self.assertRaises(ValueError):
            firmware_info(b'PASSTHRU AWDL WMI_VDEV_TYPE_WIFI_PASSTHRU')
