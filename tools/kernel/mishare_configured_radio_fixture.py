#!/usr/bin/env python3
"""Internal configured START -> actual native ordinary STOP/DOWN and cleanup."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import mishare_plan_commit_fixture as prior
from mishare_recovery_fixture import function
ROOT=prior.ROOT
TAIL=r'''
 struct mishare_runtime_status prepared=state(o);
 assert(prepared.start_preview.committed && !prepared.ndi.radio_requested && !o->radio &&
  !prepared.configured_radio.requested && "EXPECTED_CONFIG208_PREPARED");
 assert(mishare_runtime_configured_start(NULL,freq)==-EINVAL &&
  mishare_runtime_configured_start((void*)1,freq)==-ENOENT &&
  mishare_runtime_configured_stop(NULL)==-EINVAL && mishare_runtime_configured_stop((void*)1)==-ENOENT &&
  mishare_runtime_configured_stop(o)==-EINVAL && "EXPECTED_CONFIG208_IDENTITY");
 if(admission) {
  int expected=-EUCLEAN;u32 wanted=freq;
  switch(admission) {
  case 1:o->state.start_preview.committed=false;expected=-EINPROGRESS;break;
  case 2:o->state.rate.accepted=false;break;
  case 3:o->state.retry.receipt.submitted_mask^=1;break;
  case 4:o->state.bssid.applied=false;break;
  case 5:o->state.start_preview.summary.dtim_period++;break;
  case 6:o->state.work_users=1;expected=-EINPROGRESS;break;
  case 7:o->state.quiesced=MISHARE_QUIESCE_SSR;expected=-ESHUTDOWN;break;
  case 8:o->state.ndi.create.dp_cookie=0;break;
  case 9:o->state.ndi.create.stats_owned=false;break;
  case 10:o->referenced=false;break;
  case 11:wanted=freq==5240?5180:2412;break;
  case 12:o->state.radio.start_attempted=true;break;
  case 13:o->state.radio.fence.start_reply_queued=true;break;
  case 14:o->state.configured_radio.returned=true;break;
  case 15:o->state.configured_radio.stop_error=-EIO;break;
  case 16:o->state.start_preview.vdev_id++;break;
  }
  struct mishare_runtime_status before=state(o);
  assert(mishare_runtime_configured_start(o,wanted)==expected &&
   !memcmp(&before,&o->state,sizeof(before)) && !o->radio && !radio_starts && !radio_stops && !radio_downs &&
   !pe_deletes && !dp_detaches && "EXPECTED_CONFIG208_ADMISSION");return;
 }
 radio_early_start=radio_early_stop=inline_rate;
 if(radio_fault==1)radio_queue_fail=true;
 ret=mishare_runtime_configured_start(o,freq);
 if(radio_fault==1) {
  assert(ret<0 && state(o).configured_radio.requested && state(o).configured_radio.returned &&
   mishare_runtime_configured_start(o,freq)==-EALREADY && mishare_runtime_configured_stop(o)<0 &&
   !pe_deletes && !dp_detaches && "EXPECTED_CONFIG208_FAILED_SUBMISSION_NO_REPLAY");return;
 }
 assert(ret==-EINPROGRESS && o->radio && state(o).configured_radio.requested &&
  state(o).configured_radio.returned && !state(o).configured_radio.stopped &&
  mishare_runtime_configured_start(o,freq)==-EALREADY && "EXPECTED_CONFIG208_START_ONCE");
 struct mishare_runtime_owner *held=o;
 assert(mishare_runtime_destroy(&held)==-EINPROGRESS && held==o && !pe_pending.bodyptr &&
  !pe_deletes && !dp_detaches && "EXPECTED_CONFIG208_NO_PREMATURE_PE");
 assert(mishare_runtime_configured_stop(o)==-EINPROGRESS && !state(o).radio.closing &&
  !state(o).configured_radio.stop_requested && !radio_stops && "EXPECTED_CONFIG208_PENDING_START_HELD");
 if(radio_fault==2)radio_start_fail=true;
 radio_run(false);
 if(radio_fault==2) {
  assert(state(o).radio.phase==MISHARE_RADIO_BLOCKED && mishare_runtime_configured_stop(o)<0 &&
   o->radio && !pe_deletes && !dp_detaches && !radio_stops && "EXPECTED_CONFIG208_START_FAULT_HELD");return;
 }
 assert(mishare_runtime_configured_stop(o)==-EINPROGRESS && !state(o).configured_radio.stop_requested &&
  !state(o).radio.closing && "EXPECTED_CONFIG208_WAIT_START_HELD");
 if(!inline_rate)assert(radio_reply_start(0)==QDF_STATUS_SUCCESS);
 radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_UP && state(o).radio.host_up &&
  radio_starts==1 && !radio_stops && !radio_downs && "EXPECTED_CONFIG208_NATIVE_UP");
 assert(mishare_runtime_destroy(&held)==-EOPNOTSUPP && held==o && !pe_pending.bodyptr &&
  !pe_deletes && !dp_detaches && "EXPECTED_CONFIG208_UP_REQUIRES_EXPLICIT_STOP");
 if(radio_fault==6) {
  mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_SSR);
  assert(mishare_runtime_configured_stop(o)==-ESHUTDOWN && o->radio &&
   mishare_runtime_reclaim_ndi(&o)<0 && o && !pe_deletes && !dp_detaches && !radio_stops &&
   "EXPECTED_CONFIG208_SSR_NOT_INHERITED");return;
 }
 if(radio_fault==7) {
  o->state.start_preview.integrity_error=true;
  assert(mishare_runtime_configured_stop(o)==-EUCLEAN && o->radio && !radio_stops &&
   !pe_deletes && !dp_detaches && "EXPECTED_CONFIG208_CORRUPT_CONFIG_HELD");return;
 }
 if(radio_fault==3)radio_queue_fail=true;
 ret=mishare_runtime_configured_stop(o);
 if(radio_fault==3) {
  assert(ret==-EUCLEAN && state(o).configured_radio.stop_error && o->radio &&
   mishare_runtime_configured_stop(o)==-EUCLEAN && !pe_deletes && !dp_detaches &&
   "EXPECTED_CONFIG208_STOP_POST_HELD");return;
 }
 assert(ret==-EINPROGRESS && state(o).configured_radio.stop_requested && o->radio &&
  mishare_runtime_destroy(&held)==-EINPROGRESS && !pe_pending.bodyptr &&
  "EXPECTED_CONFIG208_STOP_BEFORE_PE");
 if(radio_fault==4)radio_stop_fail=true;
 radio_run(false);
 if(radio_fault==4) {
  assert(mishare_runtime_configured_stop(o)<0 && o->radio && !pe_deletes && !dp_detaches &&
   "EXPECTED_CONFIG208_STOP_FAULT_HELD");return;
 }
 assert(state(o).radio.phase==MISHARE_RADIO_WAIT_STOP && radio_stops==1 && !radio_downs &&
  mishare_runtime_configured_stop(o)==-EINPROGRESS && "EXPECTED_CONFIG208_WAIT_STOP");
 if(!inline_rate)assert(radio_reply_stop()==QDF_STATUS_SUCCESS);
 if(radio_fault==5)radio_down_fail=true;
 radio_run(false);
 if(radio_fault==5) {
  assert(mishare_runtime_configured_stop(o)<0 && o->radio && !pe_deletes && !dp_detaches &&
   "EXPECTED_CONFIG208_DOWN_FAULT_HELD");return;
 }
 assert(state(o).radio.phase==MISHARE_RADIO_DOWN && state(o).radio.down_accepted &&
  radio_stops==1 && radio_downs==1 && "EXPECTED_CONFIG208_NATIVE_DOWN");
 assert(!mishare_runtime_configured_stop(o) && !o->radio && state(o).configured_radio.stopped &&
  !memcmp(&prepared.rate,&o->state.rate,sizeof(prepared.rate)) &&
  !memcmp(&prepared.retry,&o->state.retry,sizeof(prepared.retry)) &&
  !memcmp(&prepared.start_preview,&o->state.start_preview,sizeof(prepared.start_preview)) &&
  !mishare_runtime_configured_stop(o) && radio_starts==1 && radio_stops==1 && radio_downs==1 &&
  "EXPECTED_CONFIG208_STOP_RECEIPT_NO_REPLAY");
 for(unsigned corrupt=0;corrupt<3;corrupt++) {
  pid_t child=fork();assert(child>=0);if(!child) {
   if(corrupt==0)o->state.configured_radio.stopped=false;
   if(corrupt==1)o->state.radio.down_accepted=false;
   if(corrupt==2)o->state.radio.fence.start_reply_queued=true;
   assert(mishare_runtime_destroy(&o)<0 && o && !pe_pending.bodyptr && !pe_deletes && !dp_detaches &&
    "EXPECTED_CONFIG208_DOWN_PROOF_REQUIRED");_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) &&
   "EXPECTED_CONFIG208_DOWN_PROOF_CHILD");
 }
 prestart_owner=NULL;prestart_control=NULL;prestart_session=NULL;
 clean_modes=mode;clean_fault=cleanup_fault;
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && pe_pending.bodyptr &&
  state(o).rate.ordinary_admitted && !o->radio && "EXPECTED_CONFIG208_PE_AFTER_DOWN");
 configured208_clean_end(&o);
 if(cleanup_fault)assert(o && !state(o).freed && "EXPECTED_CONFIG208_CLEANUP_FAULT_RETAIN");
 else assert(!o && !mishare_runtime_owners && !objects_live && !allocations && !module_refs &&
  !engine_allocations && !dp_objects && !stats_live && !timers_live &&
  radio_starts==1 && radio_stops==1 && radio_downs==1 && "EXPECTED_CONFIG208_COMPLETE");
}
static void configured208_cases(void) {
 const u8 pairs[][2]={{0,0},{5,0},{0,3},{5,3}};
 for(unsigned band=0;band<2;band++)for(unsigned pair=0;pair<4;pair++)
 for(unsigned early=0;early<2;early++)for(unsigned mode=0;mode<32;mode++) {
  pid_t child=fork();assert(child>=0);if(!child) {
   retry_data=pairs[pair][0];retry_mgmt=pairs[pair][1];retry_failure=retry_fault=0;retry_inline=!!early;
   configured208_case(band?5240:2437,mode,!!early,0,0,0);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) &&
   "EXPECTED_CONFIG208_CYCLE_CHILD");
 }
 for(unsigned admission=0;admission<=16;admission++)for(unsigned radio_fault=0;radio_fault<8;radio_fault++) {
  if((!admission && !radio_fault) || (admission && radio_fault))continue;
  pid_t child=fork();assert(child>=0);if(!child) {
   retry_data=5;retry_mgmt=3;retry_failure=retry_fault=0;retry_inline=false;
   configured208_case(5240,0,false,admission,radio_fault,0);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) &&
   "EXPECTED_CONFIG208_FAULT_CHILD");
 }
 for(unsigned fault=1;fault<=6;fault++) {
  pid_t child=fork();assert(child>=0);if(!child) {
   retry_data=5;retry_mgmt=3;retry_failure=retry_fault=0;retry_inline=false;
   configured208_case(5240,0,false,0,0,fault);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) &&
   "EXPECTED_CONFIG208_CLEANUP_CHILD");
 }
}
'''

def fixture(root):
    source,exits,stubbed=prior.ordinary_fixture(root)
    old=function(source,'prestart_native_cycle')
    prefix=old[:old.index(' struct mishare_runtime_rate_status before=state(o).rate;')]
    prefix=prefix[prefix.index('{')+1:]
    case='''static void configured208_case(unsigned freq,unsigned mode,bool inline_rate,unsigned admission,unsigned radio_fault,unsigned cleanup_fault) {
 unsigned failure=0,fault=0;
 preview_cycle_enabled=commit_enabled=true;preview_cycle_origin=0;preview_cycle_inline=inline_rate;
'''+prefix+TAIL
    clean=function(source,'prestart_clean_end')
    clean=clean.replace('prestart_clean_end(', 'configured208_clean_end(',1)
    needle='!state(*o).ndi.radio_requested && '
    assert clean.count(needle)==1
    clean=clean.replace(needle,'state(*o).configured_radio.stopped && state(*o).ndi.radio_requested && ',1)
    main=function(source,'main')
    source=source.replace(main,main.replace('int main(void)', 'int previous_configured208_main(void)',1)+'\n'+clean+'\n'+case+'\nint main(void) {configured208_cases();engine_contract();puts("MISHARE_CONFIGURED_RADIO_ORDINARY_FIXTURE_PASS_ONLY");return 0;}\n',1)
    return source,exits,stubbed


def controls(directory,c_file,command,env,source,root):
    original=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_runtime.c').read_text()
    mutations=[]
    for name,old,new in [
        ('mishare_runtime_configured_start','c->requested = true;', 'c->requested = false;'),
        ('mishare_runtime_configured_start','ret = mishare_runtime_configured_history(e);','ret = 0 * mishare_runtime_configured_history(e);'),
        ('mishare_runtime_configured_stop','c->stop_requested = true;', 'c->stop_requested = false;'),
        ('mishare_runtime_configured_stop','ret = mishare_radio_drain(&e->radio, &last);','ret = 0;'),
        ('mishare_runtime_configured_down','c->stop_requested && c->stopped &&','c->stop_requested && true &&'),
        ('mishare_runtime_configured_down','r->down_attempted && r->down_accepted &&','r->down_attempted && true &&'),
    ]:
        body=function(original,name);assert body.count(old)==1,(name,old)
        mutations.append(original.replace(body,body.replace(old,new,1),1))
    override=directory/'wlan_hdd_mishare_runtime.c'
    try:
        for modified in mutations:
            override.write_text(modified);c_file.write_text(source)
            subprocess.run(command,check=True)
            bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=90)
            assert bad.returncode==-6 and 'EXPECTED_CONFIG208_' in bad.stderr,(bad.returncode,bad.stderr[-2500:])
    finally:override.unlink(missing_ok=True)


def audit(root):
    engine=prior.previous.ordinary.previous.ordinary.cleanup.engine
    r=engine.audit(root,fixture_builder=fixture,extra_audit=controls)
    r.update(status='MISHARE_CONFIGURED_RADIO_ORDINARY_FIXTURE_PASS_ONLY',configured_cycles=512,
             admission_faults=16,radio_faults=7,cleanup_faults=6,new_mutations=6,
             production_sha256={p:hashlib.sha256((ROOT/'kernel/popsicle-hdd'/p).read_bytes()).hexdigest()
              for p in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h']},
             limitations='Actual runtime/configuration receipt/owned MC/native START-UP-STOP-DOWN/ordinary PE-peer-DELETE-DP and SM cleanup execute together. Parent scope and full request/current regulatory admission remain caller obligations. Scheduler, firmware delivery/WMI execution, object refs/unmap and primitive locks retain existing explicit fixture models. Pending START is held without cancellation. Active configured SSR/remove recovery, public Wonder initialization, native host caller integration and phone RF/Apple acceptance remain closed/unqualified.')
    return r

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
