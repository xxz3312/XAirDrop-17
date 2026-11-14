"""Real fixed-target controller with synthetic hardware and one-shot effect faults."""
import hashlib,json,os,re,shutil,signal,subprocess,sys,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools/retrial0199'),str(ROOT/'tools/diagnostics'),str(ROOT/'tools/kernel')]
import test_retrial0199 as prior
import stock_cnss_cycle0201 as builder
NATIVE=prior.fixtures.NATIVE
EXPECTED=['scan-off','wifi-off','hals-stop','remove-stock','insert-provider','insert-candidate',
          'candidate-hals-start','candidate-wifi-on','candidate-scan','candidate-wifi-off','candidate-hals-stop',
          'remove-candidate','remove-provider','insert-stock','hals-start','scan-restore','wifi-restore']
if os.environ.get('XAIRDROP_REQUIRE_MKSH')=='1' and not shutil.which('mksh'):raise RuntimeError('mksh required')
class HalTests(unittest.TestCase):
    SHELL='sh'
    def setUp(self):
        self.b=prior.RetrialTests();self.b.SHELL=self.SHELL;self.b.setUp();self.addCleanup(self.b.doCleanups)
        self.b.archive();a=self.a=self.b.a
        # Synthetic accepted success record; production pins actual phone bytes.
        a.state.mkdir();a.state.chmod(0o700)
        fields={'phase':'restored\n','boot-id':(a.root/'proc/sys/kernel/random/boot_id').read_text(),
                'manifest.sha256':hashlib.sha256((a.bundle/'deployment.tsv').read_bytes()).hexdigest()+'\n',
                'wifi.before':'1\n','scan.before':'enabled\n','hals':'vendor.wifi_hal_legacy\n','interface.before':'1\n',
                'commands.log':'fixture completed199\n','kernel.before.log':'before199\n','kernel.after.log':'after199\n'}
        for n,v in fields.items():(a.state/n).write_text(v)
        (a.state/(a.wlan+'.ko')).write_bytes((a.backup/(a.wlan+'.ko')).read_bytes())
        self.saved=a.a.a.files(a.state);self.inode=a.state.stat().st_ino
        self.dest=Path(str(a.state)+'.previous.0199.'+fields['boot-id'].strip())
        vals=dict(line.split('\t',1) for line in (a.bundle/'deployment.tsv').read_text().splitlines())
        c={k+'.sha256':hashlib.sha256(v.encode()).hexdigest() for k,v in fields.items()}
        c.update(boot_id=fields['boot-id'].strip(),manifest_sha256=fields['manifest.sha256'].strip())
        vals.update({'completed199.'+k:v for k,v in c.items()});vals.update(schema='7',profile='stage0201-candidate-hal-cycle')
        (a.bundle/'deployment.tsv').write_text(''.join(k+'\t'+v+'\n' for k,v in sorted(vals.items())))
        for source in (ROOT/'tools/device/cycle-0201').iterdir():
            s=source.read_text().replace('PATH=/system/bin:/system/xbin',f'PATH={a.bin}:/usr/bin:/bin')
            for cmd in ['cmd','svc','start','stop','insmod','rmmod','timeout']:s=s.replace('/system/bin/'+cmd,str(a.bin/cmd))
            s=re.sub(r'/data(?=[ /\n)])|/data/adb|/proc/sys/|/sys/module/|/sys/class/net/|/vendor(?:_dlkm)?/|/dev/(?!null)',lambda m:str(a.root)+m.group(),s)
            (a.bundle/source.name).write_text(s.replace('[ -b "','[ -f "'))
        a.a.a.a.f.command('timeout','exec /usr/bin/timeout "$@"')
        # Add candidate-aware effect names while preserving original native model.
        f=a.root/'effect.py';s=f.read_text()
        needle="with (root/'effects').open('a') as f:f.write(op+'\\n')"
        assert needle in s
        s=s.replace(needle,"""candidate=(mods/provider).exists() and (mods/wlan).exists()
if candidate and cmd in ('start','stop'):op='candidate-hals-start' if cmd=='start' else 'candidate-hals-stop'
if candidate and cmd=='svc':op='candidate-wifi-on' if args[1]=='enable' else 'candidate-wifi-off'
"""+needle)
        s=s.replace("if cmd=='svc':(root/'wifi').write_text", "if cmd=='svc':(root/'wifi').write_text")
        f.write_text(s)
        fw=a.root/'framework.py';s=fw.read_text().replace("assert args and args[0]=='wifi'", "assert args and args[0]=='wifi'\nassert os.readlink('/proc/self/fd/1').startswith('pipe:')")
        s=s.replace("if args==['wifi','status']:","""candidate=(r/'sys/module/opairshare_wonder_provider').exists()
if args==['wifi','help']:
 if os.environ.get('NO_SCAN_HELP')=='1':sys.exit(7)
 print('start-scan\\nlist-scan-results');sys.exit(0)
if args==['wifi','list-scan-results']:
 if candidate and os.environ.get('SCAN_LIST_FAIL')=='1':sys.exit(7)
 print('BSSID Frequency RSSI Age(sec) SSID Flags\\naa:bb:cc:dd:ee:ff 5240 -35 >1000.0 cached [ESS]');sys.exit(0)
if args==['wifi','start-scan']:
 assert candidate
 with (r/'effects').open('a') as f:f.write('candidate-scan\\n')
 if os.environ.get('SCAN_FAIL')=='1':sys.exit(7)
 sys.exit(0)
if args==['wifi','status']:""")
        s=s.replace(" sys.exit(0)\nassert len(args)",""" if (r/'wifi').read_text()=='1' and (not candidate or os.environ.get('NO_CANDIDATE_CONNECTION')!='1'):
  print('Wifi is connected to fixture')
  ip='null' if os.environ.get('NULL_IP')=='1' and candidate else '/192.0.2.10'
  print('WifiInfo: IP: '+ip+', Supplicant state: COMPLETED')
  print('NetworkCapabilities: IP: /192.0.2.10')
 sys.exit(0)
assert len(args)""")
        s=s.replace("if args==['wifi','status']:", "if args==['wifi','status']:\n if candidate and os.environ.get('HAL_DIES_OBSERVING')=='1' and (r/'data/adb/xairdrop17-cycle0195-transaction/phase').read_text().strip()=='candidate-observing':(r/'hal').write_text('stopped')\n if candidate and os.environ.get('HAL_RESTARTS_AFTER_STOP')=='1' and (r/'hal').read_text()=='stopped' and 'candidate-hals-stop' in (r/'effects').read_text().splitlines():(r/'hal').write_text('running')")
        fw.write_text(s);a.integrity();a.trace.unlink(missing_ok=True)
        a.run_probe=lambda *args,**env:subprocess.run([self.SHELL,str(a.bundle/'cyclectl.sh'),*args],env=dict(os.environ,**env),capture_output=True,timeout=90)
    def archive(self):
        r=self.a.run_probe('archive-0199');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(self.a.a.a.files(self.dest),self.saved);self.assertEqual(self.dest.stat().st_ino,self.inode)
        self.assertEqual(self.a.effects(),[])
    def history(self):
        self.assertEqual(self.a.a.a.files(self.dest),self.saved)
        self.assertEqual(self.a.a.a.files(self.b.dest),self.b.saved);self.a.assert_history()
    def test_full_hal_connection_shutdown_and_restoration_with_scan_caveat(self):
        a=self.a;r=a.run_probe('check');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        a.blocked(a.run_probe('cycle'));self.assertEqual(a.effects(),[]);self.archive()
        r=a.run_probe('cycle');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(a.effects(),EXPECTED);self.assertEqual(a.native(),NATIVE)
        self.assertEqual((a.state/'phase').read_text(),'restored\n');self.history()
        log=(a.state/'commands.log').read_text();self.assertEqual(log.count('CANDIDATE_HAL_STOPPED_SAMPLE:'),10)
        self.assertIn('association_ip=1:scan_request_rc0=1:scan_list_rc0=1:scan_completion_certified=false',log)
        self.assertIn('SCAN_REVIEW_PENDING',r.stdout.decode());self.assertEqual(a.wifi.read_text(),'1')
        before=a.effects();a.blocked(a.run_probe('cycle'));a.blocked(a.run_probe('archive-0199'));self.assertEqual(a.effects(),before)
    def test_exact_record_corruption_and_unexpected_residue_refused(self):
        a=self.a
        for name in self.saved:
            f=a.state/name;b=f.read_bytes();f.write_bytes(b+b'changed');a.blocked(a.run_probe('archive-0199'));f.write_bytes(b)
        for name in ['phase.new','.hidden','framework-recovery.1.log']:
            f=a.state/name;f.write_text('preserve');a.blocked(a.run_probe('archive-0199'));self.assertTrue(f.exists());f.unlink()
        self.dest.mkdir();a.blocked(a.run_probe('archive-0199'));self.assertEqual(a.effects(),[])
    def test_missing_scan_capability_blocks_before_snapshot_or_effects(self):
        self.archive();a=self.a;a.blocked(a.run_probe('cycle',NO_SCAN_HELP='1'));self.assertEqual(a.effects(),[]);self.assertFalse(a.state.exists());self.history()
    def test_scan_request_or_list_failure_and_connection_gap_restore_stock_without_false_pass(self):
        for env in ['SCAN_FAIL','SCAN_LIST_FAIL','NO_CANDIDATE_CONNECTION','NULL_IP']:
            b=type(self)();b.setUp()
            try:
                b.archive();a=b.a;r=a.run_probe('cycle',**{env:'1'});self.assertEqual(r.returncode,3,r.stdout+r.stderr)
                self.assertEqual(a.native(),NATIVE);self.assertEqual((a.state/'phase').read_text(),'restored\n')
                self.assertIn(b'STOCK_RESTORED_CANDIDATE_OBSERVATION_NOT_CONFIRMED',r.stdout);self.assertNotIn(b'REBOOT_THEN',r.stdout)
                self.assertEqual(a.effects().count('wifi-restore'),1);b.history()
            finally:b.doCleanups()
    def test_new_framework_and_native_failures_stop_at_native_prefix_without_replay(self):
        points=['candidate-hals-start','candidate-wifi-on','candidate-wifi-off','candidate-hals-stop','remove-candidate','remove-provider','insert-stock']
        for mode in ['FIXTURE_FAIL_BEFORE','FIXTURE_FAIL_AFTER']:
            for op in points:
                b=type(self)();b.setUp()
                try:
                    b.archive();a=b.a;r=a.run_probe('cycle',**{mode:op});a.blocked(r)
                    expected=[x for x in EXPECTED[:EXPECTED.index(op)+1] if x in NATIVE]
                    self.assertEqual(a.native(),expected);self.assertIn('returned:'+op+':',(a.state/'phase').read_text());b.history()
                    before=a.native();a.blocked(a.run_probe('cycle'));self.assertEqual(a.native(),before)
                finally:b.doCleanups()
    def test_busy_candidate_never_force_unloads_or_restarts_framework(self):
        self.archive();a=self.a;r=a.run_probe('cycle',FIXTURE_BUSY='1');a.blocked(r)
        self.assertEqual(a.native(),NATIVE[:3]);self.assertEqual(a.hal.read_text(),'stopped');self.history()
    def test_candidate_observing_phase_allows_post_reboot_settings_only_recovery(self):
        self.archive();a=self.a;a.blocked(a.run_probe('cycle',HAL_DIES_OBSERVING='1'))
        self.assertEqual((a.state/'phase').read_text(),'candidate-observing\n');self.assertEqual(a.native(),NATIVE[:3])
        phase=(a.state/'phase').read_bytes();before=a.native();a.restore_stock_fixture_after_reboot()
        r=a.run_probe('recover-settings');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(a.native(),before);self.assertEqual((a.state/'phase').read_bytes(),phase);self.history()
    def test_candidate_hal_restart_after_shutdown_blocks_removal(self):
        self.archive();a=self.a;r=a.run_probe('cycle',HAL_RESTARTS_AFTER_STOP='1');a.blocked(r)
        self.assertEqual(a.native(),NATIVE[:3]);self.assertEqual(a.effects().count('candidate-hals-start'),1)
        self.assertIn(b'candidate-stop-0:hal',r.stdout+r.stderr);self.history()
    def test_signal_during_candidate_observation_does_not_unload_or_restart(self):
        self.archive();a=self.a
        p=subprocess.Popen([self.SHELL,str(a.bundle/'cyclectl.sh'),'cycle'],env=dict(os.environ,SIGNAL_WAIT='1',NO_CANDIDATE_CONNECTION='1'),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                if (a.state/'phase').exists() and (a.state/'phase').read_text().strip()=='candidate-observing':break
                time.sleep(0.02)
            else:self.fail('candidate observation not reached')
            p.send_signal(signal.SIGTERM);out,err=p.communicate(timeout=20)
            self.assertEqual(p.returncode,143,out+err);self.assertEqual(a.native(),NATIVE[:3])
            self.assertEqual(a.effects().count('candidate-hals-start'),1);self.assertNotIn('candidate-hals-stop',a.effects());self.history()
        finally:
            if p.poll() is None:p.kill();p.communicate()
    def test_post_reboot_settings_recovery_only(self):
        self.archive();a=self.a;a.blocked(a.run_probe('cycle',FIXTURE_FAIL_AFTER='candidate-hals-start'))
        phase=(a.state/'phase').read_bytes();before=a.native();a.restore_stock_fixture_after_reboot()
        r=a.run_probe('recover-settings');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(a.native(),before);self.assertEqual((a.state/'phase').read_bytes(),phase);self.history()
@unittest.skipUnless(shutil.which('mksh'),'mksh required in CI')
class MkshHalTests(HalTests):SHELL='mksh'
class PolicyTests(unittest.TestCase):
    def test_actual_completed_contract_and_version(self):
        builder.policy();self.assertEqual(builder.completed_contract()['manifest_sha256'],'f802766c9d7120b438f8c03a315fb49549782aee955f4fdb22b27acc0168b551')
        p=(ROOT/'tools/device/cycle-0201/module.prop').read_text();self.assertIn('id=xairdrop17_cycle0195\n',p);self.assertIn('versionCode=201\n',p)
if __name__=='__main__':unittest.main()
