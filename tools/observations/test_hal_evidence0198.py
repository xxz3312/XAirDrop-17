"""Actual read-only collector, synthetic private files and query tools."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]

class CollectorTests(unittest.TestCase):
    SHELL='sh'
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.bin=self.root/'bin';self.bin.mkdir()
        self.state=self.root/'data/adb/xairdrop17-cycle0195-transaction'
        self.module=self.root/'data/adb/modules/xairdrop17_cycle0195'
        self.state.mkdir(parents=True);self.module.mkdir(parents=True)
        (self.root/'data/local/tmp').mkdir(parents=True);(self.root/'sdcard/Download').mkdir(parents=True)
        (self.root/'dev').mkdir();(self.root/'proc/sys/kernel/random').mkdir(parents=True)
        (self.root/'proc/uptime').write_text('1234 1234\n');(self.root/'proc/sys/kernel/random/boot_id').write_text('fixture boot\n')
        for name in ['phase','boot-id','manifest.sha256','wifi.before','scan.before','hals','interface.before','commands.log','kernel.before.log','kernel.after.log']:(self.state/name).write_text('preserve '+name+'\n')
        for name in ['module.prop','deployment.tsv','SHA256SUMS']:(self.module/name).write_text('installed fixture '+name+'\n')
        for m in ['cnss2','qca_cld3_peach_v2']:
            d=self.root/'sys/module'/m;(d/'notes').mkdir(parents=True);(d/'initstate').write_text('live\n');(d/'notes/.note.gnu.build-id').write_text(m+' note')
        self.command('id','echo 0')
        self.command('stat','if [ "$2" = %u ];then echo 0;else exec /usr/bin/stat "$@";fi')
        self.command('getprop','echo running')
        self.command('dumpsys',r'''python3 -c 'import os;assert os.readlink("/proc/self/fd/1").startswith("pipe:")' || exit 99
echo "DUMP:$*"
[ "${FAIL_QUERY:-0}" != 1 ] || exit 7''')
        self.command('logcat','echo "WifiService test log";echo "irrelevant private application log";exit 0')
        for name in ['insmod','rmmod','start','stop','svc','cmd','setprop','mount','reboot']:self.command(name,'echo FORBIDDEN >&2;exit 99')
        src=(ROOT/'tools/device/popsicle-hal-evidence-0198.sh').read_text().replace('PATH=/system/bin:/system/xbin',f'PATH={self.bin}:/usr/bin:/bin')
        for cmd in ['dumpsys','logcat']:src=src.replace('/system/bin/'+cmd,str(self.bin/cmd))
        src=re.sub(r'/data/adb|/data/local/tmp|/sdcard/Download|/dev/xairdrop17-wlan-trial.lock|/proc/uptime|/proc/sys/|/sys/module/',lambda m:str(self.root)+m.group(),src)
        self.script=self.root/'collector.sh';self.script.write_text(src)
        self.output=self.root/'sdcard/Download/xairdrop-0198-evidence.tar.gz'
    def command(self,name,body):
        p=self.bin/name;p.write_text('#!/bin/sh\n'+body+'\n');p.chmod(0o755)
    def contents(self,path):return {p.name:p.read_bytes() for p in path.iterdir() if p.is_file()}
    def run_probe(self,**env):
        r=subprocess.run([self.SHELL,str(self.script)],capture_output=True,env=dict(os.environ,**env),timeout=15)
        self.assertNotIn(b'FORBIDDEN',r.stdout+r.stderr);return r
    def test_export_preserves_sources_and_omits_unrelated_logs_and_driver_binaries(self):
        state=self.contents(self.state);module=self.contents(self.module)
        (self.state/'qca_cld3_peach_v2.ko').write_text('DO NOT EXPORT DRIVER')
        r=self.run_probe();self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn(b'EVIDENCE_EXPORTED:',r.stdout)
        for f,data in state.items():self.assertEqual((self.state/f).read_bytes(),data)
        self.assertEqual(self.contents(self.module),module)
        with tarfile.open(self.output) as t:
            names=t.getnames();self.assertNotIn('./qca_cld3_peach_v2.ko',names)
            self.assertIn('./commands.log',names);self.assertIn('./framework-wifi.txt',names)
            log=t.extractfile('./framework-logcat.txt').read();self.assertIn(b'WifiService',log);self.assertNotIn(b'irrelevant private',log)
            self.assertIn(b'CAPTURE_END:wifi:rc=0',t.extractfile('./framework-wifi.txt').read())
        self.assertEqual(list((self.root/'data/local/tmp').iterdir()),[])
    def test_missing_required_symlink_or_active_lock_blocks_without_export(self):
        f=self.state/'phase';old=f.read_bytes();f.unlink();r=self.run_probe();self.assertNotEqual(r.returncode,0);self.assertFalse(self.output.exists())
        f.symlink_to(self.state/'commands.log');r=self.run_probe();self.assertNotEqual(r.returncode,0);self.assertFalse(self.output.exists());f.unlink();f.write_bytes(old)
        lock=self.root/'dev/xairdrop17-wlan-trial.lock';lock.mkdir();r=self.run_probe();self.assertNotEqual(r.returncode,0);self.assertFalse(self.output.exists());self.assertTrue(lock.exists())
    def test_query_failure_is_kept_as_evidence_and_does_not_change_original_state(self):
        before=self.contents(self.state);r=self.run_probe(FAIL_QUERY='1');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(self.contents(self.state),before)
        with tarfile.open(self.output) as t:self.assertIn(b'CAPTURE_END:wifi:rc=7',t.extractfile('./framework-wifi.txt').read())

@unittest.skipUnless(shutil.which('mksh'),'mksh required in CI')
class MkshCollectorTests(CollectorTests):SHELL='mksh'

if __name__=='__main__':unittest.main()
