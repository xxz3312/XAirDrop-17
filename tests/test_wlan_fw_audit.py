"""Exercise the collector with a private Android filesystem fixture, no device access."""
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/device/popsicle-wlan-fw-audit.sh'

class FirmwareCollectorTests(unittest.TestCase):
    def test_collects_deduplicates_bounds_and_rejects_outside_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bindir = root / 'bin'
            bindir.mkdir()
            commands = {
                'id': 'if [ "$1" = -u ]; then echo 0; else echo fixture-root; fi',
                'getprop': 'case "$1" in ro.product.device) echo popsicle;; ro.build.version.incremental) echo OS4.0.5.0.XPBCNXM;; esac',
                'getenforce': 'echo Enforcing',
                'ip': 'echo fixture-wlan0',
                'dmesg': 'echo "cnss: firmware amss.bin fixture only"',
            }
            for name, body in commands.items():
                p = bindir / name
                p.write_text('#!/bin/sh\n' + body + '\n')
                p.chmod(0o700)
            fw = root / 'vendor/firmware'
            fw.mkdir(parents=True)
            payload = b'firmware fixture, not executable\n'
            (fw / 'amss.bin').write_bytes(payload)
            (fw / 'amss-duplicate.bin').symlink_to(fw / 'amss.bin')
            (root / 'outside.bin').write_bytes(b'outside roots')
            (fw / 'amss-outside.bin').symlink_to(root / 'outside.bin')
            with (fw / 'amss-large.bin').open('wb') as stream:
                stream.truncate(67108865)
            mod = root / 'vendor_dlkm/lib/modules'
            mod.mkdir(parents=True)
            (mod / 'qca_cld3_peach_v2.ko').write_bytes(b'changed stock module')
            proc = root / 'proc'
            proc.mkdir()
            (proc / 'modules').write_text('qca_cld3_peach_v2 fixture\n')
            # Relocate all Android filesystem roots, including allow-list patterns.
            code = re.sub(r'/(?:vendor_dlkm|odm_dlkm|system_dlkm|vendor|odm|sys|proc|sdcard|data|mnt/vendor)(?=[/\s])',
                          lambda m: str(root) + m[0], SCRIPT.read_text())
            script = root / 'collect.sh'
            script.write_text(code)
            env = dict(os.environ, PATH=str(bindir) + ':/usr/bin:/bin')
            run = subprocess.run(['sh', str(script)], env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            reports = list((root / 'sdcard/Download').glob('*.tar.gz'))
            self.assertEqual(len(reports), 1)
            with tarfile.open(reports[0]) as archive:
                manifest = archive.extractfile('./manifest.tsv').read().decode()
                result = archive.extractfile('./result.txt').read().decode()
                blobs = [m for m in archive.getmembers() if m.isfile() and m.name.startswith('./files/')]
                self.assertEqual(len(blobs), 1)
                self.assertEqual(archive.extractfile(blobs[0]).read(), payload)
                self.assertIn('DUPLICATE', manifest)
                self.assertIn('OUTSIDE_FIRMWARE_MODULE_ROOTS', manifest)
                self.assertIn('SIZE_LIMIT', manifest)
                self.assertIn('STOCK_MODULE_HASH_CHANGED', manifest)
                self.assertIn('firmware_files=1\n', result)
                self.assertIn('stock_module_files=0\n', result)
                self.assertIn('state_unchanged=1\n', result)
                self.assertIn('firmware_passthru_support=UNVERIFIED', result)
            self.assertEqual((fw / 'amss.bin').read_bytes(), payload)

    def test_changed_firmware_stops_before_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, body in [('id', 'echo 0'), ('getprop', 'case "$1" in ro.product.device) echo popsicle;; *) echo CHANGED;; esac')]:
                p = root / name
                p.write_text('#!/bin/sh\n' + body + '\n')
                p.chmod(0o700)
            run = subprocess.run(['sh', str(SCRIPT)], env=dict(os.environ, PATH=tmp + ':/usr/bin:/bin'), capture_output=True, text=True, timeout=5)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn('Firmware changed', run.stdout)
