#!/usr/bin/env python3
"""Actions-only SSR retirement of an accepted START flushed before callback execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import mishare_pre_radio_reset_fixture as prepared
from mishare_recovery_fixture import function

ROOT=prepared.ROOT
HARNESS=r'''
static struct mishare_runtime_owner *queued_start_owner(unsigned freq) {
 struct mishare_runtime_owner *o=ready_pre_radio(freq,true);
 assert(mishare_runtime_ndi_start(o)==-EINPROGRESS && o->radio && radio_q_len==1);
 assert(o->radio->start_posted && !o->radio->start_callback_entered && !radio_starts);
 return o;
}
static void assert_cancelled_start_facts(struct mishare_runtime_owner *o) {
 struct mishare_runtime_status s=state(o);assert_reset_pe_facts(o);
 assert(s.ndi.radio_requested && s.recovery_radio_start_flushed && s.recovery_radio_released && !o->radio && !mishare_radios);
 assert(s.radio.ssr_cancelled_before_start && s.radio.phase==MISHARE_RADIO_BLOCKED && s.radio.error==-ESHUTDOWN && s.radio.closing);
 assert(!s.radio.start_attempted && !s.radio.stop_attempted && !s.radio.host_up && !s.radio.down_attempted && !s.radio.down_accepted && !s.radio.pending && !s.radio.users);
 assert(!radio_starts && !radio_stops && !radio_downs && !radio_timer && !radio_start_pm && !radio_stop_pm && !radio_rt && !radio_q_len);
}
int main(void) {
 assert(!pre_radio_regressions());
 struct mishare_runtime_owner *o=NULL;
 assert(mishare_radio_ssr_cancel_check((void*)1,(void*)2,(void*)3,(void*)4,5,5240)==-ENOENT);
 assert(mishare_radio_ssr_cancel_release(NULL,NULL,NULL,NULL,0,0,NULL)==-EINVAL);
 for(unsigned band=0;band<2;band++)for(unsigned inline_cb=0;inline_cb<2;inline_cb++) {
  reset_pe_test();o=queued_start_owner(band?5240:2437);unsigned refs=last_vdev->refs;
  stop_recovery(o);assert(state(o).recovery_radio_start_flushed && !state(o).recovery_radio_released);
  assert(o->radio && o->radio->ssr_start_flushed && !o->radio->state.pending && last_vdev->refs==(int)refs);
  early_dp=inline_cb;assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);assert_cancelled_start_facts(o);
  if(!inline_cb) {assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);finish_dp();}
  assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations && !objects_live && !ctx_locks && !dp_objects && !mishare_radios);
 }
 reset_pe_test();o=queued_start_owner(5240);stop_recovery(o);
 struct mishare_runtime_reclaim_item item={o,99};o=NULL;
 assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS);assert_cancelled_start_facts(item.owner);
 finish_dp();assert(!mishare_runtime_reclaim_batch(&psoc,&item,1) && !item.owner && !item.result && !allocations);
 reset_pe_test();o=queued_start_owner(5240);struct wlan_objmgr_vdev *held=last_vdev;
 assert(!wlan_objmgr_vdev_try_get_ref(held,1));stop_recovery(o);
 assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);assert_cancelled_start_facts(o);finish_dp();
 assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && state(o).ndi_reclaim_ready);
 native_recovery_close();wlan_objmgr_vdev_release_ref(held,1);assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations);
 /* An MC observation without native queue flush cannot invent the origin. */
 reset_pe_test();pid_t child=fork();assert(child>=0);
 if(!child) {
  o=queued_start_owner(5240);mark_closed(o);mishare_runtime_mc_stopped(&psoc);
  assert(!state(o).mc_drained && !state(o).recovery_radio_start_flushed && mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);
  assert(!stop_mc() && state(o).recovery_radio_start_flushed && state(o).mc_drained);
  health_recovering=true;assert(!cds_post_disable() && state(o).recovery_window);
  assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);finish_dp();assert(!mishare_runtime_reclaim_ndi(&o) && !o);_Exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 /* Post-flush metadata alone cannot replace private controller/native proof. */
 for(int fault=0;fault<13;fault++) {
  reset_pe_test();child=fork();assert(child>=0);
  if(!child) {
   o=queued_start_owner(5240);stop_recovery(o);struct mishare_radio *r=o->radio;
   if(fault==0)r->ssr_start_flushed=false;
   if(fault==1)r->start_callback_entered=true;
   if(fault==2)r->preflight=true;
   if(fault==3)r->state.pending=1;
   if(fault==4)r->state.users=1;
   if(fault==5)r->owner=(void*)1;
   if(fault==6)r->events=(void*)1;
   if(fault==7)r->session_cookie++;
   if(fault==8)r->freq++;
   if(fault==9)r->state.start_attempted=true;
   if(fault==10)r->state.error=-EIO;
   if(fault==11)r->start_posted=false;
   if(fault==12)assert(mishare_radio_validate(last_vdev->mlme,0,NULL)!=QDF_STATUS_SUCCESS);
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && state(o).recovery_error && o->radio==r);
   assert(!state(o).recovery_radio_released && !recovery_timer_cancels && !pe_deletes && pe_heap_live==2 && !dp_detaches);
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio==r);_Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* A callback during timer drain is remembered after users drops to zero. */
 reset_pe_test();child=fork();assert(child>=0);
 if(!child) {
  o=queued_start_owner(5240);stop_recovery(o);reset_radio_callback_drift=true;
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && state(o).recovery_timer_released && o->radio && !o->radio->state.users);
  assert(o->radio->ssr_callback_after_fence && !state(o).recovery_radio_released && !pe_deletes && !dp_detaches && pe_heap_live==2);
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && recovery_timer_cancels==1);_Exit(0);
 }
 assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 /* Duplicate matched flush origins are sticky; foreign owner/psoc is ignored. */
 reset_pe_test();child=fork();assert(child>=0);
 if(!child) {
  o=queued_start_owner(5240);stop_recovery(o);struct wlan_objmgr_psoc other={9};
  mishare_runtime_radio_start_flushed(&other,last_vdev,o,o->radio);
  mishare_runtime_radio_start_flushed(&psoc,last_vdev,(void*)1,o->radio);
  assert(!state(o).ndi.completion_error);
  mishare_runtime_radio_start_flushed(&psoc,last_vdev,o,o->radio);
  assert(state(o).ndi.completion_error && mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && !pe_deletes && !dp_detaches);_Exit(0);
 }
 assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 /* Callback execution / sent START / queued reply / UP are not cancellation. */
 for(int phase=0;phase<6;phase++) {
  reset_pe_test();child=fork();assert(child>=0);
  if(!child) {
   if(phase==4) {
    o=ready_pre_radio(5240,true);radio_queue_fail=true;
    assert(mishare_runtime_ndi_start(o)<0 && o->radio && !radio_q_len);mark_closed(o);
   } else if(phase==5) {
    o=queued_start_owner(5240);assert(mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_REMOVE)==1);
   } else if(phase==0) {o=queued_start_owner(5240);mark_closed(o);radio_run(false);}
   else {
    o=queued_start_owner(5240);
    radio_run(false);
    if(phase>=2) {assert(radio_reply_start(0)==QDF_STATUS_SUCCESS);if(phase==3)radio_run(false);}
    mark_closed(o);
   }
   health_recovering=true;assert(!cds_post_disable());
   assert(!state(o).recovery_radio_start_flushed && !state(o).recovery_window && mishare_runtime_reclaim_ndi(&o)==-EUCLEAN);
   assert(o->radio && !pe_deletes && !dp_detaches && !radio_stops && !radio_downs);_Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 puts("MISHARE_QUEUED_START_SSR_CANCEL_FIXTURE_PASS_ONLY");return 0;
}
'''
NEGATIVE_HARNESS=r'''
int main(void) {
 reset_pe_test();struct mishare_runtime_owner *o=queued_start_owner(5240);stop_recovery(o);
 o->radio->ssr_start_flushed=false;
 assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && "EXPECTED_PRIVATE_FLUSH_PROVENANCE");
 _Exit(0);
}
'''


def fixture(root):
    src=prepared.fixture(root)
    src=src.replace('static bool reset_pe_drift,reset_geometry_drift,reset_completion_drift;', 'static bool reset_pe_drift,reset_geometry_drift,reset_completion_drift,reset_radio_callback_drift;',1)
    src=src.replace('reset_pe_drift=reset_geometry_drift=reset_completion_drift=false;', 'reset_pe_drift=reset_geometry_drift=reset_completion_drift=reset_radio_callback_drift=false;',1)
    needle='recovery_timer_cancels++;';assert src.count(needle)==1
    src=src.replace(needle,needle+'if(reset_radio_callback_drift)(void)mishare_radio_validate(last_vdev->mlme,0,NULL);',1)
    src=src.replace('int main(void) {','static int pre_radio_regressions(void) {',1)
    src=src.replace('puts("MISHARE_PRE_RADIO_PREPARED_RESET_FIXTURE_PASS_ONLY");return 0;','return 0;',1)
    return src+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=prepared.pe.destructor.pe.PIN:raise ValueError('Unexpected revision')
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
        radio=(production/'wlan_hdd_mishare_radio.c').read_text();guard='r->ssr_fenced_new && r->ssr_start_flushed &&';assert radio.count(guard)==1
        # Mutate only the copied production radio file; positive and negative
        # variants compile against the same owner, native helper and harness.
        (d/'wlan_hdd_mishare_radio.c').write_text(radio.replace(guard,'r->ssr_fenced_new && true && /* negative: omit private flush fact */',1))
        subprocess.run(command,check=True)
        bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env)
        assert bad.returncode==-6 and 'EXPECTED_PRIVATE_FLUSH_PROVENANCE' in bad.stderr
    assert out.strip()=='MISHARE_QUEUED_START_SSR_CANCEL_FIXTURE_PASS_ONLY'
    return {'status':out.strip(),'source_commit':prepared.pe.destructor.pe.PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h','wlan_hdd_mishare_radio.c','wlan_hdd_mishare_radio.h']},
            'negative_control_missing_private_flush_fact_rejected':True,
            'checks':['all prior pre-radio/pre-channel regressions retained; actual native scheduler queue flush publishes provenance',
                      '2.4/5240 MHz, inline/deferred DP, batch, delayed object final-free; actual controller unlink/ref release',
                      '13 private controller/native/callback faults reject before timer/PE/DP cleanup',
                      'callback during timer drain prevents controller retirement after users returns zero',
                      'duplicate flush notification is sticky; foreign owner/psoc ignored without dereference',
                      'executed START callback, sent START, pending reply, UP, queue rejection and non-SSR fence stay unsupported',
                      'radio_requested, BLOCKED/ESHUTDOWN and ordinary transaction history remain; no SM/WMI/PM/START/STOP/DOWN fabricated'],
            'limitations':'Only queue-accepted START flushed by native MC shutdown before any START callback execution. Explicit qualified reset window and retained/serialized parents required. Production radio/runtime and native scheduler/PE/peer code execute with modeled QDF, SM dispatch, PE allocation/remaining cleanup, DP/peer physical lifecycle and parents. Native MLME destroy/recovery and active START/UP are not certified. No automatic parent/shutdown coordinator, backend activation, phone/firmware/RF or AirDrop proof.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
