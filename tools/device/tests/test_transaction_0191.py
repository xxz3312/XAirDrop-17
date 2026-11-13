"""Read-only transaction fixtures; no real phone, module or archive operations."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/kernel'))
import stock_cnss_transaction as transaction
if os.environ.get('XAIRDROP_REQUIRE_MKSH')=='1' and not shutil.which('mksh'):
    raise RuntimeError('mksh required in CI')

class TransactionTests(unittest.TestCase):
    SHELL='sh'
    PROBE='popsicle-transaction-0191.sh'
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.bin=self.root/'bin';self.bin.mkdir()
        self.state=self.root/'data/adb/xairdrop17-stockcnss-transaction';self.state.mkdir(parents=True)
        self.boot='12345678-1234-1234-1234-123456789abc'
        self.put('proc/sys/kernel/random/boot_id',self.boot+'\n')
        self.files={'boot-id':self.boot+'\n','phase':'backup-only\n','wifi.before':'1\n',
                    'hals':'vendor.wifi_hal_legacy\n','qca_cld3_peach_v2.ko':'stock fixture bytes'}
        checker=json.loads((ROOT/'kernel/abi/popsicle-stock-cnss-checker-base-0136.json').read_text())
        self.files['manifest.sha256']=checker['files']['deployment.tsv']+'\n'
        for n,v in self.files.items():(self.state/n).write_text(v)
        profile=json.loads((ROOT/'kernel/abi/popsicle-pair-deployment.json').read_text())
        profile['stock']['qca_cld3_peach_v2']['sha256']=hashlib.sha256(self.files['qca_cld3_peach_v2.ko'].encode()).hexdigest()
        self.put('kernel/abi/popsicle-pair-deployment.json',json.dumps(profile))
        self.put('kernel/abi/popsicle-stock-cnss-checker-base-0136.json',json.dumps(checker))
        self.command('id','echo "${FIXTURE_UID:-0}"')
        self.command('stat','if [ "$2" = %u ];then echo "${FIXTURE_OWNER:-0}";else exec /usr/bin/stat "$@";fi')
        for name in ['rm','mv','cp','rmmod','insmod','reboot','svc','cmd','start','stop','sync']:
            self.command(name,'echo FORBIDDEN >&2;exit 99')
        source=(ROOT/'tools/device'/self.PROBE).read_text()
        source=source.replace('PATH=/system/bin:/system/xbin',f'PATH={self.bin}:/usr/bin:/bin')
        source=re.sub(r'/data(?=[ /\n)])|/data/adb|/proc/sys/',lambda m:str(self.root)+m.group(),source)
        self.script=self.root/'probe.sh';self.script.write_text(source)
    def put(self,name,value):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value)
    def command(self,name,body):
        p=self.bin/name;p.write_text('#!/bin/sh\n'+body+'\n');p.chmod(0o755)
    def run_probe(self,*args,**env):
        return subprocess.run([self.SHELL,str(self.script),*args],env=dict(os.environ,**env),capture_output=True,timeout=10)
    def classify(self,raw):
        with patch.object(transaction,'ROOT',self.root):return transaction.classify(raw)
    def edit(self,raw,key,value):
        fields=dict(line.split('\t',1) for line in raw.decode().splitlines());fields[key]=value
        return ''.join(k+'\t'+v+'\n' for k,v in fields.items()).encode()
    def assert_no_authority(self,r):
        for key in ['archive_authorized','replay_authorized','load_authorized','runtime_certified']:self.assertIs(r[key],False)

    def test_same_prior_boot_and_absence_are_read_only_observations(self):
        before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        c=self.run_probe();self.assertEqual(c.returncode,0,c.stderr)
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        r=self.classify(c.stdout);self.assertEqual(r['status'],'SAME_BOOT_TRANSACTION_PRESERVED');self.assert_no_authority(r)
        (self.state/'boot-id').write_text('00000000-0000-0000-0000-000000000000\n')
        r=self.classify(self.run_probe().stdout);self.assertEqual(r['status'],'PRIOR_BOOT_RECORD_ONLY');self.assert_no_authority(r)
        shutil.rmtree(self.state)
        r=self.classify(self.run_probe().stdout);self.assertEqual(r['status'],'NO_TRANSACTION_RECORDED');self.assert_no_authority(r)

    def test_symlink_and_untrusted_permissions_never_followed(self):
        phase=self.state/'phase';phase.unlink();phase.symlink_to('/etc/passwd')
        c=self.run_probe();self.assertNotEqual(c.returncode,0);self.assertNotIn(b'root:',c.stdout)
        self.assertEqual(self.classify(c.stdout)['status'],'TRANSACTION_RECORD_BLOCKED')
        phase.unlink();phase.write_text('active\n');self.state.chmod(0o777)
        c=self.run_probe();self.assertNotEqual(c.returncode,0);self.assertIn(b'transaction.access\tREJECTED',c.stdout)
        self.state.chmod(0o755)
        c=self.run_probe(FIXTURE_OWNER='1000');self.assertNotEqual(c.returncode,0)
        self.assertEqual(self.classify(c.stdout)['status'],'TRANSACTION_RECORD_BLOCKED')
        self.state.rename(self.root/'retained-outside')
        self.state.symlink_to(self.root/'retained-outside',target_is_directory=True)
        c=self.run_probe();self.assertNotEqual(c.returncode,0)
        self.assertNotIn(b'phase.value',c.stdout)
        self.assertEqual(self.classify(c.stdout)['status'],'TRANSACTION_RECORD_BLOCKED')

    def test_missing_oversized_and_fifo_fields_rejected_without_blocking(self):
        phase=self.state/'phase'
        for kind in ['missing','oversized','fifo']:
            if phase.exists():phase.unlink()
            if kind=='oversized':phase.write_text('x'*257)
            if kind=='fifo':os.mkfifo(phase)
            c=self.run_probe();self.assertNotEqual(c.returncode,0)
            self.assertEqual(self.classify(c.stdout)['status'],'TRANSACTION_RECORD_BLOCKED')

    def test_mutations_preserve_state_and_block_classification(self):
        raw=self.run_probe().stdout
        for key,value in [('boot_id.after','00000000-0000-0000-0000-000000000000'),
                          ('transaction.identity.after','0:0'),('phase.after.value','active'),
                          ('phase.value','unknown'),('manifest.sha256.value','0'*64),
                          ('backup.sha256','0'*64),('hals.sha256','INVALID'),
                          ('phase.new.status','OK'),('uid','2000')]:
            with self.subTest(key=key):
                r=self.classify(self.edit(raw,key,value));self.assertEqual(r['status'],'TRANSACTION_RECORD_BLOCKED');self.assert_no_authority(r)

    def test_partial_journal_and_empty_hals_block(self):
        (self.state/'phase.new').write_text('intent:remove-wlan\n')
        r=self.classify(self.run_probe().stdout);self.assertIn('unfinished_journal_preserved',r['reasons'])
        (self.state/'hals').write_text('')
        self.assertNotEqual(self.run_probe().returncode,0)

    def test_action_arguments_and_nonroot_are_rejected(self):
        for action in ['archive','apply','delete','status']:
            c=self.run_probe(action);self.assertEqual(c.returncode,2);self.assertEqual(c.stdout,b'')
        c=self.run_probe(FIXTURE_UID='2000');self.assertNotEqual(c.returncode,0)
        with self.assertRaises(ValueError):self.classify(c.stdout)

    def test_silently_suppressed_digest_cannot_claim_complete(self):
        source=self.script.read_text();a=source.index('xt_digest() {');b=source.index('\nxt_emit schema',a)
        self.script.write_text(source[:a]+'xt_digest() { :; }\n'+source[b:])
        c=self.run_probe();self.assertNotEqual(c.returncode,0)
        self.assertIn(b'capture_status\tCAPTURE_INCOMPLETE',c.stdout)
        with self.assertRaises(ValueError):self.classify(c.stdout)

    def test_malformed_ambiguous_and_missing_fields_rejected(self):
        raw=self.run_probe().stdout
        for bad in [raw+b'uid\t0\n',raw+b'extra\t1\n',raw.replace(b'uid\t0\n',b''),b'\xff',b'x'*16385]:
            with self.assertRaises((ValueError,UnicodeError)):self.classify(bad)

@unittest.skipUnless(shutil.which('mksh'),'mksh unavailable locally; mandatory in CI')
class TransactionMkshTests(TransactionTests):
    SHELL='mksh'

if __name__=='__main__':unittest.main()
