"""Completed-0199 evidence only, with exclusive publication and no state effects."""
from pathlib import Path
import os,re,shutil,sys,tarfile,unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/observations'))
import test_hal_evidence0198 as prior
if os.environ.get('XAIRDROP_REQUIRE_MKSH')=='1' and not shutil.which('mksh'):raise RuntimeError('mksh required')
class SuccessEvidenceTests(prior.CollectorTests):
    def setUp(self):
        super().setUp()
        (self.state/'phase').write_text('restored\n');(self.module/'module.prop').write_text('id=xairdrop17_cycle0195\nversionCode=199\n')
        self.command('cmd',r'''python3 -c 'import os;assert os.readlink("/proc/self/fd/1").startswith("pipe:")' || exit 99
[ "$*" = 'wifi status' ] || { echo FORBIDDEN >&2;exit 99; }
echo 'Wifi is enabled';echo 'Wifi is connected to fixture' ''')
        src=(ROOT/'tools/device/popsicle-success-evidence-0200.sh').read_text().replace('PATH=/system/bin:/system/xbin',f'PATH={self.bin}:/usr/bin:/bin')
        for cmd in ['dumpsys','logcat','cmd']:src=src.replace('/system/bin/'+cmd,str(self.bin/cmd))
        src=re.sub(r'/data/adb|/data/local/tmp|/sdcard/Download|/dev/xairdrop17-wlan-trial.lock|/proc/uptime|/proc/sys/|/sys/module/',lambda m:str(self.root)+m.group(),src)
        self.script.write_text(src);self.output=self.root/'sdcard/Download/xairdrop-0200-evidence.tar.gz'
    def test_completed_version_gate_and_exclusive_output(self):
        (self.state/'phase').write_text('done:hals-stop\n');self.assertNotEqual(self.run_probe().returncode,0);self.assertFalse(self.output.exists())
        (self.state/'phase').write_text('restored\n');(self.module/'module.prop').write_text('versionCode=197\n');self.assertNotEqual(self.run_probe().returncode,0)
        (self.module/'module.prop').write_text('versionCode=199\n');self.output.write_bytes(b'preserve previous');self.assertNotEqual(self.run_probe().returncode,0);self.assertEqual(self.output.read_bytes(),b'preserve previous')
        self.output.unlink();self.output.symlink_to(self.state/'commands.log');b=(self.state/'commands.log').read_bytes();self.assertNotEqual(self.run_probe().returncode,0);self.assertEqual((self.state/'commands.log').read_bytes(),b)
    def test_current_status_captured_and_temporary_archive_cleaned(self):
        r=self.run_probe();self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        with tarfile.open(self.output) as t:self.assertIn(b'CAPTURE_END:wifi-status:rc=0',t.extractfile('./current-wifi-status.txt').read())
        self.assertEqual(list((self.root/'data/local/tmp').iterdir()),[])
    def test_lock_appearing_after_capture_prevents_publication(self):
        self.command('logcat',f"mkdir {self.root}/dev/xairdrop17-wlan-trial.lock;echo WifiService")
        self.assertNotEqual(self.run_probe().returncode,0);self.assertFalse(self.output.exists())
@unittest.skipUnless(shutil.which('mksh'),'mksh required in CI')
class MkshSuccessEvidenceTests(SuccessEvidenceTests):SHELL='mksh'
if __name__=='__main__':unittest.main()
