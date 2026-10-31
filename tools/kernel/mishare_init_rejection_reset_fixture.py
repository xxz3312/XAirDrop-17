#!/usr/bin/env python3
"""Actions-only native INIT rejected-START provenance and explicit SSR reclaim."""
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path
import mishare_sm_entry_reset_fixture as entry
from mishare_recovery_fixture import function
from mishare_native_init_origins import remove_native_init_additions
ROOT=entry.ROOT
SM=entry.SM
API='qca-wifi-host-cmn/umac/mlme/vdev_mgr/dispatcher/src/wlan_vdev_mlme_api.c'
BASE_SM='81ed7e217c9e8ba849c2cd13b6f95f708acd0b8e1abc1dc52454a6959f504649'
HARNESS=r'''
static struct mishare_runtime_owner *init_rejected_owner(unsigned freq) {
 struct mishare_runtime_owner *o=queued_start_owner(freq);unsigned notices=native_init_down_notices,calls=native_init_calls;
 prepared_fence_at_sm=true;radio_run(false);
 assert(!sm_depth && "EXPECTED_NATIVE_SM_UNLOCK_BEFORE_RETURN");
 assert(native_init_calls==calls+1 && native_init_last_handled && native_init_down_notices==notices+1);
 assert(o->radio->ssr_fenced_init && o->radio->init_validate_rejected && o->radio->init_down_rejected && o->radio->init_native_notified);
 assert(o->radio->ssr_init_rejected && o->radio->start_sm_entered && o->radio->start_sm_return_success && !o->radio->start_sm_call_active);
 assert(state(o).recovery_radio_init_rejected && !state(o).recovery_radio_sm_entry_aborted && !state(o).recovery_radio_prepared_aborted);
 assert(!state(o).work_error && !state(o).work_pending && !state(o).work_users && !radio_q_len && !radio_starts && !radio_downs);
 return o;
}
static void assert_init_rejected_facts(struct mishare_runtime_owner *o) {
 struct mishare_runtime_status s=state(o);assert_reset_pe_facts(o);
 assert(s.ndi.radio_requested && s.recovery_radio_init_rejected && s.recovery_radio_released && !o->radio && !mishare_radios);
 assert(s.radio.ssr_cancelled_before_start && s.radio.ssr_start_init_rejected && !s.radio.ssr_start_sm_entry_aborted && !s.radio.ssr_start_prepared_aborted && !s.radio.ssr_start_body_aborted);
 assert(s.radio.phase==MISHARE_RADIO_BLOCKED && s.radio.error==-ESHUTDOWN && s.radio.closing && !s.radio.pending && !s.radio.users);
 assert(!s.radio.start_attempted && !s.radio.stop_attempted && !s.radio.host_up && !s.radio.down_attempted && !s.radio.down_accepted);
 assert(!radio_starts && !radio_stops && !radio_downs && !radio_timer && !radio_start_pm && !radio_stop_pm && !radio_rt && !sm_depth);
}
int main(void) {
 assert(!sm_entry_regressions());struct mishare_runtime_owner *o;
 for(unsigned band=0;band<2;band++)for(unsigned inline_cb=0;inline_cb<2;inline_cb++) {
  reset_pe_test();o=init_rejected_owner(band?5240:2437);assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && !pe_deletes);
  stop_recovery(o);early_dp=inline_cb;assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);assert_init_rejected_facts(o);
  if(!inline_cb)finish_dp();
  assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations && !objects_live && !dp_objects && !ctx_locks);
 }
 reset_pe_test();o=init_rejected_owner(5240);struct wlan_objmgr_vdev *held=last_vdev;assert(!wlan_objmgr_vdev_try_get_ref(held,1));stop_recovery(o);
 struct mishare_runtime_reclaim_item item={o,99};o=NULL;assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS);assert_init_rejected_facts(item.owner);finish_dp();
 assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS && item.owner);native_recovery_close();wlan_objmgr_vdev_release_ref(held,1);assert(!mishare_runtime_reclaim_batch(&psoc,&item,1) && !item.owner && !allocations);
 for(int fault=0;fault<24;fault++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=init_rejected_owner(5240);stop_recovery(o);struct mishare_radio *r=o->radio;
   if(fault==0)r->ssr_init_rejected=false;
   if(fault==1)r->init_native_notified=false;
   if(fault==2)r->init_validate_rejected=false;
   if(fault==3)r->init_down_rejected=false;
   if(fault==4)r->start_sm_return_success=false;
   if(fault==5)r->start_sm_call_active=true;
   if(fault==6)radio_native_substate=1;
   if(fault==7)ch_state=WLAN_VDEV_S_START;
   if(fault==8)r->start_sm_entered=false;
   if(fault==9)r->ssr_fenced_init=false;
   if(fault==10)r->state.ssr_start_init_rejected=false;
   if(fault==11)r->start_work_admitted=false;
   if(fault==12)r->start_prepare_succeeded=false;
   if(fault==13)r->preflight=false;
   if(fault==14)r->state.pending=1;
   if(fault==15)r->state.users=1;
   if(fault==16)(void)mishare_radio_validate(last_vdev->mlme,0,NULL);
   if(fault==17)r->state.error=-EIO;
   if(fault==18)r->owner=(void*)1;
   if(fault==19)o->state.recovery_radio_prepared_aborted=true;
   if(fault==20) {o->state.recovery_radio_init_rejected=false;o->state.recovery_radio_sm_entry_aborted=true;}
   if(fault==21)plan_pdev_fail=true;
   if(fault==22)mishare_radio_native_init_rejected(last_vdev->mlme);
   if(fault==23)o->state.ndi.radio_submit_error=-EIO;
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio==r && !recovery_timer_cancels && !pe_deletes && !dp_detaches);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 for(unsigned n=0;n<8;n++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=init_rejected_owner(5240);stop_recovery(o);
   if(n<7)prepared_plan_change(&o->radio->start_plan,n);else last_vdev->mlme->proto.generic.beacon_interval++;
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && !recovery_timer_cancels && !pe_deletes && !dp_detaches);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 for(unsigned drift=0;drift<2;drift++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {o=init_rejected_owner(5240);stop_recovery(o);if(drift)init_timer_substate_drift=true;else prepared_timer_plan_drift=true;assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && state(o).recovery_timer_released && o->radio && !pe_deletes && !dp_detaches);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 for(int fault=0;fault<5;fault++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=queued_start_owner(5240);prepared_fence_at_sm=true;
   if(fault==0)init_engine_return_error=true;
   if(fault==1)init_early_down=true;
   if(fault==2)init_extra_validate=true;
   if(fault==3)radio_native_substate=1;
   if(fault==4)init_engine_substate_drift=true;
   radio_run(false);
   assert(!sm_depth && !state(o).recovery_radio_init_rejected && !o->radio->ssr_init_rejected && !radio_starts && !radio_downs);
   health_recovering=true;assert(!cds_post_disable());assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && !pe_deletes && !dp_detaches);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 for(int origin=0;origin<6;origin++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=init_rejected_owner(5240);stop_recovery(o);struct wlan_objmgr_psoc other={9};
   mishare_runtime_radio_init_rejected(&other,last_vdev,o,o->radio);mishare_runtime_radio_init_rejected(&psoc,last_vdev,(void*)1,o->radio);assert(!state(o).ndi.completion_error);
   if(origin==0)mishare_runtime_radio_init_rejected(&psoc,last_vdev,o,o->radio);
   if(origin==1)mishare_runtime_radio_sm_entry_aborted(&psoc,last_vdev,o,o->radio);
   if(origin==2)mishare_runtime_radio_prepared_aborted(&psoc,last_vdev,o,o->radio);
   if(origin==3)mishare_runtime_radio_start_aborted(&psoc,last_vdev,o,o->radio);
   if(origin==4)mishare_runtime_radio_start_refused(&psoc,last_vdev,o,o->radio);
   if(origin==5)mishare_runtime_radio_start_flushed(&psoc,last_vdev,o,o->radio);
   assert(state(o).ndi.completion_error && mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && !pe_deletes);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 puts("MISHARE_NATIVE_INIT_REJECTION_SSR_FIXTURE_PASS_ONLY");return 0;
}
'''
NEGATIVE_HARNESS=r'''
int main(void) {
 reset_pe_test();struct mishare_runtime_owner *o=queued_start_owner(5240);prepared_fence_at_sm=true;radio_run(false);
 assert(state(o).recovery_radio_init_rejected && "EXPECTED_NATIVE_INIT_REJECT_ORIGIN");
 assert(!sm_depth && "EXPECTED_NATIVE_SM_UNLOCK_BEFORE_RETURN");_Exit(0);
}
'''

API_GLUE=r'''
static void mlme_vdev_sm_spin_lock(struct vdev_mlme_obj *m) {assert(m && !sm_depth && !lock_depth);sm_depth++;}
static void mlme_vdev_sm_spin_unlock(struct vdev_mlme_obj *m) {assert(m && sm_depth==1 && !lock_depth);sm_depth--;}
static QDF_STATUS mlme_vdev_sm_deliver_event(struct vdev_mlme_obj *,uint16_t,uint16_t,void *);
NATIVE_API
'''

def fixture(root):
    src=entry.fixture(root)
    needle='static unsigned refused_prepare_calls,refused_sm_calls;';assert src.count(needle)==1
    src=src.replace(needle,'static bool init_timer_substate_drift,init_engine_return_error,init_early_down,init_extra_validate,init_engine_substate_drift;\n'+needle,1)
    needle='recovery_timer_cancels++;';assert src.count(needle)==1
    src=src.replace(needle,needle+'if(init_timer_substate_drift)radio_native_substate=1;',1)
    model_api=function(src,'wlan_vdev_mlme_sm_deliver_evt')
    native_api=function((root/API).read_text(),'wlan_vdev_mlme_sm_deliver_evt')
    src=src.replace(model_api,API_GLUE.replace('NATIVE_API',native_api),1)
    glue=function(src,'mlme_vdev_sm_deliver_event')
    body=glue.replace('assert(e==WLAN_VDEV_SM_EV_START_REQ', 'if(e!=WLAN_VDEV_SM_EV_START_REQ) {QDF_STATUS status=radio_sm_dispatch(m->vdev,e);if(e==WLAN_VDEV_SM_EV_START) {if(init_engine_substate_drift)radio_native_substate=1;if(init_engine_return_error)return QDF_STATUS_E_FAILURE;}return status;}assert(e==WLAN_VDEV_SM_EV_START_REQ',1)
    assert body!=glue;src=src.replace(glue,body,1)
    needle='return mishare_radio_validate(m,n,p);';assert src.count(needle)==1
    src=src.replace(needle,'if(init_early_down) {init_early_down=false;(void)mishare_radio_down_complete(m,n,p);}'+needle,1)
    glue=function(src,'mlme_vdev_notify_down_complete')
    body=glue.replace('return mishare_radio_down_complete(m,n,p);','QDF_STATUS status=mishare_radio_down_complete(m,n,p);if(init_extra_validate) {init_extra_validate=false;(void)mishare_radio_validate(m,n,p);}return status;',1)
    assert body!=glue;src=src.replace(glue,body,1)
    src=src.replace('int main(void) {','static int sm_entry_regressions(void) {',1)
    src=src.replace('puts("MISHARE_SM_ENTRY_SSR_CANCEL_FIXTURE_PASS_ONLY");return 0;','return 0;',1)
    return src+HARNESS

def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=entry.prepared.early.refused.rejected.queued.prepared.pe.destructor.pe.PIN:raise ValueError('Unexpected revision')
    native=entry.prepared.early.refused.rejected.scheduler_audit(root)
    restored=remove_native_init_additions((root/SM).read_text());assert hashlib.sha256(restored.encode()).hexdigest()==BASE_SM
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:(d/n).write_text('/* platform model */\n')
        c=d/'reset.c';exe=d/'reset';command=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(c),'-o',str(exe)]
        env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'}
        c.write_text(source);subprocess.run(command,check=True);out=subprocess.check_output([exe],text=True,timeout=45,env=env)
        target=source.replace(function(source,'main'),NEGATIVE_HARNESS.strip(),1)
        c.write_text(target);subprocess.run(command,check=True);subprocess.run([exe],check=True,timeout=45,env=env)
        native_init=function(target,'mlme_vdev_state_init_event');hook='mishare_radio_native_init_rejected(vdev_mlme);';assert native_init.count(hook)==1
        c.write_text(target.replace(native_init,native_init.replace(hook,'(void)vdev_mlme; /* negative: omit native origin */',1),1))
        subprocess.run(command,check=True);bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env)
        assert bad.returncode==-6 and 'EXPECTED_NATIVE_INIT_REJECT_ORIGIN' in bad.stderr
        native_api=function(target,'wlan_vdev_mlme_sm_deliver_evt');unlock='mlme_vdev_sm_spin_unlock(vdev_mlme);';assert native_api.count(unlock)==1
        c.write_text(target.replace(native_api,native_api.replace(unlock,'(void)vdev_mlme; /* negative: omit native SM unlock */',1),1))
        subprocess.run(command,check=True);bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env)
        assert bad.returncode==-6 and 'EXPECTED_NATIVE_SM_UNLOCK_BEFORE_RETURN' in bad.stderr
    assert out.strip()=='MISHARE_NATIVE_INIT_REJECTION_SSR_FIXTURE_PASS_ONLY'
    return {'status':out.strip(),'source_commit':entry.prepared.early.refused.rejected.queued.prepared.pe.destructor.pe.PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h','wlan_hdd_mishare_radio.c','wlan_hdd_mishare_radio.h']},
            'native_scheduler_post_audit':native,
            'native_INIT_handler':{'path':SM,'sha256':hashlib.sha256((root/SM).read_bytes()).hexdigest(),'function_sha256':hashlib.sha256(function((root/SM).read_text(),'mlme_vdev_state_init_event').encode()).hexdigest(),'restored_pinned_sha256':BASE_SM},
            'native_SM_API':{'path':API,'sha256':hashlib.sha256((root/API).read_bytes()).hexdigest(),'function_sha256':hashlib.sha256(function((root/API).read_text(),'wlan_vdev_mlme_sm_deliver_evt').encode()).hexdigest()},
            'negative_control_missing_native_INIT_origin_rejected':True,'negative_control_missing_native_SM_unlock_rejected':True,
            'checks':['all 0079 regressions retained; actual native INIT START handler and native API lock/dispatch/unlock wrapper execute',
                      '2.4/5240 MHz, inline/deferred DP, batch and delayed final-free after window closure',
                      '24 provenance/state/identity faults, seven copied plan fields and current native plan reject before timer/PE/DP',
                      'exact validation rejection, down rejection, native branch origin and successful complete API return required',
                      'late/reordered/extra callbacks, failed API return, bad IDLE substate and timer-time plan/substate drift stay held',
                      'duplicate/mixed runtime origins and native origin outside active call remain sticky',
                      'no START/STOP/DOWN command or accepted DOWN fabricated; BLOCKED/ESHUTDOWN and native entry history retained'],
            'limitations':'Only original SSR before INIT validation, native START-validation failure branch with exact callback sequence and native origin, successful API return/unlock, INIT/IDLE and untouched transaction. Original parents retained/serialized through every poll. Executes production radio/runtime, native API wrapper and INIT handler, encoder and PE/peer code with modeled QDF/SM locks, generic engine/START_REQ dispatch and other states, full WMA postprocessing, PE allocation/remaining cleanup, DP/peer physical lifecycle and parents. Patched native INIT origin restores byte-for-byte to pinned baseline. No recovery after entering START state/sending START/waiting reply/UP, no automatic parent/shutdown coordinator, backend/phone/firmware/RF or AirDrop certification.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
