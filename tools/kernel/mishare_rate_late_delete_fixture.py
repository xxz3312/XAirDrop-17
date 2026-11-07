#!/usr/bin/env python3
"""Actions-only native VDEV DELETE reply arriving after the original SSR fence."""
import argparse
import json
import subprocess
from pathlib import Path
import mishare_rate_first_dp_fixture as first
from mishare_recovery_fixture import function
ROOT=first.ROOT
HARNESS=r'''
static unsigned late_fault;
static void late_delete_handoff(struct mishare_runtime_owner **o) {
 struct mishare_runtime_rate_status before=state(*o).rate;
 assert(state(*o).ndi.delete_submitted && !state(*o).ndi.delete_replied && timers_live && !dp_detaches);
 if(late_fault==1)(*o)->state.ndi.blocked=true;
 if(late_fault==3)(*o)->state.ndi.delete_submitted=false;
 if(late_fault==10)(*o)->state.rate.integrity_error=true;
 if(late_fault==2)assert(mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_REMOVE)==1);
 else mark_closed(*o);
 bool armed=late_fault!=1 && late_fault!=2 && late_fault!=3 && late_fault!=10;
 assert(state(*o).rate.late_delete_armed==armed && !state(*o).rate.late_delete_reply && "EXPECTED_LATE_DELETE_ARM");
 if(late_fault==6)mishare_runtime_ndi_peer_event(&psoc,7,(*o)->mac,*o,true); /* duplicate matching peer origin */
 if(late_fault==7)native_recovery_close();
 if(late_fault==4){timer_deinit(&psoc,7);timeout_origin(&psoc,7);}
 else if(late_fault==9){struct wlan_objmgr_psoc foreign={0};mishare_runtime_ndi_delete_event(&foreign,7,true);}
 else if(late_fault!=8)reply(); /* Actual selected native reply/timer/PM origin. */
 if(late_fault==5)mishare_runtime_ndi_delete_event(&psoc,7,true); /* Matching duplicate notification; no second native timer deinit. */
 bool received=late_fault==0 || late_fault==5 || late_fault==7;
 assert(state(*o).ndi.delete_replied==received && state(*o).rate.late_delete_reply==received &&
  state(*o).blocked && state(*o).ndi.blocked && "EXPECTED_LATE_DELETE_NATIVE_REPLY");
 if(late_fault) {
  if(late_fault==4 || late_fault==5 || late_fault==6)assert(state(*o).ndi.completion_error);
  assert(!stop_mc());int expected=late_fault==5||late_fault==10?-EUCLEAN:late_fault==7?-ESHUTDOWN:-EOPNOTSUPP;
  assert(mishare_runtime_reclaim_ndi(o)==expected && *o && !dp_detaches && !state(*o).rate.tail_dp_attempted && "EXPECTED_LATE_DELETE_RETAIN");
  assert(mishare_runtime_reclaim_ndi(o)==expected && !dp_detaches && "EXPECTED_LATE_DELETE_NO_REPLAY");
  assert(state(*o).rate.receipt.result==before.receipt.result && state(*o).rate.receipt.attempted_mask==before.receipt.attempted_mask);
  _Exit(0);
 }
 rate_history(*o,before);first_dp_handoff(o);
 assert(!*o && !allocations && !module_refs && "EXPECTED_LATE_DELETE_FINAL");
}
static void late_cycle(unsigned freq,unsigned failure,unsigned mode,bool batch,unsigned fault) {
 late_mode=true;late_fault=fault;first_dp_batch=batch;first_dp_fault=0;
 configured_ordinary_cycle(freq,failure,mode&15,0);
}
static void late_cases(void) {
 for(unsigned band=0;band<2;band++)for(unsigned failure=0;failure<4;failure++)for(unsigned mode=0;mode<16;mode++)for(unsigned batch=0;batch<2;batch++) {
  pid_t child=fork();assert(child>=0);if(!child){late_cycle(band?5240:2437,failure,mode,batch,0);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 for(unsigned fault=1;fault<=10;fault++) {
  pid_t child=fork();assert(child>=0);if(!child){late_cycle(5240,2,0,false,fault);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
}
'''


def fixture(root):
    source,exits,stubbed=first.fixture(root)
    source=first.ordinary.cleanup.owner.replace_once(source,'static void configured_clean_end(',
        'static bool late_mode;\nstatic void late_delete_handoff(struct mishare_runtime_owner **);\nstatic void configured_clean_end(')
    body=function(source,'configured_clean_end')
    needle='assert(mishare_runtime_destroy(o)==-EINPROGRESS && !dp_detaches && !delete_calls);reply();'
    changed=first.ordinary.cleanup.owner.replace_once(body,needle,
        'assert(mishare_runtime_destroy(o)==-EINPROGRESS && !dp_detaches && !delete_calls);\n  if(late_mode){late_delete_handoff(o);return;}\n  reply();')
    source=first.ordinary.cleanup.owner.replace_once(source,body,changed)
    body=function(source,'first_dp_handoff')
    changed=first.ordinary.cleanup.owner.replace_once(body,'mark_closed(*o);','if(!late_mode)mark_closed(*o);')
    source=first.ordinary.cleanup.owner.replace_once(source,body,changed)
    main=function(source,'main');source=first.ordinary.cleanup.owner.replace_once(source,main,HARNESS+'\n'+main.replace('engine_contract();','late_cases();engine_contract();',1))
    return source,exits,stubbed


def negative_controls(directory,c_file,command,env,source,root):
    runtime=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_runtime.c').read_text()
    once=first.ordinary.cleanup.owner.replace_once
    controls=[
        (once(runtime,'entry->state.rate.late_delete_armed = true;','entry->state.rate.late_delete_armed = false;'),0),
        (once(runtime,'else if (entry->state.rate.late_delete_armed &&','else if (false && entry->state.rate.late_delete_armed &&'),0),
        (once(runtime,'!entry->state.ndi.blocked && mishare_runtime_rate_delete_inflight(entry)','true && mishare_runtime_rate_delete_inflight(entry)'),1),
    ]
    override=directory/'wlan_hdd_mishare_runtime.c'
    try:
        for modified,fault in controls:
            target=source.replace(function(source,'main'),f'int main(void) {{late_cycle(5240,2,2,false,{fault});return 0;}}',1)
            c_file.write_text(target);override.unlink(missing_ok=True)
            subprocess.run(command,check=True);subprocess.run([directory/'engine'],check=True,env=env,timeout=60)
            override.write_text(modified);subprocess.run(command,check=True)
            bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=60)
            assert bad.returncode==-6 and 'EXPECTED_LATE_DELETE_' in bad.stderr,(bad.returncode,bad.stderr[-2000:])
    finally:override.unlink(missing_ok=True)


def audit(root):
    r=first.ordinary.cleanup.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    r['status']='MISHARE_RATE_LATE_DELETE_FIXTURE_PASS_ONLY';r['late_reply_combinations']=256;r['retention_cases']=10;r['native_mutations']=3
    r['limitations']='Actual selected native DELETE timer/PM reply origin after original SSR fence, followed by native prepared DP/SSR context/final-free bodies. Transport, ACK arrival, DP/peer/ref/locks modeled; caller retains parents. No ACK synthesis or post-fence command admission. Other missing PE/peer/VDEV replies, START/UP and phone/RF/Apple excluded.'
    return r


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
