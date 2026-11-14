"""Exact-index verified adapter predicates only; original files/effects unchanged."""
import hashlib,os,re,shutil,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/hal0201'))
import test_hal0201 as prior
if os.environ.get('XAIRDROP_REQUIRE_MKSH')=='1' and not shutil.which('mksh'):raise RuntimeError('mksh required')
class DiagnosticTests(unittest.TestCase):
    SHELL='sh'
    def setUp(self):
        b=self.b=prior.HalTests();b.SHELL=self.SHELL;b.setUp();self.addCleanup(b.doCleanups);b.archive();a=self.a=b.a
        s=(ROOT/'tools/device/popsicle-preflight-0202.sh').read_text()
        s=s.replace('5ade011bae0bd7ca5ffe4a959f4ea9916cecddd60c977ec26f353ec9a46bb05f',hashlib.sha256((a.bundle/'SHA256SUMS').read_bytes()).hexdigest())
        s=s.replace('PATH=/system/bin:/system/xbin',f'PATH={a.bin}:/usr/bin:/bin')
        for cmd in ['cmd','timeout']:s=s.replace('/system/bin/'+cmd,str(a.bin/cmd))
        s=re.sub(r'/data(?=[ /\n)])|/data/adb|/proc/sys/|/sys/class/net/|/dev/(?!null)',lambda m:str(a.root)+m.group(),s)
        self.script=a.root/'diag.sh';self.script.write_text(s)
        self.saved=a.a.a.files(a.root)
    def run_diag(self,**env):
        r=subprocess.run([self.SHELL,str(self.script)],env=dict(os.environ,**env),capture_output=True,timeout=30)
        self.assertEqual(self.a.effects(),[]);self.assertEqual(self.a.a.a.files(self.a.root),self.saved)
        return r
    def test_pass_lists_predicates_without_any_snapshot_or_effect(self):
        r=self.run_diag();self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn(b'READONLY_PREDICATE:cy_observation_capabilities:rc=0',r.stdout)
        self.assertFalse(self.a.state.exists());self.b.history()
    def test_unsupported_help_and_missing_timeout_are_visible_not_reboot_advice(self):
        r=self.run_diag(NO_SCAN_HELP='1');self.assertNotEqual(r.returncode,0)
        self.assertIn(b'WIFI_HELP:rc=7',r.stdout);self.assertNotIn(b'REBOOT',r.stdout)
        (self.a.bin/'timeout').unlink();self.saved=self.a.a.a.files(self.a.root)
        r=self.run_diag();self.assertNotEqual(r.returncode,0);self.assertIn(b'ANDROID_TIMEOUT_MISSING',r.stdout);self.assertIn(b'DIRECT_WIFI_STATUS:rc=0',r.stdout)
    def test_checksum_change_blocks_before_source(self):
        f=self.a.bundle/'SHA256SUMS';f.write_text(f.read_text()+'changed');self.saved=self.a.a.a.files(self.a.root)
        r=self.run_diag();self.assertNotEqual(r.returncode,0);self.assertNotIn(b'READONLY_0201_PREFLIGHT_DIAGNOSTICS_BEGIN',r.stdout)
    def test_existing_state_is_reported_and_never_modified(self):
        self.a.state.mkdir();(self.a.state/'phase').write_text('candidate-observing\n');self.saved=self.a.a.a.files(self.a.root)
        r=self.run_diag();self.assertNotEqual(r.returncode,0);self.assertIn(b'CURRENT_phase:candidate-observing',r.stdout)
@unittest.skipUnless(shutil.which('mksh'),'mksh required in CI')
class MkshDiagnosticTests(DiagnosticTests):SHELL='mksh'
if __name__=='__main__':unittest.main()
