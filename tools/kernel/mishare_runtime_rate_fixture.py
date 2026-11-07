#!/usr/bin/env python3
"""Actual runtime rate hooks/bridge/work wrapper against modeled native owner APIs."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from mishare_rate_work_fixture import HARNESS as WORK_HARNESS, ROOT

MODEL=r'''
#include "wlan_hdd_mishare_runtime_rate.h"
struct mishare_ndi_status {
 struct {bool timer_ready,dp_attached,stats_owned;} create;
 bool blocked,active,legacy_ready,wma_bound,peer_created,pe_ready,pe_submitted,pe_completed;
 bool channel_submitted,channel_completed,channel_prepared,start_plan_requested,radio_requested;
 bool pe_delete_requested,pe_delete_submitted,pe_delete_completed,peer_delete_pending,peer_delete_submitted,peer_delete_replied,delete_pending,delete_submitted,delete_replied,dp_detaching,dp_detach_submitted,dp_freed;
 int completion_error;
};
struct runtime_model_state {
 bool blocked,draining,allocated,freed,host_reclaim,host_delete_accepted;int quiesced;
 bool mc_drained,recovery_window,recovery_window_closed,ndi_reclaim_started,ndi_reclaim_ready;
 bool recovery_timer_attempted,recovery_timer_released,recovery_pe_attempted,recovery_pe_released;
 bool recovery_context_attempted,recovery_context_finish_attempted,recovery_context_released;
 bool recovery_peer_released,recovery_dp_attempted,recovery_dp_freed;
 int work_error,recovery_error,reclaim_error;
 unsigned work_pending,work_users;
 struct mishare_ndi_status ndi;
 struct mishare_runtime_rate_status rate;
};
struct mishare_runtime_owner {
 struct mishare_runtime_owner *next;struct wlan_objmgr_vdev *vdev;
 bool referenced;void *events,*radio;unsigned long cookie,pe_cookie;struct runtime_model_state state;
};
static struct mishare_runtime_owner owner,*mishare_runtime_owners=&owner;
static int mishare_runtime_lock,lock_depth;
#define spin_lock_irqsave(l,f) do{(void)(l);(f)=0;assert(!lock_depth);lock_depth++;}while(0)
#define spin_unlock_irqrestore(l,f) do{(void)(l);(void)(f);assert(lock_depth==1);lock_depth--;}while(0)
#define MISHARE_QUIESCE_SSR 1
RUNTIME_BLOCK
'''
RESET=r'''
static void reset(void){
 assert(v.refs==1 && !pending && !users && !allocs && !lock_depth);
 queued=(struct scheduler_msg){0};observed=(struct mishare_rate_submission){0};execs=done_calls=0;exec_error=last_result=0;
 fail_alloc=fail_ref=fail_get=fail_post=fenced=inline_finish=false;
 owner=(struct mishare_runtime_owner){.vdev=&v,.referenced=true,.events=&v,.cookie=(unsigned long)&v,.pe_cookie=1};
 owner.state.allocated=true;owner.state.ndi.create.timer_ready=owner.state.ndi.create.dp_attached=true;
 owner.state.ndi=(struct mishare_ndi_status){.create={.timer_ready=true,.dp_attached=true},.active=true,.legacy_ready=true,.wma_bound=true,.peer_created=true,
 .pe_ready=true,.pe_submitted=true,.pe_completed=true,.channel_submitted=true,.channel_completed=true,.channel_prepared=true};
}
'''
MAIN=r'''
int main(void){
 struct wondertap_fixed_tx_rate_params p={.preamble=WONDERTAP_RATE_PREAMBLE_HT,.nss=1,.mcs=7};
 struct mishare_runtime_rate_request request={.preamble=1,.nss=1,.mcs=7};
 struct wlan_objmgr_vdev *out=(void*)1;
 reset();assert(mishare_runtime_rate_begin((void*)1,&request,&out)==-ENOENT && !out);
 assert(mishare_runtime_rate_configure(NULL,&p)==-EINVAL && !owner.state.rate.requested);
 p.nss=0;assert(mishare_runtime_rate_configure(&owner,&p)==-EINVAL && !owner.state.rate.requested);p.nss=1;
 for(int fault=0;fault<6;fault++){
  reset();
  if(fault==0)owner.state.ndi.channel_prepared=false;
  if(fault==1)owner.state.ndi.start_plan_requested=true;
  if(fault==2)owner.state.quiesced=1;
  if(fault==3)owner.state.draining=true;
  if(fault==4)owner.state.blocked=true;
  if(fault==5)owner.referenced=false;
  int expected=fault==2 || fault==3?-ESHUTDOWN:fault==4?-EUCLEAN:-EBUSY;
  assert(mishare_runtime_rate_configure(&owner,&p)==expected && !owner.state.rate.requested && !allocs && "EXPECTED_RATE_RUNTIME_ADMISSION");
 }
 for(int fault=0;fault<4;fault++){
  reset();fail_alloc=fault==0;fail_ref=fault==1;fail_get=fault==2;fail_post=fault==3;
  int expected=fault==0?-ENOMEM:fault==1?-ENODEV:fault==2?-ESHUTDOWN:-EIO;
  assert(mishare_runtime_rate_configure(&owner,&p)==expected && "EXPECTED_RATE_RUNTIME_POST_FAILURE");
  struct mishare_runtime_rate_status *r=&owner.state.rate;
  assert(r->requested && r->posted && !r->accepted && r->completed && r->receipt.result==expected && !r->receipt.attempted && !r->integrity_error && "EXPECTED_RATE_RUNTIME_POST_FAILURE");
  assert(!mishare_runtime_rate_retire_check(&owner) && !allocs && !pending && v.refs==1);
  assert(mishare_runtime_rate_configure(&owner,&p)==-EALREADY && "EXPECTED_RATE_RUNTIME_ONCE");
 }
 for(int mode=0;mode<6;mode++){
  reset();inline_finish=mode==4;exec_error=mode==3?-ENOSPC:0;
  assert(mishare_runtime_rate_configure(&owner,&p)==-EINPROGRESS);
  struct mishare_runtime_rate_status *r=&owner.state.rate;
  assert(r->requested && r->posted && r->accepted && !r->integrity_error && "EXPECTED_RATE_RUNTIME_POSTED");
  assert(mishare_runtime_rate_configure(&owner,&p)==-EALREADY && "EXPECTED_RATE_RUNTIME_ONCE");
  if(mode!=4){
   assert(!r->completed && mishare_runtime_rate_retire_check(&owner)==-EINPROGRESS && "EXPECTED_RATE_RUNTIME_PENDING");
   if(mode==2)fenced=true;
   if(mode==5){p.nss=0;p.mcs=99;}
   assert(!(mode==1?queued.flush_callback(&queued):queued.callback(&queued)));p.nss=1;p.mcs=7;
  }
  int expected=mode==1?-ECANCELED:mode==2?-ESHUTDOWN:mode==3?-ENOSPC:0;
  assert(r->completed && !r->integrity_error && r->receipt.result==expected && r->receipt.attempted==!!execs && "EXPECTED_RATE_RUNTIME_COMPLETED");
  assert(mishare_runtime_rate_retire_check(&owner)==(execs?-EOPNOTSUPP:0) && "EXPECTED_RATE_RUNTIME_RETAIN_ATTEMPT");
  assert(!pending && !users && !allocs && v.refs==1 && !owner.state.work_pending && !owner.state.work_users);
  struct mishare_runtime_rate_result saved=r->receipt;
  mishare_runtime_rate_complete(&owner,&saved);
  assert(r->integrity_error && !memcmp(&saved,&r->receipt,sizeof(saved)) && mishare_runtime_rate_retire_check(&owner)==-EUCLEAN && "EXPECTED_RATE_RUNTIME_DUPLICATE");
 }
 for(int fault=0;fault<7;fault++){
  reset();assert(!mishare_runtime_rate_begin(&owner,&request,&out));owner.state.work_pending=fault==0?0:1;
  struct mishare_runtime_rate_result r={.result=-ECANCELED};
  if(fault==1)r.busy=true;
  if(fault==2)r.attempted=true;
  if(fault==3){r.attempted=true;r.attempted_mask=2;}
  if(fault==4)r.complete=true;
  if(fault==5)r.submitted_mask=1;
  if(fault==6)r.result=0;
  mishare_runtime_rate_complete(&owner,&r);
  assert(owner.state.rate.integrity_error && !owner.state.rate.completed && "EXPECTED_RATE_RUNTIME_RECEIPT_SHAPE");
 }
 reset();assert(!mishare_runtime_rate_begin(&owner,&request,&out));owner.state.work_pending=1;
 struct mishare_runtime_rate_result canceled={.result=-ECANCELED};mishare_runtime_rate_complete(&owner,&canceled);
 assert(owner.state.rate.completed && !owner.state.rate.integrity_error);
 mishare_runtime_rate_posted(&owner,-EIO);
 assert(owner.state.rate.integrity_error && owner.state.rate.receipt.result==-ECANCELED && "EXPECTED_RATE_RUNTIME_INLINE_CONTRADICTION");
 for(int fault=0;fault<8;fault++){
  reset();inline_finish=true;assert(mishare_runtime_rate_configure(&owner,&p)==-EINPROGRESS);
  owner.state.quiesced=1;owner.state.mc_drained=true;
  if(fault==0)owner.state.quiesced=0;
  if(fault==1)owner.state.mc_drained=false;
  if(fault==2)owner.state.work_pending=1;
  if(fault==3)owner.state.ndi.radio_requested=true;
  if(fault==4)owner.state.ndi.start_plan_requested=true;
  if(fault==5)owner.state.recovery_window_closed=true;
  if(fault==6)owner.state.recovery_error=-EIO;
  int expected=fault==0||fault==3||fault==4?-EOPNOTSUPP:fault==1||fault==2?-EINPROGRESS:fault==5?-ESHUTDOWN:fault==6?-EUCLEAN:0;
  assert(mishare_runtime_rate_reset_check(&owner)==expected && "EXPECTED_RATE_RESET_ELIGIBILITY");
  assert(mishare_runtime_rate_retire_check(&owner)==-EOPNOTSUPP && "EXPECTED_RATE_RESET_ORDINARY_BLOCKED");
 }
 reset();inline_finish=true;assert(mishare_runtime_rate_configure(&owner,&p)==-EINPROGRESS);
 owner.state.quiesced=1;owner.state.mc_drained=true;owner.state.rate.reset_admitted=true;
 assert(mishare_runtime_rate_reset_check(&owner)==-EUCLEAN && "EXPECTED_RATE_RESET_WINDOW");
 owner.state.recovery_window=true;assert(!mishare_runtime_rate_reset_check(&owner));
 owner.state.rate.reset_completed=true;
 assert(mishare_runtime_rate_reset_check(&owner)==-EUCLEAN && "EXPECTED_RATE_RESET_TERMINAL_FACTS");
 owner.state.ndi_reclaim_started=owner.state.ndi_reclaim_ready=true;
 owner.state.recovery_timer_attempted=owner.state.recovery_timer_released=true;
 owner.state.recovery_pe_attempted=owner.state.recovery_pe_released=true;
 owner.state.recovery_context_attempted=owner.state.recovery_context_finish_attempted=owner.state.recovery_context_released=true;
 owner.state.recovery_peer_released=owner.state.recovery_dp_attempted=owner.state.recovery_dp_freed=true;
 owner.state.ndi.active=owner.state.ndi.legacy_ready=owner.state.ndi.wma_bound=owner.state.ndi.peer_created=owner.state.ndi.pe_ready=false;
 owner.state.ndi.create.timer_ready=owner.state.ndi.create.dp_attached=false;
 owner.state.recovery_window=false;owner.state.recovery_window_closed=true;
 assert(!mishare_runtime_rate_reset_check(&owner) && "EXPECTED_RATE_RESET_METADATA_AFTER_CLOSE");
 owner.state.recovery_dp_freed=false;
 assert(mishare_runtime_rate_reset_check(&owner)==-EUCLEAN && "EXPECTED_RATE_RESET_TERMINAL_FACTS");

 for(int fault=0;fault<10;fault++){
  reset();inline_finish=true;assert(mishare_runtime_rate_configure(&owner,&p)==-EINPROGRESS);
  if(fault==0)owner.state.quiesced=1;
  if(fault==1)owner.state.work_pending=1;
  if(fault==2)owner.state.ndi.radio_requested=true;
  if(fault==3)owner.state.ndi.start_plan_requested=true;
  if(fault==4)owner.state.rate.reset_admitted=true;
  if(fault==5)owner.state.work_error=-EIO;
  if(fault==6)owner.pe_cookie=0;
  if(fault==7)owner.state.ndi.pe_delete_requested=true;
  if(fault==9)owner.state.ndi.create.timer_ready=false;
  int expected=fault==1?-EINPROGRESS:fault==5?-EUCLEAN:fault==8?0:-EOPNOTSUPP;
  assert(mishare_runtime_rate_ordinary_check(&owner)==expected && "EXPECTED_RATE_ORDINARY_ADMISSION");
 }
 reset();inline_finish=true;assert(mishare_runtime_rate_configure(&owner,&p)==-EINPROGRESS);
 owner.state.rate.ordinary_admitted=true;
 assert(!mishare_runtime_rate_ordinary_check(&owner));
 owner.state.rate.ordinary_completed=true;
 assert(mishare_runtime_rate_ordinary_check(&owner)==-EUCLEAN && "EXPECTED_RATE_ORDINARY_TERMINAL");
 owner.state.ndi.active=owner.state.ndi.pe_ready=owner.state.ndi.legacy_ready=owner.state.ndi.wma_bound=false;
 owner.pe_cookie=0;owner.state.ndi.create.timer_ready=false;
 owner.state.ndi.pe_delete_requested=owner.state.ndi.pe_delete_submitted=owner.state.ndi.pe_delete_completed=true;
 owner.state.ndi.peer_delete_pending=owner.state.ndi.peer_delete_submitted=owner.state.ndi.peer_delete_replied=true;
 owner.state.ndi.delete_pending=owner.state.ndi.delete_submitted=owner.state.ndi.delete_replied=true;
 owner.state.ndi.dp_detaching=owner.state.ndi.dp_detach_submitted=owner.state.ndi.dp_freed=true;
 assert(!mishare_runtime_rate_ordinary_check(&owner) && "EXPECTED_RATE_ORDINARY_TERMINAL");

 owner.state.quiesced=1;owner.state.host_delete_accepted=owner.state.draining=true;
 owner.vdev=NULL;owner.referenced=false;owner.events=NULL;
 owner.state.recovery_window_closed=true;
 assert(!mishare_runtime_rate_final_check(&owner) && "EXPECTED_RATE_FINAL_METADATA");
 assert(mishare_runtime_rate_ordinary_check(&owner)==-EOPNOTSUPP);
 for(int fault=0;fault<8;fault++){
  struct runtime_model_state saved=owner.state;
  if(fault==0)owner.state.host_delete_accepted=false;
  if(fault==1)owner.state.ndi.peer_delete_replied=false;
  if(fault==2)owner.state.ndi.dp_freed=false;
  if(fault==3)owner.state.work_error=-EIO;
  if(fault==4)owner.state.ndi.create.timer_ready=true;
  if(fault==5)owner.state.quiesced=2;
  if(fault==6)owner.state.rate.ordinary_completed=false;
  if(fault==7)owner.state.rate.reset_admitted=true;
  int expected=fault==5||fault==6?-EOPNOTSUPP:-EUCLEAN;
  assert(mishare_runtime_rate_final_check(&owner)==expected && "EXPECTED_RATE_FINAL_RETAIN");
  owner.state=saved;
 }
 owner.state.ndi.peer_delete_replied=false;
 assert(mishare_runtime_rate_final_check(&owner)==-EUCLEAN && "EXPECTED_RATE_FINAL_TERMINAL");

 reset();inline_finish=true;assert(mishare_runtime_rate_configure(&owner,&p)==-EINPROGRESS);
 owner.state.rate.ordinary_admitted=true;owner.state.quiesced=1;owner.state.mc_drained=true;
 owner.state.ndi.pe_ready=false;owner.pe_cookie=0;
 owner.state.ndi.pe_delete_requested=owner.state.ndi.pe_delete_submitted=owner.state.ndi.pe_delete_completed=true;
 owner.state.ndi.peer_delete_pending=owner.state.ndi.peer_delete_submitted=owner.state.ndi.peer_delete_replied=true;
 owner.state.ndi.delete_pending=owner.state.ndi.delete_submitted=owner.state.ndi.delete_replied=true;
 owner.state.ndi.dp_detaching=owner.state.ndi.dp_detach_submitted=true;owner.state.ndi.create.timer_ready=false;
 for(int fault=0;fault<7;fault++){
  struct runtime_model_state saved=owner.state;
  if(fault==0)owner.state.ndi.peer_delete_replied=false;
  if(fault==1)owner.state.ndi.dp_detach_submitted=false;
  if(fault==2)owner.state.mc_drained=false;
  if(fault==3)owner.state.rate.tail_attempted=true;
  if(fault==4)owner.state.recovery_window_closed=true;
  if(fault==5)owner.state.ndi.completion_error=-EIO;
  int expected=fault==0||fault==1?-EOPNOTSUPP:fault==2?-EINPROGRESS:fault==3||fault==5?-EUCLEAN:fault==4?-ESHUTDOWN:0;
  assert(mishare_runtime_rate_tail_check(&owner)==expected && "EXPECTED_RATE_TAIL_ELIGIBILITY");owner.state=saved;
 }
 owner.state.rate.tail_attempted=owner.state.rate.tail_completed=owner.state.rate.ordinary_completed=true;
 owner.state.ndi.active=owner.state.ndi.legacy_ready=owner.state.ndi.wma_bound=false;
 owner.state.ndi.dp_freed=true;
 assert(!mishare_runtime_rate_tail_check(&owner) && "EXPECTED_RATE_TAIL_COMPLETED");
 reset();puts("MISHARE_RUNTIME_RATE_FIXTURE_PASS_ONLY");return 0;
}
'''


def main():
    production=ROOT/'kernel/popsicle-hdd'
    runtime=(production/'wlan_hdd_mishare_runtime.c').read_text()
    block=runtime.split('/* MISHARE_RUNTIME_RATE_BEGIN */',1)[1].split('/* MISHARE_RUNTIME_RATE_END */',1)[0]
    code=WORK_HARNESS[:WORK_HARNESS.index('int main(void){')]
    code=code.replace('static struct scheduler_msg queued;',MODEL.replace('RUNTIME_BLOCK',block)+'\nstatic struct scheduler_msg queued;')
    code=code.replace('static int owner,allocs,','static int allocs,')
    code=code.replace('pending++;return 0;', 'pending++;owner.state.work_pending++;return 0;')
    code=code.replace('users++;return 0;', 'users++;owner.state.work_users++;return 0;')
    code=code.replace('users--;}', 'users--;owner.state.work_users--;}')
    code=code.replace('pending--;}', 'pending--;owner.state.work_pending--;}')
    code=re.sub(r'static void completed\(.*?^\}\n','',code,flags=re.S|re.M)
    code=re.sub(r'static void reset\(void\)\{.*?^\}\n',RESET,code,flags=re.S|re.M)
    code+='\n#include "wlan_hdd_mishare_runtime_rate.c"\n'+MAIN
    terminal=re.search(r'static bool mishare_runtime_rate_ordinary_terminal\(.*?^\}',block,re.S|re.M)[0]
    mutations=[
        ('if (entry->state.rate.requested)', 'if (false && entry->state.rate.requested)'),
        ('entry->state.rate.requested = true;', 'entry->state.rate.requested = false;'),
        ('if (!r->posted || !r->completed)', 'if (false && (!r->posted || !r->completed))'),
        ('return r->receipt.attempted ? -EOPNOTSUPP : 0;', 'return r->receipt.attempted ? 0 : 0;'),
        ('!entry->state.work_pending || entry->state.work_users || result->busy', 'false || entry->state.work_users || result->busy'),
        ('!n->channel_prepared ||\n                 n->start_plan_requested', '(false && !n->channel_prepared) ||\n                 n->start_plan_requested'),
        ('r->ordinary_completed ||\n        entry->state.quiesced != MISHARE_QUIESCE_SSR ||', 'r->ordinary_completed ||\n        false ||'),
        (terminal, terminal.replace('!n->peer_delete_submitted || !n->peer_delete_replied ||', '!n->peer_delete_submitted || false ||', 1)),
        ('!n->create.timer_ready || !n->create.dp_attached ||', 'false || !n->create.dp_attached ||'),
        ('!entry->state.recovery_dp_freed || n->active', 'false || n->active'),
        ('if (!entry->state.recovery_window)', 'if (false && !entry->state.recovery_window)'),
        ('!entry->state.host_delete_accepted || !entry->state.draining ||', 'false || !entry->state.draining ||'),
        ('if (r->tail_attempted)\n            return -EUCLEAN;', 'if (false && r->tail_attempted)\n            return -EUCLEAN;'),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        for name in ['linux/slab.h','qdf_status.h','scheduler_api.h','wlan_objmgr_vdev_obj.h','wlan_hdd_mishare_ndi.h','linux/if_ether.h']:(d/name).write_text('/* modeled in harness */\n')
        (d/'linux/errno.h').write_text('#include_next <linux/errno.h>\n');(d/'linux/types.h').write_text('/* scalar types in harness */\n')
        sources=['wlan_hdd_mishare_rate_work.c','wlan_hdd_mishare_runtime_rate.c','wlan_hdd_mishare_rate.h','wlan_hdd_mishare_runtime_rate.h']
        for name in sources:(d/name).write_bytes((production/name).read_bytes())
        (d/'wlan_hdd_mishare_wonder_api.h').write_bytes((ROOT/'kernel/provider/wondertap.h').read_bytes())
        source=d/'test.c';source.write_text(code);exe=d/'test'
        command=['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+tmp,str(source),'-o',str(exe)]
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks='+('1' if os.environ.get('GITHUB_ACTIONS')=='true' else '0')+':abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        subprocess.run(command,check=True);result=subprocess.check_output([exe],text=True,env=env,timeout=10).strip()
        for needle,replacement in mutations:
            assert block.count(needle)==1,needle
            source.write_text(code.replace(block,block.replace(needle,replacement),1));subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=10)
            assert bad.returncode==-6 and ('EXPECTED_RATE_RUNTIME_' in bad.stderr or 'EXPECTED_RATE_RESET_' in bad.stderr or 'EXPECTED_RATE_ORDINARY_' in bad.stderr or 'EXPECTED_RATE_FINAL_' in bad.stderr or 'EXPECTED_RATE_TAIL_' in bad.stderr),(needle,bad.returncode,bad.stderr[-1600:])
    out=ROOT/'.popsicle-ci/artifacts/reports/mishare-runtime-rate-fixture.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'status':result,'mutation_controls':len(mutations),'production_block_sha256':hashlib.sha256(block.encode()).hexdigest(),'limitations':'Actual scalar runtime hooks, configure bridge and MC wrapper with modeled owner metadata/ref/runtime accounting/scheduler/executor. Complete native runtime cleanup gates run separately on Actions. No firmware ACK, full parent/configuration teardown or RF/Apple proof.'},indent=2)+'\n');print(result)


if __name__=='__main__':main()
