"""Regression of the phone-observed restart at sample 7, before any driver command."""
from pathlib import Path
import os
import shutil
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/diagnostics'))
import test_cycle0197 as fixtures

if os.environ.get('XAIRDROP_REQUIRE_MKSH')=='1' and not shutil.which('mksh'):
    raise RuntimeError('mksh is required in CI')

class RestartObservationTests(unittest.TestCase):
    SHELL='sh'
    def test_sample_7_restart_with_both_toggles_off_blocks_before_removal_and_recovers(self):
        a=fixtures.UpgradeTests();a.SHELL=self.SHELL;a.setUp();self.addCleanup(a.doCleanups)
        a.archive()
        framework=a.root/'framework.py';s=framework.read_text()
        needle="if args==['wifi','status']:\n"
        assert needle in s
        s=s.replace(needle,needle+''' if (r/'hal').read_text()=='stopped':
  count=r/'stopped-status-count'
  n=int(count.read_text())+1 if count.exists() else 1;count.write_text(str(n))
  if n==8:(r/'hal').write_text('running')
''');framework.write_text(s)
        r=a.run_probe('cycle');a.blocked(r)
        self.assertIn(b'GATE_BLOCKED:hal-sample-7:hal:rc=1',r.stdout+r.stderr)
        self.assertIn(b'STAGE0197_FAILURE_FRAMEWORK_BASELINE_RESTORED_ONLY',r.stdout)
        self.assertEqual(a.native(),[])
        self.assertEqual((a.state/'phase').read_text(),'done:hals-stop\n')
        self.assertEqual(a.wifi.read_text(),'1');self.assertEqual(a.scan.read_text(),'enabled');self.assertEqual(a.hal.read_text(),'running')
        before=a.effects();a.blocked(a.run_probe('cycle'));self.assertEqual(a.effects(),before)
        a.assert_history()

@unittest.skipUnless(shutil.which('mksh'),'mksh required in CI')
class MkshRestartObservationTests(RestartObservationTests):SHELL='mksh'

if __name__=='__main__':unittest.main()
