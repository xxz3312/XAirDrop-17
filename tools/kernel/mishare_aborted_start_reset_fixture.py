#!/usr/bin/env python3
"""Actions-only SSR retirement of admitted START before preparation entry."""
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path
import mishare_refused_start_reset_fixture as refused
from mishare_recovery_fixture import function
ROOT=refused.ROOT
HARNESS=r'''
static struct mishare_runtime_owner *aborted_start_owner(unsigned freq,unsigned boundary) {
 struct mishare_runtime_owner *o=queued_start_owner(freq);unsigned prepare_before=refused_prepare_calls,sm_before=refused_sm_calls;
 if(boundary==0)refused_work_mode=2;else aborted_after_allowed=true;
 radio_run(false);
 assert(refused_prepare_calls==prepare_before && refused_sm_calls==sm_before);
 assert(o->radio && o->radio->start_work_admitted && !o->radio->start_prepare_entered && o->radio->ssr_fenced_before_prepare && o->radio->ssr_start_aborted);
 assert(state(o).recovery_radio_start_aborted && !state(o).recovery_radio_start_refused && !state(o).recovery_radio_start_flushed);
 assert(!state(o).ndi.radio_submit_error && !state(o).work_error && !state(o).work_pending && !state(o).work_users && !state(o).mc_drained);
 assert(!o->radio->state.pending && !o->radio->state.users && !radio_q_len && !radio_starts);
 return o;
}
static void assert_aborted_start_facts(struct mishare_runtime_owner *o) {
 struct mishare_runtime_status s=state(o);assert_reset_pe_facts(o);
 assert(s.ndi.radio_requested && !s.ndi.radio_submit_error && s.recovery_radio_start_aborted && !s.recovery_radio_start_refused && !s.recovery_radio_start_flushed && s.recovery_radio_released && !o->radio && !mishare_radios);
 assert(s.radio.ssr_cancelled_before_start && s.radio.ssr_start_body_aborted && !s.radio.ssr_start_callback_refused && !s.radio.ssr_start_submit_error && s.radio.phase==MISHARE_RADIO_BLOCKED && s.radio.error==-ESHUTDOWN && s.radio.closing);
 assert(!s.radio.start_attempted && !s.radio.stop_attempted && !s.radio.host_up && !s.radio.down_attempted && !s.radio.down_accepted && !s.radio.pending && !s.radio.users);
 assert(!radio_starts && !radio_stops && !radio_downs && !radio_timer && !radio_start_pm && !radio_stop_pm && !radio_rt && !radio_q_len);
}
int main(void) {
 assert(!refused_start_regressions());struct mishare_runtime_owner *o;
 for(unsigned band=0;band<2;band++)for(unsigned inline_cb=0;inline_cb<2;inline_cb++)for(unsigned boundary=0;boundary<2;boundary++) {
  reset_pe_test();o=aborted_start_owner(band?5240:2437,boundary);
  assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && !recovery_timer_cancels && !pe_deletes);
  stop_recovery(o);early_dp=inline_cb;assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);assert_aborted_start_facts(o);
  if(!inline_cb)finish_dp();
  assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations && !objects_live && !dp_objects && !ctx_locks);
 }
 reset_pe_test();o=aborted_start_owner(5240,0);struct wlan_objmgr_vdev *held=last_vdev;assert(!wlan_objmgr_vdev_try_get_ref(held,1));stop_recovery(o);
 struct mishare_runtime_reclaim_item item={o,99};o=NULL;assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS);assert_aborted_start_facts(item.owner);finish_dp();
 assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS && item.owner && !state(item.owner).freed);
 native_recovery_close();wlan_objmgr_vdev_release_ref(held,1);assert(!mishare_runtime_reclaim_batch(&psoc,&item,1) && !item.owner && !allocations);
 for(int fault=0;fault<18;fault++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=aborted_start_owner(5240,0);stop_recovery(o);struct mishare_radio *r=o->radio;
   if(fault==0)r->ssr_start_aborted=false;
   if(fault==1)r->ssr_fenced_before_prepare=false;
   if(fault==2)r->start_work_admitted=false;
   if(fault==3)r->start_prepare_entered=true;
   if(fault==4)r->state.ssr_start_body_aborted=false;
   if(fault==5)r->ssr_start_flushed=true;
   if(fault==6)r->ssr_start_refused=true;
   if(fault==7)r->preflight=true;
   if(fault==8)r->state.pending=1;
   if(fault==9)r->state.users=1;
   if(fault==10)r->state.error=-EIO;
   if(fault==11)r->owner=(void*)1;
   if(fault==12)(void)mishare_radio_validate(last_vdev->mlme,0,NULL);
   if(fault==13)o->state.recovery_radio_start_flushed=true;
   if(fault==14)o->state.ndi.radio_submit_error=-EIO;
   if(fault==15) {o->state.recovery_radio_start_aborted=false;o->state.recovery_radio_start_refused=true;}
   if(fault==16)r->start_callback_entered=false;
   if(fault==17)r->start_posted=false;
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio==r && !pe_deletes && !dp_detaches && !recovery_timer_cancels);
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 reset_pe_test();pid_t child=fork();assert(child>=0);
 if(!child) {
  o=aborted_start_owner(5240,0);stop_recovery(o);reset_radio_callback_drift=true;
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && o->radio->ssr_callback_after_fence && state(o).recovery_timer_released);
  assert(!pe_deletes && !dp_detaches && !state(o).recovery_radio_released);_Exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 for(int origin=0;origin<3;origin++) {
  reset_pe_test();child=fork();assert(child>=0);
  if(!child) {
   o=aborted_start_owner(5240,0);stop_recovery(o);struct wlan_objmgr_psoc other={9};
   mishare_runtime_radio_start_aborted(&other,last_vdev,o,o->radio);mishare_runtime_radio_start_aborted(&psoc,last_vdev,(void*)1,o->radio);assert(!state(o).ndi.completion_error);
   if(origin==0)mishare_runtime_radio_start_aborted(&psoc,last_vdev,o,o->radio);
   if(origin==1)mishare_runtime_radio_start_refused(&psoc,last_vdev,o,o->radio);
   if(origin==2)mishare_runtime_radio_start_flushed(&psoc,last_vdev,o,o->radio);
   assert(state(o).ndi.completion_error && mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && !pe_deletes);_Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* Once preparation's entry gate was crossed, even failure/no SM is held.
  * Successful preparation followed by fence must not overwrite BLOCKED/enter SM. */
 for(int boundary=1;boundary<=2;boundary++) {
  reset_pe_test();child=fork();assert(child>=0);
  if(!child) {
   o=queued_start_owner(5240);unsigned prepare_before=refused_prepare_calls,sm_before=refused_sm_calls;aborted_prepare_fence=boundary;radio_run(false);
   assert(refused_prepare_calls==prepare_before+1 && refused_sm_calls==sm_before && o->radio->start_prepare_entered);
   assert(o->radio->state.phase==MISHARE_RADIO_BLOCKED && !o->radio->ssr_fenced_before_prepare && !o->radio->ssr_start_aborted && !state(o).recovery_radio_start_aborted);
   health_recovering=true;assert(!cds_post_disable());assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && !pe_deletes && !dp_detaches);_Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 puts("MISHARE_ABORTED_START_SSR_CANCEL_FIXTURE_PASS_ONLY");return 0;
}
'''
NEGATIVE_HARNESS=r'''
int main(void) {
 reset_pe_test();struct mishare_runtime_owner *o=aborted_start_owner(5240,0);stop_recovery(o);
 o->radio->ssr_start_aborted=false;
 assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && "EXPECTED_PRIVATE_BODY_ABORT_PROVENANCE");_Exit(0);
}
'''

BOUNDARY=r'''
bool aborted_work_allowed(struct wlan_objmgr_vdev *v,void *o) {
 bool allowed=mishare_runtime_work_allowed(v,o);
 if(allowed && aborted_after_allowed) {aborted_after_allowed=false;assert(mishare_runtime_quiesce_psoc(wlan_vdev_get_psoc(v),MISHARE_QUIESCE_SSR)==1);}
 return allowed;
}
'''
PREPARE=r'''
int mishare_ndi_radio_prepare(struct wlan_objmgr_vdev *v,void *o,unsigned long c,uint32_t f) {
 unsigned mode=aborted_prepare_fence;aborted_prepare_fence=0;refused_prepare_calls++;
 if(mode==1)assert(mishare_runtime_quiesce_psoc(wlan_vdev_get_psoc(v),MISHARE_QUIESCE_SSR)==1);
 int ret=refused_native_prepare(v,o,c,f);
 if(mode==2) {assert(!ret);assert(mishare_runtime_quiesce_psoc(wlan_vdev_get_psoc(v),MISHARE_QUIESCE_SSR)==1);}
 return ret;
}
'''

def fixture(root):
    src=refused.fixture(root)
    needle='static unsigned refused_prepare_calls,refused_sm_calls;';assert src.count(needle)==1
    src=src.replace(needle,'static bool aborted_after_allowed;static unsigned aborted_prepare_fence;\n'+needle,1)
    prepare=function(src,'mishare_ndi_radio_prepare');src=src.replace(prepare,PREPARE.strip(),1)
    include='#include "wlan_hdd_mishare_radio.c"';assert src.count(include)==1
    src=src.replace(include,BOUNDARY+'\n#define mishare_runtime_work_allowed aborted_work_allowed\n'+include+'\n#undef mishare_runtime_work_allowed',1)
    src=src.replace('int main(void) {','static int refused_start_regressions(void) {',1)
    src=src.replace('puts("MISHARE_REFUSED_START_SSR_CANCEL_FIXTURE_PASS_ONLY");return 0;','return 0;',1)
    return src+HARNESS

def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=refused.rejected.queued.prepared.pe.destructor.pe.PIN:raise ValueError('Unexpected revision')
    native=refused.rejected.scheduler_audit(root)
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
        radio=(production/'wlan_hdd_mishare_radio.c').read_text();guard='r->ssr_fenced_before_prepare && r->ssr_start_aborted &&';assert radio.count(guard)==1
        # Mutate only the copied production radio file; positive and negative
        # variants compile against the same owner, native helper and harness.
        (d/'wlan_hdd_mishare_radio.c').write_text(radio.replace(guard,'r->ssr_fenced_before_prepare && true && /* negative: omit private pre-prepare abort */',1))
        subprocess.run(command,check=True)
        bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env)
        assert bad.returncode==-6 and 'EXPECTED_PRIVATE_BODY_ABORT_PROVENANCE' in bad.stderr
    assert out.strip()=='MISHARE_ABORTED_START_SSR_CANCEL_FIXTURE_PASS_ONLY'
    return {'status':out.strip(),'source_commit':refused.rejected.queued.prepared.pe.destructor.pe.PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h','wlan_hdd_mishare_radio.c','wlan_hdd_mishare_radio.h']},
            'native_scheduler_post_audit':native,'negative_control_missing_private_abort_fact_rejected':True,
            'checks':['all 0076 regressions retained; admitted work aborted at two boundaries before prepare/SM',
                      '2.4/5240 MHz, inline/deferred DP, batch, delayed object final-free; actual controller unlink/ref release',
                      '18 private controller/native/callback faults reject before timer/PE/DP cleanup',
                      'callback during timer drain prevents controller retirement after users returns zero',
                      'duplicate/mixed origins sticky; preparation-entry and post-prepare fences retain resources and never enter SM',
                      'executed preparation or SM, sent START, pending reply, UP and non-SSR fence stay unsupported',
                      'radio_requested, BLOCKED/original submission error and ordinary transaction history remain; no SM/WMI/PM/START/STOP/DOWN fabricated'],
            'limitations':'Adds only work-admitted START aborted by SSR before the synchronized preparation-entry gate. Work-exit and pending reservations drain before a separate body-abort origin. Preparation already entered remains unsupported even if it failed or fenced before SM. A post-prepare phase check preserves BLOCKED and avoids SM dispatch after fence. Preparation/SM function counters prove absence in the model. Other callback-entry histories stay unsupported. 0075 queue rejection and 0074 actual flush regressions retained. Original error and distinct flush/rejection histories retained. Native scheduler post is separately executed with modeled primitives; production radio rejection uses its transport model. Explicit qualified reset window and retained/serialized parents required. Production radio/runtime and native scheduler/PE/peer code execute with modeled QDF, SM dispatch, PE allocation/remaining cleanup, DP/peer physical lifecycle and parents. Native MLME destroy/recovery and active START/UP are not certified. No automatic parent/shutdown coordinator, backend activation, phone/firmware/RF or AirDrop proof.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
