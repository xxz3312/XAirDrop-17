#!/usr/bin/env python3
"""Actions-only SSR retirement after successful preparation before START SM commitment."""
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path
import mishare_aborted_start_reset_fixture as early
from mishare_recovery_fixture import function
ROOT=early.ROOT
HARNESS=r'''
static void prepared_plan_change(struct mishare_ndi_start_summary *p,unsigned n) {
 switch(n) {case 0:p->freq++;break;case 1:p->center_freq++;break;case 2:p->phy_mode++;break;case 3:p->tx_streams++;break;case 4:p->rx_streams++;break;case 5:p->beacon_interval++;break;case 6:p->dtim_period++;break;default:assert(0);}
}
static struct mishare_runtime_owner *completed_prepare_owner(unsigned freq,unsigned boundary) {
 struct mishare_runtime_owner *o=queued_start_owner(freq);unsigned prepares=refused_prepare_calls,sm=refused_sm_calls;
 aborted_prepare_fence=boundary;radio_run(false);
 assert(refused_prepare_calls==prepares+1 && refused_sm_calls==sm && !radio_q_len && !radio_starts);
 assert(o->radio->start_prepare_entered && o->radio->start_prepare_succeeded && !o->radio->start_sm_committed && o->radio->ssr_fenced_preparation && o->radio->ssr_prepared_abort);
 assert(state(o).recovery_radio_prepared_aborted && !state(o).recovery_radio_start_aborted && !state(o).recovery_radio_start_refused && !state(o).recovery_radio_start_flushed);
 assert(!state(o).ndi.radio_submit_error && !state(o).work_pending && !state(o).work_users && !state(o).work_error && !state(o).mc_drained);
 return o;
}
static void assert_completed_prepare_facts(struct mishare_runtime_owner *o) {
 struct mishare_runtime_status s=state(o);assert_reset_pe_facts(o);
 assert(s.ndi.radio_requested && s.recovery_radio_prepared_aborted && s.recovery_radio_released && !o->radio && !mishare_radios);
 assert(!s.recovery_radio_start_aborted && !s.recovery_radio_start_refused && !s.recovery_radio_start_flushed && !s.ndi.radio_submit_error);
 assert(s.radio.ssr_cancelled_before_start && s.radio.ssr_start_prepared_aborted && !s.radio.ssr_start_body_aborted && !s.radio.ssr_start_callback_refused && !s.radio.ssr_start_submit_error);
 assert(s.radio.phase==MISHARE_RADIO_BLOCKED && s.radio.error==-ESHUTDOWN && s.radio.closing && !s.radio.pending && !s.radio.users);
 assert(!s.radio.start_attempted && !s.radio.stop_attempted && !s.radio.host_up && !s.radio.down_attempted && !s.radio.down_accepted);
 assert(!radio_starts && !radio_stops && !radio_downs && !radio_timer && !radio_start_pm && !radio_stop_pm && !radio_rt);
}
int main(void) {
 assert(!aborted_start_regressions());struct mishare_runtime_owner *o;
 for(unsigned band=0;band<2;band++)for(unsigned inline_cb=0;inline_cb<2;inline_cb++)for(unsigned boundary=1;boundary<=2;boundary++) {
  reset_pe_test();o=completed_prepare_owner(band?5240:2437,boundary);assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && !pe_deletes);
  stop_recovery(o);early_dp=inline_cb;assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);assert_completed_prepare_facts(o);
  if(!inline_cb)finish_dp();
  assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations && !objects_live && !dp_objects && !ctx_locks);
 }
 reset_pe_test();o=completed_prepare_owner(5240,2);struct wlan_objmgr_vdev *held=last_vdev;assert(!wlan_objmgr_vdev_try_get_ref(held,1));stop_recovery(o);
 struct mishare_runtime_reclaim_item item={o,99};o=NULL;assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS);assert_completed_prepare_facts(item.owner);finish_dp();
 assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS && item.owner);native_recovery_close();wlan_objmgr_vdev_release_ref(held,1);
 assert(!mishare_runtime_reclaim_batch(&psoc,&item,1) && !item.owner && !allocations);
 /* Caller storage is copied at open, never borrowed. */
 reset_pe_test();o=ready_pre_radio(5240,true);struct mishare_ndi_start_summary caller_plan=state(o).ndi.start_plan;
 o->state.ndi.radio_requested=true;assert(mishare_radio_open(last_vdev,o->events,o,o->pe_cookie,5240,&caller_plan,&o->radio)==-EINPROGRESS);
 for(unsigned n=0;n<7;n++)prepared_plan_change(&caller_plan,n);
 aborted_prepare_fence=2;radio_run(false);stop_recovery(o);assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);assert_completed_prepare_facts(o);finish_dp();assert(!mishare_runtime_reclaim_ndi(&o) && !o);
 for(int fault=0;fault<20;fault++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=completed_prepare_owner(5240,2);stop_recovery(o);struct mishare_radio *r=o->radio;
   if(fault==0)r->ssr_prepared_abort=false;
   if(fault==1)r->start_prepare_succeeded=false;
   if(fault==2)r->start_sm_committed=true;
   if(fault==3)r->start_prepare_entered=false;
   if(fault==4)r->ssr_fenced_preparation=false;
   if(fault==5)r->state.ssr_start_prepared_aborted=false;
   if(fault==6)r->preflight=true;
   if(fault==7)r->state.pending=1;
   if(fault==8)r->state.users=1;
   if(fault==9)r->state.error=-EIO;
   if(fault==10)r->owner=(void*)1;
   if(fault==11)r->start_work_admitted=false;
   if(fault==12)r->start_callback_entered=false;
   if(fault==13)r->start_posted=false;
   if(fault==14)(void)mishare_radio_validate(last_vdev->mlme,0,NULL);
   if(fault==15)o->state.recovery_radio_start_aborted=true;
   if(fault==16)o->state.ndi.radio_submit_error=-EIO;
   if(fault==17) {o->state.recovery_radio_prepared_aborted=false;o->state.recovery_radio_start_aborted=true;}
   if(fault==18)plan_pdev_fail=true;
   if(fault==19)r->ssr_fenced_before_prepare=true;
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio==r && !recovery_timer_cancels && !pe_deletes && !dp_detaches);
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* All seven original plan fields are checked against the current native encoder. */
 for(unsigned n=0;n<8;n++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=completed_prepare_owner(5240,2);stop_recovery(o);
   if(n<7)prepared_plan_change(&o->radio->start_plan,n);else last_vdev->mlme->proto.generic.beacon_interval++;
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && !recovery_timer_cancels && !pe_deletes && !dp_detaches);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* A mismatch after successful preparation grants neither SM nor reset cleanup. */
 for(unsigned n=0;n<7;n++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=queued_start_owner(5240);prepared_plan_change(&o->radio->start_plan,n);unsigned sm=refused_sm_calls;aborted_prepare_fence=2;radio_run(false);
   assert(o->radio->start_prepare_entered && !o->radio->start_prepare_succeeded && !o->radio->start_sm_committed && !state(o).recovery_radio_prepared_aborted && refused_sm_calls==sm);
   health_recovering=true;assert(!cds_post_disable());assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && !pe_deletes);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 reset_pe_test();pid_t child=fork();assert(child>=0);
 if(!child) {
  o=completed_prepare_owner(5240,2);stop_recovery(o);prepared_timer_plan_drift=true;
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && state(o).recovery_timer_released && o->radio && !state(o).recovery_radio_released && !pe_deletes && !dp_detaches);_Exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 /* The SM commitment flag, even with native INIT and no sent START, holds. */
 reset_pe_test();child=fork();assert(child>=0);
 if(!child) {
  o=queued_start_owner(5240);unsigned sm=refused_sm_calls;prepared_fence_at_sm=true;radio_run(false);
  assert(o->radio->start_prepare_succeeded && o->radio->start_sm_committed && refused_sm_calls==sm+1 && ch_state==WLAN_VDEV_S_INIT && !radio_starts);
  assert(!state(o).recovery_radio_prepared_aborted && !o->radio->ssr_fenced_preparation);health_recovering=true;assert(!cds_post_disable());
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && !pe_deletes && !dp_detaches);_Exit(0);
 }
 assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 for(int origin=0;origin<4;origin++) {
  reset_pe_test();child=fork();assert(child>=0);
  if(!child) {
   o=completed_prepare_owner(5240,2);stop_recovery(o);struct wlan_objmgr_psoc other={9};
   mishare_runtime_radio_prepared_aborted(&other,last_vdev,o,o->radio);mishare_runtime_radio_prepared_aborted(&psoc,last_vdev,(void*)1,o->radio);assert(!state(o).ndi.completion_error);
   if(origin==0)mishare_runtime_radio_prepared_aborted(&psoc,last_vdev,o,o->radio);
   if(origin==1)mishare_runtime_radio_start_aborted(&psoc,last_vdev,o,o->radio);
   if(origin==2)mishare_runtime_radio_start_refused(&psoc,last_vdev,o,o->radio);
   if(origin==3)mishare_runtime_radio_start_flushed(&psoc,last_vdev,o,o->radio);
   assert(state(o).ndi.completion_error && mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && !pe_deletes);_Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 puts("MISHARE_COMPLETED_PREPARE_SSR_CANCEL_FIXTURE_PASS_ONLY");return 0;
}
'''
NEGATIVE_HARNESS=r'''
int main(void) {
 reset_pe_test();struct mishare_runtime_owner *o=completed_prepare_owner(5240,2);stop_recovery(o);
 o->radio->ssr_prepared_abort=false;
 assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && "EXPECTED_PRIVATE_COMPLETED_PREPARE_PROVENANCE");_Exit(0);
}
'''
PLAN_NEGATIVE_HARNESS=r'''
int main(void) {
 reset_pe_test();struct mishare_runtime_owner *o=completed_prepare_owner(5240,2);stop_recovery(o);
 last_vdev->mlme->proto.generic.beacon_interval++;
 assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && "EXPECTED_CURRENT_NATIVE_PLAN_RECHECK");_Exit(0);
}
'''

def fixture(root):
    src=early.fixture(root)
    needle='static unsigned refused_prepare_calls,refused_sm_calls;';assert src.count(needle)==1
    src=src.replace(needle,'static bool prepared_timer_plan_drift,prepared_fence_at_sm;\n'+needle,1)
    needle='recovery_timer_cancels++;';assert src.count(needle)==1
    src=src.replace(needle,needle+'if(prepared_timer_plan_drift)last_vdev->mlme->proto.generic.beacon_interval++;',1)
    needle='{refused_sm_calls++;';assert src.count(needle)==1
    src=src.replace(needle,needle+'if(prepared_fence_at_sm) {prepared_fence_at_sm=false;assert(mishare_runtime_quiesce_psoc(wlan_vdev_get_psoc(v),MISHARE_QUIESCE_SSR)==1);}',1)
    src=src.replace('int main(void) {','static int aborted_start_regressions(void) {',1)
    src=src.replace('puts("MISHARE_ABORTED_START_SSR_CANCEL_FIXTURE_PASS_ONLY");return 0;','return 0;',1)
    return src+HARNESS

def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=early.refused.rejected.queued.prepared.pe.destructor.pe.PIN:raise ValueError('Unexpected revision')
    native=early.refused.rejected.scheduler_audit(root)
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
        radio=(production/'wlan_hdd_mishare_radio.c').read_text();guard='r->ssr_fenced_preparation && r->ssr_prepared_abort &&';assert radio.count(guard)==1
        # Mutate only the copied production radio file; positive and negative
        # variants compile against the same owner, native helper and harness.
        (d/'wlan_hdd_mishare_radio.c').write_text(radio.replace(guard,'r->ssr_fenced_preparation && true && /* negative: omit private completed-prepare abort */',1))
        subprocess.run(command,check=True)
        bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env)
        assert bad.returncode==-6 and 'EXPECTED_PRIVATE_COMPLETED_PREPARE_PROVENANCE' in bad.stderr
        (d/'wlan_hdd_mishare_radio.c').unlink()
        c.write_text(source.replace(function(source,'main'),PLAN_NEGATIVE_HARNESS.strip(),1))
        subprocess.run(command,check=True);subprocess.run([exe],check=True,timeout=45,env=env)
        plan_guard='!radio_plan_equal(&observed_plan, &expected_plan)';assert radio.count(plan_guard)==1
        (d/'wlan_hdd_mishare_radio.c').write_text(radio.replace(plan_guard,'((void)expected_plan, false) /* negative: omit native plan recheck */',1))
        subprocess.run(command,check=True);bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env)
        assert bad.returncode==-6 and 'EXPECTED_CURRENT_NATIVE_PLAN_RECHECK' in bad.stderr
    assert out.strip()=='MISHARE_COMPLETED_PREPARE_SSR_CANCEL_FIXTURE_PASS_ONLY'
    return {'status':out.strip(),'source_commit':early.refused.rejected.queued.prepared.pe.destructor.pe.PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h','wlan_hdd_mishare_radio.c','wlan_hdd_mishare_radio.h']},
            'native_scheduler_post_audit':native,'negative_control_missing_private_prepared_abort_rejected':True,'negative_control_missing_current_plan_recheck_rejected':True,
            'checks':['all 0077 regressions retained; successful preparation and exact copied plan before any SM commitment',
                      '2.4/5240 MHz, inline/deferred DP, batch, delayed object final-free; actual controller unlink/ref release',
                      '20 private controller/native/callback faults and all seven copied plan fields/current native plan reject before timer/PE/DP cleanup',
                      'callback during timer drain prevents controller retirement after users returns zero',
                      'duplicate/mixed origins sticky; plan drift before/after timer and before startup rejected; caller plan copied by value; SM commitment retains even INIT',
                      'failed/partial preparation, SM commitment, sent START, pending reply, UP and non-SSR fence stay unsupported',
                      'radio_requested, BLOCKED/original submission error and ordinary transaction history remain; no SM/WMI/PM/START/STOP/DOWN fabricated'],
            'limitations':'Adds only successful START preparation whose rebuilt native seven-u32 encoder plan exactly matches the copied completed plan, with no SM commitment. The same encoder plan is rechecked before and after timer drain outside the radio lock. Work-exit and pending reservations drain before a separate body-abort origin. Failed/partial preparation, mismatched plans and committed SM dispatch remain unsupported. A post-prepare phase check preserves BLOCKED and avoids SM dispatch after fence. Preparation/SM function counters prove absence in the model. Other callback-entry histories stay unsupported. 0075 queue rejection and 0074 actual flush regressions retained. Original error and distinct flush/rejection histories retained. Native scheduler post is separately executed with modeled primitives; production radio rejection uses its transport model. Explicit qualified reset window and retained/serialized parents required. Production radio/runtime and native scheduler/PE/peer code execute with modeled QDF, SM dispatch, PE allocation/remaining cleanup, DP/peer physical lifecycle and parents. Native MLME destroy/recovery and active START/UP are not certified. No automatic parent/shutdown coordinator, backend activation, phone/firmware/RF or AirDrop proof.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
