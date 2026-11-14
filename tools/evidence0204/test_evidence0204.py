"""203 success collection uses the qualified200 isolated read-only exporter."""
import os,re,shutil,sys,tarfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/observations'))
import test_hal_evidence0198 as prior
if os.environ.get('XAIRDROP_REQUIRE_MKSH')=='1' and not shutil.which('mksh'):raise RuntimeError('mksh required')
class EvidenceTests(prior.CollectorTests):
    def setUp(self):
        super().setUp();(self.state/'phase').write_text('restored\n');(self.module/'module.prop').write_text('id=xairdrop17_cycle0195\nversionCode=203\n')
        self.command('cmd',r'''python3 -c 'import os;assert os.readlink("/proc/self/fd/1").startswith("pipe:")' || exit 99
[ "$*" = 'wifi status' ] || { echo FORBIDDEN >&2;exit 99; }
echo 'Wifi is enabled';echo 'Wifi is connected to fixture' ''')
        s=(ROOT/'tools/device/popsicle-hal-scan-evidence-0204.sh').read_text().replace('PATH=/system/bin:/system/xbin',f'PATH={self.bin}:/usr/bin:/bin')
        for cmd in ['dumpsys','logcat','cmd']:s=s.replace('/system/bin/'+cmd,str(self.bin/cmd))
        s=re.sub(r'/data/adb|/data/local/tmp|/sdcard/Download|/dev/xairdrop17-wlan-trial.lock|/proc/uptime|/proc/sys/|/sys/module/',lambda m:str(self.root)+m.group(),s)
        self.script.write_text(s);self.output=self.root/'sdcard/Download/xairdrop-0204-evidence.tar.gz'
    def test_requires_completed203_and_preserves_existing_output(self):
        (self.module/'module.prop').write_text('versionCode=199\n');self.assertNotEqual(self.run_probe().returncode,0);self.assertFalse(self.output.exists())
        (self.module/'module.prop').write_text('versionCode=203\n');(self.state/'phase').write_text('candidate-observing\n');self.assertNotEqual(self.run_probe().returncode,0)
        (self.state/'phase').write_text('restored\n');self.output.write_bytes(b'keep');self.assertNotEqual(self.run_probe().returncode,0);self.assertEqual(self.output.read_bytes(),b'keep')
    def test_status_receipt_and_late_lock_refusal(self):
        r=self.run_probe();self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        with tarfile.open(self.output) as t:self.assertIn(b'CAPTURE_END:wifi-status:rc=0',t.extractfile('./current-wifi-status.txt').read())
        self.output.unlink();self.command('logcat',f'mkdir {self.root}/dev/xairdrop17-wlan-trial.lock;echo WifiService')
        self.assertNotEqual(self.run_probe().returncode,0);self.assertFalse(self.output.exists())
@unittest.skipUnless(shutil.which('mksh'),'mksh required in CI')
class MkshEvidenceTests(EvidenceTests):SHELL='mksh'
if __name__=='__main__':unittest.main()
