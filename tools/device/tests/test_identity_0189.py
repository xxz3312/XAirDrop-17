"""Host filesystem/command fixtures, never phone execution or ELF acceptance."""
import copy
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/kernel'))
import stock_cnss_identity as identity

class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.bin=self.root/'bin';self.bin.mkdir()
        self.profile=json.loads((ROOT/'kernel/abi/popsicle-pair-deployment.json').read_text())
        self.put('proc/sys/kernel/random/boot_id','12345678-1234-1234-1234-123456789abc\n')
        self.put('dev/block/by-name/boot_a','fixture boot')
        self.profile['boot_sha256']=self.digest('dev/block/by-name/boot_a')
        for m in identity.MODULES:
            self.put(f'vendor/lib/modules/{m}.ko',m+' fixture file')
            self.put(f'sys/module/{m}/initstate','live\n')
            self.put(f'sys/module/{m}/notes/.note.gnu.build-id',m+' fixture note')
            self.profile['stock'][m]={'sha256':self.digest(f'vendor/lib/modules/{m}.ko'),
                'note_sha256':self.digest(f'sys/module/{m}/notes/.note.gnu.build-id')}
        self.put('kernel/abi/popsicle-pair-deployment.json',json.dumps(self.profile))
        self.command('id','echo "${FIXTURE_UID:-0}"')
        self.command('uname',f'case "$1" in -r) echo {self.profile["kernel_release"]};; -m) echo aarch64;; *) exit 1;; esac')
        self.command('getprop',f'''case "$1" in
ro.product.device) echo popsicle;;
ro.build.version.incremental) echo {self.profile['firmware']};;
ro.boot.slot_suffix) echo _a;;
sys.boot_completed) echo 1;;
*) exit 1;; esac''')
        for name in ['insmod','rmmod','reboot','svc','cmd','start','stop','setprop','mount','rm','mv','cp','sync']:
            self.command(name,'echo FORBIDDEN >&2; exit 99')
        source=(ROOT/'tools/device/popsicle-identity-0189.sh').read_text()
        source=source.replace('PATH=/system/bin:/system/xbin',f'PATH={self.bin}:/usr/bin:/bin')
        source=re.sub(r'/proc/sys/|/dev/block/|/sys/module/|/data/adb/|/\$area/lib/',
                      lambda m:str(self.root)+m.group(),source)
        # A host regular-file fixture stands in for an Android boot block device.
        source=source.replace('[ -b "$boot" ]','[ -f "$boot" ]')
        self.script=self.root/'probe.sh';self.script.write_text(source)

    def put(self,path,content):
        p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
    def digest(self,path):return hashlib.sha256((self.root/path).read_bytes()).hexdigest()
    def command(self,name,body):
        p=self.bin/name;p.write_text('#!/bin/sh\n'+body+'\n');p.chmod(0o755)
    def run_probe(self,*args,**env):
        return subprocess.run(['sh',str(self.script),*args],capture_output=True,env=dict(os.environ,**env))
    def evaluate(self,raw):
        with patch.object(identity,'ROOT',self.root):return identity.evaluate(raw)
    def capture(self):
        r=self.run_probe();self.assertEqual(r.returncode,0,r.stderr);return r.stdout
    def edit(self,raw,key,value):
        f=identity.parse(raw);f[key]=value
        return ''.join(k+'\t'+v+'\n' for k,v in f.items()).encode()

    def test_actual_collector_read_only_and_matched_fixture_has_no_authority(self):
        before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        r=self.run_probe();self.assertEqual(r.returncode,0,r.stderr)
        after={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after);self.assertNotIn(b'FORBIDDEN',r.stderr)
        a=self.evaluate(r.stdout);self.assertEqual(a['status'],'CAPTURED_STOCK_IDENTITY_MATCH_ONLY')
        for key in ['load_authorized','runtime_certified','deployment_bundle_created','phone_execution_independently_witnessed']:
            self.assertIs(a[key],False)

    def test_capture_io_failure_and_root_requirement(self):
        self.command('sha256sum','exit 1')
        r=self.run_probe();self.assertNotEqual(r.returncode,0)
        self.assertIn(b'capture_status\tCAPTURE_INCOMPLETE',r.stdout)
        self.assertEqual(self.evaluate(r.stdout)['status'],'IDENTITY_MISMATCH_BLOCKED')
        r=self.run_probe(FIXTURE_UID='2000');self.assertNotEqual(r.returncode,0)
        with self.assertRaises(ValueError):self.evaluate(r.stdout)

    def test_no_apply_or_other_action_is_accepted(self):
        for args in [('apply',),('check',),('backup',),('anything','else')]:
            r=self.run_probe(*args);self.assertEqual(r.returncode,2);self.assertEqual(r.stdout,b'')

    def test_identity_changes_are_blocked(self):
        raw=self.capture()
        for key,value in [('device','other'),('firmware','other'),('kernel','other'),
                          ('slot','_c'),('boot_completed','0'),('uid','2000'),
                          ('boot_id','invalid'),('boot_id.after','00000000-0000-0000-0000-000000000000'),
                          ('firmware.after','other'),('slot.after','_b'),('boot_sha256','0'*64),
                          ('cnss2.note_sha256','0'*64),('qca_cld3_peach_v2.initstate','coming'),
                          ('cnss2.vendor.sha256','0'*64),('wonder.loaded','1'),
                          ('xairdrop17-stockcnss-transaction.present','1')]:
            with self.subTest(key=key):
                self.assertEqual(self.evaluate(self.edit(raw,key,value))['status'],'IDENTITY_MISMATCH_BLOCKED')

    def test_missing_loaded_module_or_conflicting_stock_file(self):
        (self.root/'sys/module/cnss2').rename(self.root/'sys/module/absent-cnss2')
        self.assertIn('cnss2.loaded',self.evaluate(self.capture())['mismatched_fields'])
        self.put('vendor_dlkm/lib/modules/qca_cld3_peach_v2.ko','conflicting file')
        self.assertIn('qca_cld3_peach_v2.vendor_dlkm.sha256',self.evaluate(self.capture())['mismatched_fields'])
        (self.root/'vendor/lib/modules/cnss2.ko').unlink()
        self.assertIn('cnss2.stock_file_missing',self.evaluate(self.capture())['mismatched_fields'])

    def test_ambiguous_malformed_or_incomplete_capture_rejected(self):
        raw=self.capture()
        for bad in [raw+b'uid\t0\n',raw+b'unknown\t1\n',raw.replace(b'uid\t0\n',b''),
                    raw+b'bad\tx\textra\n',raw+b'bad\t\n',b'\xff',b'x'*32769,
                    self.edit(raw,'cnss2.vendor.present','2')]:
            with self.subTest(raw=bad[:30]),self.assertRaises((ValueError,UnicodeError)):self.evaluate(bad)

if __name__=='__main__':unittest.main()
