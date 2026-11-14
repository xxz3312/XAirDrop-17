"""Help255 is valid only with semantic help and independently successful queries."""
from pathlib import Path
import os,re,shutil,subprocess,sys,unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools/hal0201'),str(ROOT/'tools/kernel')]
import test_hal0201 as prior
import stock_cnss_cycle0203 as builder
class HelpTests(prior.HalTests):
    def setUp(self):
        super().setUp();a=self.a
        p=a.bundle/'deployment.tsv';vals=dict(line.split('\t',1) for line in p.read_text().splitlines())
        vals.update(schema='8',profile='stage0203-help-compatible-hal-cycle');p.write_text(''.join(k+'\t'+v+'\n' for k,v in sorted(vals.items())))
        for source in (ROOT/'tools/device/cycle-0203').iterdir():
            s=source.read_text().replace('PATH=/system/bin:/system/xbin',f'PATH={a.bin}:/usr/bin:/bin')
            for cmd in ['cmd','svc','start','stop','insmod','rmmod','timeout']:s=s.replace('/system/bin/'+cmd,str(a.bin/cmd))
            s=re.sub(r'/data(?=[ /\n)])|/data/adb|/proc/sys/|/sys/module/|/sys/class/net/|/vendor(?:_dlkm)?/|/dev/(?!null)',lambda m:str(a.root)+m.group(),s)
            (a.bundle/source.name).write_text(s.replace('[ -b "','[ -f "'))
        fw=a.root/'framework.py';s=fw.read_text()
        old=" print('start-scan\\nlist-scan-results');sys.exit(0)"
        assert old in s
        s=s.replace(old,""" mode=os.environ.get('HELP_MODE','valid')
 text={'valid':'Wi-Fi (wifi) commands:\\n  list-scan-results\\n    Lists the latest scan results\\n  start-scan\\n    Start a new scan',
       'missing_header':'  start-scan\\n  list-scan-results',
       'missing_command':'Wi-Fi (wifi) commands:\\n  list-scan-results',
       'substring_only':'Wi-Fi (wifi) commands:\\nunknown start-scan or list-scan-results',
       'exception':'Wi-Fi (wifi) commands:\\n  start-scan\\n  list-scan-results\\nException occurred while executing help'}[mode]
 print(text);sys.exit(int(os.environ.get('HELP_RC','255')))""")
        s=s.replace("if args==['wifi','list-scan-results']:","if args==['wifi','list-scan-results']:\n if not candidate and os.environ.get('PRE_LIST_FAIL')=='1':sys.exit(255)")
        fw.write_text(s);a.integrity()
    def test_help_zero_is_accepted_with_same_required_lines(self):
        self.archive();r=self.a.run_probe('cycle',HELP_RC='0');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn(b'WIFI_HELP_VALIDATED:rc=0',r.stderr+r.stdout);self.history()
    def test_other_help_failures_and_bad_text_are_visible_before_snapshot_without_controls(self):
        self.archive();a=self.a
        cases=[{'HELP_MODE':m} for m in ['missing_header','missing_command','substring_only','exception']]
        cases += [{'HELP_RC':r} for r in ['7','124','127','137']]+[{'PRE_LIST_FAIL':'1'}]
        for env in cases:
            with self.subTest(env=env):
                r=a.run_probe('cycle',**env);a.blocked(r)
                self.assertEqual(a.effects(),[]);self.assertFalse(a.state.exists())
                self.assertIn(b'GATE_BLOCKED:preflight-observation-capabilities',r.stderr+r.stdout)
                self.assertIn(b'PRE_EFFECT_ABORT_PRESERVE_STATE_NO_WIFI_OR_DRIVER_CONTROL_THIS_RUN',r.stdout)
                self.assertNotIn(b'REBOOT_THEN',r.stdout);self.history()
    def test_snapshot_failure_keeps_residue_but_never_restores_framework_or_requests_reboot(self):
        self.archive();a=self.a;r=a.run_probe('cycle',FIXTURE_DMESG_FAIL='1');a.blocked(r)
        self.assertEqual(a.effects(),[]);self.assertTrue(list(a.root.glob('data/adb/xairdrop17-cycle0195-transaction.preparing.*')))
        self.assertIn(b'GATE_BLOCKED:cycle-snapshot',r.stdout+r.stderr);self.assertNotIn(b'REBOOT_THEN',r.stdout)
        a.blocked(a.run_probe('cycle'));self.assertEqual(a.effects(),[]);self.history()
    def test_journal_publish_failure_before_effects_does_not_mutate_framework(self):
        self.archive();a=self.a;r=a.run_probe('cycle',FIXTURE_JFAIL='prepared');a.blocked(r)
        self.assertEqual(a.effects(),[]);self.assertTrue((a.state/'phase.new').exists())
        self.assertIn(b'PRE_EFFECT_ABORT_',r.stdout);self.assertNotIn(b'FAILURE_FRAMEWORK_BASELINE_RESTORED',r.stdout)
        self.history()
@unittest.skipUnless(shutil.which('mksh'),'mksh required in CI')
class MkshHelpTests(HelpTests):SHELL='mksh'
class PolicyTests(unittest.TestCase):
    def test_exact_phone_help_evidence_and_stable_version(self):
        builder.policy();text=(ROOT/'tools/device/cycle-0203/module.prop').read_text()
        self.assertIn('id=xairdrop17_cycle0195\n',text);self.assertIn('versionCode=203\n',text)
if __name__=='__main__':unittest.main()
