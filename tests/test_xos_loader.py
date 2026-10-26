"""Run on Actions: execute the real probe against harmless host fixture libraries."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class XosLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.work = Path(cls.tmp.name)
        cls.probe = cls.work / 'probe'
        subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(ROOT / 'native/xos/loader-probe.c'), '-ldl', '-o', str(cls.probe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def fixture(self, directory, missing_symbol=False):
        directory.mkdir()
        source = directory / 'fixture.c'
        source.write_text('#include <unistd.h>\n' + ''.join(
            'void ' + name + '(void) { _exit(99); }\n'
            for name in ['domestic_xos_start', 'domestic_xoscomm_stop', 'domestic_xoscomm_get_status'] +
                        ([] if missing_symbol else ['domestic_xoscomm_set_aggregation_config'])))
        for name in ['com.domestic.xoscomm-V1-ndk.so', 'libxos.so']:
            subprocess.run(['cc', '-shared', '-fPIC', str(source), '-o', str(directory / name)], check=True)

    def run_probe(self, directory):
        return subprocess.run([str(self.probe), str(directory)], text=True, capture_output=True, timeout=5)

    def test_all_exports_resolve_without_calling_abort_functions(self):
        directory = self.work / 'valid';self.fixture(directory)
        result = self.run_probe(directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count('DLSYM_OK'), 4)
        self.assertIn('PASS_DLOPEN_DLSYM_ONLY', result.stdout)

    def test_missing_export_fails_without_success_marker(self):
        directory = self.work / 'missing-symbol';self.fixture(directory, True)
        result = self.run_probe(directory)
        self.assertEqual(result.returncode, 1)
        self.assertIn('DLSYM_FAIL', result.stderr)
        self.assertNotIn('PASS_', result.stdout)

    def test_missing_ndk_and_xos_libraries_fail(self):
        for missing in ['com.domestic.xoscomm-V1-ndk.so', 'libxos.so']:
            directory = self.work / ('missing-' + missing);self.fixture(directory)
            (directory / missing).unlink()
            result = self.run_probe(directory)
            self.assertEqual(result.returncode, 1)
            self.assertIn('DLOPEN_FAIL', result.stderr)
            self.assertNotIn('PASS_', result.stdout)

    def test_relative_path_rejected(self):
        result = self.run_probe('relative')
        self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
