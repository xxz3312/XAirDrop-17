#!/usr/bin/env python3
"""Actions-only ordinary NDI completion identity/order checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import mishare_parent_fixture as parent
ROOT=parent.ROOT
PREVIOUS_RECOVERY_CALLBACK='static void mishare_runtime_recovery_dp_freed(void *context)\n{\n    struct mishare_runtime_owner *entry;\n    unsigned long flags;\n    spin_lock_irqsave(&mishare_runtime_lock, flags);\n    for (entry = mishare_runtime_owners; entry; entry = entry->next) {\n        if (entry != context || !entry->state.ndi_reclaim_started)\n            continue;\n        if (!entry->state.recovery_dp_attempted || entry->state.recovery_dp_freed) {\n            if (!entry->state.recovery_error)\n                entry->state.recovery_error = -EUCLEAN;\n        } else {\n            entry->state.recovery_dp_freed = true;\n        }\n        break;\n    }\n    spin_unlock_irqrestore(&mishare_runtime_lock, flags);\n    /* No access to context after publication. Unknown/freed tokens are ignored. */\n}\n'
HARNESS=r'''
static void normal_delete_reply(struct mishare_runtime_owner *o) {
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && wire_deletes==1 && !dp_detaches);
 reply();assert(state(o).ndi.delete_replied && !state(o).ndi.completion_error && !timers_live);
}
int main(void) {
 struct mishare_runtime_owner *o=NULL;
 /* Valid inline/delayed completion and opaque callbacks after final owner free. */
 for(int inline_cb=0;inline_cb<2;inline_cb++) {
  reset_recovery();o=early_ndi();normal_delete_reply(o);early_dp=inline_cb;
  assert(mishare_runtime_destroy(&o)==-EINPROGRESS && dp_detaches==1);
  if(!inline_cb) {assert(!state(o).ndi.dp_freed);finish_dp();}
  assert(state(o).ndi.dp_freed && !state(o).ndi.completion_error);
  void *token=o;mishare_runtime_ndi_dp_freed((void*)1);
  assert(!state(o).ndi.completion_error && !mishare_runtime_destroy(&o) && !o && !objects_live && !allocations);
  for(int i=0;i<64;i++)mishare_runtime_ndi_dp_freed(token);
 }
 /* A legitimate final-free may publish after fencing, without authorizing
  * further cleanup or changing the first shutdown reason. */
 reset_recovery();pid_t child=fork();assert(child>=0);
 if(!child) {
  o=early_ndi();normal_delete_reply(o);assert(mishare_runtime_destroy(&o)==-EINPROGRESS);
  mark_closed(o);assert(!stop_mc());finish_dp();
  assert(state(o).ndi.dp_freed && !state(o).ndi.completion_error && state(o).quiesced==MISHARE_QUIESCE_SSR);
  assert(mishare_runtime_destroy(&o)==-EUCLEAN && !delete_calls);_Exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 for(int fault=0;fault<7;fault++) {
  reset_recovery();child=fork();assert(child>=0);
  if(!child) {
   if(fault==0) {assert(!create(&o));mishare_runtime_ndi_dp_freed(o);}
   else {
    o=early_ndi();
    if(fault==1)mishare_runtime_ndi_dp_freed(o); /* before DELETE/detach */
    if(fault==2) {normal_delete_reply(o);mishare_runtime_ndi_dp_freed(o);}
    if(fault==3) {normal_delete_reply(o);assert(mishare_runtime_destroy(&o)==-EINPROGRESS);finish_dp();mishare_runtime_ndi_dp_freed(o);}
    if(fault==4) {normal_delete_reply(o);mishare_runtime_ndi_delete_event(&psoc,7,true);}
    if(fault==5) {assert(mishare_runtime_destroy(&o)==-EINPROGRESS);mishare_runtime_ndi_delete_event(&psoc,7,false);}
    if(fault==6) {
     stop_recovery(o);assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);
     mishare_runtime_ndi_dp_freed(o); /* recovery callback cannot use ordinary route */
     finish_dp();assert(state(o).recovery_dp_freed && !state(o).ndi.dp_freed);
    }
   }
   assert(state(o).ndi.completion_error==-EUCLEAN && state(o).ndi.blocked);
   assert(state(o).ndi.dp_freed==(fault==3));
   int deletes=delete_calls,detaches=dp_detaches,wires_before=wire_deletes;
   assert(mishare_runtime_destroy(&o)==-EUCLEAN);
   if(!state(o).quiesced) {mark_closed(o);assert(!stop_mc());}
   assert(mishare_runtime_reclaim_host(&o)==-EUCLEAN && mishare_runtime_reclaim_ndi(&o)==-EUCLEAN);
   struct mishare_runtime_reclaim_item item={o,77};
   assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EUCLEAN && item.owner==o && item.result==77);
   mishare_runtime_ndi_dp_freed(o);assert(state(o).ndi.completion_error==-EUCLEAN);
   assert(delete_calls==deletes && dp_detaches==detaches && wire_deletes==wires_before && o);_Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* Recovery completions must not silently accept a known token on the
  * ordinary route, before recovery admission, or with conflicting facts. */
 for(int fault=0;fault<15;fault++) {
  reset_recovery();child=fork();assert(child>=0);
  if(!child) {
   if(fault==0)assert(!create(&o));
   else o=early_ndi();
   if(fault==2)stop_recovery(o);
   if(fault==3) {normal_delete_reply(o);assert(mishare_runtime_destroy(&o)==-EINPROGRESS);}
   if(fault>=4) {
    stop_recovery(o);assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);
    if(fault==4)o->state.recovery_dp_attempted=false;
    if(fault==5)o->state.ndi_completed_reclaim=true;
    if(fault==6)o->state.ndi.active=false;
    if(fault==7)o->state.ndi.create.dp_attached=false;
    if(fault==8)o->state.ndi.dp_detaching=true;
    if(fault==9)o->state.ndi.dp_detach_submitted=true;
    if(fault==10)o->state.ndi.dp_freed=true;
    if(fault==11)o->state.ndi.delete_pending=true;
    if(fault==12)finish_dp(); /* duplicate preserves actual free history */
    if(fault==13)o->state.ndi.delete_submitted=true;
    if(fault==14)o->state.ndi.delete_replied=true;
   }
   mishare_runtime_recovery_dp_freed(o);
   assert(state(o).recovery_error==-EUCLEAN && state(o).blocked && state(o).ndi.blocked);
   assert(state(o).recovery_dp_freed==(fault==12));
   int deletes=delete_calls,detaches=dp_detaches,wires_before=wire_deletes;
   if(!state(o).quiesced) {mark_closed(o);assert(!stop_mc());}
   assert(mishare_runtime_destroy(&o)==-EUCLEAN && mishare_runtime_reclaim_host(&o)==-EUCLEAN);
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && mishare_runtime_reclaim_final(&o)==-EUCLEAN);
   struct mishare_runtime_reclaim_item item={o,77};
   assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EUCLEAN && item.owner==o && item.result==77);
   mishare_runtime_recovery_dp_freed(o);
   assert(state(o).recovery_error==-EUCLEAN && state(o).recovery_dp_freed==(fault==12));
   assert(delete_calls==deletes && dp_detaches==detaches && wire_deletes==wires_before);_Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* A valid late physical fact does not clear an earlier error or reopen
  * the closed window. No additional native cleanup is authorized. */
 reset_recovery();child=fork();assert(child>=0);
 if(!child) {
  o=early_ndi();stop_recovery(o);assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);
  o->state.recovery_error=-EIO;native_recovery_close();finish_dp();
  assert(state(o).recovery_dp_freed && state(o).recovery_error==-EIO && state(o).recovery_window_closed);
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && !delete_calls);_Exit(0);
 }
 assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 /* Unknown/freed recovery tokens have no effect, including after normal free. */
 reset_recovery();assert(!create(&o));void *old_recovery_token=o;
 mishare_runtime_recovery_dp_freed((void*)1);
 assert(!state(o).recovery_error && !mishare_runtime_destroy(&o) && !o);
 for(int i=0;i<64;i++)mishare_runtime_recovery_dp_freed(old_recovery_token);
 reset_recovery();assert(!create(&o));mishare_runtime_ndi_dp_freed((void*)1);
 assert(!state(o).ndi.completion_error && !state(o).ndi.blocked && !mishare_runtime_destroy(&o));
 puts("MISHARE_NDI_COMPLETION_INTEGRITY_FIXTURE_PASS_ONLY");return 0;
}
'''


def fixture(root):
    src=parent.fixture(root)
    return src[:src.index('int main(void) {')]+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    pin=parent.recovery.work.shutdown.radio.plan.channel.pe.PIN
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=pin:raise ValueError('Unexpected revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:(d/n).write_text('/* platform model declarations */\n')
        (d/'completion.c').write_text(source);exe=d/'completion'
        command=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(d/'completion.c'),'-o',str(exe)]
        subprocess.run(command,check=True)
        out=subprocess.check_output([exe],text=True,timeout=45,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
        runtime=(production/'wlan_hdd_mishare_runtime.c').read_text()
        current=parent.recovery.function(runtime,'mishare_runtime_recovery_dp_freed')
        (d/'wlan_hdd_mishare_runtime.c').write_text(runtime.replace(current,PREVIOUS_RECOVERY_CALLBACK,1))
        subprocess.run(command,check=True)
        rejected=subprocess.run([exe],text=True,timeout=45,capture_output=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
        assert rejected.returncode==-6 and 'state(o).recovery_error==-EUCLEAN && state(o).blocked && state(o).ndi.blocked' in rejected.stderr
    if out.strip()!='MISHARE_NDI_COMPLETION_INTEGRITY_FIXTURE_PASS_ONLY':raise ValueError('Unexpected fixture output')
    return {'status':out.strip(),'source_commit':pin,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'negative_control':{'previous_recovery_callback_sha256':hashlib.sha256(PREVIOUS_RECOVERY_CALLBACK.encode()).hexdigest(),'previous_callback_rejected_by_recovery_error_assertion':True},
            'native_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in parent.BASE},
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h']},
            'checks':['opaque ordinary DP completion token is matched in live registry before dereference','inline and delayed normal DP completion require active detach plus actual DELETE reply','unknown/freed token callbacks ignored under ASan/UBSan','premature/duplicate/wrong-route DP and duplicate/non-firmware DELETE notifications record sticky completion_error','normal completion after SSR publishes actual DP final-free without reopening admission','normal destroy, host reclaim, NDI reclaim and batch preflight cannot bypass sticky completion errors','15 recovery-route failures preserve sticky error across normal/host/NDI/final/batch APIs; unknown and freed recovery tokens ignored','previous exact recovery callback fails the targeted error assertion','valid completion history is retained on duplicate notification; no fabricated DELETE/DP completion'],
            'limitations':'Executes production owner/controller and native owned DELETE response/DP wrapper plus object-manager final-free under ASan/UBSan. DP storage free and callback delivery, QDF/timer primitives, object construction and component teardown remain models; full native DP and HDD teardown are not executed. Pointer matching protects unknown/freed tokens at the observed registry instant, not owner address reuse/ABA or callback text lifetime. No parent-lifetime coordinator, automatic recovery, prepared/STARTed recovery or phone behavior is certified. Backend remains disabled.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
