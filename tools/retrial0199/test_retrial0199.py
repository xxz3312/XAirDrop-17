"""Real controller fixtures for exact pre-native preservation; no hardware acceptance."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools/diagnostics'),str(ROOT/'tools/kernel')]
import test_cycle0197 as fixtures
import stock_cnss_cycle0199 as cycle

if os.environ.get('XAIRDROP_REQUIRE_MKSH')=='1' and not shutil.which('mksh'):
    raise RuntimeError('mksh is required in CI')

class RetrialTests(unittest.TestCase):
    SHELL='sh'
    def setUp(self):
        self.a=fixtures.UpgradeTests();self.a.SHELL=self.SHELL;self.a.setUp();self.addCleanup(self.a.doCleanups)
        a=self.a;a.archive()
        # First obtain a genuine 0197 controller pre-unload abort in the fixture.
        f=a.root/'framework.py';original=f.read_text()
        f.write_text(original.replace("if args==['wifi','status']:\n", "if args==['wifi','status']:\n if (r/'hal').read_text()=='stopped':(r/'hal').write_text('running')\n"))
        a.blocked(a.run_probe('cycle'));self.assertEqual(a.native(),[])
        f.write_text(original)
        self.saved=a.a.a.files(a.state);self.inode=a.state.stat().st_ino
        self.dest=Path(str(a.state)+'.previous.0197.'+(a.state/'boot-id').read_text().strip())
        values=dict(line.split('\t',1) for line in (a.bundle/'deployment.tsv').read_text().splitlines())
        c={name+'.sha256':hashlib.sha256((a.state/name).read_bytes()).hexdigest() for name in self.saved if not name.endswith('.ko')}
        c['boot_id']=(a.state/'boot-id').read_text().strip();c['manifest_sha256']=(a.state/'manifest.sha256').read_text().strip()
        values.update({'aborted197.'+k:v for k,v in c.items()})
        values.update(schema='6',profile='stage0199-preserved-retrial-cycle')
        (a.bundle/'deployment.tsv').write_text(''.join(k+'\t'+v+'\n' for k,v in sorted(values.items())))
        for source in (ROOT/'tools/device/cycle-0199').iterdir():
            if source.name in ['cyclectl.sh','cycle-io.sh']:
                # Reuse precisely the existing fixed-target fixture path mapping.
                import re
                s=source.read_text().replace('PATH=/system/bin:/system/xbin',f'PATH={a.bin}:/usr/bin:/bin')
                for cmd in ['cmd','svc','start','stop','insmod','rmmod']:s=s.replace('/system/bin/'+cmd,str(a.bin/cmd))
                s=re.sub(r'/data(?=[ /\n)])|/data/adb|/proc/sys/|/sys/module/|/sys/class/net/|/vendor(?:_dlkm)?/|/dev/(?!null)',lambda m:str(a.root)+m.group(),s)
                (a.bundle/source.name).write_text(s.replace('[ -b "','[ -f "'))
            else:shutil.copyfile(source,a.bundle/source.name)
        a.integrity();a.trace.unlink(missing_ok=True)
    def archive(self):
        a=self.a;r=a.run_probe('archive-0197');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(a.a.a.files(self.dest),self.saved);self.assertEqual(self.dest.stat().st_ino,self.inode)
        self.assertEqual(a.effects(),[]);a.assert_history()
    def test_check_is_readonly_and_only_explicit_archive_enables_fresh_cycle(self):
        a=self.a;before=a.a.a.files(a.root)
        r=a.run_probe('check');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(a.a.a.files(a.root),before);a.blocked(a.run_probe('cycle'));self.assertEqual(a.effects(),[])
        self.archive();self.archive()
        r=a.run_probe('cycle');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(a.effects(),fixtures.EFFECTS);self.assertEqual(a.a.a.files(self.dest),self.saved)
        self.assertEqual((a.state/'phase').read_text(),'restored\n')
        self.assertIn(b'TEST_FINISHED',r.stdout);self.assertEqual((a.state/'commands.log').read_text().count('HAL_STABLE_SAMPLE:'),10)
        before=a.effects();a.blocked(a.run_probe('cycle'));a.blocked(a.run_probe('archive-0197'));self.assertEqual(a.effects(),before)
    def test_every_original_file_corruption_blocks_preservation_without_effects(self):
        a=self.a
        for name in self.saved:
            with self.subTest(name=name):
                f=a.state/name;b=f.read_bytes();f.write_bytes(b+b'corrupt')
                before=a.a.a.files(a.root);a.blocked(a.run_probe('archive-0197'))
                self.assertEqual(a.a.a.files(a.root),before);self.assertEqual(a.effects(),[]);f.write_bytes(b)
    def test_extra_residue_symlink_permissions_and_destination_collision_block(self):
        a=self.a
        for name in ['phase.new','framework-recovery.123.log','.hidden','unexpected']:
            f=a.state/name;f.write_text('preserve')
            a.blocked(a.run_probe('archive-0197'));self.assertTrue(f.exists());f.unlink()
        f=a.state/'commands.log';b=f.read_bytes();f.unlink();f.symlink_to(a.root/'stock.note')
        a.blocked(a.run_probe('archive-0197'));f.unlink();f.write_bytes(b)
        f.chmod(0o666);a.blocked(a.run_probe('archive-0197'));f.chmod(0o600)
        self.dest.mkdir();a.blocked(a.run_probe('archive-0197'));self.assertTrue(a.state.exists());self.assertEqual(a.effects(),[])
    def test_lock_and_incomplete_snapshot_prevent_archive(self):
        a=self.a
        lock=a.root/'dev/xairdrop17-wlan-trial.lock';lock.mkdir();a.blocked(a.run_probe('archive-0197'));lock.rmdir()
        p=Path(str(a.state)+'.preparing.123');p.mkdir();a.blocked(a.run_probe('archive-0197'));self.assertTrue(p.exists());self.assertEqual(a.effects(),[])
    def test_mutated_archived_history_blocks_new_snapshot(self):
        self.archive();a=self.a;(self.dest/'commands.log').write_text('changed')
        a.blocked(a.run_probe('cycle'));self.assertFalse(a.state.exists());self.assertEqual(a.effects(),[])
    def test_aborted_archive_works_after_reboot_only_with_same_exact_record(self):
        a=self.a;a.restore_stock_fixture_after_reboot();self.archive()
        r=a.run_probe('cycle');self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertEqual(a.native(),fixtures.NATIVE)
    def test_stop_failure_cleanup_does_not_request_unnecessary_reboot_or_allow_replay(self):
        self.archive();a=self.a;r=a.run_probe('cycle',FIXTURE_FAIL_AFTER='hals-stop');a.blocked(r)
        self.assertIn(b'STOPPED_FRAMEWORK_RESTORED_PRESERVE_STATE_NO_REPLAY',r.stdout)
        self.assertNotIn(b'REBOOT_THEN',r.stdout);self.assertEqual(a.native(),[])
        self.assertEqual(a.wifi.read_text(),'1');self.assertEqual(a.scan.read_text(),'enabled')
        before=a.effects();a.blocked(a.run_probe('cycle'));a.blocked(a.run_probe('archive-0197'));self.assertEqual(a.effects(),before)
    def test_post_unload_restart_still_blocks_without_native_retry(self):
        self.archive();a=self.a;r=a.run_probe('cycle',RESTART_AFTER_REMOVE='1');a.blocked(r)
        self.assertEqual(a.native(),['remove-stock']);self.assertIn(b'REBOOT_THEN_RECOVER_SETTINGS',r.stdout)
        self.assertEqual(a.a.a.files(self.dest),self.saved)
        a.restore_stock_fixture_after_reboot();phase=(a.state/'phase').read_bytes();before=a.native()
        r=a.run_probe('recover-settings');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(a.native(),before);self.assertEqual((a.state/'phase').read_bytes(),phase)
    def test_all_effect_failures_preserve_prefix_without_replay(self):
        for key in ['FIXTURE_FAIL_BEFORE','FIXTURE_FAIL_AFTER']:
            for i,e in enumerate(fixtures.EFFECTS):
                with self.subTest(key=key,e=e):
                    b=type(self)();b.setUp()
                    try:
                        b.archive();a=b.a;a.blocked(a.run_probe('cycle',**{key:e}))
                        self.assertEqual(a.native(),[x for x in fixtures.EFFECTS[:i+1] if x in fixtures.NATIVE])
                        before=a.native();a.blocked(a.run_probe('cycle'));a.blocked(a.run_probe('archive-0197'));self.assertEqual(a.native(),before)
                        self.assertEqual(a.a.a.files(b.dest),b.saved);a.assert_history()
                    finally:b.doCleanups()

@unittest.skipUnless(shutil.which('mksh'),'mksh required in CI')
class MkshRetrialTests(RetrialTests):SHELL='mksh'

class PolicyTests(unittest.TestCase):
    def test_actual_phone_contract_and_version(self):
        cycle.policy();c=cycle.aborted_contract();self.assertEqual(c['commands.log.sha256'],'4072a2665a34e5660ffce4a8ff073fb1789f8792d38f1d0b8c4893796f886fa7')
        p=(ROOT/'tools/device/cycle-0199/module.prop').read_text();self.assertIn('id=xairdrop17_cycle0195\n',p);self.assertIn('versionCode=199\n',p)

if __name__=='__main__':unittest.main()
