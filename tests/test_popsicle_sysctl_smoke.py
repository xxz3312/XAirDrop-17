"""Exercise device-script guards and cleanup with mocked module tools only."""
import hashlib
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest


class SmokeScriptTests(unittest.TestCase):
    def run_case(self, *, existing=False, corrupt=False, **flags):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        binary = root / 'bin'
        binary.mkdir()
        node, module = root / 'node', root / 'module'
        trace = root / 'trace'
        payload = b'mock module - never passed to the real insmod'
        (root / 'wonder_sysctl.ko').write_bytes(payload if not corrupt else b'corrupt')
        source = Path(__file__).resolve().parents[1] / 'tools/device/popsicle-sysctl-smoke.sh'
        script = source.read_text().replace('/proc/sys/net/wonder/wonder_enable', str(node))
        script = script.replace('/sys/module/wonder_sysctl', str(module))
        script = script.replace('/data/local/tmp', str(root / 'tmp'))
        script = script.replace('/sdcard/Download', str(root / 'reports'))
        script = script.replace('b7ac3e8dd7d3544cfdfe67ea39b3b546fcc734897fe64478f20a88893532f625',
                                hashlib.sha256(payload).hexdigest())
        (root / 'run-test.sh').write_text(script)
        commands = {
            'id': 'echo 0',
            'uname': 'echo 6.12.69-android16-6-g43b5ab7e247d-abogki558343811-4k',
            'getprop': 'case "$1" in ro.product.device) echo popsicle;; *) echo "${FIRMWARE:-OS4.0.5.0.XPBCNXM}";; esac',
            'dmesg': 'echo "mock module log"',
            'insmod': 'echo insmod >> "$TRACE"; [ "${FAIL_LOAD:-0}" = 0 ] || exit 1; '
                      'mkdir "$MODULE"; echo "${NODE_VALUE:-0}" > "$NODE"',
            'rmmod': 'echo rmmod >> "$TRACE"; [ "${FAIL_UNLOAD:-0}" = 0 ] || exit 1; '
                     'rm "$NODE"; rmdir "$MODULE"',
        }
        for name, body in commands.items():
            path = binary / name
            path.write_text('#!/bin/sh\n' + body + '\n')
            path.chmod(0o700)
        if existing:
            node.write_text('0\n')
        env = dict(os.environ, PATH=str(binary) + ':' + os.environ['PATH'],
                   TRACE=str(trace), NODE=str(node), MODULE=str(module), **flags)
        result = subprocess.run(['sh', root / 'run-test.sh'], env=env,
                                capture_output=True, text=True, timeout=10)
        calls = trace.read_text().splitlines() if trace.exists() else []
        archives = list((root / 'reports').glob('*.tar.gz'))
        self.assertEqual(len(archives), 1, result.stdout + result.stderr)
        with tarfile.open(archives[0]) as bundle:
            self.assertNotIn('wonder_sysctl.ko', bundle.getnames())
            report = bundle.extractfile('result.txt').read().decode()
        return result, calls, report, node.exists(), module.exists()

    def test_success_unloads_and_removes_node(self):
        result, calls, report, node, module = self.run_case()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(calls, ['insmod', 'rmmod'])
        self.assertIn('PASS_SYSCTL_LOAD_READ_UNLOAD', report)
        self.assertFalse(node or module)

    def test_existing_node_is_not_loaded_or_removed(self):
        result, calls, _, node, _ = self.run_case(existing=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])
        self.assertTrue(node)

    def test_wrong_firmware_and_bad_hash_stop_before_insmod(self):
        for flags in [{'FIRMWARE': 'other'}, {'corrupt': True}]:
            with self.subTest(flags=flags):
                result, calls, _, _, _ = self.run_case(**flags)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])

    def test_failed_insmod_does_not_unload_something_unowned(self):
        result, calls, report, _, _ = self.run_case(FAIL_LOAD='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, ['insmod'])
        self.assertIn('FAIL_OR_INTERRUPTED', report)

    def test_bad_node_value_still_unloads(self):
        result, calls, report, node, module = self.run_case(NODE_VALUE='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, ['insmod', 'rmmod'])
        self.assertIn('FAIL_OR_INTERRUPTED', report)
        self.assertFalse(node or module)

    def test_unload_failure_cannot_report_success(self):
        result, calls, report, node, module = self.run_case(FAIL_UNLOAD='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, ['insmod', 'rmmod'])
        self.assertIn('module_still_owned=1', report)
        self.assertIn('FAIL_OR_INTERRUPTED', report)
        self.assertTrue(node and module)


if __name__ == '__main__':
    unittest.main()
