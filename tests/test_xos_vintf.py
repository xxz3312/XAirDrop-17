"""Reject unintended boot behavior, unknown module files and incorrect AIDL instances."""
import shutil
import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/xos'))
from package_vintf import ROOT, FRAGMENT, validated_files


class VintfModuleTests(unittest.TestCase):
    def test_exact_declaration_and_bound_manual_action(self):
        files = validated_files(ROOT / 'modules/xos-vintf')
        self.assertNotIn('@MANIFEST_SHA256@', files['action.sh'].decode())
        self.assertNotIn('service.sh', files)
        self.assertNotIn('sepolicy.rule', files)

    def test_unexpected_boot_script_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source';shutil.copytree(ROOT/'modules/xos-vintf',source)
            (source/'service.sh').write_text('exit 0\n')
            with self.assertRaises(ValueError):validated_files(source)

    def test_aidl_on_unsupported_meta_version_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source';shutil.copytree(ROOT/'modules/xos-vintf',source)
            p=source/FRAGMENT;p.write_text(p.read_text().replace('manifest version="2.0"','manifest version="1.0"'))
            with self.assertRaises(ValueError):validated_files(source)

    def test_wrong_aidl_instance_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source';shutil.copytree(ROOT/'modules/xos-vintf',source)
            p=source/FRAGMENT;p.write_text(p.read_text().replace('IDomesticXOsComm/default','IDomesticXOsComm/other'))
            with self.assertRaises(ValueError):validated_files(source)


if __name__ == '__main__':unittest.main()
