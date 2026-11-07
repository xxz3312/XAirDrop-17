#!/usr/bin/env python3
"""Actions-only configured ordinary DP tail continued through qualified SSR."""
import argparse
import json
import subprocess
from pathlib import Path
import mishare_rate_ordinary_fixture as ordinary
from mishare_recovery_fixture import function

ROOT=ordinary.ROOT
HARNESS=r'''
static bool tail_enabled,tail_batch;
static unsigned tail_fault;
static int tail_poll(struct mishare_runtime_owner **o) {
 if(!tail_batch)return mishare_runtime_reclaim_ndi(o);
 struct mishare_runtime_reclaim_item item={*o,77};int ret=mishare_runtime_reclaim_batch(&psoc,&item,1);*o=item.owner;return ret;
}
static void tail_handoff(struct mishare_runtime_owner **o) {
 struct mishare_runtime_rate_status before=state(*o).rate;
 struct wlan_objmgr_vdev *held=last_vdev;assert(!wlan_objmgr_vdev_try_get_ref(held,WLAN_HDD_ID_OBJ_MGR));
 unsigned peers=clean_peer_sends,pe=pe_deletes;int wires=wire_deletes,dp=dp_detaches;
 mark_closed(*o);assert(tail_poll(o)==-EINPROGRESS && "EXPECTED_RATE_TAIL_MC_WAIT");
 health_recovering=true;recovery_subject=*o;
 assert(!cds_post_disable() && state(*o).recovery_window && "EXPECTED_RATE_TAIL_WINDOW");recovery_subject=NULL;
 if(!state(*o).ndi.dp_freed) {
  assert(tail_poll(o)==-EINPROGRESS && !state(*o).rate.tail_attempted &&
   state(*o).ndi.wma_bound && state(*o).ndi.legacy_ready && "EXPECTED_RATE_TAIL_DP_WAIT");
 }
 if(!clean_peer_gone)clean_peer_unmap();
 if(pending_dp_cb)finish_dp();
 assert(state(*o).ndi.dp_freed && !dp_objects && !stats_live && clean_peer_gone);
 if(tail_fault) {
  if(tail_fault==1)native_recovery_close();
  if(tail_fault==2)wma_context.interfaces[7].vdev=NULL;
  if(tail_fault==3)(*o)->state.ndi.create.dp_cookie++;
  if(tail_fault==4)ctx_reset_peer_count=1;
  if(tail_fault==5)(*o)->state.ndi.completion_error=-EIO;
  int expected=tail_fault==1?-ESHUTDOWN:-EUCLEAN;
  assert(tail_poll(o)==expected && *o && !state(*o).rate.tail_completed &&
   !state(*o).host_delete_accepted && "EXPECTED_RATE_TAIL_FAULT_RETAIN");
  bool attempted=state(*o).rate.tail_attempted;
  assert(attempted==(tail_fault>=2 && tail_fault<=4));
  assert(tail_poll(o)==expected && state(*o).rate.tail_attempted==attempted && "EXPECTED_RATE_TAIL_NO_RETRY");
  rate_history(*o,before);assert(pe_deletes==pe && wire_deletes==wires && dp_detaches==dp && clean_peer_sends==peers);
  _Exit(0);
 }
 assert(tail_poll(o)==-EINPROGRESS && *o && state(*o).rate.tail_attempted && state(*o).rate.tail_completed &&
  state(*o).rate.ordinary_completed && state(*o).host_delete_accepted && !state(*o).freed &&
  !state(*o).ndi.wma_bound && !state(*o).ndi.legacy_ready && !ctx_locks && "EXPECTED_RATE_TAIL_CONTEXT_RELEASE");
 rate_history(*o,before);assert(!state(*o).rate.reset_admitted && !state(*o).rate.reset_completed);
 native_recovery_close();wlan_objmgr_vdev_release_ref(held,WLAN_HDD_ID_OBJ_MGR);
 assert(state(*o).freed && clean_sm_destroys==1 && !engine_allocations);
 assert(!mishare_runtime_reclaim_final(o) && !*o && !module_refs && !allocations && !objects_live && "EXPECTED_RATE_TAIL_FINAL");
 assert(pe_deletes==pe && wire_deletes==wires && dp_detaches==dp && clean_peer_sends==peers &&
  !reset_wmi_calls && !reset_force_detaches && !recovery_timer_cancels && "EXPECTED_RATE_TAIL_NO_REPLAY");
}
static void tail_cycle(unsigned freq,unsigned failure,unsigned mode,bool batch,unsigned fault) {
 tail_enabled=true;tail_batch=batch;tail_fault=fault;configured_ordinary_cycle(freq,failure,mode,0);
}
static void tail_cases(void) {
 for(unsigned band=0;band<2;band++)for(unsigned failure=0;failure<4;failure++)for(unsigned mode=0;mode<32;mode++) {
  pid_t child=fork();assert(child>=0);if(!child){tail_cycle(band?5240:2437,failure,mode,mode&1,0);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 for(unsigned fault=1;fault<=5;fault++)for(unsigned batch=0;batch<2;batch++) {
  pid_t child=fork();assert(child>=0);if(!child){tail_cycle(5240,2,0,batch,fault);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
}
'''


def fixture(root):
    source,exits,stubbed=ordinary.fixture(root)
    source=ordinary.cleanup.owner.replace_once(source,'static void configured_clean_end(',
        'static bool tail_enabled;\nstatic void tail_handoff(struct mishare_runtime_owner **);\nstatic void configured_clean_end(')
    body=function(source,'configured_clean_end')
    needle='assert(ret==-EINPROGRESS && dp_detaches==1 && !delete_calls && engine_allocations==1);'
    changed=ordinary.cleanup.owner.replace_once(body,needle,needle+'\n if(tail_enabled){tail_handoff(o);return;}')
    source=ordinary.cleanup.owner.replace_once(source,body,changed)
    main=function(source,'main')
    source=ordinary.cleanup.owner.replace_once(source,main,HARNESS+'\n'+main.replace('engine_contract();','tail_cases();engine_contract();',1))
    return source,exits,stubbed


def negative_controls(directory,c_file,command,env,source,root):
    runtime=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_runtime.c').read_text()
    target=source.replace(function(source,'main'),'int main(void) {tail_cycle(5240,2,2,false,0);return 0;}',1)
    c_file.write_text(target);subprocess.run(command,check=True);subprocess.run([directory/'engine'],check=True,env=env,timeout=60)
    controls=[
        runtime.replace('(!entry->state.recovery_window || !entry->state.ndi.dp_freed)','(!entry->state.recovery_window || false)',1),
        runtime.replace('entry->state.rate.tail_completed = true;','entry->state.rate.tail_completed = false;',1),
        runtime.replace('!mishare_runtime_rate_tail_check(entry)))','false && !mishare_runtime_rate_tail_check(entry)))'),
    ]
    override=directory/'wlan_hdd_mishare_runtime.c'
    try:
        for index,modified in enumerate(controls):
            assert modified!=runtime
            override.write_text(modified);subprocess.run(command,check=True)
            bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=60)
            marker='!dp_objects && !pending_dp_cb' if index==0 else 'EXPECTED_RATE_TAIL_'
            assert bad.returncode==-6 and marker in bad.stderr,(bad.returncode,bad.stderr[-2000:])
    finally:
        override.unlink(missing_ok=True)


def audit(root):
    r=ordinary.cleanup.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    r['status']='MISHARE_RATE_SSR_ORDINARY_TAIL_FIXTURE_PASS_ONLY'
    r['tail_combinations']=256;r['retention_faults']=10;r['native_mutations']=3
    r['limitations']='Ordinary native PE/peer/VDEV/DP cleanup and existing native SSR WMA/legacy finish in modeled transport/ACK/DP/peer/lock environment. Parent retention is a caller/fixture contract. Earlier incomplete DELETE stages remain held; no configured START/UP, phone/RF/Apple proof.'
    return r


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
