#!/usr/bin/env python3
"""Actions-only SSR metadata handoff after configured ordinary host deletion."""
import argparse
import json
import subprocess
from pathlib import Path
import mishare_rate_ordinary_fixture as ordinary
from mishare_recovery_fixture import function

ROOT = ordinary.ROOT
HANDOFF = r'''
static bool final_rate_enabled,final_rate_batch;
static unsigned final_rate_fault;
static int final_rate_poll(struct mishare_runtime_owner **o) {
 if(!final_rate_batch)return mishare_runtime_reclaim_final(o);
 struct mishare_runtime_reclaim_item item={*o,77};
 int ret=mishare_runtime_reclaim_batch(&psoc,&item,1);*o=item.owner;
 if(!ret)assert(!item.result);
 else if(ret==-EINPROGRESS)assert(item.result==77 || item.result==ret);
 return ret;
}
static void configured_final_handoff(struct mishare_runtime_owner **o,struct wlan_objmgr_vdev *held) {
 struct mishare_runtime_rate_status before=state(*o).rate;
 unsigned deletes=delete_calls,dp=dp_detaches,wires=wire_deletes,pe=pe_deletes;
 assert(state(*o).rate.ordinary_completed && state(*o).host_delete_accepted && !(*o)->vdev &&
  !(*o)->referenced && !(*o)->events && !state(*o).ndi.active && !state(*o).freed);
 assert(mishare_runtime_reclaim_final(o)==-EOPNOTSUPP && "EXPECTED_RATE_FINAL_NO_FENCE");
 mark_closed(*o);
 assert(final_rate_poll(o)==-EINPROGRESS && "EXPECTED_RATE_FINAL_MC_WAIT");
 assert(!stop_mc());native_recovery_close();
 assert(final_rate_poll(o)==-EINPROGRESS && *o && !state(*o).freed &&
  module_refs==1 && "EXPECTED_RATE_FINAL_FREE_WAIT");
 rate_history(*o,before);
 assert(mishare_runtime_destroy(o)==-EOPNOTSUPP && "EXPECTED_RATE_FINAL_NO_ORDINARY_RESUME");
 wlan_objmgr_vdev_release_ref(held,WLAN_HDD_ID_OBJ_MGR);
 assert(state(*o).freed && !last_vdev && clean_sm_destroys==1 && !engine_allocations);
 if(final_rate_fault) {
  if(final_rate_fault==1)(*o)->state.host_delete_accepted=false;
  if(final_rate_fault==2)(*o)->state.rate.ordinary_completed=false;
  if(final_rate_fault==3)(*o)->state.ndi.peer_delete_replied=false;
  if(final_rate_fault==4)(*o)->state.ndi.dp_freed=false;
  if(final_rate_fault==5)(*o)->state.ndi.delete_replied=false;
  if(final_rate_fault==6)(*o)->state.rate.integrity_error=true;
  if(final_rate_fault==7)(*o)->state.ndi.completion_error=-EIO;
  if(final_rate_fault==8)(*o)->state.quiesced=MISHARE_QUIESCE_REMOVE;
  if(final_rate_fault==9)(*o)->events=(void*)1;
  if(final_rate_fault==10)(*o)->state.work_error=-EIO;
  if(final_rate_fault==11)(*o)->state.ndi.create.timer_ready=true;
  int expected=final_rate_fault==2||final_rate_fault==8?-EOPNOTSUPP:-EUCLEAN;
  assert(final_rate_poll(o)==expected && *o && module_refs==1 && "EXPECTED_RATE_FINAL_FAULT_RETAIN");
  assert(final_rate_poll(o)==expected && *o && module_refs==1 && "EXPECTED_RATE_FINAL_FAULT_RETAIN");
  assert(delete_calls==(int)deletes && dp_detaches==(int)dp && wire_deletes==(int)wires && pe_deletes==pe);
  _Exit(0); /* Fault cases intentionally retain owner/module, no success claim. */
 }
 void *old=*o;rate_history(*o,before);
 assert(!final_rate_poll(o) && !*o && !module_refs && !allocations && !objects_live && "EXPECTED_RATE_FINAL_RETIRE");
 struct mishare_runtime_owner *unknown=old;
 assert(mishare_runtime_reclaim_final(&unknown)==-ENOENT);
 assert(delete_calls==(int)deletes && dp_detaches==(int)dp && wire_deletes==(int)wires && pe_deletes==pe &&
  !ctx_locks && !stats_live && !dp_objects && !reset_wmi_calls && !reset_force_detaches && "EXPECTED_RATE_FINAL_NO_NATIVE_REPLAY");
}
static void configured_final_case(unsigned freq,unsigned failure,unsigned mode,bool batch,unsigned fault) {
 final_rate_enabled=true;final_rate_batch=batch;final_rate_fault=fault;
 configured_ordinary_cycle(freq,failure,mode|8,0);
}
static void final_rate_cases(void) {
 for(unsigned band=0;band<2;band++)for(unsigned failure=0;failure<4;failure++)for(unsigned mode=0;mode<32;mode++) {
  if(!(mode&8))continue;
  for(unsigned batch=0;batch<2;batch++) {
   pid_t child=fork();assert(child>=0);if(!child){configured_final_case(band?5240:2437,failure,mode,batch,0);_Exit(0);}
   int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
  }
 }
 for(unsigned fault=1;fault<=11;fault++)for(unsigned batch=0;batch<2;batch++) {
  pid_t child=fork();assert(child>=0);if(!child){configured_final_case(5240,2,8,batch,fault);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* An actual PE-delete message interrupted by SSR cannot use metadata retirement. */
 pid_t child=fork();assert(child>=0);if(!child){
  reset_pe_test();struct mishare_runtime_owner *o=configured_rate(5240,1);
  assert(mishare_runtime_destroy(&o)==-EINPROGRESS && pe_pending.bodyptr);
  mark_closed(o);assert(!stop_mc());
  assert(!state(o).rate.ordinary_completed && pe_heap_live && !wire_deletes && !dp_detaches);
  assert(mishare_runtime_reclaim_final(&o)==-EOPNOTSUPP &&
   mishare_runtime_reclaim_ndi(&o)==-EOPNOTSUPP && o && "EXPECTED_RATE_FINAL_PARTIAL_RETAIN");_Exit(0);
 }int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
}
'''


def fixture(root):
    source, exits, stubbed = ordinary.fixture(root)
    anchor='static void configured_clean_end('
    source=ordinary.cleanup.owner.replace_once(source,anchor,
        'static bool final_rate_enabled;\nstatic void configured_final_handoff(struct mishare_runtime_owner **,struct wlan_objmgr_vdev *);\n'+anchor)
    body=function(source,'configured_clean_end')
    needle='wlan_objmgr_vdev_release_ref(held,WLAN_HDD_ID_OBJ_MGR);assert(!mishare_runtime_destroy(o));'
    changed=ordinary.cleanup.owner.replace_once(body,needle,
        'if(final_rate_enabled){configured_final_handoff(o,held);return;}\n  '+needle)
    source=ordinary.cleanup.owner.replace_once(source,body,changed)
    main=function(source,'main')
    # The prior full ordinary/native regressions remain in main.
    source=ordinary.cleanup.owner.replace_once(source,main,HANDOFF+'\n'+main.replace('engine_contract();','final_rate_cases();engine_contract();',1))
    return source, exits, stubbed


def negative_controls(directory,c_file,command,env,source,root):
    runtime=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_runtime.c').read_text()
    override=directory/'wlan_hdd_mishare_runtime.c'
    final=function(runtime,'mishare_runtime_reclaim_final')
    changed=ordinary.cleanup.owner.replace_once(final,'ret = mishare_runtime_rate_final_check(entry);','ret = mishare_runtime_rate_retire_check(entry);')
    controls=[
        (runtime.replace(final,changed,1),0),
        (ordinary.cleanup.owner.replace_once(runtime,'entry->state.work_users || !entry->state.freed)','entry->state.work_users || false)'),0),
        (ordinary.cleanup.owner.replace_once(runtime,'!n->dp_detaching || !n->dp_detach_submitted || !n->dp_freed ||','!n->dp_detaching || !n->dp_detach_submitted || false ||'),4),
    ]
    try:
        for modified,fault in controls:
            target=source.replace(function(source,'main'),f'int main(void) {{configured_final_case(5240,2,8,false,{fault});return 0;}}',1)
            c_file.write_text(target);override.unlink(missing_ok=True)
            subprocess.run(command,check=True);subprocess.run([directory/'engine'],check=True,timeout=60,env=env)
            override.write_text(modified);subprocess.run(command,check=True)
            bad=subprocess.run([directory/'engine'],capture_output=True,text=True,timeout=60,env=env)
            assert bad.returncode==-6 and 'EXPECTED_RATE_FINAL_' in bad.stderr,(bad.returncode,bad.stderr[-2000:])
    finally:
        override.unlink(missing_ok=True)


def audit(root):
    r=ordinary.cleanup.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    r['status']='MISHARE_RATE_FINAL_HANDOFF_FIXTURE_PASS_ONLY'
    r['handoff_combinations']=256
    r['retention_faults']=22
    r['partial_PE_delete_interruption']=True
    r['native_mutation_controls']=3
    r['limitations']='Native ordinary cleanup and final-free bodies with modeled rate transport, ACK/DP/peer primitives and external refs. SSR final API performs metadata only after accepted host delete. Partial native cleanup remains retained. No parent lease/full SSR coordinator, START/UP, phone/RF/Apple certification.'
    return r


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
