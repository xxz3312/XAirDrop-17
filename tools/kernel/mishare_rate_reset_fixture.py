#!/usr/bin/env python3
"""Actions-only configured pre-START SSR retirement using native reset functions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import mishare_pre_radio_reset_fixture as pre

ROOT=pre.ROOT
HARNESS=r'''
static struct mishare_runtime_owner *configured_rate(unsigned freq,unsigned failure) {
 struct mishare_runtime_owner *o=ready_pre_radio(freq,false);
 struct mishare_runtime_rate_request q={.preamble=3,.nss=1,.mcs=7};
 struct mishare_runtime_rate_result r={.attempted=true,.complete=!failure,
 .attempted_mask=failure?(1U<<failure)-1:7,.submitted_mask=failure?(1U<<(failure-1))-1:7,
 .result=failure?-EIO:0,.first_error=failure?-EIO:0};
 struct wlan_objmgr_vdev *v=NULL;
 assert(!mishare_runtime_rate_begin(o,&q,&v) && v==last_vdev);
 /* Model a native submission result while a real runtime reservation is held.
  * Actual executor/WMA transport is exercised by its separate rate fixture. */
 assert(!mishare_runtime_work_get(v,o));mishare_runtime_rate_posted(o,0);
 mishare_runtime_rate_complete(o,&r);mishare_runtime_work_put(v,o);
 assert(state(o).rate.completed && !state(o).rate.integrity_error && "EXPECTED_RATE_RESET_RECEIPT");
 return o;
}
static void rate_history(struct mishare_runtime_owner *o,struct mishare_runtime_rate_status before) {
 struct mishare_runtime_rate_status r=state(o).rate;
 assert(r.requested && r.posted && r.accepted && r.completed && !r.integrity_error &&
 r.receipt.attempted==before.receipt.attempted && r.receipt.complete==before.receipt.complete &&
 r.receipt.attempted_mask==before.receipt.attempted_mask && r.receipt.submitted_mask==before.receipt.submitted_mask &&
 r.receipt.result==before.receipt.result && r.receipt.first_error==before.receipt.first_error &&
 r.request.preamble==before.request.preamble && r.request.bw==before.request.bw && r.request.gi==before.request.gi &&
 r.request.nss==before.request.nss && r.request.mcs==before.request.mcs &&
 "EXPECTED_RATE_RESET_HISTORY");
}
int main(void) {
 assert(!pre_rate_regressions());
 struct mishare_runtime_owner *o=NULL;
 for(unsigned band=0;band<2;band++)for(unsigned failure=0;failure<4;failure++)for(unsigned inline_cb=0;inline_cb<2;inline_cb++) {
  reset_pe_test();o=configured_rate(band?5240:2437,failure);
  struct mishare_runtime_rate_status before=state(o).rate;
  assert(mishare_runtime_destroy(&o)==-EOPNOTSUPP && !pe_deletes && !dp_detaches && "EXPECTED_RATE_RESET_ORDINARY");
  assert(mishare_runtime_ndi_start_plan(o)==-EOPNOTSUPP && mishare_runtime_ndi_start(o)==-EOPNOTSUPP);
  stop_recovery(o);early_dp=inline_cb;
  assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && o && "EXPECTED_RATE_RESET_BEGIN");
  assert(state(o).rate.reset_admitted && !state(o).rate.reset_completed && "EXPECTED_RATE_RESET_ADMISSION");
  rate_history(o,before);
  assert(pe_deletes==1 && dp_detaches==1 && !reset_wmi_calls && !wire_deletes && "EXPECTED_RATE_RESET_NO_FW_DELETE");
  if(!inline_cb){assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && pe_deletes==1);finish_dp();}
  assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations && !objects_live && !ctx_locks && !dp_objects && "EXPECTED_RATE_RESET_FINAL");
 }
 { /* Proven pre-publication failure uses the existing prepared reset policy. */
  reset_pe_test();o=ready_pre_radio(5240,false);
  struct mishare_runtime_rate_request q={.preamble=3,.nss=1,.mcs=7};struct wlan_objmgr_vdev *v=NULL;
  assert(!mishare_runtime_rate_begin(o,&q,&v));mishare_runtime_rate_posted(o,-ENOMEM);stop_recovery(o);
  assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && !state(o).rate.reset_admitted && !state(o).rate.reset_completed && state(o).rate.receipt.result==-ENOMEM && "EXPECTED_RATE_RESET_ZERO_ATTEMPT");
  finish_dp();assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations);
 }
 reset_pe_test();o=configured_rate(5240,2);struct mishare_runtime_rate_status before=state(o).rate;stop_recovery(o);
 struct mishare_runtime_reclaim_item item={o,99};o=NULL;
 assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS);rate_history(item.owner,before);
 finish_dp();assert(!mishare_runtime_reclaim_batch(&psoc,&item,1) && !item.owner && !item.result && !allocations && "EXPECTED_RATE_RESET_BATCH");
 reset_pe_test();o=configured_rate(5240,3);before=state(o).rate;
 struct wlan_objmgr_vdev *held=last_vdev;assert(!wlan_objmgr_vdev_try_get_ref(held,1));stop_recovery(o);
 assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);finish_dp();
 assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && state(o).rate.reset_completed && state(o).host_delete_accepted && "EXPECTED_RATE_RESET_WAIT_FINAL_FREE");
 rate_history(o,before);assert(mishare_runtime_destroy(&o)==-EOPNOTSUPP && o);
 native_recovery_close();wlan_objmgr_vdev_release_ref(held,1);
 assert(!mishare_runtime_reclaim_final(&o) && !o && !allocations && "EXPECTED_RATE_RESET_FINAL_AFTER_CLOSE");
 /* Reuse the actual CDS/HTC/HIF/WMI qualification failure matrix with rate history. */
 for(int fault=0;fault<6;fault++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=configured_rate(5240,1);mark_closed(o);health_recovering=fault!=0;
   recovery_bad_reset=fault==1;if(fault==2)recovery_cds.htc_ctx=NULL;
   recovery_rx_status=fault==3?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;
   recovery_bad_validate=fault==4?1:fault==5?3:0;
   recovery_validates=0; /* Isolate the native qualification calls from setup. */
   QDF_STATUS s=cds_post_disable();assert((s!=QDF_STATUS_SUCCESS)==(fault==3));
   assert(!state(o).recovery_window && mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS &&
    !state(o).rate.reset_admitted && !pe_deletes && !dp_detaches && !recovery_timer_cancels && "EXPECTED_RATE_RESET_NATIVE_WINDOW");_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 for(int fault=0;fault<7;fault++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=configured_rate(5240,2);before=state(o).rate;stop_recovery(o);
   int expected=-EUCLEAN;
   if(fault==0)o->state.rate.integrity_error=true;
   if(fault==1){o->state.rate.completed=false;expected=-EINPROGRESS;}
   if(fault==2){o->state.ndi.radio_requested=true;expected=-EOPNOTSUPP;}
   if(fault==3){native_recovery_close();expected=-ESHUTDOWN;}
   if(fault==4)wma_context.interfaces[7].vdev=NULL;
   if(fault==5)pe_slot.curr_op_freq=5180;
   if(fault==6)o->state.rate.reset_completed=true;
   assert(mishare_runtime_reclaim_ndi(&o)==expected && o && !pe_deletes && !dp_detaches && !recovery_timer_cancels && "EXPECTED_RATE_RESET_FAULT_RETAIN");
   assert(state(o).rate.receipt.result==before.receipt.result && state(o).rate.receipt.attempted_mask==before.receipt.attempted_mask);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 reset_pe_test();pid_t partial=fork();assert(partial>=0);
 if(!partial){
  o=configured_rate(5240,1);before=state(o).rate;stop_recovery(o);reset_obj_failure=true;
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && state(o).rate.reset_admitted && !state(o).rate.reset_completed && state(o).recovery_error && "EXPECTED_RATE_RESET_PARTIAL_RETAIN");
  unsigned attempts=reset_force_detaches;rate_history(o,before);
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && reset_force_detaches==attempts);_Exit(0);
 }
 int status;assert(waitpid(partial,&status,0)==partial && WIFEXITED(status) && !WEXITSTATUS(status));
 puts("MISHARE_RATE_RESET_FIXTURE_PASS_ONLY");return 0;
}
'''


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('Native composition runs on Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=pre.pe.destructor.pe.PIN:raise ValueError('Unexpected native revision')
    source=pre.fixture(root)
    assert source.count('int main(void) {')==1
    source=source.replace('int main(void) {','static int pre_rate_regressions(void) {',1).replace('puts("MISHARE_PRE_RADIO_PREPARED_RESET_FIXTURE_PASS_ONLY");','')+HARNESS
    production=ROOT/'kernel/popsicle-hdd'
    original=(production/'wlan_hdd_mishare_runtime.c').read_text()
    mutations=[
        ('entry->state.rate.reset_admitted = true;','entry->state.rate.reset_admitted = false;'),
        ('entry->state.rate.reset_completed = true;','entry->state.rate.reset_completed = false;'),
    ]
    a=original.index('static bool mishare_runtime_ndi_recovery_candidate(');b=original.index('unsigned int mishare_runtime_recovery_candidates(',a)
    body=original[a:b];assert body.count('mishare_runtime_rate_reset_check(entry)')==1
    for n,_ in mutations:assert original.count(n)==1,n
    controls=[original.replace(n,r,1) for n,r in mutations]
    controls.append(original.replace(body,body.replace('mishare_runtime_rate_reset_check(entry)','mishare_runtime_rate_retire_check(entry)',1),1))
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/module.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:(d/n).write_text('/* modeled native primitive */\n')
        c=d/'test.c';c.write_text(source);exe=d/'test'
        command=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(c),'-o',str(exe)]
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        subprocess.run(command,check=True);out=subprocess.check_output([exe],text=True,env=env,timeout=60).strip()
        assert out=='MISHARE_RATE_RESET_FIXTURE_PASS_ONLY',out
        for changed in controls:
            (d/'wlan_hdd_mishare_runtime.c').write_text(changed);subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=60)
            assert bad.returncode==-6 and ('EXPECTED_RATE_RESET_' in bad.stderr or 'recovery_window' in bad.stderr),(bad.returncode,bad.stderr[-2000:])
    return {'status':out,'source_commit':pre.pe.destructor.pe.PIN,'configured_combinations':16,'native_mutation_controls':len(controls),'qualification_failures':6,'retention_faults':7,'production_sha256':hashlib.sha256(original.encode()).hexdigest(),'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),'limitations':'Production registry/rate hooks and prepared SSR cleanup plus selected native CDS/HIF/WMI/PE/timer/DP/object lifecycle functions. Native rate submission results, refs/locks/IRQ/firmware/DP physical primitives modeled; no ordinary post-config cleanup, START/UP, full parent/remove coordination, RF or Apple certification.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
