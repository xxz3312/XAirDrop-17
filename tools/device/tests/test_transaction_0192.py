"""Android /data ancestor permissions and explicit refusal diagnostics."""
import os
from pathlib import Path
import shutil
import unittest
import test_transaction_0191 as fixtures
import stock_cnss_transaction as transaction

class Transaction0192Tests(fixtures.TransactionTests):
    PROBE='popsicle-transaction-0192.sh'
    def setUp(self):
        super().setUp()
        self.command('stat',f'''
if [ "$3" = "{self.root}/data" ] && [ "${{FIXTURE_ANDROID_DATA:-0}}" = 1 ];then
 case "$2" in
  %u) echo "${{DATA_UID:-1000}}";;
  %g) echo 1000;;
  %a) echo "${{DATA_MODE:-771}}";;
  %u:%g:%a) echo "${{DATA_UID:-1000}}:1000:${{DATA_MODE:-771}}";;
  *) exec /usr/bin/stat "$@";;
 esac
elif [ "$2" = %u ];then echo "${{FIXTURE_OWNER:-0}}"
elif [ "$2" = %u:%g:%a ];then echo "${{FIXTURE_OWNER:-0}}:0:755"
else exec /usr/bin/stat "$@";fi
''')

    def test_android_system_parent_matches_new_probe_but_legacy_probe_blocks(self):
        new=self.script.read_text()
        old=(fixtures.ROOT/'tools/device/popsicle-transaction-0191.sh').read_text()
        # Use the exact same host path remapping as the inherited fixture.
        old=old.replace('PATH=/system/bin:/system/xbin',f'PATH={self.bin}:/usr/bin:/bin')
        import re
        old=re.sub(r'/data(?=[ /\n)])|/data/adb|/proc/sys/',lambda m:str(self.root)+m.group(),old)
        self.script.write_text(old)
        legacy=self.run_probe(FIXTURE_ANDROID_DATA='1')
        self.assertNotEqual(legacy.returncode,0)
        self.assertIn(b'transaction.present\tUNKNOWN',legacy.stdout)
        self.script.write_text(new)
        current=self.run_probe(FIXTURE_ANDROID_DATA='1')
        self.assertEqual(current.returncode,0,current.stderr)
        self.assertIn(b'parent.data.meta\t1000:1000:771',current.stdout)
        r=self.classify(current.stdout);self.assertEqual(r['status'],'SAME_BOOT_TRANSACTION_PRESERVED');self.assert_no_authority(r)

    def test_unexpected_system_uid_or_permissions_remain_blocked_and_visible(self):
        for env in [{'DATA_UID':'1001'},{'DATA_MODE':'777'},{'DATA_MODE':'773'}]:
            c=self.run_probe(FIXTURE_ANDROID_DATA='1',**env)
            self.assertNotEqual(c.returncode,0)
            self.assertIn(b'parent.data.meta\t',c.stdout)
            self.assertIn(b'transaction.present\tUNKNOWN',c.stdout)
            r=self.classify(c.stdout);self.assertEqual(r['status'],'TRANSACTION_RECORD_BLOCKED');self.assert_no_authority(r)

    def test_host_parent_whitelist_does_not_relax_private_adb(self):
        for value in ['1000:1000:771','1000:1000:0771']:
            self.assertTrue(transaction.parent_signature_allowed(value,True))
            self.assertFalse(transaction.parent_signature_allowed(value,False))
        for value in ['1001:1000:771','0:0:777','0:0:775','0:0:646','UNREADABLE','0:0:7x1']:
            self.assertFalse(transaction.parent_signature_allowed(value,True))
        self.assertTrue(transaction.parent_signature_allowed('0:0:700'))

@unittest.skipUnless(shutil.which('mksh'),'mksh unavailable locally; mandatory in CI')
class Transaction0192MkshTests(Transaction0192Tests):
    SHELL='mksh'

if __name__=='__main__':unittest.main()
