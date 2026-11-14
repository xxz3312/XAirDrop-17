"""Request-correlated scanner observations plus real lifecycle/effect fixtures."""
import hashlib,json,os,re,shutil,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools/help0203'),str(ROOT/'tools/kernel')]
import test_help0203 as prior
import stock_cnss_cycle0205 as builder
NATIVE=prior.prior.NATIVE
if os.environ.get('XAIRDROP_REQUIRE_MKSH')=='1' and not shutil.which('mksh'):raise RuntimeError('mksh required')
class ScanTests(unittest.TestCase):
    SHELL='sh'
    def setUp(self):
        self.old=prior.HelpTests();self.old.SHELL=self.SHELL;self.old.setUp();self.addCleanup(self.old.doCleanups);self.old.archive()
        a=self.a=self.old.a
        a.state.mkdir();a.state.chmod(0o700)
        fields={'phase':'restored\n','boot-id':(a.root/'proc/sys/kernel/random/boot_id').read_text(),
                'manifest.sha256':hashlib.sha256((a.bundle/'deployment.tsv').read_bytes()).hexdigest()+'\n',
                'wifi.before':'1\n','scan.before':'enabled\n','hals':'vendor.wifi_hal_legacy\n','interface.before':'1\n',
                'commands.log':'fixture203 reviewed HAL/validation roundtrip\n','kernel.before.log':'before203\n','kernel.after.log':'after203\n'}
        for n,v in fields.items():(a.state/n).write_text(v)
        (a.state/(a.wlan+'.ko')).write_bytes((a.backup/(a.wlan+'.ko')).read_bytes())
        self.saved=a.a.a.files(a.state);self.inode=a.state.stat().st_ino
        self.dest=Path(str(a.state)+'.previous.0203.'+fields['boot-id'].strip())
        vals=dict(l.split('\t',1) for l in (a.bundle/'deployment.tsv').read_text().splitlines())
        c={k+'.sha256':hashlib.sha256(v.encode()).hexdigest() for k,v in fields.items()}
        c.update(boot_id=fields['boot-id'].strip(),manifest_sha256=fields['manifest.sha256'].strip())
        vals.update({'reviewed203.'+k:v for k,v in c.items()});vals.update(schema='9',profile='stage0205-scan-completion-cycle')
        (a.bundle/'deployment.tsv').write_text(''.join(k+'\t'+v+'\n' for k,v in sorted(vals.items())))
        for f in (ROOT/'tools/device/cycle-0205').iterdir():
            s=f.read_text().replace('PATH=/system/bin:/system/xbin',f'PATH={a.bin}:/usr/bin:/bin')
            for cmd in ['cmd','svc','start','stop','insmod','rmmod','timeout','dumpsys']:s=s.replace('/system/bin/'+cmd,str(a.bin/cmd))
            s=re.sub(r'/data(?=[ /\n)])|/data/adb|/proc/sys/|/proc/uptime|/sys/module/|/sys/class/net/|/vendor(?:_dlkm)?/|/dev/(?!null)',lambda m:str(a.root)+m.group(),s)
            (a.bundle/f.name).write_text(s.replace('[ -b "','[ -f "'))
        (a.root/'proc/uptime').write_text('100.00 100.00\n')
        a.a.a.a.f.command('dumpsys',f'exec python3 {a.root}/scanner.py {a.root} "$@"')
        (a.root/'scanner.py').write_text('''import pathlib,sys,os
r=pathlib.Path(sys.argv[1]);assert sys.argv[2:]==['-t','10','wifiscanner']
assert os.readlink('/proc/self/fd/1').startswith('pipe:')
candidate=(r/'sys/module/opairshare_wonder_provider').exists()
mode=os.environ.get('SCAN_MODE','delayed');effects=(r/'effects').read_text().splitlines() if (r/'effects').exists() else []
requested='candidate-scan' in effects
if (not candidate and mode=='preflight_unavailable') or (candidate and not requested and mode=='baseline_unavailable'):sys.exit(7)
poll=0
if candidate and requested:
 p=r/'scanner-polls';poll=int(p.read_text())+1 if p.exists() else 1;p.write_text(str(poll))
 if mode=='query_unavailable':sys.exit(7)
 if mode in ('stale','wrong_listener','timeout'):(r/'proc/uptime').write_text('200.00 200.00\\n')
 if mode=='hal_dies':(r/'hal').write_text('stopped')
print('WifiScanningService - Log Begin ----')
root='ClientInfo[uid=1000, package=com.android.shell, attributionTag=null, com.android.server.wifi.scanner.WifiScannerInternal$ScanListener@'
def req(i):return 'now - addSingleScanRequest: '+root+i+'],WorkSource{0 com.android.shell}, ScanSettings { band:24Ghz & 5Ghz }'
def ok(i,n):return 'now - singleScanResults: '+root+i+'],results='+str(n)
print(req('abc111'));print(ok('abc111',22))
print('now - singleScanResults: ClientInfo[uid=1000, package=null, attributionTag=null, com.android.server.wifi.scanner.WifiScannerInternal$ScanListener@aa01],results=12')
if candidate and requested and mode!='stale':
 print(req('def222'))
 if mode=='ambiguous':print(req('eff333'))
 if mode=='failed':print('now - singleScanFailed: '+root+'def222],reason=-1, Scan failed')
 elif mode=='wrong_listener':print(ok('fff444',12))
 elif mode not in ('timeout','hal_dies') and (mode!='delayed' or poll>=3):
  print(ok('def222',0 if mode=='empty' else 17))
  if mode=='conflicting':print('now - singleScanFailed: '+root+'def222],reason=-1, Scan failed')
  else:(r/'scanner-complete').touch()
if not (candidate and requested and mode=='truncated'):print('WifiScanningService - Log End ----')
''')
        f=a.root/'effect.py';s=f.read_text();needle="with (root/'effects').open('a') as f:f.write(op+'\\n')"
        assert needle in s
        s=s.replace(needle,"""if op=='candidate-wifi-off' and os.environ.get('SCAN_MODE','delayed')=='delayed' and not (root/'scanner-complete').exists():
 print('FORBIDDEN premature WiFi teardown',file=sys.stderr);sys.exit(99)
"""+needle);f.write_text(s)
        a.integrity();a.trace.unlink(missing_ok=True)
        a.run_probe=lambda *args,**env:subprocess.run([self.SHELL,str(a.bundle/'cyclectl.sh'),*args],env=dict(os.environ,**env),capture_output=True,timeout=110)
    def archive(self):
        r=self.a.run_probe('archive-0203');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(self.a.a.a.files(self.dest),self.saved);self.assertEqual(self.dest.stat().st_ino,self.inode);self.assertEqual(self.a.effects(),[])
    def history(self):
        self.assertEqual(self.a.a.a.files(self.dest),self.saved);self.old.history()
    def test_delayed_request_completion_precedes_wifi_off_and_preserves_history(self):
        a=self.a;r=a.run_probe('check');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        a.blocked(a.run_probe('cycle'));self.assertEqual(a.effects(),[]);self.archive();self.archive()
        r=a.run_probe('cycle');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(a.native(),NATIVE);self.assertEqual(a.effects().count('candidate-scan'),1)
        self.assertEqual((a.root/'scanner-polls').read_text(),'3')
        self.assertEqual((a.state/'phase').read_text(),'restored\n');self.history()
        log=(a.state/'commands.log').read_text();self.assertIn('SCAN_WAIT_VERDICT:complete:listener=def222:results=17',log)
        self.assertLess(log.index('SCAN_REQUEST_CALLBACK:'),log.index('PHASE:intent:candidate-wifi-off'))
        self.assertEqual(log.count('CANDIDATE_HAL_STOPPED_SAMPLE:'),10);self.assertIn('REQUEST_SCAN_COMPLETED',r.stdout.decode())
        before=a.effects();a.blocked(a.run_probe('cycle'));a.blocked(a.run_probe('archive-0203'));self.assertEqual(a.effects(),before)
    def test_exact_reviewed203_bytes_and_residue_must_match(self):
        a=self.a
        for name in self.saved:
            f=a.state/name;b=f.read_bytes();f.write_bytes(b+b'changed');a.blocked(a.run_probe('archive-0203'));f.write_bytes(b)
        (a.state/'phase.new').write_text('keep');a.blocked(a.run_probe('archive-0203'));self.assertEqual(a.effects(),[])
    def test_failed_empty_stale_wrong_ambiguous_conflicting_and_query_gaps_restore_without_success(self):
        for mode in ['failed','empty','stale','wrong_listener','ambiguous','conflicting','query_unavailable','truncated','baseline_unavailable']:
            b=type(self)();b.setUp()
            try:
                b.archive();a=b.a;r=a.run_probe('cycle',SCAN_MODE=mode)
                self.assertEqual(r.returncode,3,r.stdout+r.stderr);self.assertEqual(a.native(),NATIVE)
                self.assertEqual((a.state/'phase').read_text(),'restored\n');self.assertIn(b'STOCK_RESTORED_CANDIDATE_OBSERVATION_NOT_CONFIRMED',r.stdout)
                self.assertNotIn(b'REBOOT_THEN',r.stdout);self.assertEqual(a.effects().count('candidate-scan'),0 if mode=='baseline_unavailable' else 1);b.history()
            finally:b.doCleanups()
    def test_scanner_preflight_failure_has_no_snapshot_or_effects(self):
        self.archive();a=self.a;r=a.run_probe('cycle',SCAN_MODE='preflight_unavailable');a.blocked(r)
        self.assertEqual(a.effects(),[]);self.assertFalse(a.state.exists());self.assertIn(b'PRE_EFFECT_ABORT',r.stdout);self.history()
    def test_hal_failure_in_scan_wait_blocks_teardown_and_post_reboot_recovery_never_replays(self):
        self.archive();a=self.a;a.blocked(a.run_probe('cycle',SCAN_MODE='hal_dies'))
        self.assertEqual((a.state/'phase').read_text(),'candidate-scan-wait\n');self.assertEqual(a.native(),NATIVE[:3]);self.assertNotIn('candidate-wifi-off',a.effects())
        phase=(a.state/'phase').read_bytes();before=a.native();a.restore_stock_fixture_after_reboot()
        r=a.run_probe('recover-settings');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(a.native(),before);self.assertEqual((a.state/'phase').read_bytes(),phase);self.history()
    def test_post_wait_framework_native_faults_keep_prefix_and_no_replay(self):
        for mode in ['FIXTURE_FAIL_BEFORE','FIXTURE_FAIL_AFTER']:
            for op,count in [('candidate-wifi-off',3),('candidate-hals-stop',3),('remove-candidate',4),('insert-stock',6)]:
                b=type(self)();b.setUp()
                try:
                    b.archive();a=b.a;a.blocked(a.run_probe('cycle',**{mode:op}))
                    self.assertEqual(a.native(),NATIVE[:count]);self.assertIn('returned:'+op+':',(a.state/'phase').read_text())
                    before=a.native();a.blocked(a.run_probe('cycle'));self.assertEqual(a.native(),before);b.history()
                finally:b.doCleanups()
    def test_signal_while_waiting_does_not_unload_or_restart(self):
        self.archive();a=self.a
        p=subprocess.Popen([self.SHELL,str(a.bundle/'cyclectl.sh'),'cycle'],env=dict(os.environ,SIGNAL_WAIT='1',SCAN_MODE='hal_dies'),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+35
            while time.monotonic()<deadline:
                if (a.state/'phase').exists() and (a.state/'phase').read_text().strip()=='candidate-scan-wait':break
                time.sleep(0.02)
            else:self.fail('scan wait not reached')
            p.send_signal(signal.SIGTERM);out,err=p.communicate(timeout=20)
            self.assertEqual(p.returncode,143,out+err);self.assertEqual(a.native(),NATIVE[:3]);self.assertNotIn('candidate-wifi-off',a.effects());self.history()
        finally:
            if p.poll() is None:p.kill();p.communicate()
@unittest.skipUnless(shutil.which('mksh'),'mksh required in CI')
class MkshScanTests(ScanTests):SHELL='mksh'

class ParserTests(unittest.TestCase):
    SHELL='sh'
    def parse(self,body,tail):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'input';p.write_text(body)
            r=subprocess.run([self.SHELL,'-c','. "$1"; cs_data=$(cat "$2"); '+tail,'test',str(ROOT/'tools/device/cycle-0205/scan-io.sh'),str(p)],capture_output=True)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr);return r.stdout.decode().strip()
    def test_passive_or_unrelated_callbacks_never_complete_target(self):
        root='ClientInfo[uid=1000, package=com.android.shell, attributionTag=null, WifiScannerInternal$ScanListener@'
        text='now - singleScanResults listener: '+root+'ab12],results=5\nnow - singleScanResults: '+root+'ef34],results=6\n'
        self.assertEqual(self.parse(text,'cs_target=ab12; cs_callback; echo "$cs_outcome"'),'pending')
    def test_baseline_callback_without_request_still_prevents_hash_reuse(self):
        line='now - singleScanResults: ClientInfo[uid=1000, package=com.android.shell, attributionTag=null, WifiScannerInternal$ScanListener@ab12],results=3\n'
        self.assertEqual(self.parse(line,'cs_baseline_ids=$(cs_seen_ids); cs_data="now - addSingleScanRequest: ClientInfo[uid=1000, package=com.android.shell, attributionTag=null, WifiScannerInternal\\$ScanListener@ab12],WorkSource{0 com.android.shell}"; cs_new_request; echo "$cs_new_count"'),'0')
    def test_malformed_counts_do_not_succeed(self):
        for n in ['-1','?','10000']:
            line='now - singleScanResults: ClientInfo[uid=1000, package=com.android.shell, attributionTag=null, WifiScannerInternal$ScanListener@ab12],results='+n+'\n'
            self.assertEqual(self.parse(line,'cs_target=ab12; cs_callback; echo "$cs_outcome"'),'conflicting')
@unittest.skipUnless(shutil.which('mksh'),'mksh required in CI')
class MkshParserTests(ParserTests):SHELL='mksh'
class PolicyTests(unittest.TestCase):
    def test_actual203_review_and_stable_version(self):
        builder.policy();self.assertEqual(builder.reviewed_contract()['manifest_sha256'],'dac59a7c2ec97c849cf3094e4aee4c7482b4832b2412818ca309ecf95a8caa7e')
        text=(ROOT/'tools/device/cycle-0205/module.prop').read_text();self.assertIn('id=xairdrop17_cycle0195\n',text);self.assertIn('versionCode=205\n',text)
if __name__=='__main__':unittest.main()
