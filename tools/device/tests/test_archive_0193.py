"""Archive real temporary directories only; Android/stock identities are fixtures."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest
import test_identity_0189 as fixtures
ROOT=fixtures.ROOT

class ArchiveTests(unittest.TestCase):
    SHELL='sh'
    def setUp(self):
        self.f=fixtures.IdentityTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.root;self.bin=self.f.bin
        self.profile=json.loads((ROOT/'docs/research/popsicle-stock-4.0.6-0193.json').read_text())
        self.record=self.profile['expected_record'];self.state=self.root/'data/adb/xairdrop17-stockcnss-transaction'
        self.state.mkdir(parents=True);self.state.chmod(0o700)
        self.dest=Path(str(self.state)+'.previous.0193.'+self.record['boot_id'])
        self.lock=self.root/'dev/xairdrop17-wlan-trial.lock'
        wlan=self.root/'vendor/lib/modules/qca_cld3_peach_v2.ko'
        for name,value in {'boot-id':self.record['boot_id']+'\n','phase':self.record['phase']+'\n',
                           'manifest.sha256':self.record['manifest_sha256']+'\n','wifi.before':'1\n',
                           'hals':'vendor.wifi_hal_legacy\n'}.items():(self.state/name).write_text(value)
        (self.state/'qca_cld3_peach_v2.ko').write_bytes(wlan.read_bytes())
        (self.state/'kernel.latest.log').write_text('retained log, never replayed\n')
        self.f.command('getprop',f'''case "$1" in
ro.product.device) echo popsicle;;
ro.build.version.incremental) echo "${{FIXTURE_FIRMWARE:-{self.profile['firmware']}}}";;
ro.boot.slot_suffix) echo _a;;sys.boot_completed) echo 1;;*)exit 1;;esac''')
        self.f.command('stat',f'''
if [ "$2" = %u ];then echo 0
elif [ "$2" = %u:%g:%a ] && [ "$3" = "{self.root}/data" ];then echo 1000:1000:771
elif [ "$2" = %d ] && [ "$3" = "{self.root}/data/adb" ] && [ "${{FIXTURE_CROSS_FS:-0}}" = 1 ];then echo 99999
else exec /usr/bin/stat "$@";fi''')
        self.f.command('mv',f'''echo EFFECT:mv
case "${{FIXTURE_MOVE:-ok}}" in
 fail-before) exit 7;; noop) exit 0;;
 fail-after) /usr/bin/mv "$@";exit 7;;
 replace-lock) /usr/bin/mv "$@" || exit $?
  /usr/bin/mv "{self.lock}" "{self.root}/retained-lock"
  /usr/bin/mkdir "{self.lock}"; exit 0;;
 *)exec /usr/bin/mv "$@";;esac''')
        source=(ROOT/'tools/device/popsicle-archive-0193.sh').read_text()
        # Substitute hashes only in the test copy. Production pins remain untouched.
        replacements={self.profile['boot_sha256']:self.f.digest('dev/block/by-name/boot_a'),
                      self.record['hals_sha256']:hashlib.sha256((self.state/'hals').read_bytes()).hexdigest()}
        for m in ('cnss2','qca_cld3_peach_v2'):
            replacements[self.profile['stock'][m]['sha256']]=self.f.digest(f'vendor/lib/modules/{m}.ko')
            replacements[self.profile['stock'][m]['note_sha256']]=self.f.digest(f'sys/module/{m}/notes/.note.gnu.build-id')
        for a,b in replacements.items():source=source.replace(a,b)
        source=source.replace('PATH=/system/bin:/system/xbin',f'PATH={self.bin}:/usr/bin:/bin')
        source=re.sub(r'/data(?=[ /\n)])|/data/adb|/proc/sys/|/sys/module/|/vendor(?:_dlkm)?/|/dev/(?!null)',lambda m:str(self.root)+m.group(),source)
        source=source.replace('[ -b "','[ -f "') # ordinary host file stands in for the boot block device
        self.script=self.root/'archive.sh';self.script.write_text(source)
    def run_probe(self,*args,**env):
        return subprocess.run([self.SHELL,str(self.script),*args],capture_output=True,env=dict(os.environ,**env),timeout=10)
    def contents(self,path):
        return {str(p.relative_to(path)):p.read_bytes() for p in path.rglob('*') if p.is_file()}
    def assert_blocked(self,result):
        self.assertNotEqual(result.returncode,0,result.stdout)
        self.assertNotIn(b'ARCHIVED_RECORD_ONLY_NOT_FOR_INSTALL',result.stdout)
        self.assertNotIn(b'FORBIDDEN',result.stderr)

    def test_default_check_never_writes_and_successful_archive_preserves_all_bytes(self):
        before=self.contents(self.root)
        r=self.run_probe();self.assertEqual(r.returncode,0,r.stderr);self.assertNotIn(b'EFFECT:',r.stdout)
        self.assertEqual(before,self.contents(self.root));self.assertFalse(self.lock.exists())
        saved=self.contents(self.state);inode=self.state.stat().st_ino
        r=self.run_probe('archive');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn(b'ARCHIVED_RECORD_ONLY_NOT_FOR_INSTALL',r.stdout)
        self.assertEqual(r.stdout.count(b'EFFECT:mv'),1)
        self.assertFalse(self.state.exists());self.assertEqual(saved,self.contents(self.dest))
        self.assertEqual(self.dest.stat().st_ino,inode);self.assertFalse(self.lock.exists())
        self.assert_blocked(self.run_probe('archive'));self.assertEqual(saved,self.contents(self.dest))

    def test_occupied_destination_is_not_merged_or_overwritten(self):
        self.dest.mkdir();(self.dest/'sentinel').write_text('preserve')
        before=self.contents(self.root);r=self.run_probe('archive');self.assert_blocked(r)
        self.assertNotIn(b'EFFECT:mv',r.stdout);self.assertEqual(before,self.contents(self.root))

    def test_existing_foreign_lock_is_preserved(self):
        self.lock.mkdir();(self.lock/'owner').write_text('foreign')
        before=self.contents(self.root)
        for action in ['check','archive']:
            r=self.run_probe(action);self.assert_blocked(r);self.assertNotIn(b'EFFECT:mv',r.stdout)
            self.assertEqual(before,self.contents(self.root));self.assertTrue(self.lock.exists())

    def test_each_identity_record_boundary_blocks_before_move(self):
        changes=[('phase','prepared\n'),('phase.new','intent:remove-wlan\n'),
                 ('boot-id','12345678-1234-1234-1234-123456789abc\n'),
                 ('manifest.sha256','0'*64+'\n'),('qca_cld3_peach_v2.ko','changed'),('hals','changed'),('wifi.before','0\n')]
        for name,value in changes:
            p=self.state/name;old=p.read_bytes() if p.exists() else None;p.write_text(value)
            before=self.contents(self.root);r=self.run_probe('archive');self.assert_blocked(r)
            self.assertNotIn(b'EFFECT:mv',r.stdout);self.assertEqual(before,self.contents(self.root))
            if old is None:p.unlink()
            else:p.write_bytes(old)
        for env in [{'FIXTURE_FIRMWARE':'other'},{'FIXTURE_CROSS_FS':'1'}]:
            r=self.run_probe('archive',**env);self.assert_blocked(r);self.assertNotIn(b'EFFECT:mv',r.stdout)

    def test_boot_note_or_candidate_presence_blocks(self):
        boot=self.root/'dev/block/by-name/boot_a';original=boot.read_bytes();boot.write_bytes(b'changed')
        r=self.run_probe('archive');self.assert_blocked(r);self.assertNotIn(b'EFFECT:mv',r.stdout);boot.write_bytes(original)
        note=self.root/'sys/module/cnss2/notes/.note.gnu.build-id';note.write_bytes(b'changed')
        r=self.run_probe('archive');self.assert_blocked(r);self.assertNotIn(b'EFFECT:mv',r.stdout)
        (self.root/'sys/module/opairshare_wonder_provider').mkdir()
        self.assert_blocked(self.run_probe('archive'))

    def test_private_record_and_symlink_rules_are_retained(self):
        phase=self.state/'phase';data=phase.read_bytes();phase.chmod(0o666)
        self.assert_blocked(self.run_probe('archive'));phase.chmod(0o600)
        phase.unlink();phase.symlink_to('/etc/passwd')
        r=self.run_probe('archive');self.assert_blocked(r);self.assertNotIn(b'root:',r.stdout)
        phase.unlink();phase.write_bytes(data)
        self.dest.symlink_to(self.root/'missing')
        self.assert_blocked(self.run_probe('archive'));self.assertTrue(self.dest.is_symlink())

    def test_move_failures_stop_without_rollback_or_success_claim(self):
        for fault in ['fail-before','noop']:
            before=self.contents(self.root);r=self.run_probe('archive',FIXTURE_MOVE=fault);self.assert_blocked(r)
            self.assertEqual(before,self.contents(self.root));self.assertTrue(self.state.exists())
            self.assertEqual(r.stdout.count(b'EFFECT:mv'),1)
        saved=self.contents(self.state)
        r=self.run_probe('archive',FIXTURE_MOVE='fail-after');self.assert_blocked(r)
        self.assertFalse(self.state.exists());self.assertEqual(saved,self.contents(self.dest))
        self.assertEqual(r.stdout.count(b'EFFECT:mv'),1)

    def test_foreign_replacement_lock_is_not_removed_on_exit(self):
        r=self.run_probe('archive',FIXTURE_MOVE='replace-lock');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertTrue(self.lock.exists());self.assertTrue((self.root/'retained-lock').exists())

    def test_only_explicit_archive_or_check_arguments_are_allowed(self):
        for args in [('apply',),('restore',),('archive','extra')]:
            r=self.run_probe(*args);self.assertEqual(r.returncode,2);self.assertTrue(self.state.exists())

    def test_production_profile_pins_are_archive_only_and_present_in_script(self):
        s=(ROOT/'tools/device/popsicle-archive-0193.sh').read_text()
        for value in [self.profile['firmware'],self.profile['boot_sha256'],self.profile['kernel_release'],
                      self.record['boot_id'],self.record['manifest_sha256'],self.record['backup_sha256'],self.record['hals_sha256']]:
            self.assertIn(value,s)
        self.assertIs(self.profile['deployment_load_qualified'],False)
        self.assertIs(self.profile['runtime_certified'],False)

@unittest.skipUnless(shutil.which('mksh'),'mksh unavailable locally; mandatory in CI')
class ArchiveMkshTests(ArchiveTests):
    SHELL='mksh'

if __name__=='__main__':unittest.main()
