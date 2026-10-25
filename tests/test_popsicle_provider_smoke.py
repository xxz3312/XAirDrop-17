"""Mocked device tests: no real kernel module commands are ever invoked."""
import hashlib
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

PROVIDER = 'opairshare_wonder_provider'
PROBE = 'opairshare_route_b_probe'


class ProviderSmokeTests(unittest.TestCase):
    def run_case(self, existing=False, **flags):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        modules = root / 'modules'
        modules.mkdir()
        (modules / 'qca_cld3_peach_v2').mkdir()
        device = root / 'wonder-device'
        if existing:
            device.mkdir()
        binary = root / 'bin'
        binary.mkdir()
        trace = root / 'trace'
        code = (Path(__file__).resolve().parents[1] /
                'tools/device/popsicle-provider-smoke.sh').read_text()
        code = code.replace('/sys/module/', str(modules) + '/')
        code = code.replace('/sys/bus/platform/devices/qcom,cnss-vendor-wlan-wonder', str(device))
        code = code.replace('/proc/sys/net/wonder/wonder_enable', str(root / 'absent-node'))
        code = code.replace('/data/local/tmp', str(root / 'tmp'))
        code = code.replace('/sdcard/Download', str(root / 'reports'))
        for name, original in [
            (PROVIDER, '8b1c55b4d98d2867209671e47b4e2b676e64d19553f7e2bf611201dadfc4ab6a'),
            (PROBE, '158e250cbef5d64f906758bdb2fea9ca755a9c4aa9ca6c2748ea8e5171ef8ade')]:
            payload = ('mock ' + name).encode()
            (root / (name + '.ko')).write_bytes(payload)
            code = code.replace(original, hashlib.sha256(payload).hexdigest())
        (root / 'run-test.sh').write_text(code)
        commands = {
            'id': 'echo 0',
            'uname': 'echo 6.12.69-android16-6-g43b5ab7e247d-abogki558343811-4k',
            'getprop': 'case "$1" in ro.product.device) echo popsicle;; *) echo "${FIRMWARE:-OS4.0.5.0.XPBCNXM}";; esac',
            'dmesg': 'echo "opairshare mock log"',
            'insmod': 'n=$(basename "$1" .ko); echo "load:$n" >> "$TRACE"; '
                      '[ "${FAIL_LOAD:-none}" != "$n" ] || exit 1; mkdir "$MODULES/$n"; '
                      'if [ "$n" = opairshare_wonder_provider ]; then mkdir "$DEVICE"; fi',
            'rmmod': 'echo "unload:$1" >> "$TRACE"; [ "${FAIL_UNLOAD:-none}" != "$1" ] || exit 1; '
                     'rmdir "$MODULES/$1"; '
                     'if [ "$1" = opairshare_wonder_provider ]; then rmdir "$DEVICE"; fi',
        }
        for name, body in commands.items():
            p = binary / name
            p.write_text('#!/bin/sh\n' + body + '\n')
            p.chmod(0o700)
        env = dict(os.environ, PATH=str(binary) + ':' + os.environ['PATH'],
                   MODULES=str(modules), DEVICE=str(device), TRACE=str(trace), **flags)
        result = subprocess.run(['sh', root / 'run-test.sh'], env=env,
                                capture_output=True, text=True, timeout=10)
        calls = trace.read_text().splitlines() if trace.exists() else []
        archives = list((root / 'reports').glob('*.tar.gz'))
        self.assertEqual(len(archives), 1, result.stdout + result.stderr)
        with tarfile.open(archives[0]) as t:
            self.assertFalse(any(n.endswith('.ko') for n in t.getnames()))
            report = t.extractfile('result.txt').read().decode()
        return result, calls, report, device.exists()

    def test_success_unloads_in_dependency_order(self):
        r, calls, report, device = self.run_case()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls, ['load:' + PROVIDER, 'load:' + PROBE,
                                 'unload:' + PROBE, 'unload:' + PROVIDER])
        self.assertIn('PASS_PROVIDER_PROBE_REGISTER_UNREGISTER', report)
        self.assertFalse(device)

    def test_probe_load_failure_still_unloads_provider(self):
        r, calls, _, device = self.run_case(FAIL_LOAD=PROBE)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(calls, ['load:' + PROVIDER, 'load:' + PROBE, 'unload:' + PROVIDER])
        self.assertFalse(device)

    def test_probe_unload_failure_preserves_provider(self):
        r, calls, report, device = self.run_case(FAIL_UNLOAD=PROBE)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(calls, ['load:' + PROVIDER, 'load:' + PROBE, 'unload:' + PROBE])
        self.assertIn('provider_still_owned=1', report)
        self.assertIn('probe_still_owned=1', report)
        self.assertTrue(device)

    def test_provider_unload_failure_is_not_success(self):
        r, _, report, device = self.run_case(FAIL_UNLOAD=PROVIDER)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('provider_still_owned=1', report)
        self.assertIn('FAIL_OR_INTERRUPTED', report)
        self.assertTrue(device)

    def test_existing_device_or_wrong_firmware_stops_before_load(self):
        for options in [{'existing': True}, {'FIRMWARE': 'other'}]:
            r, calls, _, _ = self.run_case(**options)
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
