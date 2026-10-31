#!/usr/bin/env python3
"""Actions-only stable pre-channel PE SSR cleanup, with native destructor/peer paths."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

import mishare_reset_context_fixture as prepared
import mishare_pe_destructor_fixture as destructor

ROOT = prepared.ROOT
API = destructor.pe.API
HARNESS = r'''
static TX_TIMER reset_confirm_timers[3];
static bool reset_pe_drift;
static void reset_pe_test(void) {
 reset_prepared_test();reset_pe_drift=false;memset(reset_confirm_timers,0,sizeof(reset_confirm_timers));
}
static struct mishare_runtime_owner *ready_pe_owner(void) {
 struct mishare_runtime_owner *o=with_session();
 pe_mac.lim.maxStation=2;pe_mac.lim.lim_timers.gpLimCnfWaitTimer=reset_confirm_timers;
 reset_confirm_timers[0]=(TX_TIMER){.sessionId=0};
 reset_confirm_timers[1]=(TX_TIMER){.sessionId=1,.running=true};
 reset_confirm_timers[2]=(TX_TIMER){.sessionId=0};
 pe_slot.dph.dphHashTable.pHashTable=pe_heap_alloc(16);
 memset(pe_nodes,0x5a,sizeof(pe_nodes));pe_slot.dph.dphHashTable.pDphNodeArray=pe_nodes;
 pe_slot.dph.dphHashTable.size=33;pe_slot.model_idxpool=pe_heap_alloc(8);
 return o;
}
static void assert_reset_pe_facts(struct mishare_runtime_owner *o) {
 struct mishare_runtime_status s=state(o);
 assert(s.recovery_pe_attempted && s.recovery_pe_released && !s.ndi.pe_ready && !o->pe_cookie);
 assert(s.ndi.pe_requested && s.ndi.pe_submitted && s.ndi.pe_completed);
 assert(!s.ndi.pe_delete_requested && !s.ndi.pe_delete_submitted && !s.ndi.pe_delete_completed);
 assert(!s.ndi.delete_pending && !s.ndi.delete_submitted && !s.ndi.delete_replied);
 assert(!pe_slot.valid && !pe_slot.vdev && !pe_slot.mac_ctx && !pe_heap_live);
 assert(reset_confirm_timers[1].running && !pe_timer_stops && !reset_wmi_calls && !pe_pending.bodyptr);
}
int main(void) {
 struct mishare_runtime_owner *o=NULL;
 for(int inline_cb=0;inline_cb<2;inline_cb++) {
  reset_pe_test();o=ready_pe_owner();unsigned posts=pe_posts;stop_recovery(o);early_dp=inline_cb;
  assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && o);assert_reset_pe_facts(o);
  assert(pe_deletes==1 && pe_posts==posts && reset_force_detaches==1 && dp_detaches==1);
  assert(state(o).ndi.legacy_ready && state(o).ndi.wma_bound && !state(o).recovery_context_released);
  if(!inline_cb) {assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && pe_deletes==1);finish_dp();}
  assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations && !objects_live && !dp_objects && !ctx_locks);
 }
 reset_pe_test();o=ready_pe_owner();stop_recovery(o);
 struct mishare_runtime_reclaim_item item={o,99};o=NULL;
 assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS && item.owner);assert_reset_pe_facts(item.owner);
 finish_dp();assert(!mishare_runtime_reclaim_batch(&psoc,&item,1) && !item.owner && !item.result);
 /* Native final-free can outlive the window; PE is already physically gone. */
 reset_pe_test();o=ready_pe_owner();struct wlan_objmgr_vdev *held=last_vdev;
 assert(!wlan_objmgr_vdev_try_get_ref(held,1));stop_recovery(o);
 assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);assert_reset_pe_facts(o);finish_dp();
 assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && state(o).ndi_reclaim_ready);
 native_recovery_close();wlan_objmgr_vdev_release_ref(held,1);
 assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations);
 /* Preflight identity, native state and timer failures do not delete PE,
  * cancel the response timer, remove peers or detach DP. Sticky, no retries. */
 for(int fault=0;fault<22;fault++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=ready_pe_owner();stop_recovery(o);
   if(fault==0)pe_slot.mishare_owner=(void*)1;
   if(fault==1)pe_slot.vdev=(void*)1;
   if(fault==2)pe_slot.bssType=0;
   if(fault==3)pe_slot.limSystemRole=0;
   if(fault==4)pe_slot.self_mac_addr[0]^=1;
   if(fault==5)pe_slot.bssId[0]^=1;
   if(fault==6)pe_slot.mac_ctx=NULL;
   if(fault==7)pe_slot.opmode=0;
   if(fault==8)pe_slot.peSessionId=1;
   if(fault==9)pe_slot.vdev_id=8;
   if(fault==10)pe_slot.limMlmState=1;
   if(fault==11)pe_slot.limSmeState=1;
   if(fault==12)pe_slot.curr_op_freq=5240;
   if(fault==13)pe_slot.pLimStartBssReq=(void*)1;
   if(fault==14)pe_slot.dph.dphHashTable.size=2;
   if(fault==15)pe_mac.lim.gpSession=NULL;
   if(fault==16)pe_mac.lim.lim_timers.gpLimCnfWaitTimer=NULL;
   if(fault==17)reset_confirm_timers[0].running=true;
   if(fault==18)pe_slot.valid=false;
   if(fault==19)o->pe_cookie++;
   if(fault==20)pe_mac.psoc=NULL;
   if(fault==21)pe_slot.defaultAuthFailureTimeout=50;
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && state(o).recovery_error);
   assert(!pe_deletes && !recovery_timer_cancels && !reset_force_detaches && !dp_detaches && pe_heap_live==2);
   assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && !pe_deletes && !recovery_timer_cancels);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* Identity drift during the response timer's synchronous cancel is rejected
  * by the native release recheck; PE and all remaining context stay owned. */
 reset_pe_test();pid_t child=fork();assert(child>=0);
 if(!child) {
  o=ready_pe_owner();stop_recovery(o);reset_pe_drift=true;
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && state(o).recovery_error && state(o).recovery_timer_released);
  assert(state(o).recovery_pe_attempted && !state(o).recovery_pe_released && !pe_deletes && pe_slot.valid && pe_heap_live==2);
  assert(!reset_force_detaches && !dp_detaches && mishare_runtime_reclaim_ndi(&o)==-EUCLEAN);_Exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 /* Later peer teardown failure publishes completed PE destruction, retains
  * WMA/legacy/DP, and never replays PE deletion or pretends an ordinary ACK. */
 reset_pe_test();child=fork();assert(child>=0);
 if(!child) {
  o=ready_pe_owner();stop_recovery(o);reset_obj_failure=true;
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && state(o).recovery_error);assert_reset_pe_facts(o);
  assert(pe_deletes==1 && !dp_detaches && state(o).ndi.legacy_ready && state(o).ndi.wma_bound);
  assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && pe_deletes==1 && !dp_detaches);_Exit(0);
 }
 assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 /* Pending/failed PE, channel request history, plan/radio and fabricated reset
  * markers never acquire a recovery window. */
 for(int fault=0;fault<8;fault++) {
  reset_pe_test();child=fork();assert(child>=0);
  if(!child) {
   o=ready_pe_owner();
   if(fault==0)o->state.ndi.pe_submitted=false;
   if(fault==1)o->state.ndi.pe_completed=false;
   if(fault==2)o->state.ndi.pe_error=-EIO;
   if(fault==3)o->state.ndi.channel_requested=true;
   if(fault==4)o->state.ndi.start_plan_requested=true;
   if(fault==5)o->state.ndi.radio_requested=true;
   if(fault==6)o->state.recovery_pe_released=true;
   if(fault==7)o->state.recovery_pe_attempted=true;
   mark_closed(o);health_recovering=true;assert(!cds_post_disable());
   assert(!state(o).recovery_window && mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && !pe_deletes && !dp_detaches);_Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 puts("MISHARE_PRE_CHANNEL_PE_RESET_FIXTURE_PASS_ONLY");return 0;
}
'''


def fixture(root):
    src = prepared.fixture(root)
    src = destructor.augment(root,src)
    src = src.replace('struct pe_session {','struct pe_session {int limMlmState,limSmeState;',1)
    a=src.index('/* PE_RESET_TRANSPORT_STUBS */');b=src.index('/* END_PE_RESET_TRANSPORT_STUBS */',a)+len('/* END_PE_RESET_TRANSPORT_STUBS */')
    src=src[:a]+src[b:]
    # Only the cancel boundary injects drift; native code is rechecked as-is.
    needle='static bool qdf_timer_sync_cancel('
    src=src.replace(needle,'static bool reset_pe_drift;\n'+needle,1)
    needle='recovery_timer_cancels++;'
    assert src.count(needle)==1
    src=src.replace(needle,needle+'if(reset_pe_drift)pe_slot.mishare_owner=(void*)1;',1)
    native=(root/API).read_text()
    block=re.search(r'/\* MISHARE_PE_RESET_BEGIN:helpers \*/\n(.*?)/\* MISHARE_PE_RESET_END:helpers \*/',native,re.S)[1]
    needle='\tpe_delete_session(mac, session);'
    assert block.count(needle)==1
    block=block.replace(needle,'\tassert(!timers_live && ctx_peer_present && dp_objects && ctx_locks);\n'+needle,1)
    block='#define eLIM_MLM_IDLE_STATE 0\n#define eLIM_SME_IDLE_STATE 0\n#define cds_get_context pe_cds_get_context\n'+block+'\n#undef cds_get_context\n'
    # The original native helper calls the full destructor through the model's
    # wrapper. Its return and actual MAC-ref release still execute in full.
    harness=HARNESS.replace('static bool reset_pe_drift;\n','',1)
    return src[:src.index('int main(void) {')]+block+harness


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=destructor.pe.PIN:raise ValueError('Unexpected revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:(d/n).write_text('/* platform model */\n')
        c=d/'reset.c';exe=d/'reset'
        command=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(c),'-o',str(exe)]
        env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'}
        c.write_text(source);subprocess.run(command,check=True);out=subprocess.check_output([exe],text=True,timeout=45,env=env)
        guard='if (session->bssType != eSIR_MISHARE_PAS_MODE)';assert source.count(guard)==1
        c.write_text(source.replace(guard,'if (true) /* negative: shared SAE cleanup */',1));subprocess.run(command,check=True)
        bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env)
        assert bad.returncode==-6 and 'FOREIGN_AUTH_TIMER_MUTATION' in bad.stderr
    assert out.strip()=='MISHARE_PRE_CHANNEL_PE_RESET_FIXTURE_PASS_ONLY'
    return {'status':out.strip(),'source_commit':destructor.pe.PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h']},
            'native_sha256':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in [API,destructor.pe.SESSION,destructor.UTILS,destructor.AUTH,prepared.WMA]},
            'negative_control_PAS_shared_auth_cleanup_rejected':True,
            'checks':['production runtime and native PE check/release, complete native PE destructor and no-FW peer path',
                      'inline/deferred DP final-free; actual batch dispatch; external object final-free reference',
                      '22 native identity/state/timer preflight failures retain every resource; no replay',
                      'native PE identity rechecked after synchronous response-timer drain',
                      'later peer failure preserves completed PE fact and remaining WMA/legacy/DP',
                      'pending/failed PE, incomplete channel/plan or any radio history and fabricated reset markers rejected',
                      'PE history retained without ordinary PE/VDEV DELETE acknowledgement or MC post'],
            'limitations':'Stable PE success before any channel request only, in the explicit qualified SSR window with retained parents. Production runtime, native PE/context/timer/DP wrappers, full native PE destructor and WMA peer removal execute with modeled PE allocation, remaining cleanup callees, timers, synchronization, DP force detach, object-peer physical lifecycle and physical parents. No automatic native shutdown caller/parent lease, channel/START/UP recovery, backend activation, phone/firmware/RF or AirDrop proof.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
