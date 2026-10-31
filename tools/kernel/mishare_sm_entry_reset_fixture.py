#!/usr/bin/env python3
"""Actions-only START SM entry gate and native INIT validation-failure behavior."""
import argparse,hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
import mishare_completed_prepare_reset_fixture as prepared
from mishare_recovery_fixture import function
ROOT=prepared.ROOT
SM='qca-wifi-host-cmn/umac/mlme/vdev_mgr/core/src/vdev_mlme_sm.c'
HARNESS=r'''
static struct mishare_runtime_owner *sm_entry_aborted_owner(unsigned freq) {
 struct mishare_runtime_owner *o=queued_start_owner(freq);unsigned sm=refused_sm_calls,notices=native_init_down_notices;
 sm_entry_prepare_floor=refused_prepare_calls;sm_entry_fence_armed=true;radio_run(false);
 assert(!sm_entry_fence_armed && refused_sm_calls==sm && native_init_down_notices==notices);
 assert(o->radio->start_sm_committed && !o->radio->start_sm_entered && o->radio->preflight && o->radio->ssr_fenced_sm_gate && o->radio->ssr_sm_entry_aborted);
 assert(state(o).recovery_radio_sm_entry_aborted && !state(o).recovery_radio_prepared_aborted && !state(o).recovery_radio_start_aborted && !state(o).recovery_radio_start_refused && !state(o).recovery_radio_start_flushed);
 assert(!state(o).work_pending && !state(o).work_users && !state(o).work_error && !state(o).mc_drained && !radio_q_len && !radio_starts);
 return o;
}
static void assert_sm_entry_abort_facts(struct mishare_runtime_owner *o) {
 struct mishare_runtime_status s=state(o);assert_reset_pe_facts(o);
 assert(s.ndi.radio_requested && s.recovery_radio_sm_entry_aborted && s.recovery_radio_released && !o->radio && !mishare_radios);
 assert(s.radio.ssr_cancelled_before_start && s.radio.ssr_start_sm_entry_aborted && !s.radio.ssr_start_prepared_aborted && !s.radio.ssr_start_body_aborted && !s.radio.ssr_start_callback_refused && !s.radio.ssr_start_submit_error);
 assert(s.radio.phase==MISHARE_RADIO_BLOCKED && s.radio.error==-ESHUTDOWN && s.radio.closing && !s.radio.pending && !s.radio.users);
 assert(!s.radio.start_attempted && !s.radio.stop_attempted && !s.radio.host_up && !s.radio.down_attempted && !s.radio.down_accepted);
 assert(!radio_starts && !radio_stops && !radio_downs && !radio_timer && !radio_start_pm && !radio_stop_pm && !radio_rt);
}
static void check_entered_native_init_refusal(void) {
 struct mishare_runtime_owner *o=queued_start_owner(5240);unsigned sm=refused_sm_calls,notices=native_init_down_notices,calls=native_init_calls;
 prepared_fence_at_sm=true;radio_run(false);
 assert(refused_sm_calls==sm+1 && native_init_calls==calls+1 && native_init_last_handled);
 assert(native_init_down_notices==notices+1 && "EXPECTED_NATIVE_INIT_FAILURE_NOTIFICATION");
 assert(o->radio->start_sm_committed && o->radio->start_sm_entered && !o->radio->ssr_fenced_sm_gate && !o->radio->ssr_sm_entry_aborted && !state(o).recovery_radio_sm_entry_aborted);
 assert(ch_state==WLAN_VDEV_S_INIT && !radio_starts && !radio_downs && !o->radio->state.down_attempted && !o->radio->state.down_accepted && o->radio->state.phase==MISHARE_RADIO_BLOCKED);
 radio_native_substate=1;health_recovering=true;assert(!cds_post_disable());assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && !pe_deletes && !dp_detaches);
}
int main(void) {
 assert(!completed_prepare_regressions());struct mishare_runtime_owner *o;
 for(unsigned band=0;band<2;band++)for(unsigned inline_cb=0;inline_cb<2;inline_cb++) {
  reset_pe_test();o=sm_entry_aborted_owner(band?5240:2437);assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && !pe_deletes);
  stop_recovery(o);early_dp=inline_cb;assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);assert_sm_entry_abort_facts(o);
  if(!inline_cb)finish_dp();
  assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations && !objects_live && !dp_objects && !ctx_locks);
 }
 reset_pe_test();o=sm_entry_aborted_owner(5240);struct wlan_objmgr_vdev *held=last_vdev;assert(!wlan_objmgr_vdev_try_get_ref(held,1));stop_recovery(o);
 struct mishare_runtime_reclaim_item item={o,99};o=NULL;assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS);assert_sm_entry_abort_facts(item.owner);finish_dp();
 assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS && item.owner);native_recovery_close();wlan_objmgr_vdev_release_ref(held,1);assert(!mishare_runtime_reclaim_batch(&psoc,&item,1) && !item.owner && !allocations);
 for(int fault=0;fault<20;fault++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=sm_entry_aborted_owner(5240);stop_recovery(o);struct mishare_radio *r=o->radio;
   if(fault==0)r->ssr_sm_entry_aborted=false;
   if(fault==1)r->start_sm_entered=true;
   if(fault==2)r->start_sm_committed=false;
   if(fault==3)r->ssr_fenced_sm_gate=false;
   if(fault==4)r->preflight=false;
   if(fault==5)r->state.ssr_start_sm_entry_aborted=false;
   if(fault==6)r->start_prepare_succeeded=false;
   if(fault==7)r->state.pending=1;
   if(fault==8)r->state.users=1;
   if(fault==9)r->state.error=-EIO;
   if(fault==10)r->owner=(void*)1;
   if(fault==11)r->start_work_admitted=false;
   if(fault==12)r->start_callback_entered=false;
   if(fault==13)r->start_posted=false;
   if(fault==14)(void)mishare_radio_validate(last_vdev->mlme,0,NULL);
   if(fault==15)o->state.recovery_radio_prepared_aborted=true;
   if(fault==16)o->state.ndi.radio_submit_error=-EIO;
   if(fault==17) {o->state.recovery_radio_sm_entry_aborted=false;o->state.recovery_radio_prepared_aborted=true;}
   if(fault==18)plan_pdev_fail=true;
   if(fault==19)r->start_prepare_entered=false;
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio==r && !recovery_timer_cancels && !pe_deletes && !dp_detaches);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 for(unsigned n=0;n<8;n++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=sm_entry_aborted_owner(5240);stop_recovery(o);
   if(n<7)prepared_plan_change(&o->radio->start_plan,n);else last_vdev->mlme->proto.generic.beacon_interval++;
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && !recovery_timer_cancels && !pe_deletes && !dp_detaches);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 reset_pe_test();pid_t child=fork();assert(child>=0);
 if(!child) {o=sm_entry_aborted_owner(5240);stop_recovery(o);prepared_timer_plan_drift=true;assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && state(o).recovery_timer_released && o->radio && !pe_deletes && !dp_detaches);_Exit(0);}
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 reset_pe_test();child=fork();assert(child>=0);if(!child) {check_entered_native_init_refusal();_Exit(0);}assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 for(int origin=0;origin<5;origin++) {
  reset_pe_test();child=fork();assert(child>=0);
  if(!child) {
   o=sm_entry_aborted_owner(5240);stop_recovery(o);struct wlan_objmgr_psoc other={9};
   mishare_runtime_radio_sm_entry_aborted(&other,last_vdev,o,o->radio);mishare_runtime_radio_sm_entry_aborted(&psoc,last_vdev,(void*)1,o->radio);assert(!state(o).ndi.completion_error);
   if(origin==0)mishare_runtime_radio_sm_entry_aborted(&psoc,last_vdev,o,o->radio);
   if(origin==1)mishare_runtime_radio_prepared_aborted(&psoc,last_vdev,o,o->radio);
   if(origin==2)mishare_runtime_radio_start_aborted(&psoc,last_vdev,o,o->radio);
   if(origin==3)mishare_runtime_radio_start_refused(&psoc,last_vdev,o,o->radio);
   if(origin==4)mishare_runtime_radio_start_flushed(&psoc,last_vdev,o,o->radio);
   assert(state(o).ndi.completion_error && mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && !pe_deletes);_Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 puts("MISHARE_SM_ENTRY_SSR_CANCEL_FIXTURE_PASS_ONLY");return 0;
}
'''
NEGATIVE_HARNESS=r'''
int main(void) {
 reset_pe_test();struct mishare_runtime_owner *o=sm_entry_aborted_owner(5240);stop_recovery(o);
 o->radio->ssr_sm_entry_aborted=false;
 assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && "EXPECTED_PRIVATE_SM_ENTRY_ABORT_PROVENANCE");_Exit(0);
}
'''
NATIVE_INIT_NEGATIVE_HARNESS=r'''
int main(void) {reset_pe_test();check_entered_native_init_refusal();_Exit(0);}
'''
INIT_GLUE=r'''
#define WLAN_VDEV_SM_EV_START_REQ 201
#define WLAN_VDEV_SM_EV_START_REQ_FAIL 202
#define WLAN_VDEV_SM_EV_ROAM 203
#ifndef fallthrough
#define fallthrough __attribute__((fallthrough))
#endif
static unsigned native_init_calls,native_init_down_notices;
static bool native_init_last_handled;
static QDF_STATUS mlme_vdev_validate_basic_params(struct vdev_mlme_obj *m,uint16_t n,void *p) {return mishare_radio_validate(m,n,p);}
static void mlme_vdev_sm_transition_to(struct vdev_mlme_obj *m,unsigned state) {assert(m->vdev==last_vdev);ch_state=state;}
static QDF_STATUS mlme_vdev_sm_deliver_event(struct vdev_mlme_obj *m,uint16_t e,uint16_t n,void *p) {assert(e==WLAN_VDEV_SM_EV_START_REQ && ch_state==WLAN_VDEV_S_START);radio_native_substate=WLAN_VDEV_SS_START_START_PROGRESS;return mishare_radio_start_send(m,n,p);}
static QDF_STATUS mlme_vdev_notify_down_complete(struct vdev_mlme_obj *m,uint16_t n,void *p) {native_init_down_notices++;return mishare_radio_down_complete(m,n,p);}
static void mlme_vdev_init_down(struct vdev_mlme_obj *m) {assert(m);}
static void mlme_vdev_down_cmpl_notify_mlo_mgr(struct vdev_mlme_obj *m) {assert(m);}
static bool wlan_vdev_mlme_is_mlo_link_vdev(struct wlan_objmgr_vdev *v) {assert(v);return false;}
NATIVE_INIT
'''

def fixture(root):
    src=prepared.fixture(root)
    needle='static unsigned refused_prepare_calls,refused_sm_calls;';assert src.count(needle)==1
    src=src.replace(needle,'static bool sm_entry_fence_armed;static unsigned sm_entry_prepare_floor;\n'+needle,1)
    needle='bool allowed=mishare_runtime_work_allowed(v,o);';assert src.count(needle)==1
    src=src.replace(needle,needle+'if(allowed && sm_entry_fence_armed && refused_prepare_calls>sm_entry_prepare_floor) {sm_entry_fence_armed=false;assert(mishare_runtime_quiesce_psoc(wlan_vdev_get_psoc(v),MISHARE_QUIESCE_SSR)==1);}',1)
    dispatcher=function(src,'radio_sm_dispatch')
    old='s=mishare_radio_validate(m,0,NULL);if(s)return s;ch_state=WLAN_VDEV_S_START;\n  radio_native_substate=WLAN_VDEV_SS_START_START_PROGRESS;return mishare_radio_start_send(m,0,NULL);';assert dispatcher.count(old)==1
    new='native_init_calls++;native_init_last_handled=mlme_vdev_state_init_event(m,e,0,NULL);return native_init_last_handled?QDF_STATUS_SUCCESS:QDF_STATUS_E_FAILURE;'
    native_init=function((root/SM).read_text(),'mlme_vdev_state_init_event')
    src=src.replace(dispatcher,INIT_GLUE.replace('NATIVE_INIT',native_init)+'\n'+dispatcher.replace(old,new,1),1)
    src=src.replace('int main(void) {','static int completed_prepare_regressions(void) {',1)
    src=src.replace('puts("MISHARE_COMPLETED_PREPARE_SSR_CANCEL_FIXTURE_PASS_ONLY");return 0;','return 0;',1)
    return src+HARNESS

def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=prepared.early.refused.rejected.queued.prepared.pe.destructor.pe.PIN:raise ValueError('Unexpected revision')
    native=prepared.early.refused.rejected.scheduler_audit(root)
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
        radio=(production/'wlan_hdd_mishare_radio.c').read_text();guard='r->ssr_fenced_sm_gate && r->ssr_sm_entry_aborted &&';assert radio.count(guard)==1
        # Mutate only the copied production radio file; positive and negative
        # variants compile against the same owner, native helper and harness.
        (d/'wlan_hdd_mishare_radio.c').write_text(radio.replace(guard,'r->ssr_fenced_sm_gate && true && /* negative: omit private SM entry abort */',1))
        subprocess.run(command,check=True)
        bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env)
        assert bad.returncode==-6 and 'EXPECTED_PRIVATE_SM_ENTRY_ABORT_PROVENANCE' in bad.stderr
        (d/'wlan_hdd_mishare_radio.c').unlink()
        c.write_text(source.replace(function(source,'main'),NATIVE_INIT_NEGATIVE_HARNESS.strip(),1))
        subprocess.run(command,check=True);subprocess.run([exe],check=True,timeout=45,env=env)
        init=function(source,'mlme_vdev_state_init_event')
        bad_init,count=re.subn(r'mlme_vdev_notify_down_complete\(vdev_mlme,\s*event_data_len,\s*event_data\);','/* negative: omit INIT validation-failure down notification */',init,count=1)
        assert count==1
        c.write_text(source.replace(function(source,'main'),NATIVE_INIT_NEGATIVE_HARNESS.strip(),1).replace(init,bad_init,1))
        subprocess.run(command,check=True);bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env)
        assert bad.returncode==-6 and 'EXPECTED_NATIVE_INIT_FAILURE_NOTIFICATION' in bad.stderr
    assert out.strip()=='MISHARE_SM_ENTRY_SSR_CANCEL_FIXTURE_PASS_ONLY'
    return {'status':out.strip(),'source_commit':prepared.early.refused.rejected.queued.prepared.pe.destructor.pe.PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h','wlan_hdd_mishare_radio.c','wlan_hdd_mishare_radio.h']},
            'native_scheduler_post_audit':native,'negative_control_missing_private_SM_entry_abort_rejected':True,'negative_control_missing_native_INIT_failure_notification_rejected':True,
            'native_INIT_handler':{'path':SM,'sha256':hashlib.sha256((root/SM).read_bytes()).hexdigest(),'function_sha256':hashlib.sha256(function((root/SM).read_text(),'mlme_vdev_state_init_event').encode()).hexdigest()},
            'checks':['all 0078 regressions retained, including native INIT START handling with modeled transition/START-request dispatch glue',
                      '2.4/5240 MHz, inline/deferred DP, batch, delayed object final-free; actual controller unlink/ref release',
                      '20 SM-entry controller/identity faults plus seven plan fields/current native plan reject before timer/PE/DP cleanup',
                      'callback during timer drain prevents controller retirement after users returns zero',
                      'duplicate/mixed origins sticky; native entry remains held even when INIT handler reports handled and notifies down-complete after validation failure',
                      'failed/partial preparation, actual native SM entry, sent START, pending reply, UP and non-SSR fence stay unsupported',
                      'radio_requested, BLOCKED/original submission error and ordinary transaction history remain; no SM/WMI/PM/START/STOP/DOWN fabricated'],
            'limitations':'Adds a shared-lock gate between START SM intent commitment and actual native dispatch entry. An original SSR fence before entry prevents native dispatch and records its own cancellation proof. Once entry is marked, no recovery is admitted, even if native INIT remains. The same encoder plan is rechecked before and after timer drain outside the radio lock. Work-exit and pending reservations drain before a separate body-abort origin. Failed/partial preparation, mismatched plans and committed SM dispatch remain unsupported. A post-prepare phase check preserves BLOCKED and avoids SM dispatch after fence. Preparation/SM function counters prove absence in the model. Other callback-entry histories stay unsupported. 0075 queue rejection and 0074 actual flush regressions retained. Original error and distinct flush/rejection histories retained. Native scheduler post is separately executed with modeled primitives; production radio rejection uses its transport model. Explicit qualified reset window and retained/serialized parents required. Production radio/runtime and native scheduler/PE/peer code execute with modeled QDF, SM dispatch, PE allocation/remaining cleanup, DP/peer physical lifecycle and parents. Native MLME destroy/recovery and active START/UP are not certified. No automatic parent/shutdown coordinator, backend activation, phone/firmware/RF or AirDrop proof.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
