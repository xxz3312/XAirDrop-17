#!/usr/bin/env python3
"""Actions-only host finalization after ordinary NDI DELETE and DP completion."""
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path
import mishare_completion_fixture as completion
ROOT=completion.ROOT
HARNESS=r'''
static struct mishare_runtime_owner *completed_subject;
static void completed_delete_fault(void) {mishare_runtime_ndi_dp_freed(completed_subject);}
static struct mishare_runtime_owner *completed_ndi(bool inline_cb) {
 struct mishare_runtime_owner *o=early_ndi();normal_delete_reply(o);early_dp=inline_cb;
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && dp_detaches==1);
 if(!inline_cb)finish_dp();
 assert(state(o).ndi.delete_submitted && state(o).ndi.delete_replied && state(o).ndi.dp_detaching && state(o).ndi.dp_detach_submitted && state(o).ndi.dp_freed);
 assert(!state(o).ndi.create.timer_ready && !state(o).ndi.create.stats_owned && !state(o).ndi.completion_error);
 return o;
}
static void completed_no_new_transport(void) {
 assert(wire_deletes==1 && dp_detaches==1 && !recovery_timer_cancels && !recovery_timer_frees);
 assert(!timers_live && !dp_objects && !stats_live);
}
int main(void) {
 struct mishare_runtime_owner *o=NULL;
 for(int inline_cb=0;inline_cb<2;inline_cb++) {
  reset_recovery();o=completed_ndi(inline_cb);
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && !delete_calls);
  stop_recovery(o);assert(state(o).recovery_window && !state(o).ndi_completed_reclaim);
  assert(!mishare_runtime_reclaim_ndi(&o) && !o && !objects_live && !allocations);
  completed_no_new_transport();assert(delete_calls==1);
 }
 /* Batch uses the same route and retains normal completion history while a
  * real external VDEV ref delays physical final-free. */
 reset_recovery();defer_ref=1;o=completed_ndi(false);struct wlan_objmgr_vdev *held=last_vdev;
 stop_recovery(o);struct mishare_runtime_reclaim_item item={o,0};
 assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS && item.owner==o);
 struct mishare_runtime_status s=state(o);
 assert(s.ndi_completed_reclaim && s.ndi_reclaim_started && s.ndi_reclaim_ready && !s.ndi.active && !s.ndi.create.dp_attached);
 assert(s.ndi.delete_pending && s.ndi.delete_submitted && s.ndi.delete_replied && s.ndi.dp_detaching && s.ndi.dp_freed);
 assert(s.ndi.create.wire_attempted && s.ndi.create.wire_accepted && !s.recovery_dp_attempted && !s.recovery_dp_freed && !s.recovery_timer_attempted && !s.recovery_timer_released);
 assert(s.blocked && s.quiesced==MISHARE_QUIESCE_SSR && held->refs==1 && held->mlme && held->mlme->mgmt.generic.type==9);
 assert(mishare_runtime_reclaim_host(&o)==-EUCLEAN);
 native_recovery_close();wlan_objmgr_vdev_release_ref(held,2);
 assert(!mishare_runtime_reclaim_batch(&psoc,&item,1) && !item.owner && !allocations && !objects_live);o=NULL;
 completed_no_new_transport();
 /* Inline free cannot turn a failed detach return into successful submission. */
 reset_recovery();pid_t failed_submit=fork();assert(failed_submit>=0);
 if(!failed_submit) {
  o=early_ndi();normal_delete_reply(o);early_dp=true;completed_fail_after_callback=true;
  assert(mishare_runtime_destroy(&o)==-EUCLEAN && state(o).ndi.dp_freed && !state(o).ndi.dp_detach_submitted);
  o->state.ndi.create.stats_owned=false; /* native model actually reset the ID */
  mark_closed(o);health_recovering=true;assert(!cds_post_disable() && !state(o).recovery_window);
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && !delete_calls);
  completed_no_new_transport();_Exit(0);
 }
 int submit_status;assert(waitpid(failed_submit,&submit_status,0)==failed_submit && WIFEXITED(submit_status) && !WEXITSTATUS(submit_status));
 /* Incomplete ordinary proof cannot be converted to completed recovery. */
 for(int fault=1;fault<4;fault++) {
  reset_recovery();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=early_ndi();
   if(fault>=1)assert(mishare_runtime_destroy(&o)==-EINPROGRESS);
   if(fault>=2)reply();
   if(fault>=3)assert(mishare_runtime_destroy(&o)==-EINPROGRESS);
   mark_closed(o);health_recovering=true;assert(!cds_post_disable());
   unsigned deletes=delete_calls,detaches=dp_detaches,wires_before=wire_deletes;
   int ret=mishare_runtime_reclaim_ndi(&o);
   assert(ret==-EUCLEAN && !state(o).ndi_completed_reclaim);
   assert(delete_calls==(int)deletes && dp_detaches==(int)detaches && wire_deletes==(int)wires_before);
   if(fault==3) {
    finish_dp();assert(!state(o).recovery_window);
    assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && !delete_calls); /* no qualified WMI window was opened */
   }
   _Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* Closed parent window, native drift, transaction history, delete failure,
  * and a completion error concurrent with host deletion all retain diagnosis. */
 for(int fault=0;fault<6;fault++) {
  reset_recovery();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=completed_ndi(false);stop_recovery(o);
   if(fault==0)native_recovery_close();
   if(fault==1)ch_state=1;
   if(fault==2)last_vdev->mlme->ext_vdev_ptr=(void*)1;
   if(fault==3)o->events->txn.serial=1;
   if(fault==4)delete_fail=1;
   if(fault==5) {completed_subject=o;completed_delete_hook=completed_delete_fault;}
   assert(mishare_runtime_reclaim_ndi(&o)==(fault==0?-ESHUTDOWN:-EUCLEAN) && o);
   unsigned deletes=delete_calls;
   assert(mishare_runtime_reclaim_ndi(&o)==(fault==0?-ESHUTDOWN:-EUCLEAN) && delete_calls==(int)deletes);
   if(fault==5) {assert(state(o).ndi.completion_error && state(o).freed && !objects_live && allocations==1);}
   else assert(objects_live==1);
   completed_no_new_transport();_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* Fully completed transport does not erase prior prepared/peer ownership. */
 reset_recovery();pid_t child=fork();assert(child>=0);
 if(!child) {
  o=prepared();assert(mishare_runtime_destroy(&o)==-EINPROGRESS && ctx_pending);
  ctx_fw_origin(ctx_pending);normal_delete_reply(o);
  assert(mishare_runtime_destroy(&o)==-EINPROGRESS);finish_dp();
  mark_closed(o);health_recovering=true;assert(!cds_post_disable() && !state(o).recovery_window);
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && !delete_calls && state(o).ndi.legacy_ready && state(o).ndi.wma_bound);
  completed_no_new_transport();_Exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 reset_recovery();assert(!create(&o) && !mishare_runtime_destroy(&o));
 puts("MISHARE_COMPLETED_NDI_HOST_RECLAIM_FIXTURE_PASS_ONLY");return 0;
}
'''


def fixture(root):
    src=completion.fixture(root)
    needle='static struct wlan_objmgr_vdev *last_vdev;';assert src.count(needle)==1
    src=src.replace(needle,needle+'\nstatic void (*completed_delete_hook)(void);\nstatic bool completed_fail_after_callback;',1)
    needle='delete_calls++;if(delete_fail)';assert src.count(needle)==1
    src=src.replace(needle,'delete_calls++;if(completed_delete_hook)completed_delete_hook();if(delete_fail)',1)
    needle='if(early_dp)finish_dp();return QDF_STATUS_SUCCESS;';assert src.count(needle)==1
    src=src.replace(needle,'if(early_dp)finish_dp();return completed_fail_after_callback?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;',1)
    return src[:src.index('int main(void) {')]+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    pin=completion.parent.recovery.work.shutdown.radio.plan.channel.pe.PIN
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=pin:raise ValueError('Unexpected revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:(d/n).write_text('/* platform model declarations */\n')
        (d/'completed.c').write_text(source);exe=d/'completed'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(d/'completed.c'),'-o',str(exe)],check=True)
        out=subprocess.check_output([exe],text=True,timeout=45,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    if out.strip()!='MISHARE_COMPLETED_NDI_HOST_RECLAIM_FIXTURE_PASS_ONLY':raise ValueError('Unexpected fixture output')
    return {'status':out.strip(),'source_commit':pin,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'native_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in completion.parent.BASE},
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h']},
            'checks':['real ordinary DELETE reply and DP final-free required before qualified SSR/WMI window','inline/delayed ordinary DP completion can finish never-prepared owner with host deletion only','batch follows completed route and waits for actual external VDEV final-free','ordinary CREATE/DELETE/DP history preserved; recovery timer/DP attempt flags remain false','incomplete facts, late completion without qualified window and prepared/peer history do not qualify','closed window, native/transaction drift and object deletion failure retain owner without retry','completion fault injected during host deletion preserves diagnostic owner even after actual VDEV free'],
            'limitations':'Executes production controller, real owned DELETE response/DP wrapper, native CDS post-disable/WMI work flush functions and object-manager final-free under ASan/UBSan. Full DP storage free, HIF/HTC/IRQ/QDF/timer primitives and component destructors remain models. Completed eligibility is limited to never-prepared/non-STARTed NDI; both ordinary completion facts must precede qualification/opening of the SSR window. No automatic requalification, parent-lifetime coordinator, prepared/STARTed recovery, address-reuse/ABA, safe module unload or phone behavior is certified. Caller retains exact parents and serializes every poll/teardown; backend remains disabled.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
