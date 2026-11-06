import copy
import io
import json
from pathlib import Path
import sys
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/kernel'))
import stock_cnss_bundle as bundle


class StockCNSSBundleTests(unittest.TestCase):
    def integrity_fixture(self, root):
        for name, content in {'customize.sh': 'installer', 'module.prop': 'old version',
                              'CHECK_FIRST.txt': 'old instructions', 'driver.ko': 'retained ELF',
                              'controller.sh': 'retained script',
                              'popsicle-stock-cnss-io.sh': 'old IO adapter'}.items():
            (root / name).write_text(content)

    def checksum(self, root, name):
        return subprocess.run(['sha256sum', '-c', name], cwd=root, capture_output=True)

    def test_both_manifests_pass_before_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.integrity_fixture(root)
            bundle.write_integrity(root)
            self.assertEqual(self.checksum(root, 'SHA256SUMS').returncode, 0)
            self.assertEqual(self.checksum(root, 'INSTALL_SHA256SUMS').returncode, 0)
            self.assertNotIn('customize.sh', (root / 'SHA256SUMS').read_text())
            self.assertIn('customize.sh', (root / 'INSTALL_SHA256SUMS').read_text())

    def test_KSU_installer_deletion_does_not_break_runtime_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.integrity_fixture(root)
            bundle.write_integrity(root)
            (root / 'customize.sh').unlink()
            self.assertEqual(self.checksum(root, 'SHA256SUMS').returncode, 0)
            self.assertNotEqual(self.checksum(root, 'INSTALL_SHA256SUMS').returncode, 0)

    def test_runtime_still_rejects_missing_or_changed_retained_files(self):
        for name in ['controller.sh', 'driver.ko']:
            for remove in [False, True]:
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    self.integrity_fixture(root)
                    bundle.write_integrity(root)
                    if remove:
                        (root / name).unlink()
                    else:
                        (root / name).write_text('changed')
                    self.assertNotEqual(self.checksum(root, 'SHA256SUMS').returncode, 0)

    def update_fixture(self, root, mutate_retained=False):
        self.integrity_fixture(root)
        old = {p.name: bundle.sha(p) for p in root.iterdir()}
        baseline = {'bundle_sha256': '2a07638505b70bfaf2f8eba3bdce33185dc5ea61f2d34a4e0024fd34fa1e6ade', 'files': old}
        (root / 'module.prop').write_text('new version')
        (root / 'CHECK_FIRST.txt').write_text('new instructions')
        (root / 'popsicle-stock-cnss-io.sh').write_text('streamed IO adapter')
        if mutate_retained:
            (root / 'driver.ko').write_text('modified driver')
        bundle.write_integrity(root)
        package = root / 'new.zip'
        with zipfile.ZipFile(package, 'w') as archive:
            for path in root.iterdir():
                if path != package:
                    archive.write(path, path.name)
        return package, baseline

    def test_IO_update_contains_only_the_four_allowlisted_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package, baseline = self.update_fixture(root)
            output = root / 'update.zip'
            report = bundle.checker_update(package, output, baseline)
            self.assertFalse(report['retained_modules_and_unlisted_scripts_changed'])
            self.assertTrue(report['runtime_IO_adapter_updated'])
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(sorted(archive.namelist()), ['CHECK_FIRST.txt', 'SHA256SUMS', 'module.prop', 'popsicle-stock-cnss-io.sh'])

    def test_checker_update_refuses_changed_driver_even_with_new_valid_checksum(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package, baseline = self.update_fixture(root, mutate_retained=True)
            with self.assertRaises(ValueError):
                bundle.checker_update(package, root / 'update.zip', baseline)

    def test_checkpoint_does_not_accept_failed_mixed_or_runtime_certified_evidence(self):
        accepted = bundle.evidence()
        for key, value in [('required_jobs_success', 6), ('actual_wlan_cnss2_import_count', 62),
                           ('actual_wlan_checked_or_live_arm_imports', ['checked']),
                           ('runtime_certified', True), ('phone_executed', True),
                           ('runtime_certified', 0), ('workflow_run', 1)]:
            data = copy.deepcopy(accepted)
            data[key] = value
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                target = root / 'docs/research/popsicle-stock-cnss-0135-validation.json'
                target.parent.mkdir(parents=True)
                target.write_text(json.dumps(data))
                with patch.object(bundle, 'ROOT', root), self.assertRaises(ValueError):
                    bundle.evidence()

    def test_wrong_raw_module_is_rejected_before_ELF_parser(self):
        with tempfile.TemporaryDirectory() as folder:
            modules = Path(folder)
            (modules / 'qca_cld3_peach_v2.ko').write_bytes(b'wrong')
            with patch.object(bundle, 'inspect') as parser, self.assertRaises(ValueError):
                bundle.verified_inputs(modules, bundle.evidence())
            parser.assert_not_called()

    def test_symlink_candidate_is_not_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            modules = Path(folder)
            (modules / 'target').write_bytes(b'not ELF')
            (modules / 'qca_cld3_peach_v2.ko').symlink_to(modules / 'target')
            with patch.object(bundle, 'inspect') as parser, self.assertRaises(ValueError):
                bundle.verified_inputs(modules, bundle.evidence())
            parser.assert_not_called()

    def test_artifact_hash_is_checked_before_opening_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'artifact.zip'
            path.write_bytes(b'not the accepted artifact')
            with patch.object(bundle.zipfile, 'ZipFile') as opener, self.assertRaises(ValueError):
                bundle.extract_accepted(path, Path(folder), bundle.evidence())
            opener.assert_not_called()

    def test_nested_module_symlinks_and_duplicates_are_rejected(self):
        for duplicate in [False, True]:
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                nested = io.BytesIO()
                with tarfile.open(fileobj=nested, mode='w:gz') as archive:
                    info = tarfile.TarInfo('qca_cld3_peach_v2.ko')
                    if duplicate:
                        info.size = 1
                        archive.addfile(info, io.BytesIO(b'x'))
                        archive.addfile(info, io.BytesIO(b'y'))
                    else:
                        info.type = tarfile.SYMTYPE
                        info.linkname = '/unrelated/path'
                        archive.addfile(info)
                path = root / 'artifact.zip'
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr('diagnostic-modules-not-for-install.tar.gz', nested.getvalue())
                accepted = {'full_artifact_sha256': bundle.sha(path)}
                with self.assertRaises(ValueError):
                    bundle.extract_accepted(path, root, accepted)

    def test_only_WLAN_and_provider_are_packaged(self):
        self.assertEqual(set(bundle.NAMES.values()), {'qca_cld3_peach_v2', 'opairshare_wonder_provider'})
        self.assertNotIn('cnss2', bundle.NAMES.values())


if __name__ == '__main__':
    unittest.main()
