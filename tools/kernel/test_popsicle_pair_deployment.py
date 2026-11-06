"""Execute the policy core against a modeled Android IO adapter; no device IO."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import popsicle_pair_bundle as bundle
ROOT=Path(__file__).resolve().parents[2]
MODEL=r'''
set -u
W_STATE=stock;C_STATE=stock;P_STATE=absent;W_REFS=0;WIFI=1;HAL=running;SNAP=0;PHASE=none
[ "$ACTION" != restore ] || { W_STATE=candidate;C_STATE=candidate;P_STATE=candidate;W_REFS=2;SNAP=1;PHASE=active; }
pp_message(){ echo "M:$*"; }
pp_environment(){ [ "$BLOCK" != environment ]; }
pp_verify_bundle(){ [ "$BLOCK" != bundle ]; }
pp_no_conflict(){ [ "$BLOCK" != conflict ]; }
pp_no_transaction(){ [ "$SNAP" = 0 ]; }
pp_check_transaction(){ pp_no_transaction || [ "$PHASE" = backup-only ]; }
pp_prepare_snapshot(){ if pp_no_transaction; then pp_snapshot;else pp_verify_snapshot;fi; }
pp_expect_module(){
 case "$1" in cnss2) value=$C_STATE;;qca_cld3_peach_v2) value=$W_STATE;;opairshare_wonder_provider) value=$P_STATE;;*)return 1;;esac
 [ "$BLOCK" != "identity:$1" ] && [ "$value" = "$2" ]
}
pp_expect_absent(){
 case "$1" in cnss2)value=$C_STATE;;qca_cld3_peach_v2)value=$W_STATE;;opairshare_wonder_provider)value=$P_STATE;;esac
 [ "$value" = absent ]
}
pp_holders(){ [ "$BLOCK" != "holders:$1" ]; }
pp_zero_refs(){ [ "$BLOCK" != "refs:$1" ] || return 1;[ "$1" != qca_cld3_peach_v2 ] || [ "$W_REFS" = 0 ]; }
pp_healthy(){ [ "$BLOCK" != health ]; }
pp_ifaces(){ [ "$BLOCK" != interfaces ]; }
pp_snapshot(){ SNAP=1;echo SNAPSHOT;pp_journal backup-only; }
pp_verify_snapshot(){ [ "$BLOCK" != snapshot ] && [ "$SNAP" = 1 ]; }
pp_require_active(){ pp_verify_snapshot && [ "$PHASE" = active ]; }
pp_wifi_off(){ [ "$BLOCK" != wifi-observation ] && [ "$WIFI" = 0 ]; }
pp_hals_stopped(){ [ "$BLOCK" != hal-observation ] && [ "$HAL" = stopped ]; }
pp_journal(){
 echo "J:$1";[ "$JFAIL" != "$1" ] || return 1;PHASE=$1
}
pp_effect(){
 echo "E:$1:${2:-}"
 # Deliberately mutate BEFORE reporting an injected failure: nonzero does
 # not imply that a kernel command had no effects.
 case "$1" in
  wifi-off)WIFI=0;;hals-stop)HAL=stopped;;hals-start)HAL=running;;wifi-on)WIFI=1;;
  live-unload)W_REFS=0;;
  remove)case "$2" in cnss2)C_STATE=absent;;qca_cld3_peach_v2)W_STATE=absent;;opairshare_wonder_provider)P_STATE=absent;;esac;;
  insert)case "$2" in cnss2)C_STATE=candidate;;qca_cld3_peach_v2)W_STATE=candidate;W_REFS=2;;opairshare_wonder_provider)P_STATE=candidate;;esac;;
  stock-insert)case "$2" in cnss2)C_STATE=stock;;qca_cld3_peach_v2)W_STATE=stock;W_REFS=0;;esac;;
  *)return 1;;
 esac
 [ "$FAIL" != "$1:${2:-}" ]
}
pp_restore_services(){ pp_change hals-start || return 1;pp_change wifi-on; }
'''
APPLY=['wifi-off:','hals-stop:','remove:qca_cld3_peach_v2','remove:cnss2','insert:opairshare_wonder_provider','insert:cnss2','insert:qca_cld3_peach_v2','hals-start:','wifi-on:']
RESTORE=['wifi-off:','hals-stop:','live-unload:','remove:qca_cld3_peach_v2','remove:cnss2','remove:opairshare_wonder_provider','stock-insert:cnss2','stock-insert:qca_cld3_peach_v2','hals-start:','wifi-on:']

class DeploymentPolicyTests(unittest.TestCase):
    def run_model(self,action='apply',block='',fail='',jfail='',suffix=''):
        script=MODEL+'\n. "$ENGINE"\n'+suffix+'\nif pp_'+('start_pair' if action=='apply' else 'restore_pair')+';then r=0;else r=$?;fi\necho "RESULT:$r:$PHASE:$W_STATE:$C_STATE:$P_STATE"\nexit "$r"\n'
        return subprocess.run(['sh','-c',script],text=True,capture_output=True,env=dict(os.environ,ENGINE=str(ROOT/'tools/device/popsicle-pair-engine.sh'),ACTION=action,BLOCK=block,FAIL=fail,JFAIL=jfail))
    def effects(self,r):return [x[2:] for x in r.stdout.splitlines() if x.startswith('E:')]
    def test_apply_order_and_intent_before_every_effect(self):
        r=self.run_model();self.assertEqual(r.returncode,0,r.stderr+r.stdout);self.assertEqual(self.effects(r),APPLY)
        lines=r.stdout.splitlines()
        for i,line in enumerate(lines):
            if line.startswith('E:'):self.assertEqual(lines[i-1],'J:intent:'+line[2:])
        self.assertIn('RESULT:0:active:candidate:candidate:candidate',r.stdout)
    def test_restore_drains_before_rmmod_and_removes_provider_last(self):
        r=self.run_model('restore');self.assertEqual(r.returncode,0,r.stderr+r.stdout);self.assertEqual(self.effects(r),RESTORE);self.assertIn('RESULT:0:restored:stock:stock:absent',r.stdout)
    def test_every_apply_effect_failure_stops_without_automatic_rollback(self):
        for i,e in enumerate(APPLY):
            with self.subTest(effect=e):
                r=self.run_model(fail=e);self.assertNotEqual(r.returncode,0);self.assertEqual(self.effects(r),APPLY[:i+1]);self.assertIn('J:failed:'+e,r.stdout)
    def test_every_restore_effect_failure_stops_without_retry(self):
        for i,e in enumerate(RESTORE):
            with self.subTest(effect=e):
                r=self.run_model('restore',fail=e);self.assertNotEqual(r.returncode,0);self.assertEqual(self.effects(r),RESTORE[:i+1])
    def test_identity_bundle_and_extra_holder_blocks_before_any_effect(self):
        for b in ['environment','bundle','conflict','identity:cnss2','identity:qca_cld3_peach_v2','holders:cnss2','holders:qca_cld3_peach_v2','interfaces']:
            with self.subTest(block=b):
                r=self.run_model(block=b);self.assertNotEqual(r.returncode,0);self.assertFalse(self.effects(r));self.assertNotIn('SNAPSHOT',r.stdout)
    def test_journal_intent_failure_never_submits_that_effect(self):
        for i,e in enumerate(APPLY):
            with self.subTest(effect=e):
                r=self.run_model(jfail='intent:'+e);self.assertNotEqual(r.returncode,0);self.assertEqual(self.effects(r),APPLY[:i])
    def test_busy_wlan_never_attempts_remove(self):
        r=self.run_model(block='refs:qca_cld3_peach_v2');self.assertNotEqual(r.returncode,0);self.assertEqual(self.effects(r),APPLY[:2])
    def test_live_controller_failure_prevents_all_module_removal(self):
        r=self.run_model('restore',fail='live-unload:');self.assertEqual(self.effects(r),RESTORE[:3]);self.assertNotEqual(r.returncode,0)
    def test_corrupt_snapshot_or_unhealthy_pair_never_changes_runtime(self):
        for b in ['snapshot','health','identity:opairshare_wonder_provider']:
            r=self.run_model('restore',block=b);self.assertNotEqual(r.returncode,0);self.assertFalse(self.effects(r))
    def test_interrupted_intent_cannot_be_replayed(self):
        r=self.run_model('restore',suffix='PHASE=intent:live-unload:');self.assertNotEqual(r.returncode,0);self.assertFalse(self.effects(r))
    def test_existing_backup_can_be_used_without_snapshot_overwrite(self):
        r=self.run_model(suffix='SNAP=1;PHASE=backup-only');self.assertEqual(r.returncode,0,r.stderr+r.stdout);self.assertNotIn('SNAPSHOT',r.stdout)
    def test_legacy_driver_trial_refuses_checked_bundle_early(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'kernel').mkdir();(p/'kernel/cnss2.ko').write_bytes(b'checked')
            # Model the root inventory response, without acquiring privileges.
            (p/'id').write_text('#!/bin/sh\nprintf 0\n');(p/'id').chmod(0o755)
            for action in ['run','run-mgmt-rx','restore']:
                r=subprocess.run(['sh',str(ROOT/'tools/device/popsicle-wlan-trial.sh'),action,str(p)],capture_output=True,text=True,env=dict(os.environ,PATH=str(p)+':'+os.environ['PATH']))
                self.assertNotEqual(r.returncode,0);self.assertIn('Checked three-module pair requires',r.stdout)

class DeviceManifestParserTests(unittest.TestCase):
    def test_actual_parser_rejects_duplicate_missing_and_extra_fields(self):
        text=(ROOT/'tools/device/popsicle-pairctl.sh').read_text()
        fn=text[text.index('pp_key() {'):text.index('\npp_environment()')]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'deployment.tsv'
            for content,want in [('schema\t1\n',0),('schema\t1\nschema\t1\n',1),('other\t1\n',1),('schema\t1\textra\n',1)]:
                p.write_text(content)
                r=subprocess.run(['sh','-c',fn+'\npp_key schema'],capture_output=True,text=True,env=dict(os.environ,BUNDLE=tmp))
                self.assertEqual(r.returncode,want,content)
                if not want:self.assertEqual(r.stdout,'1\n')

class BundleContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);(self.root/'binaries').mkdir()
        mods={}
        for role,name in bundle.NAMES.items():
            p=self.root/'binaries'/(name+'.ko');p.write_bytes(name.encode());mods[role]={'sha256':bundle.sha(p),'vermagic':['exact kernel'],'vermagic_stock_loader_match':True,'stock_loader_kernel_sha256':'loader'}
        self.accept={'phone_executed':False,'pair_result_accepted':True,'provider_control_parameter_owner_and_ops_relocations_verified':True,'provider_control_parameter_permission':'0200','pair_report':{'status':'CHECKED_PLATFORM_PAIR_LINK_AND_RECORDED_CHECKS_ONLY','paired_WLAN_built':True,'CRC_gate_waived':False,'radio_backend_activation_enabled':False,'export_surface':{'match':True,'legacy_count':81},'modules':mods}}
        self.policy=json.loads((ROOT/'kernel/abi/popsicle-pair-deployment.json').read_text())
        for m in self.accept['pair_report']['modules'].values():m['stock_loader_kernel_sha256']=self.policy['loader_kernel_sha256']
        def inspect(p):return {'modinfo':{'name':[p.stem],'vermagic':['exact kernel']},'versions':{'opairshare_wlan_live_unload_arm_v1':'0x12345678'}}
        for name,fn in [('inspect',inspect),('note_hash',lambda p:'note'),('export_records',lambda p:{'opairshare_wlan_live_unload_arm_v1':{'crc':'0x12345678'}})]:
            patcher=patch.object(bundle,name,fn);patcher.start();self.addCleanup(patcher.stop)
    def verify(self,a=None):return bundle.verified_inputs(self.root,a or self.accept,self.policy)
    def test_matching_accepted_pair_is_only_offline_preparation(self):self.assertEqual(len(self.verify()),3)
    def test_waived_or_incomplete_or_radio_active_report_rejected(self):
        for key,value in [('CRC_gate_waived',True),('radio_backend_activation_enabled',True),('paired_WLAN_built',False)]:
            a=copy.deepcopy(self.accept);a['pair_report'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.verify(a)
    def test_changed_module_content_is_rejected(self):
        (self.root/'binaries/cnss2.ko').write_bytes(b'wrong')
        with self.assertRaises(ValueError):self.verify()
    def test_symlink_module_is_rejected(self):
        p=self.root/'binaries/cnss2.ko';p.unlink();p.symlink_to('qca_cld3_peach_v2.ko')
        with self.assertRaises(ValueError):self.verify()
    def test_missing_or_wrong_live_import_is_rejected(self):
        with patch.object(bundle,'export_records',return_value={}):
            with self.assertRaises(ValueError):self.verify()
    def test_wrong_module_name_or_kernel_is_rejected(self):
        with patch.object(bundle,'inspect',return_value={'modinfo':{'name':['other'],'vermagic':['exact kernel']}}):
            with self.assertRaises(ValueError):self.verify()
    def test_control_wiring_and_permission_required(self):
        for k,v in [('provider_control_parameter_owner_and_ops_relocations_verified',False),('provider_control_parameter_permission','0666')]:
            a=copy.deepcopy(self.accept);a[k]=v
            with self.subTest(key=k),self.assertRaises(ValueError):self.verify(a)

    def test_wrong_boot_policy_is_not_accepted(self):
        self.policy['boot_sha256']='0'*64
        with self.assertRaises(ValueError):self.verify()
    def test_changed_candidate_vermagic_is_rejected_even_when_stock_rule_was_accepted(self):
        with patch.object(bundle,'inspect',side_effect=lambda p:{'modinfo':{'name':[p.stem],'vermagic':['different candidate']},'versions':{}}):
            with self.assertRaises(ValueError):self.verify()
    def test_missing_recorded_stock_loader_match_is_rejected(self):
        self.accept['pair_report']['modules']['provider']['vermagic_stock_loader_match']=False
        with self.assertRaises(ValueError):self.verify()
