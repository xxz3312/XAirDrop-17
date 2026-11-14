"""Actual same-ID upgrade/archive/controller fixtures; never native acceptance."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import time
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/device/tests'))
import test_cycle0195 as old
import stock_cnss_cycle0197 as cycle
from stock_cnss_bundle import write_integrity
EFFECTS=['scan-off','wifi-off','hals-stop','remove-stock','insert-provider','insert-candidate',
         'remove-candidate','remove-provider','insert-stock','hals-start','scan-restore','wifi-restore']
NATIVE=['remove-stock','insert-provider','insert-candidate','remove-candidate','remove-provider','insert-stock']

class UpgradeTests(unittest.TestCase):
    SHELL='sh'
    def setUp(self):
        self.a=old.CycleTests();self.a.setUp();self.addCleanup(self.a.doCleanups)
        self.root=self.a.root;self.bin=self.a.bin;self.sys=self.a.sys
        self.state=self.a.state;self.wlan=self.a.wlan;self.provider=self.a.provider
        self.backup=self.a.a.backup;self.archive193=self.a.a.a.dest
        self.saved_backup=self.a.a.files(self.backup);self.saved_archive193=self.a.a.files(self.archive193)
        p=copy.deepcopy(self.a.a.a.profile);p['boot_sha256']=self.a.a.a.f.digest('dev/block/by-name/boot_a')
        for m in ('cnss2',self.wlan):
            p['stock'][m]={'sha256':self.a.a.a.f.digest(f'vendor/lib/modules/{m}.ko'),
                           'note_sha256':self.a.a.a.f.digest(f'sys/module/{m}/notes/.note.gnu.build-id')}
        checked={}
        for role,name in cycle.ROLES.items():
            f=self.root/(name+'.ko');checked[role]={'path':f,'record':{'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'note_sha256':hashlib.sha256(('candidate '+name).encode()).hexdigest()}}
        ghost=self.root/'original-profile-render';cycle.previous.render(ghost,checked,{}, {},p,{'archive_path':str(self.archive193)})
        legacy={'boot_id':(self.root/'proc/sys/kernel/random/boot_id').read_text().strip(),
                'manifest_sha256':hashlib.sha256((ghost/'deployment.tsv').read_bytes()).hexdigest()}
        self.state.mkdir();self.state.chmod(0o700)
        fields={'boot-id':legacy['boot_id']+'\n','manifest.sha256':legacy['manifest_sha256']+'\n',
                'phase':'returned:insert-provider:1\n','wifi.before':'1\n','interface.before':'1\n','hals':'vendor.wifi_hal_legacy\n',
                'commands.log':'fixture failed 0195 command journal\n','kernel.before.log':'fixture before\n','kernel.after.log':'fixture after\n'}
        for name,value in fields.items():(self.state/name).write_text(value)
        for f in ['commands.log','kernel.before.log','kernel.after.log']:legacy[f+'.sha256']=hashlib.sha256((self.state/f).read_bytes()).hexdigest()
        (self.state/(self.wlan+'.ko')).write_bytes((self.backup/(self.wlan+'.ko')).read_bytes())
        self.legacy_saved=self.a.a.files(self.state);self.legacy_inode=self.state.stat().st_ino
        self.legacy_dest=Path(str(self.state)+'.previous.0195.'+legacy['boot_id'])
        (self.root/'proc/sys/kernel/random/boot_id').write_text('ffffffff-1111-2222-3333-444444444444\n')
        self.a.bundle.rename(self.root/'old-package-preserved-in-fixture')
        self.bundle=self.a.bundle
        with patch.object(cycle,'legacy_contract',return_value=legacy):
            cycle.render(self.bundle,checked,{}, {},p,{'archive_path':str(self.archive193)})
        # Only synthetic fixture pins differ; production binds the reviewed 194 manifest.
        manifest=self.bundle/'deployment.tsv';lines=manifest.read_text().splitlines()
        digest=hashlib.sha256((self.a.a.bundle/'deployment.tsv').read_bytes()).hexdigest()
        manifest.write_text(''.join(('stage0194_manifest_sha256\t'+digest if x.startswith('stage0194_manifest_sha256\t') else x)+'\n' for x in lines))
        self.scan=self.root/'scan';self.scan.write_text('enabled')
        self.trace=self.a.trace;self.wifi=self.a.wifi;self.hal=self.a.hal
        self.a.a.a.f.command('cmd',f'''exec python3 {self.root}/framework.py {self.root} "$@"''')
        (self.root/'framework.py').write_text('''import os,pathlib,sys
r=pathlib.Path(sys.argv[1]);args=sys.argv[2:]
assert args and args[0]=='wifi'
if args==['wifi','status']:
 assert os.readlink('/proc/self/fd/1').startswith('pipe:')
 print('Wifi is '+('enabled' if (r/'wifi').read_text()=='1' else 'disabled'))
 print('Wifi scanning is '+('always available' if (r/'scan').read_text()=='enabled' else 'only available when wifi is enabled'))
 sys.exit(0)
assert len(args)==3 and args[1]=='set-scan-always-available' and args[2] in ('enabled','disabled')
previous=(r/'effects').read_text() if (r/'effects').exists() else ''
op='scan-off' if 'scan-off' not in previous.splitlines() else 'scan-restore'
with (r/'effects').open('a') as f:f.write(op+'\\n')
if os.environ.get('FIXTURE_FAIL_BEFORE')==op:sys.exit(7)
(r/'scan').write_text(args[2])
if os.environ.get('FIXTURE_FAIL_AFTER')==op:sys.exit(7)
''')
        effect=self.root/'effect.py';s=effect.read_text().replace("op='wifi-off' if not (root/'effects').exists() else 'wifi-restore'","op='wifi-off' if 'wifi-off' not in (root/'effects').read_text().splitlines() else 'wifi-restore'")
        s=s.replace("if os.environ.get('FIXTURE_FAIL_AFTER')==op:sys.exit(7)","if op=='remove-stock' and os.environ.get('RESTART_AFTER_REMOVE')=='1':(root/'hal').write_text('running')\nif os.environ.get('FIXTURE_FAIL_AFTER')==op:sys.exit(7)")
        effect.write_text(s)
        for name in ['cyclectl.sh','stage-io.sh','cycle-io.sh']:
            f=self.bundle/name;s=f.read_text().replace('PATH=/system/bin:/system/xbin',f'PATH={self.bin}:/usr/bin:/bin')
            for cmd in ['cmd','svc','start','stop','insmod','rmmod']:s=s.replace('/system/bin/'+cmd,str(self.bin/cmd))
            s=re.sub(r'/data(?=[ /\n)])|/data/adb|/proc/sys/|/sys/module/|/sys/class/net/|/vendor(?:_dlkm)?/|/dev/(?!null)',lambda m:str(self.root)+m.group(),s)
            f.write_text(s.replace('[ -b "','[ -f "'))
        self.a.a.a.f.command('sleep','[ "${SIGNAL_WAIT:-0}" != 1 ] || /bin/sleep 0.2;exit 0')
        self.integrity()
    def integrity(self):
        for f in ['SHA256SUMS','INSTALL_SHA256SUMS']:(self.bundle/f).unlink(missing_ok=True)
        write_integrity(self.bundle)
    def run_probe(self,*args,**env):
        return subprocess.run([self.SHELL,str(self.bundle/'cyclectl.sh'),*args],env=dict(os.environ,**env),capture_output=True,timeout=25)
    def effects(self):return self.trace.read_text().splitlines() if self.trace.exists() else []
    def native(self):return [e for e in self.effects() if e in NATIVE]
    def blocked(self,r):
        self.assertNotEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertNotIn(b'STAGE0197_SCAN_GUARDED_CYCLE_STOCK_RESTORED_ONLY',r.stdout)
        self.assertNotIn(b'FORBIDDEN',r.stderr)
    def archive(self):
        r=self.run_probe('archive-0195');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(self.a.a.files(self.legacy_dest),self.legacy_saved)
        self.assertEqual(self.legacy_dest.stat().st_ino,self.legacy_inode)
    def assert_history(self):
        self.assertEqual(self.a.a.files(self.backup),self.saved_backup)
        self.assertEqual(self.a.a.files(self.archive193),self.saved_archive193)
        self.assertEqual(self.a.a.files(self.legacy_dest),self.legacy_saved)
    def test_same_id_upgrade_readonly_check_and_explicit_no_clobber_archive(self):
        prop=(self.bundle/'module.prop').read_text();self.assertIn('id=xairdrop17_cycle0195\n',prop);self.assertIn('versionCode=197\n',prop)
        before=self.a.a.files(self.root);r=self.run_probe('check');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(before,self.a.a.files(self.root));self.blocked(self.run_probe('cycle'));self.assertEqual(self.effects(),[])
        self.archive();self.assertEqual(self.effects(),[]);self.assert_history()
        r=self.run_probe('archive-0195');self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assert_history()
    def test_legacy_corruption_current_boot_or_occupied_destination_blocks_archive(self):
        for field,value in [('phase','other\n'),('commands.log','changed'),('boot-id','ffffffff-1111-2222-3333-444444444444\n')]:
            p=self.state/field;old=p.read_bytes();p.write_text(value);before=self.a.a.files(self.root)
            self.blocked(self.run_probe('archive-0195'));self.assertEqual(before,self.a.a.files(self.root));p.write_bytes(old)
        self.legacy_dest.mkdir();self.blocked(self.run_probe('archive-0195'));self.assertTrue(self.state.exists())
    def test_full_scan_aware_cycle_restores_toggles_and_preserves_old_failed_record(self):
        self.archive();r=self.run_probe('cycle');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(self.effects(),EFFECTS);self.assertEqual(self.scan.read_text(),'enabled');self.assertEqual(self.wifi.read_text(),'1')
        self.assertEqual((self.state/'scan.before').read_text(),'enabled\n');self.assertEqual((self.state/'phase').read_text(),'restored\n')
        log=(self.state/'commands.log').read_text();self.assertEqual(log.count('HAL_STABLE_SAMPLE:'),10)
        self.assertIn('GATE:insert-provider:hal-stopped:rc=0',log);self.assert_history()
        self.blocked(self.run_probe('cycle'));self.assertEqual(self.effects(),EFFECTS)
    def test_disabled_scan_and_wifi_baseline_restored_exactly(self):
        self.archive();self.scan.write_text('disabled');self.wifi.write_text('0')
        r=self.run_probe('cycle');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(self.scan.read_text(),'disabled');self.assertEqual(self.wifi.read_text(),'0')
    def test_every_effect_failure_keeps_native_prefix_and_does_not_replay(self):
        for key in ['FIXTURE_FAIL_BEFORE','FIXTURE_FAIL_AFTER']:
            for i,e in enumerate(EFFECTS):
                with self.subTest(key=key,e=e):
                    a=type(self)();a.setUp()
                    try:
                        a.archive();a.blocked(a.run_probe('cycle',**{key:e}))
                        self.assertEqual(a.native(),[x for x in EFFECTS[:i+1] if x in NATIVE])
                        self.assertIn('returned:'+e+':7',(a.state/'phase').read_text())
                        before=a.native();a.blocked(a.run_probe('cycle'));self.assertEqual(a.native(),before);a.assert_history()
                    finally:a.doCleanups()
    def test_lazy_hal_restart_after_stock_removal_is_labelled_and_no_insert_occurs(self):
        self.archive();r=self.run_probe('cycle',RESTART_AFTER_REMOVE='1');self.blocked(r)
        self.assertEqual(self.native(),['remove-stock'])
        self.assertIn(b'GATE_BLOCKED:insert-provider:hal-stopped',r.stdout+r.stderr)
        self.assertEqual((self.state/'phase').read_text(),'returned:insert-provider:1\n')
        self.assertIn(b'FRAMEWORK_RECOVERY_SKIPPED_STOCK_NOT_CONFIRMED',r.stdout)
    def test_pre_native_error_restores_framework_but_does_not_mark_cycle_success(self):
        self.archive();r=self.run_probe('cycle',FIXTURE_FAIL_AFTER='hals-stop');self.blocked(r)
        self.assertEqual(self.native(),[]);self.assertEqual(self.scan.read_text(),'enabled');self.assertEqual(self.wifi.read_text(),'1')
        self.assertIn(b'STAGE0197_FAILURE_FRAMEWORK_BASELINE_RESTORED_ONLY',r.stdout)
        self.assertEqual((self.state/'phase').read_text(),'returned:hals-stop:7\n')
    def test_journal_failure_before_or_after_stock_removal_keeps_evidence(self):
        for phase,count in [('intent:remove-stock',0),('returned:remove-stock:0',1)]:
            a=type(self)();a.setUp()
            try:
                a.archive();a.blocked(a.run_probe('cycle',FIXTURE_JFAIL=phase))
                self.assertEqual(a.native(),NATIVE[:count]);self.assertTrue((a.state/'phase.new').exists())
                self.assertEqual((a.state/'phase.new').read_text(),phase+'\n')
                a.blocked(a.run_probe('cycle'));self.assertEqual(a.native(),NATIVE[:count]);a.assert_history()
            finally:a.doCleanups()
    def test_signal_before_native_switch_restores_framework_without_phase_replay(self):
        self.archive()
        p=subprocess.Popen([self.SHELL,str(self.bundle/'cyclectl.sh'),'cycle'],env=dict(os.environ,SIGNAL_WAIT='1'),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+12
            while time.monotonic()<deadline:
                if 'hals-stop' in self.effects():break
                time.sleep(0.01)
            else:self.fail('HAL stop was not reached')
            p.send_signal(signal.SIGTERM);out,err=p.communicate(timeout=15)
            self.assertEqual(p.returncode,143,out+err);self.assertEqual(self.native(),[])
            self.assertEqual(self.wifi.read_text(),'1');self.assertEqual(self.scan.read_text(),'enabled')
            self.assertIn(b'STAGE0197_FAILURE_FRAMEWORK_BASELINE_RESTORED_ONLY',out)
            self.assertNotEqual((self.state/'phase').read_text(),'restored\n');self.assert_history()
        finally:
            if p.poll() is None:p.kill();p.communicate()
    def test_busy_candidate_no_force_unload_and_no_framework_start_with_candidate(self):
        self.archive();r=self.run_probe('cycle',FIXTURE_BUSY='1');self.blocked(r)
        self.assertEqual(self.native(),NATIVE[:3]);self.assertEqual(self.hal.read_text(),'stopped')
        self.assertNotIn('hals-start',self.effects());self.assertEqual(self.scan.read_text(),'disabled')
    def restore_stock_fixture_after_reboot(self):
        m=self.sys/self.wlan
        if m.exists():shutil.rmtree(m)
        (m/'notes').mkdir(parents=True);(m/'holders').mkdir();(m/'initstate').write_text('live\n');(m/'refcnt').write_text('0\n')
        (m/'notes/.note.gnu.build-id').write_bytes((self.root/'stock.note').read_bytes())
        (self.sys/'cnss2/holders'/self.wlan).touch()
        provider=self.sys/self.provider
        if provider.exists():shutil.rmtree(provider)
        (self.root/'proc/sys/kernel/random/boot_id').write_text('eeeeeeee-1111-2222-3333-444444444444\n')
    def test_post_reboot_framework_recovery_keeps_phase_and_never_replays_native(self):
        self.archive();self.blocked(self.run_probe('cycle',RESTART_AFTER_REMOVE='1'))
        phase=(self.state/'phase').read_bytes();self.blocked(self.run_probe('recover-settings'))
        self.restore_stock_fixture_after_reboot();before=self.native()
        r=self.run_probe('recover-settings');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn(b'STAGE0197_POST_REBOOT_SETTINGS_RESTORED_NO_CYCLE_REPLAY',r.stdout)
        self.assertEqual(self.native(),before);self.assertEqual((self.state/'phase').read_bytes(),phase)
        self.assertEqual(self.wifi.read_text(),'1');self.assertEqual(self.scan.read_text(),'enabled');self.assert_history()
        self.blocked(self.run_probe('cycle'));self.assertEqual(self.native(),before)
    def test_source_corruption_blocks_before_source_and_manager_never_cycles(self):
        p=self.bundle/'cycle-io.sh';p.write_text('echo MUST_NOT_EXECUTE\n'+p.read_text())
        r=self.run_probe('check');self.blocked(r);self.assertNotIn(b'MUST_NOT_EXECUTE',r.stdout)
        self.assertEqual(self.effects(),[])
        self.assertIn('cyclectl.sh" check',(self.bundle/'action.sh').read_text())
        self.assertEqual((self.bundle/'service.sh').read_text().splitlines()[-1],'exit 0')

@unittest.skipUnless(shutil.which('mksh'),'mksh required in CI')
class UpgradeMkshTests(UpgradeTests):SHELL='mksh'

class PolicyTests(unittest.TestCase):
    def test_exact_phone_evidence_and_same_id_version_are_required(self):
        cycle.policy()
        text=(ROOT/'tools/device/cycle-0197/module.prop').read_text()
        self.assertIn('id=xairdrop17_cycle0195\n',text);self.assertIn('versionCode=197\n',text)
    def test_nested_gate_preserves_outer_label_in_logs(self):
        source=ROOT/'tools/device/cycle-0197/cycle-io.sh'
        script='. "$1"; sc_log(){ printf "%s\\n" "$*"; }; inner(){ cy_gate inner false; }; cy_gate outer inner'
        r=subprocess.run(['sh','-c',script,'test',str(source)],capture_output=True)
        self.assertNotEqual(r.returncode,0);self.assertIn(b'GATE:outer:rc=1',r.stdout)
        self.assertIn(b'GATE_BLOCKED:outer:rc=1',r.stderr)
    def test_original_0195_sources_are_still_historical_and_have_no_scan_changes(self):
        source=(ROOT/'tools/device/cycle-0195/cycle-engine.sh').read_text()
        self.assertNotIn('scan-off',source)

if __name__=='__main__':unittest.main()
