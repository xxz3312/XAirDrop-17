"""Real staging/backup filesystem fixtures. Fake ELF bytes never certify ABI."""
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
import test_archive_0193 as fixtures
from stock_cnss_bundle import write_integrity
import stock_cnss_stage0194 as stage
ROOT=fixtures.ROOT

class StageTests(unittest.TestCase):
    SHELL='sh'
    def setUp(self):
        self.a=fixtures.ArchiveTests();self.a.setUp();self.addCleanup(self.a.doCleanups)
        self.root=self.a.root;self.bin=self.a.bin;self.a.state.rename(self.a.dest)
        self.bundle=self.root/'data/adb/modules/xairdrop17_stage0194'
        p=copy.deepcopy(self.a.profile);p['boot_sha256']=self.a.f.digest('dev/block/by-name/boot_a')
        for m in ('cnss2','qca_cld3_peach_v2'):
            p['stock'][m]={'sha256':self.a.f.digest(f'vendor/lib/modules/{m}.ko'),
                           'note_sha256':self.a.f.digest(f'sys/module/{m}/notes/.note.gnu.build-id')}
        checked={}
        for role,name in stage.ROLES.items():
            f=self.root/(name+'.ko');f.write_bytes(('container fixture '+name).encode())
            checked[role]={'path':f,'record':{'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'note_sha256':'0'*64}}
        stage.render(self.bundle,checked,{'fixture':'not ELF certification'},{'fixture':'not ABI certification'},p,
                     {'archive_path':str(self.a.dest)})
        self.backup=self.root/'data/adb/xairdrop17-stage0194-backup'
        holders=self.root/'sys/module/cnss2/holders';holders.mkdir();(holders/'qca_cld3_peach_v2').touch()
        (self.root/'sys/class/net/wlan0').mkdir(parents=True)
        self.a.f.command('getprop',f'''
if [ "$#" = 0 ];then
 [ "${{FIXTURE_NO_HAL:-0}}" = 1 ] || echo '[init.svc.vendor.wifi_hal_legacy]: [running]'
 exit 0
fi
case "$1" in ro.product.device) echo popsicle;;
ro.build.version.incremental) echo "${{FIXTURE_FIRMWARE:-{p['firmware']}}}";;
ro.boot.slot_suffix) echo _a;;sys.boot_completed) echo 1;;*)exit 1;;esac''')
        self.a.f.command('cmd',r'''[ "$*" = 'wifi status' ] || exit 1
[ "${FIXTURE_CMD_FAIL:-0}" != 1 ] || exit 1
python3 -c 'import os;assert os.readlink("/proc/self/fd/1").startswith("pipe:");assert os.readlink("/proc/self/fd/2").startswith("pipe:")' || exit 1
case "${FIXTURE_WIFI:-1}" in 1) echo 'Wifi is enabled';;0) echo 'Wifi is disabled';;*)echo unknown;;esac''')
        self.a.f.command('cp',r'''echo EFFECT:copy
[ "${FIXTURE_COPY_FAIL:-0}" != 1 ] || exit 7
exec /usr/bin/cp "$@"''')
        for name in ['stagectl.sh','stage-io.sh']:
            f=self.bundle/name;s=f.read_text()
            s=s.replace('PATH=/system/bin:/system/xbin',f'PATH={self.bin}:/usr/bin:/bin')
            s=s.replace('/system/bin/cmd',str(self.bin/'cmd')).replace('/system/bin/svc',str(self.bin/'svc'))
            s=re.sub(r'/data(?=[ /\n)])|/data/adb|/proc/sys/|/sys/module/|/sys/class/net/|/vendor(?:_dlkm)?/|/dev/(?!null)',lambda m:str(self.root)+m.group(),s)
            s=s.replace('[ -b "','[ -f "') # host file models boot block device
            f.write_text(s)
        self.integrity()
    def integrity(self):
        for name in ['SHA256SUMS','INSTALL_SHA256SUMS']:(self.bundle/name).unlink(missing_ok=True)
        write_integrity(self.bundle)
    def run_probe(self,*args,**env):
        return subprocess.run([self.SHELL,str(self.bundle/'stagectl.sh'),*args],capture_output=True,env=dict(os.environ,**env),timeout=15)
    def assert_blocked(self,r):
        self.assertNotEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertNotIn(b'STAGE0194_BACKUP_VERIFIED_ONLY',r.stdout)
        self.assertNotIn(b'FORBIDDEN',r.stderr)
    def files(self,folder):return self.a.contents(folder)

    def test_check_and_status_are_read_only_and_apply_is_unconditionally_rejected(self):
        before=self.files(self.root)
        for args in [(),('check',),('status',)]:
            r=self.run_probe(*args);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn(b'STAGE0194_CHECK_PASS_ONLY',r.stdout);self.assertNotIn(b'EFFECT:',r.stdout)
            self.assertEqual(before,self.files(self.root))
        for args in [('apply',),('archive',),('restore',),('backup','extra')]:
            r=self.run_probe(*args);self.assertEqual(r.returncode,2);self.assertEqual(before,self.files(self.root))

    def test_backup_preserves_wifi_and_archive_and_is_idempotent(self):
        archive=self.files(self.a.dest)
        for before in ['1','0']:
            r=self.run_probe('backup',FIXTURE_WIFI=before);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn(b'STAGE0194_BACKUP_VERIFIED_ONLY_NO_DRIVER_EFFECTS',r.stdout)
            self.assertEqual((self.backup/'wifi.before').read_text().strip(),before)
            self.assertEqual((self.backup/'qca_cld3_peach_v2.ko').read_bytes(),(self.root/'vendor/lib/modules/qca_cld3_peach_v2.ko').read_bytes())
            saved=self.files(self.backup)
            r=self.run_probe('backup',FIXTURE_WIFI=before);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn(b'STAGE0194_EXISTING_BACKUP_VERIFIED_ONLY',r.stdout)
            self.assertNotIn(b'EFFECT:copy',r.stdout);self.assertEqual(saved,self.files(self.backup))
            self.assertEqual(archive,self.files(self.a.dest));shutil.rmtree(self.backup)

    def test_installer_deletion_of_customize_does_not_break_runtime_integrity(self):
        (self.bundle/'customize.sh').unlink()
        r=self.run_probe();self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        candidate=self.bundle/'kernel/opairshare_wonder_provider.ko';old=candidate.read_bytes()
        candidate.write_bytes(b'tampered');self.assert_blocked(self.run_probe());candidate.write_bytes(old)
        helper=self.bundle/'stage-io.sh';helper.write_text('echo SHOULD_NOT_EXECUTE\n'+helper.read_text())
        r=self.run_probe();self.assert_blocked(r);self.assertNotIn(b'SHOULD_NOT_EXECUTE',r.stdout)

    def test_conflicting_vendor_copy_or_stale_identity_rejected(self):
        r=self.run_probe('backup',FIXTURE_FIRMWARE='other');self.assert_blocked(r);self.assertFalse(self.backup.exists())
        p=self.root/'vendor_dlkm/lib/modules/cnss2.ko';p.parent.mkdir(parents=True);p.write_bytes(b'conflicting')
        self.assert_blocked(self.run_probe());p.unlink()
        (self.a.dest/'phase').write_text('prepared\n');self.assert_blocked(self.run_probe())

    def test_legacy_state_lock_or_candidate_blocks_before_backup(self):
        for p in [self.a.state,self.a.lock,self.root/'sys/module/wonder']:
            p.mkdir();r=self.run_probe('backup');self.assert_blocked(r);self.assertNotIn(b'EFFECT:copy',r.stdout)
            self.assertTrue(p.exists());p.rmdir()

    def test_interrupted_backup_is_preserved_and_never_retried(self):
        r=self.run_probe('backup',FIXTURE_COPY_FAIL='1');self.assert_blocked(r)
        pending=list(self.backup.parent.glob(self.backup.name+'.preparing.*'));self.assertEqual(len(pending),1)
        self.assertFalse(self.backup.exists())
        r=self.run_probe('backup');self.assert_blocked(r);self.assertNotIn(b'EFFECT:copy',r.stdout)
        self.assertEqual(pending,list(self.backup.parent.glob(self.backup.name+'.preparing.*')))

    def test_no_hal_or_wifi_transport_failure_cannot_create_backup(self):
        for env in [{'FIXTURE_NO_HAL':'1'},{'FIXTURE_CMD_FAIL':'1'}]:
            r=self.run_probe('backup',**env);self.assert_blocked(r);self.assertFalse(self.backup.exists())

    def test_existing_snapshot_change_blocks_without_overwrite(self):
        self.assertEqual(self.run_probe('backup').returncode,0)
        (self.backup/'manifest.sha256').write_text('0'*64+'\n');before=self.files(self.backup)
        r=self.run_probe('backup');self.assert_blocked(r);self.assertEqual(before,self.files(self.backup))

    def test_move_noop_and_after_failure_do_not_announce_success(self):
        r=self.run_probe('backup',FIXTURE_MOVE='noop');self.assert_blocked(r);self.assertFalse(self.backup.exists())
        for p in self.backup.parent.glob(self.backup.name+'.preparing.*'):shutil.rmtree(p)
        r=self.run_probe('backup',FIXTURE_MOVE='fail-after');self.assert_blocked(r);self.assertTrue(self.backup.exists())
        self.assertEqual((self.backup/'phase').read_text(),'backup-only\n')

    def test_module_action_and_boot_do_not_call_backup_or_apply(self):
        self.assertEqual((self.bundle/'service.sh').read_text().splitlines()[-1],'exit 0')
        action=(self.bundle/'action.sh').read_text();self.assertIn('stagectl.sh" check',action);self.assertNotIn('apply',action)
        io=(self.bundle/'stage-io.sh').read_text();self.assertNotIn('sc_effect()',io)

class StagePolicyTests(unittest.TestCase):
    def test_real_evidence_is_accepted_only_for_check_backup(self):
        p,r=stage.policy();self.assertEqual(p['firmware'],'OS4.0.6.0.XPBCNXM');self.assertIs(p['deployment_load_qualified'],False)
    def test_wrong_kernel_or_archive_cannot_be_retargeted(self):
        profile=json.loads((ROOT/'docs/research/popsicle-stock-4.0.6-0193.json').read_text())
        receipt=json.loads((ROOT/'docs/research/popsicle-0193-archive-receipt.json').read_text())
        old=json.loads((ROOT/'kernel/abi/popsicle-pair-deployment.json').read_text())
        for mutate in [lambda p,r:p.update(kernel_sha256='0'*64),lambda p,r:p.update(deployment_load_qualified=True),
                       lambda p,r:r.update(receipt_sha256='0'*64),lambda p,r:r.update(archive_path='/wrong')]:
            p=copy.deepcopy(profile);r=copy.deepcopy(receipt);mutate(p,r)
            with patch.object(stage.json,'loads',side_effect=[p,r,old]),self.assertRaises(ValueError):stage.policy()

@unittest.skipUnless(shutil.which('mksh'),'mksh unavailable locally; mandatory in CI')
class StageMkshTests(StageTests):
    SHELL='mksh'

if __name__=='__main__':unittest.main()
