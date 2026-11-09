#!/usr/bin/env python3
"""Batch retry work, registry and prestart-to-native ordinary retirement."""
import argparse
import json
from pathlib import Path
import mishare_prestart_native_fixture as previous
from mishare_recovery_fixture import function
ROOT=previous.ROOT
MODEL=r'''
static struct scheduler_msg retry_queue;
static u8 retry_data,retry_mgmt;
static unsigned retry_failure,retry_fault,retry_posts,retry_execs,retry_replies;
static bool retry_inline;
static struct mishare_runtime_retry_status retry_saved_history;
static void retry_history_check(struct mishare_runtime_owner *o,struct mishare_runtime_rate_status before) {
 prestart_history(o,before);
 struct mishare_runtime_retry_status now=state(o).retry;
 assert(!memcmp(&now,&retry_saved_history,sizeof(now)) && "EXPECTED_RETRY_NATIVE_HISTORY");
}
int mishare_retry_submit_mc(struct wlan_objmgr_vdev *v,u8 d,u8 m,struct mishare_retry_submission *r) {
 assert(v==last_vdev && state(prestart_owner).work_pending==1 && state(prestart_owner).work_users==1 &&
  d==retry_data && m==retry_mgmt && !r->attempted && "EXPECTED_RETRY_NATIVE_EXECUTION");
 retry_execs++;r->attempted=true;r->vdev_id=wlan_vdev_get_id(v);r->data_limit=d;r->mgmt_limit=m;
 for(unsigned group=0;group<2;group++) {
  u8 bit=1U<<group;
  if(!(group?m:d)){r->skipped_mask|=bit;continue;}
  r->attempted_mask|=bit;
  if(retry_failure==group+1){r->first_error=-EIO;return -EIO;}
  r->submitted_mask|=bit;
 }
 r->complete=true;return 0;
}
static QDF_STATUS retry_scheduler(int from,int dest,int queue,struct scheduler_msg *m) {
 assert(from==QDF_MODULE_ID_HDD && dest==QDF_MODULE_ID_PE && queue==QDF_MODULE_ID_TARGET_IF &&
  m->bodyptr && m->callback && m->flush_callback && !retry_queue.bodyptr &&
  state(prestart_owner).work_pending==1 && !state(prestart_owner).work_users && "EXPECTED_RETRY_NATIVE_PUBLICATION");
 retry_posts++;if(retry_fault==1)return QDF_STATUS_E_FAILURE;
 retry_queue=*m;
 if(retry_inline)assert(!retry_queue.callback(&retry_queue));
 return QDF_STATUS_SUCCESS;
}
HOST_RETRY_TAIL
#define scheduler_post_message retry_scheduler
#include "wlan_hdd_mishare_retry_work.c"
#undef scheduler_post_message
static void retry_publish(struct mishare_runtime_owner *o,const struct mishare_retry_submission *r,int ret) {
 mishare_runtime_retry_complete(o,r,ret);retry_replies++;
 assert(o==prestart_owner && state(o).work_pending==1 && !state(o).work_users &&
  state(o).retry.completed && !state(o).retry.integrity_error && "EXPECTED_RETRY_NATIVE_RECEIPT");
 if(!state(o).quiesced && !ret)assert(retry_host_poll(retry_data,retry_mgmt)==-EINPROGRESS &&
  "EXPECTED_RETRY_NATIVE_HOST_PUBLISH_BARRIER");
 struct mishare_runtime_owner *held=o;
 int destroy_result=mishare_runtime_destroy(&held);
 if(destroy_result!=(state(o).quiesced?-EUCLEAN:-EINPROGRESS) || held!=o || state(o).ndi.pe_delete_requested)
  fprintf(stderr,"retry publish: d=%u m=%u fail=%u fault=%u inline=%u quiesced=%u pending=%u posted=%u destroy=%d\n",
   retry_data,retry_mgmt,retry_failure,retry_fault,retry_inline,state(o).quiesced,state(o).work_pending,state(o).retry.posted,destroy_result);
 assert(destroy_result==(state(o).quiesced?-EUCLEAN:-EINPROGRESS) && held==o &&
  !state(o).ndi.pe_delete_requested && "EXPECTED_RETRY_NATIVE_RETAIN_DURING_PUBLISH");
}
#define mishare_runtime_retry_complete retry_publish
#include "wlan_hdd_mishare_runtime_retry.c"
#undef mishare_runtime_retry_complete
static void retry_batch(void) {
 struct mishare_runtime_owner *o=prestart_owner;struct wlan_objmgr_vdev *out=(void*)1;
 struct mishare_runtime_retry_status original;
 retry_queue=(struct scheduler_msg){0};retry_posts=retry_execs=retry_replies=0;
 if(retry_fault==2)fail_alloc_at=alloc_calls+1;
 if(retry_fault==3)fail_ref_at=ref_calls+1;
 int post_error=retry_fault==1?-EIO:retry_fault==2?-ENOMEM:retry_fault==3?-ENODEV:0;
 int ret=retry_host_poll(retry_data,retry_mgmt);
 assert(ret==(post_error?post_error:-EINPROGRESS) && "EXPECTED_RETRY_NATIVE_SUBMIT_RETURN");
 assert(mishare_runtime_retry_begin(o,0,0,&out)==-EALREADY && !out && "EXPECTED_RETRY_NATIVE_ONCE");
 if(!post_error && !retry_inline) {
  assert(retry_queue.bodyptr && state(o).work_pending==1 && !state(o).retry.completed &&
   "EXPECTED_RETRY_NATIVE_WAIT");
  if(retry_fault==5)mark_closed(o);
  struct scheduler_msg msg=retry_queue;retry_queue.bodyptr=NULL;
  assert(!(retry_fault==4?msg.flush_callback(&msg):msg.callback(&msg)) && !msg.bodyptr);
 }
 int expected=post_error?post_error:retry_fault==4?-ECANCELED:retry_fault==5?-ESHUTDOWN:retry_failure?-EIO:0;
 original=state(o).retry;
 assert(retry_host_poll(retry_data,retry_mgmt)==expected && "EXPECTED_RETRY_NATIVE_HOST_RESULT");
 if(retry_fault!=5)assert(retry_host_poll(retry_data^1,retry_mgmt)==-EBUSY &&
  "EXPECTED_RETRY_NATIVE_HOST_IMMUTABLE");
 assert(original.requested && original.posted && original.completed && original.accepted==!post_error &&
  original.result==expected && !original.integrity_error && !state(o).work_pending && !state(o).work_users &&
  retry_execs==(post_error||retry_fault==4||retry_fault==5?0u:1u) && "EXPECTED_RETRY_NATIVE_RESULT");
 if(retry_fault==5 || retry_fault==6 || retry_fault==7) {
  if(retry_fault==6) {
   assert(!wlan_objmgr_vdev_try_get_ref(last_vdev,WLAN_LEGACY_MAC_ID));
   assert(!mishare_runtime_work_get(last_vdev,o));
   mishare_runtime_retry_complete(o,&original.receipt,original.result);
   mishare_runtime_work_put(last_vdev,o);wlan_objmgr_vdev_release_ref(last_vdev,WLAN_LEGACY_MAC_ID);
  }
  if(retry_fault==7)mark_closed(o);
  if(retry_fault==5 || retry_fault==7)assert(mishare_runtime_rate_reset_check(o)==-EUCLEAN &&
   "EXPECTED_RETRY_NATIVE_SSR_RESET_FENCE");
  if(retry_fault==6)assert(state(o).retry.integrity_error && "EXPECTED_RETRY_NATIVE_DUPLICATE_FENCE");
  assert(mishare_runtime_destroy(&o)<0 && o && state(o).ndi.active && pe_slot.valid && dp_objects &&
   timers_live && !wire_deletes && !dp_detaches && !state(o).ndi.pe_delete_requested &&
   "EXPECTED_RETRY_NATIVE_SSR_OR_DUPLICATE_RETAIN");
  _Exit(0); /* Deliberate retained native owner; no cleanup/parent release claim. */
 }
 assert(!mishare_runtime_rate_ordinary_check(o) && "EXPECTED_RETRY_NATIVE_ORDINARY_ADMISSION");
 retry_saved_history=state(o).retry;
}
'''
CASES=r'''
static void retry_native_cases(void) {
 const u8 pairs[][2]={{0,0},{5,0},{0,3},{5,3},{255,255}};
 for(unsigned pair=0;pair<5;pair++)for(unsigned fail=0;fail<3;fail++)for(unsigned timing=0;timing<2;timing++)for(unsigned mode=0;mode<32;mode++) {
  if((fail==1 && !pairs[pair][0]) || (fail==2 && !pairs[pair][1]))continue;
  pid_t child=fork();assert(child>=0);if(!child) {
   retry_data=pairs[pair][0];retry_mgmt=pairs[pair][1];retry_failure=fail;retry_fault=0;retry_inline=timing;
   prestart_native_cycle(mode&1?5240:2437,0,mode,false,0);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 for(unsigned fault=1;fault<=7;fault++) {
  pid_t child=fork();assert(child>=0);if(!child) {
   retry_data=5;retry_mgmt=3;retry_failure=0;retry_fault=fault;retry_inline=false;
   prestart_native_cycle(5240,0,0,false,0);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
}
'''

def fixture(root):
    source,exits,stubbed=previous.fixture(root)
    once=previous.ordinary.cleanup.owner.replace_once
    cycle=function(source,'prestart_native_cycle')
    needle=' struct mishare_runtime_rate_status before=state(o).rate;'
    changed=once(cycle,needle,' retry_batch();\n'+needle)
    # Preserve actual retry history through every native cleanup stage.
    changed=once(changed,' prestart_clean_end(&o);',' struct mishare_runtime_retry_status retry_history=state(o).retry;\n prestart_clean_end(&o);\n assert(!o && retry_history.completed && "EXPECTED_RETRY_NATIVE_HISTORY");')
    host=function((ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_host.c').read_text(),'mishare_wonder_host_retry_step_locked')
    tail=host[host.index('    if (!host->prestart.selected'):]
    host_tail=r'''struct retry_host_model {struct mishare_prestart prestart;struct mishare_session session;struct mishare_runtime_owner *runtime;};
static int retry_host_tail(struct retry_host_model *host,u8 data_limit,u8 mgmt_limit) {
 struct mishare_runtime_status state;const struct mishare_runtime_retry_status *r=&state.retry;int ret;
'''+tail+r'''
static int retry_host_poll(u8 d,u8 m) {
 struct retry_host_model host={.prestart=*prestart_control,.session=*prestart_session,.runtime=prestart_owner};
 return retry_host_tail(&host,d,m);
}
'''
    model=MODEL.replace('HOST_RETRY_TAIL',host_tail,1)
    source=once(source,cycle,model+'\n'+changed)
    clean=function(source,'prestart_clean_end')
    source=once(source,clean,'static void retry_history_check(struct mishare_runtime_owner *,struct mishare_runtime_rate_status);\n'+clean.replace('prestart_history(', 'retry_history_check('))
    old=function(source,'prestart_native_cases')
    source=once(source,old,CASES)
    source=once(source,'prestart_native_cases();engine_contract();','retry_native_cases();engine_contract();')
    return source,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
    import subprocess
    prod=ROOT/'kernel/popsicle-hdd';once=previous.ordinary.cleanup.owner.replace_once
    work=(prod/'wlan_hdd_mishare_retry_work.c').read_text()
    runtime=(prod/'wlan_hdd_mishare_runtime.c').read_text()
    controls=[('wlan_hdd_mishare_retry_work.c',0,once(work,'    complete(owner, &receipt, ret);','    mishare_runtime_work_put(vdev, owner);\n    complete(owner, &receipt, ret);')),
              ('wlan_hdd_mishare_runtime.c',6,once(runtime,'if (!r->requested || r->completed || (r->posted && !r->accepted) ||\n            !entry->vdev','if (!r->requested || false || (r->posted && !r->accepted) ||\n            !entry->vdev')),
              ('wlan_hdd_mishare_runtime.c',7,once(runtime,'        if (entry->state.quiesced)\n            return -EUCLEAN;','        if (false && entry->state.quiesced)\n            return -EUCLEAN;'))]
    for name,fault,changed in controls:
        # engine.audit leaves a drift-only main selected; each extra control
        # must select its own retry baseline before applying an override.
        main='int main(void) {retry_data=5;retry_mgmt=3;retry_failure=0;retry_fault='+str(fault)+';retry_inline=false;prestart_native_cycle(5240,0,0,false,0);return 0;}'
        c_file.write_text(once(source,function(source,'main'),main))
        path=directory/name;path.unlink(missing_ok=True)
        subprocess.run(command,check=True)
        subprocess.run([directory/'engine'],check=True,timeout=90,env=env)
        path.write_text(changed)
        try:
            subprocess.run(command,check=True)
            bad=subprocess.run([str(directory/'engine')],capture_output=True,text=True,timeout=90,env=env)
            assert bad.returncode==-6 and 'EXPECTED_RETRY_NATIVE_' in bad.stderr,(name,bad.returncode,bad.stderr[-1400:])
        finally:path.unlink()

def audit(root):
    r=previous.ordinary.cleanup.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    r.update(status='MISHARE_RETRY_NATIVE_FIXTURE_PASS_ONLY',retry_combinations=704,publication_and_retention_cases=7,native_mutations=3)
    r['limitations']='Actual prestart/rate/runtime/retry MC work and selected native ordinary teardown; retry WMI executor boundary modeled and separately qualified in scalar fixture. Retry SSR and duplicate evidence retain native resources. No firmware ACK, parent lease, public init/START, phone/RF/Apple certification.'
    return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
