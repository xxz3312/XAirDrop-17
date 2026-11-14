"""Real controller/adapter fault fixtures; synthetic modules never establish ABI."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest
from unittest.mock import patch
import test_stage0194 as stagefixtures
import stock_cnss_cycle0195 as cycle
from stock_cnss_bundle import write_integrity
ROOT=stagefixtures.ROOT
EFFECTS=['wifi-off','hals-stop','remove-stock','insert-provider','insert-candidate',
         'remove-candidate','remove-provider','insert-stock','hals-start','wifi-restore']

class CycleTests(unittest.TestCase):
    SHELL='sh'
    def setUp(self):
        self.a=stagefixtures.StageTests();self.a.setUp();self.addCleanup(self.a.doCleanups)
        self.root=self.a.root;self.bin=self.a.bin
        r=self.a.run_probe('backup');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.old_backup=self.a.files(self.a.backup);self.old_archive=self.a.files(self.a.a.dest)
        p=copy.deepcopy(self.a.a.profile);p['boot_sha256']=self.a.a.f.digest('dev/block/by-name/boot_a')
        for m in ('cnss2','qca_cld3_peach_v2'):
            p['stock'][m]={'sha256':self.a.a.f.digest(f'vendor/lib/modules/{m}.ko'),
                           'note_sha256':self.a.a.f.digest(f'sys/module/{m}/notes/.note.gnu.build-id')}
        checked={}
        for role,name in cycle.ROLES.items():
            f=self.root/(name+'.ko')
            checked[role]={'path':f,'record':{'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'note_sha256':hashlib.sha256(('candidate '+name).encode()).hexdigest()}}
        self.bundle=self.root/'data/adb/modules/xairdrop17_cycle0195'
        cycle.render(self.bundle,checked,{'fixture':'synthetic, not ELF acceptance'},{'fixture':'not ABI'},p,{'archive_path':str(self.a.a.dest)})
        self.state=self.root/'data/adb/xairdrop17-cycle0195-transaction'
        self.wlan='qca_cld3_peach_v2';self.provider='opairshare_wonder_provider'
        self.sys=self.root/'sys/module';self.cnss_note=(self.sys/'cnss2/notes/.note.gnu.build-id').read_bytes()
        for name in [self.wlan]:
            (self.sys/name/'holders').mkdir(exist_ok=True);(self.sys/name/'refcnt').write_text('0\n')
        self.wifi=self.root/'wifi';self.wifi.write_text('1')
        self.hal=self.root/'hal';self.hal.write_text('running')
        self.trace=self.root/'effects'
        self.a.a.f.command('getprop',f'''
if [ "$#" = 0 ];then
 if [ "$(cat {self.hal})" = running ];then echo '[init.svc.vendor.wifi_hal_legacy]: [running]';fi
 [ "${{FIXTURE_EXTRA_HAL:-0}}" != 1 ] || echo '[init.svc.vendor.wifi_hal_other]: [running]'
 exit 0
fi
case "$1" in ro.product.device)echo popsicle;;ro.build.version.incremental)echo "${{FIXTURE_FIRMWARE:-{p['firmware']}}}";;ro.boot.slot_suffix)echo _a;;sys.boot_completed)echo 1;;init.svc.vendor.wifi_hal_legacy)cat {self.hal};;*)exit 1;;esac''')
        self.a.a.f.command('cmd',f'''
[ "$*" = 'wifi status' ] || exit 1
[ "${{FIXTURE_CMD_FAIL:-0}}" != 1 ] || exit 7
python3 -c 'import os;assert os.readlink("/proc/self/fd/1").startswith("pipe:")' || exit 1
if [ "$(cat {self.wifi})" = 1 ];then echo 'Wifi is enabled';else echo 'Wifi is disabled';fi''')
        self.a.a.f.command('dmesg','[ "${FIXTURE_DMESG_FAIL:-0}" != 1 ] || exit 7;echo "fixture kernel log"')
        self.a.a.f.command('sync','[ "${FIXTURE_SYNC_FAIL:-0}" != 1 ]')
        self.a.a.f.command('sleep','exit 0')
        self.a.a.f.command('mv',f'''
case "$*" in *phase.new*)
 [ "$(cat "$3")" != "${{FIXTURE_JFAIL:-none}}" ] || exit 7;;esac
exec /usr/bin/mv "$@"''')
        effect=self.root/'effect.py'
        effect.write_text('''import os,pathlib,shutil,sys
root=pathlib.Path(sys.argv[1]);cmd=sys.argv[2];args=sys.argv[3:]
wlan='qca_cld3_peach_v2';provider='opairshare_wonder_provider';mods=root/'sys/module'
if cmd=='svc':
 assert len(args)==2 and args[0]=='wifi'
 op='wifi-off' if not (root/'effects').exists() else 'wifi-restore'
elif cmd in ('start','stop'):
 assert args==['vendor.wifi_hal_legacy'];op='hals-start' if cmd=='start' else 'hals-stop'
elif cmd=='rmmod':
 assert len(args)==1 and args[0] in (wlan,provider)
 op='remove-provider' if args[0]==provider else ('remove-stock' if not (mods/provider).exists() else 'remove-candidate')
elif cmd=='insmod':
 assert len(args)==1
 name=pathlib.Path(args[0]).stem;assert name in (wlan,provider)
 op='insert-provider' if name==provider else ('insert-stock' if 'transaction/' in args[0] else 'insert-candidate')
else:raise AssertionError(cmd)
with (root/'effects').open('a') as f:f.write(op+'\\n')
if os.environ.get('FIXTURE_FAIL_BEFORE')==op:sys.exit(7)
if cmd=='svc':(root/'wifi').write_text('1' if args[1]=='enable' else '0')
elif cmd in ('start','stop'):(root/'hal').write_text('running' if cmd=='start' else 'stopped')
elif cmd=='rmmod':
 shutil.rmtree(mods/args[0])
 if args[0]==wlan:
  (mods/'cnss2/holders'/wlan).unlink()
  if (mods/provider/'holders'/wlan).exists():(mods/provider/'holders'/wlan).unlink()
elif cmd=='insmod':
 m=mods/name;(m/'notes').mkdir(parents=True);(m/'holders').mkdir();(m/'initstate').write_text('live\\n');(m/'refcnt').write_text('0\\n')
 if op=='insert-stock':note=(root/'stock.note').read_bytes()
 else:note=('candidate '+name).encode()
 (m/'notes/.note.gnu.build-id').write_bytes(note)
 if name==wlan:
  (mods/'cnss2/holders'/wlan).touch()
  if op=='insert-candidate':
   (mods/provider/'holders'/wlan).touch();(mods/provider/'refcnt').write_text('1\\n')
 if op=='insert-stock' and os.environ.get('FIXTURE_BAD_STOCK')=='1':(m/'notes/.note.gnu.build-id').write_bytes(b'wrong')
 if op=='insert-candidate' and os.environ.get('FIXTURE_BUSY')=='1':(m/'refcnt').write_text('1\\n')
if op=='remove-candidate':(mods/provider/'refcnt').write_text('0\\n')
if os.environ.get('FIXTURE_DRIFT')==op:(mods/'cnss2/notes/.note.gnu.build-id').write_bytes(b'changed')
if os.environ.get('FIXTURE_FAIL_AFTER')==op:sys.exit(7)
''')
        (self.root/'stock.note').write_bytes((self.sys/self.wlan/'notes/.note.gnu.build-id').read_bytes())
        for cmd in ['svc','start','stop','insmod','rmmod']:
            self.a.a.f.command(cmd,f'exec python3 {effect} {self.root} {cmd} "$@"')
        for name in ['cyclectl.sh','stage-io.sh','cycle-io.sh']:
            f=self.bundle/name;s=f.read_text().replace('PATH=/system/bin:/system/xbin',f'PATH={self.bin}:/usr/bin:/bin')
            for cmd in ['cmd','svc','start','stop','insmod','rmmod']:s=s.replace('/system/bin/'+cmd,str(self.bin/cmd))
            s=re.sub(r'/data(?=[ /\n)])|/data/adb|/proc/sys/|/sys/module/|/sys/class/net/|/vendor(?:_dlkm)?/|/dev/(?!null)',lambda m:str(self.root)+m.group(),s)
            s=s.replace('[ -b "','[ -f "');f.write_text(s)
        # Fixture-only binding: 0194 originally used zero candidate-note placeholders.
        # Bind to its actual synthetic manifest; production never changes this pin.
        manifest=self.bundle/'deployment.tsv'
        lines=manifest.read_text().splitlines()
        digest=hashlib.sha256((self.a.bundle/'deployment.tsv').read_bytes()).hexdigest()
        manifest.write_text(''.join((('stage0194_manifest_sha256\t'+digest) if x.startswith('stage0194_manifest_sha256\t') else x)+'\n' for x in lines))
        self.integrity()
    def integrity(self):
        for name in ['SHA256SUMS','INSTALL_SHA256SUMS']:(self.bundle/name).unlink(missing_ok=True)
        write_integrity(self.bundle)
    def run_probe(self,*args,**env):
        return subprocess.run([self.SHELL,str(self.bundle/'cyclectl.sh'),*args],capture_output=True,env=dict(os.environ,**env),timeout=20)
    def effects(self):return self.trace.read_text().splitlines() if self.trace.exists() else []
    def blocked(self,r):
        self.assertNotEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertNotIn(b'STAGE0195_DIAGNOSTIC_CYCLE_STOCK_RESTORED_ONLY',r.stdout)
        self.assertNotIn(b'FORBIDDEN',r.stderr)
    def test_check_status_and_manager_are_read_only(self):
        before=self.a.files(self.root)
        for action in ['check','status']:
            r=self.run_probe(action);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn(b'STAGE0195_CHECK_PASS_ONLY',r.stdout);self.assertEqual(before,self.a.files(self.root))
        for action in ['apply','restore','archive','start']:
            self.assertEqual(self.run_probe(action).returncode,2)
        self.assertEqual((self.bundle/'service.sh').read_text().splitlines()[-1],'exit 0')
        self.assertIn('cyclectl.sh" check',(self.bundle/'action.sh').read_text())
    def test_full_cycle_returns_to_stock_and_preserves_previous_records(self):
        r=self.run_probe('cycle');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(self.effects(),EFFECTS)
        self.assertIn(b'STAGE0195_DIAGNOSTIC_CYCLE_STOCK_RESTORED_ONLY',r.stdout)
        self.assertEqual((self.state/'phase').read_text(),'restored\n')
        self.assertEqual(self.a.files(self.a.backup),self.old_backup);self.assertEqual(self.a.files(self.a.a.dest),self.old_archive)
        self.assertEqual((self.sys/'cnss2/notes/.note.gnu.build-id').read_bytes(),self.cnss_note)
        log=(self.state/'commands.log').read_text()
        for e in EFFECTS:
            self.assertIn('PHASE:intent:'+e,log);self.assertIn('PHASE:returned:'+e+':0',log);self.assertIn('PHASE:done:'+e,log)
        before=self.a.files(self.state);self.blocked(self.run_probe('cycle'));self.assertEqual(self.a.files(self.state),before)
        self.assertEqual(self.effects(),EFFECTS)
    def test_wifi_off_baseline_is_preserved(self):
        self.wifi.write_text('0');r=self.run_probe('cycle');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(self.wifi.read_text(),'0');self.assertEqual(self.effects(),EFFECTS)
    def test_prior_boot_backup_is_bytes_only_current_baseline_is_fresh(self):
        (self.a.backup/'boot-id').write_text('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\n')
        self.wifi.write_text('0');r=self.run_probe('cycle');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual((self.state/'wifi.before').read_text(),'0\n')
        self.assertEqual((self.state/'boot-id').read_text(),(self.root/'proc/sys/kernel/random/boot_id').read_text())
    def test_each_command_failure_before_or_after_effect_stops_no_retry(self):
        for key in ['FIXTURE_FAIL_BEFORE','FIXTURE_FAIL_AFTER']:
            for i,e in enumerate(EFFECTS):
                with self.subTest(key=key,e=e):
                    # independent filesystem for each destructive fixture
                    a=type(self)();a.setUp()
                    try:
                        a.blocked(a.run_probe('cycle',**{key:e}));self.assertEqual(a.effects(),EFFECTS[:i+1])
                        self.assertIn('returned:'+e+':7',(a.state/'phase').read_text())
                        a.blocked(a.run_probe('cycle'));self.assertEqual(a.effects(),EFFECTS[:i+1])
                    finally:a.doCleanups()
    def test_journal_and_original_identity_failures_stop_at_exact_boundary(self):
        for i,e in enumerate(EFFECTS):
            for key,value,count in [('FIXTURE_JFAIL','intent:'+e,i),('FIXTURE_JFAIL','returned:'+e+':0',i+1),('FIXTURE_JFAIL','done:'+e,i+1),('FIXTURE_DRIFT',e,i+1)]:
                a=type(self)();a.setUp()
                try:a.blocked(a.run_probe('cycle',**{key:value}));self.assertEqual(a.effects(),EFFECTS[:count])
                finally:a.doCleanups()
    def test_prepared_loaded_and_restored_journal_failures_cannot_announce_success(self):
        for phase,count in [('prepared',0),('candidate-pair-live',5),('restored',10)]:
            a=type(self)();a.setUp()
            try:a.blocked(a.run_probe('cycle',FIXTURE_JFAIL=phase));self.assertEqual(a.effects(),EFFECTS[:count])
            finally:a.doCleanups()
    def test_busy_candidate_is_not_force_unloaded(self):
        self.blocked(self.run_probe('cycle',FIXTURE_BUSY='1'))
        self.assertEqual(self.effects(),EFFECTS[:5]);self.assertTrue((self.sys/self.wlan).exists())
    def test_bad_original_reinsert_cannot_announce_recovery_or_start_hal(self):
        self.blocked(self.run_probe('cycle',FIXTURE_BAD_STOCK='1'));self.assertEqual(self.effects(),EFFECTS[:8])
    def test_preflight_and_copy_failures_have_no_driver_effects(self):
        for env in [{'FIXTURE_FIRMWARE':'wrong'},{'FIXTURE_CMD_FAIL':'1'},{'FIXTURE_COPY_FAIL':'1'},{'FIXTURE_DMESG_FAIL':'1'},{'FIXTURE_SYNC_FAIL':'1'}]:
            a=type(self)();a.setUp()
            try:a.blocked(a.run_probe('cycle',**env));self.assertEqual(a.effects(),[])
            finally:a.doCleanups()
    def test_foreign_state_and_lock_and_interrupted_snapshot_are_preserved(self):
        for p in [self.a.a.lock,Path(str(self.state)+'.preparing.old'),self.state,self.root/'sys/module/wonder']:
            p.mkdir();before=self.a.files(self.root);self.blocked(self.run_probe('cycle'))
            self.assertEqual(self.effects(),[]);self.assertEqual(self.a.files(self.root),before);p.rmdir()
    def test_checksum_failure_blocks_before_helpers_and_ksu_installer_deletion_is_supported(self):
        (self.bundle/'customize.sh').unlink();self.assertEqual(self.run_probe().returncode,0)
        p=self.bundle/'cycle-io.sh';p.write_text('echo MUST_NOT_RUN\n'+p.read_text())
        r=self.run_probe('cycle');self.blocked(r);self.assertNotIn(b'MUST_NOT_RUN',r.stdout);self.assertEqual(self.effects(),[])

@unittest.skipUnless(shutil.which('mksh'),'mksh mandatory in CI')
class CycleMkshTests(CycleTests):
    SHELL='mksh'

class CyclePolicyTests(unittest.TestCase):
    def test_exact_0194_receipt_required(self):
        cycle.policy()
        with patch.object(cycle.prior,'policy',return_value=cycle.prior.policy()):
            with patch.object(cycle.json,'loads',return_value={'status':'wrong'}),self.assertRaises((ValueError,KeyError)):
                cycle.policy()
    def test_engine_source_is_inert_and_unknown_effect_is_rejected_before_journal(self):
        engine=ROOT/'tools/device/cycle-0195/cycle-engine.sh'
        for tail,rc in [('',0),('cy_step remove-cnss2',2),('cy_step insert-cnss2',2)]:
            r=subprocess.run(['sh','-c','. "$1";'+(tail or ':'),'fixture',str(engine)],capture_output=True)
            self.assertEqual(r.returncode,rc);self.assertEqual(r.stdout+r.stderr,b'')

if __name__=='__main__':unittest.main()
