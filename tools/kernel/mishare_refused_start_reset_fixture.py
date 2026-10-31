#!/usr/bin/env python3
"""Actions-only SSR retirement after START callback work admission refusal."""
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path
import mishare_rejected_start_reset_fixture as rejected
from mishare_recovery_fixture import function
ROOT=rejected.ROOT
HARNESS=r'''
static struct mishare_runtime_owner *refused_start_owner(unsigned freq) {
 struct mishare_runtime_owner *o=queued_start_owner(freq);unsigned prepare_before=refused_prepare_calls,sm_before=refused_sm_calls;
 mark_closed(o);radio_run(false);
 assert(refused_prepare_calls==prepare_before && refused_sm_calls==sm_before);
 assert(o->radio && o->radio->start_callback_entered && o->radio->ssr_start_refused && o->radio->state.ssr_start_callback_refused);
 assert(!state(o).recovery_radio_start_flushed && state(o).recovery_radio_start_refused && !state(o).ndi.radio_submit_error);
 assert(!state(o).work_pending && !state(o).work_users && !state(o).work_error && !state(o).mc_drained);
 assert(!o->radio->state.pending && !o->radio->state.users && !radio_q_len && !radio_starts);
 return o;
}
static void assert_refused_start_facts(struct mishare_runtime_owner *o) {
 struct mishare_runtime_status s=state(o);assert_reset_pe_facts(o);
 assert(s.ndi.radio_requested && !s.ndi.radio_submit_error && s.recovery_radio_start_refused && !s.recovery_radio_start_flushed && s.recovery_radio_released && !o->radio && !mishare_radios);
 assert(s.radio.ssr_cancelled_before_start && s.radio.ssr_start_callback_refused && !s.radio.ssr_start_submit_error && s.radio.phase==MISHARE_RADIO_BLOCKED && s.radio.error==-ESHUTDOWN && s.radio.closing);
 assert(!s.radio.start_attempted && !s.radio.stop_attempted && !s.radio.host_up && !s.radio.down_attempted && !s.radio.down_accepted && !s.radio.pending && !s.radio.users);
 assert(!radio_starts && !radio_stops && !radio_downs && !radio_timer && !radio_start_pm && !radio_stop_pm && !radio_rt && !radio_q_len);
}
int main(void) {
 assert(!rejected_start_regressions());
 struct mishare_runtime_owner *o;
 for(unsigned band=0;band<2;band++)for(unsigned inline_cb=0;inline_cb<2;inline_cb++) {
  reset_pe_test();o=refused_start_owner(band?5240:2437);
  assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && !recovery_timer_cancels && !pe_deletes);
  stop_recovery(o);early_dp=inline_cb;
  assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);assert_refused_start_facts(o);
  if(!inline_cb)finish_dp();
  assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations && !objects_live && !dp_objects && !ctx_locks);
 }
 reset_pe_test();o=refused_start_owner(5240);struct wlan_objmgr_vdev *held=last_vdev;
 assert(!wlan_objmgr_vdev_try_get_ref(held,1));stop_recovery(o);
 struct mishare_runtime_reclaim_item item={o,99};o=NULL;
 assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS);assert_refused_start_facts(item.owner);finish_dp();
 assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS && item.owner && !state(item.owner).freed);
 wlan_objmgr_vdev_release_ref(held,1);assert(!mishare_runtime_reclaim_batch(&psoc,&item,1) && !item.owner && !allocations);
 for(int fault=0;fault<16;fault++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=refused_start_owner(5240);stop_recovery(o);struct mishare_radio *r=o->radio;
   if(fault==0)r->ssr_start_refused=false;
   if(fault==1)r->start_callback_entered=false;
   if(fault==2)r->ssr_fenced_new=false;
   if(fault==3)r->start_posted=false;
   if(fault==4)r->ssr_start_flushed=true;
   if(fault==5)r->preflight=true;
   if(fault==6)r->state.pending=1;
   if(fault==7)r->state.users=1;
   if(fault==8)r->state.error=-EIO;
   if(fault==9)r->start_post_error=-EIO;
   if(fault==10)(void)mishare_radio_validate(last_vdev->mlme,0,NULL);
   if(fault==11)r->owner=(void*)1;
   if(fault==12)r->state.ssr_start_callback_refused=false;
   if(fault==13)o->state.recovery_radio_start_flushed=true;
   if(fault==14)o->state.ndi.radio_submit_error=-EIO;
   if(fault==15) {o->state.recovery_radio_start_refused=false;o->state.recovery_radio_start_flushed=true;}
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio==r && !pe_deletes && !dp_detaches && !recovery_timer_cancels);
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 reset_pe_test();pid_t child=fork();assert(child>=0);
 if(!child) {
  o=refused_start_owner(5240);stop_recovery(o);reset_radio_callback_drift=true;
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && o->radio->ssr_callback_after_fence && state(o).recovery_timer_released);
  assert(!pe_deletes && !dp_detaches && !state(o).recovery_radio_released);_Exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 /* Mixed/duplicate origins are sticky; foreign identity is ignored. */
 for(int mixed=0;mixed<2;mixed++) {
  reset_pe_test();child=fork();assert(child>=0);
  if(!child) {
   o=refused_start_owner(5240);stop_recovery(o);struct wlan_objmgr_psoc other={9};
   mishare_runtime_radio_start_refused(&other,last_vdev,o,o->radio);
   mishare_runtime_radio_start_refused(&psoc,last_vdev,(void*)1,o->radio);assert(!state(o).ndi.completion_error);
   if(mixed)mishare_runtime_radio_start_flushed(&psoc,last_vdev,o,o->radio);
   else mishare_runtime_radio_start_refused(&psoc,last_vdev,o,o->radio);
   assert(state(o).ndi.completion_error && mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && !pe_deletes);_Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* Actual work-enter boundary ordering: late fence, admitted work, other error,
  * executed preparation failure and REMOVE never gain the SSR refusal proof. */
 for(int phase=0;phase<5;phase++) {
  if(phase==1)continue; /* 0077 covers admitted work fenced before prepare. */
  reset_pe_test();child=fork();assert(child>=0);
  if(!child) {
   o=queued_start_owner(5240);unsigned before=refused_prepare_calls;
   if(phase==0)refused_work_mode=1; /* fence after callback-entry flag */
   if(phase==1)refused_work_mode=2; /* fence after work_enter accepted */
   if(phase==2) {mark_closed(o);refused_work_mode=3;}
   if(phase==3)ch_scan=true;
   if(phase==4)assert(mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_REMOVE)==1);
   radio_run(false);refused_work_mode=0;
   if(phase==3) {assert(refused_prepare_calls==before+1);ch_scan=false;mark_closed(o);}
   else assert(refused_prepare_calls==before);
   assert(!state(o).recovery_radio_start_refused && !state(o).recovery_radio_start_flushed);
   health_recovering=true;assert(!cds_post_disable());
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && !pe_deletes && !dp_detaches);_Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 puts("MISHARE_REFUSED_START_SSR_CANCEL_FIXTURE_PASS_ONLY");return 0;
}
'''
NEGATIVE_HARNESS=r'''
int main(void) {
 reset_pe_test();struct mishare_runtime_owner *o=refused_start_owner(5240);stop_recovery(o);
 o->radio->ssr_start_refused=false;
 assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && "EXPECTED_PRIVATE_REFUSAL_PROVENANCE");_Exit(0);
}
'''

BOUNDARY=r'''
static unsigned refused_prepare_calls,refused_sm_calls;
static int refused_work_mode;
int mishare_ndi_radio_prepare(struct wlan_objmgr_vdev *v,void *o,unsigned long c,uint32_t f) {
 refused_prepare_calls++;return refused_native_prepare(v,o,c,f);
}
int refused_work_enter(struct wlan_objmgr_vdev *v,void *o) {
 if(refused_work_mode==1) {refused_work_mode=0;assert(mishare_runtime_quiesce_psoc(wlan_vdev_get_psoc(v),MISHARE_QUIESCE_SSR)==1);}
 if(refused_work_mode==2) {refused_work_mode=0;int ret=mishare_runtime_work_enter(v,o);assert(!ret);assert(mishare_runtime_quiesce_psoc(wlan_vdev_get_psoc(v),MISHARE_QUIESCE_SSR)==1);return ret;}
 if(refused_work_mode==3) {refused_work_mode=0;return -EIO;}
 return mishare_runtime_work_enter(v,o);
}
'''

def fixture(root):
    src=rejected.fixture(root)
    prepare=function(src,'mishare_ndi_radio_prepare')
    src=src.replace(prepare,prepare.replace('mishare_ndi_radio_prepare','refused_native_prepare',1),1)
    include='#include "wlan_hdd_mishare_radio.c"';assert src.count(include)==1
    src=src.replace(include,BOUNDARY+'\n#define mishare_runtime_work_enter refused_work_enter\n'+include+'\n#undef mishare_runtime_work_enter',1)
    sm=function(src,'radio_sm_dispatch');src=src.replace(sm,sm.replace('{','{refused_sm_calls++;',1),1)
    src=src.replace('int main(void) {','static int rejected_start_regressions(void) {',1)
    src=src.replace('puts("MISHARE_REJECTED_START_SSR_CANCEL_FIXTURE_PASS_ONLY");return 0;','return 0;',1)
    return src+HARNESS

def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=rejected.queued.prepared.pe.destructor.pe.PIN:raise ValueError('Unexpected revision')
    native=rejected.scheduler_audit(root)
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
        radio=(production/'wlan_hdd_mishare_radio.c').read_text();guard='r->ssr_fenced_new && r->ssr_start_refused &&';assert radio.count(guard)==1
        # Mutate only the copied production radio file; positive and negative
        # variants compile against the same owner, native helper and harness.
        (d/'wlan_hdd_mishare_radio.c').write_text(radio.replace(guard,'r->ssr_fenced_new && true && /* negative: omit private work refusal */',1))
        subprocess.run(command,check=True)
        bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env)
        assert bad.returncode==-6 and 'EXPECTED_PRIVATE_REFUSAL_PROVENANCE' in bad.stderr
    assert out.strip()=='MISHARE_REFUSED_START_SSR_CANCEL_FIXTURE_PASS_ONLY'
    return {'status':out.strip(),'source_commit':rejected.queued.prepared.pe.destructor.pe.PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h','wlan_hdd_mishare_radio.c','wlan_hdd_mishare_radio.h']},
            'native_scheduler_post_audit':native,'negative_control_missing_private_refusal_fact_rejected':True,
            'checks':['all 0075 regressions retained; callback work admission refused after original SSR fence; no prepare or SM dispatch',
                      '2.4/5240 MHz, inline/deferred DP, batch, delayed object final-free; actual controller unlink/ref release',
                      '16 private controller/native/callback faults reject before timer/PE/DP cleanup',
                      'callback during timer drain prevents controller retirement after users returns zero',
                      'mixed and duplicate origins remain sticky; late fence, admitted body, other errors, preparation failure and REMOVE stay held',
                      'executed preparation or SM, sent START, pending reply, UP and non-SSR fence stay unsupported',
                      'radio_requested, BLOCKED/original submission error and ordinary transaction history remain; no SM/WMI/PM/START/STOP/DOWN fabricated'],
            'limitations':'Adds only accepted START whose callback enters after original SSR fence but work_enter returns ESHUTDOWN before radio_execute. Preparation/SM function counters prove absence in the model. Other callback-entry histories stay unsupported. 0075 queue rejection and 0074 actual flush regressions retained. Original error and distinct flush/rejection histories retained. Native scheduler post is separately executed with modeled primitives; production radio rejection uses its transport model. Explicit qualified reset window and retained/serialized parents required. Production radio/runtime and native scheduler/PE/peer code execute with modeled QDF, SM dispatch, PE allocation/remaining cleanup, DP/peer physical lifecycle and parents. Native MLME destroy/recovery and active START/UP are not certified. No automatic parent/shutdown coordinator, backend activation, phone/firmware/RF or AirDrop proof.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
