#!/usr/bin/env python3
"""Actions-only adoption of owned START encoder receipt, never radio activation."""
import argparse
import json
from pathlib import Path
import mishare_plan_preview_fixture as previous
from mishare_recovery_fixture import function
ROOT=previous.ROOT
COMMIT=r'''
static void commit_observe(struct mishare_runtime_owner *o,u32 freq,unsigned origin) {
 if(!commit_enabled)return;
 struct mishare_start_preview_status before=state(o).start_preview;
 unsigned posts=pe_posts,builds=plan_builds;
 int expected=state(o).quiesced?-ESHUTDOWN:before.result;
 for(unsigned repeat=0;repeat<3;repeat++) {
  assert(mishare_runtime_start_plan_commit(o,freq)==expected && pe_posts==posts && plan_builds==builds &&
   "EXPECTED_PLAN_COMMIT_NO_REPLAY");
  if(!expected)assert(state(o).start_preview.committed &&
   state(o).ndi.start_plan_requested && state(o).ndi.start_plan_submitted &&
   state(o).ndi.start_plan_completed && state(o).ndi.start_plan_ready &&
   !state(o).ndi.start_plan_error && mishare_preview_summary_equal(&state(o).start_preview.summary,&state(o).ndi.start_plan) &&
   "EXPECTED_PLAN_COMMIT_EXACT_RECORD");
  else assert(!state(o).start_preview.committed && !state(o).ndi.start_plan_requested &&
   "EXPECTED_PLAN_COMMIT_ERROR_PRESERVED");
 }
 assert(!state(o).ndi.radio_requested && !o->radio &&
  mishare_runtime_ndi_start(o)==-EOPNOTSUPP && "EXPECTED_PLAN_COMMIT_RADIO_CLOSED");
 assert(!mishare_runtime_preview_retire_check(o) && "EXPECTED_PLAN_COMMIT_RETIRE_SHAPE");
 (void)origin;
}
'''
FAULTS=r'''
static void commit_fault_cases(void) {
 for(unsigned fault=0;fault<12;fault++) {
  pid_t child=fork();assert(child>=0);if(!child) {
   reset_pe_test();commit_enabled=false;
   struct mishare_runtime_owner *o=retry_prepared_ready(5240,5,3,0,false,false);
   assert(mishare_runtime_start_plan_commit((void*)1,5240)==-ENOENT &&
    mishare_runtime_start_plan_commit(NULL,5240)==-EINVAL &&
    mishare_runtime_start_plan_commit(o,0)==-EINVAL && "EXPECTED_PLAN_COMMIT_IDENTITY");
   if(fault==0){assert(mishare_runtime_start_plan_commit(o,5240)==-EINPROGRESS &&
    !state(o).start_preview.committed && !state(o).ndi.start_plan_requested && "EXPECTED_PLAN_COMMIT_NO_PREVIEW");_Exit(0);}
   if(fault==1){assert(mishare_runtime_start_preview(o,5240)==-EINPROGRESS &&
    mishare_runtime_start_plan_commit(o,5240)==-EINPROGRESS && !state(o).ndi.start_plan_requested &&
    "EXPECTED_PLAN_COMMIT_PENDING");_Exit(0);}
   preview_exercise(o,5240,0,false);
   int expected=-EUCLEAN;
   if(fault==2){expected=-EBUSY;assert(mishare_runtime_start_plan_commit(o,5180)==expected &&
    !state(o).start_preview.committed && !state(o).ndi.start_plan_requested && "EXPECTED_PLAN_COMMIT_FROZEN_FREQ");_Exit(0);}
   if(fault==3){assert(!mishare_runtime_start_plan_commit(o,5240));o->state.ndi.start_plan.dtim_period++;}
   if(fault==4)o->state.ndi.start_plan_requested=true;
   if(fault==5)o->state.rate.accepted=false;
   if(fault==6)o->state.retry.receipt.submitted_mask^=1;
   if(fault==7)o->state.bssid.applied=false;
   if(fault==8){mark_closed(o);expected=-ESHUTDOWN;}
   if(fault==9){o->referenced=false;expected=-EBUSY;}
   if(fault==10){assert(!mishare_runtime_work_get(last_vdev,o));expected=-EINPROGRESS;}
   if(fault==11){assert(!mishare_runtime_start_plan_commit(o,5240));
    struct mishare_ndi_start_summary q=state(o).start_preview.summary;
    mishare_runtime_ndi_start_plan_event(&psoc,7,o,5240,0,&q);}
   assert(mishare_runtime_start_plan_commit(o,5240)==expected &&
    !state(o).ndi.radio_requested && !o->radio && !pe_deletes && !dp_detaches &&
    "EXPECTED_PLAN_COMMIT_REFUSAL");
   if(fault==3 || fault==11) {
    struct mishare_runtime_owner *held=o;
    assert(mishare_runtime_destroy(&held)==-EUCLEAN && held==o && !pe_deletes && !dp_detaches &&
     "EXPECTED_PLAN_COMMIT_CORRUPT_RETAIN");
   }
   _Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) &&
   "EXPECTED_PLAN_COMMIT_FAULT_CHILD");
 }
}
'''
def compose(source):
    needle='static struct mishare_runtime_owner *preview_owner;'
    assert source.count(needle)==1
    source=source.replace(needle,'static bool commit_enabled=true;\n'+needle,1)
    exercise=function(source,'preview_exercise')
    changed=exercise.replace(' preview_owner=NULL;', ' commit_observe(o,freq,origin);\n preview_owner=NULL;',1)
    assert changed!=exercise
    source=source.replace(exercise,COMMIT+changed,1)
    publish=function(source,'preview_publish')
    needle=' struct mishare_runtime_owner *o=token,*held=o;'
    changed=publish.replace(needle,needle+'\n assert(mishare_runtime_start_plan_commit(o,freq)==(state(o).quiesced?-ESHUTDOWN:-EINPROGRESS) &&\n  !state(o).start_preview.committed && !state(o).ndi.start_plan_requested && "EXPECTED_PLAN_COMMIT_PUBLISH_BARRIER");',1)
    assert changed!=publish
    return source.replace(publish,changed,1)

def reset_fixture(root):
    source=compose(previous.reset_fixture(root))
    main=previous.main_body(source)
    source=source.replace(main,FAULTS+'\nint main(void) {preview_reset_cases();commit_fault_cases();puts("MISHARE_RATE_RESET_FIXTURE_PASS_ONLY");return 0;}',1)
    return source

def ordinary_fixture(root):
    source,exits,stubbed=previous.ordinary_fixture(root)
    source=compose(source)
    # The old helper asserted absence of a plan. This extension now checks an
    # actual committed receipt while all native cleanup bodies stay unchanged.
    body=function(source,'prestart_clean_end')
    needle='!state(*o).ndi.start_plan_requested'
    assert body.count(needle)==1
    changed=body.replace(needle,'state(*o).start_preview.committed && state(*o).ndi.start_plan_ready',1)
    return source.replace(body,changed,1),exits,stubbed

def mutations(original):
    out=previous.mutations(original)
    def mutate(name,old,new):
        body=function(original,name);assert body.count(old)==1,old
        out.append(original.replace(body,body.replace(old,new,1),1))
    mutate('mishare_runtime_start_plan_commit','p->committed = true;','p->committed = false;')
    mutate('mishare_runtime_start_plan_commit','n->start_plan = p->summary;','(void)p;')
    mutate('mishare_runtime_start_plan_commit','n->start_plan_submitted = true;','n->start_plan_submitted = false;')
    mutate('mishare_runtime_start_plan_commit','!entry->state.rate.accepted ||','false ||')
    mutate('mishare_runtime_preview_retire_check','!mishare_preview_summary_equal(&p->summary, &entry->state.ndi.start_plan)','false')
    mutate('mishare_runtime_rate_ordinary_check','(n->start_plan_requested && !entry->state.start_preview.committed)','n->start_plan_requested')
    mutate('mishare_runtime_rate_reset_check','(n->start_plan_requested && !entry->state.start_preview.committed)','n->start_plan_requested')
    return out

def audit(root):
    r=previous.reset.previous.previous.audit(root,fixture_builder=reset_fixture,additional_mutations=mutations,
       mutation_markers=('EXPECTED_PLAN_PREVIEW_','EXPECTED_PLAN_COMMIT_'))
    q=previous.ordinary.previous.ordinary.cleanup.engine.audit(root,fixture_builder=ordinary_fixture)
    return {'status':'MISHARE_CONFIGURED_PLAN_COMMIT_FIXTURE_PASS_ONLY','ssr_combinations':192,
      'ordinary_combinations':160,'commit_faults':12,'preview_faults':9,'new_commit_mutations':7,
      'ssr_report':r,'ordinary_report':q,
      'limitations':'Actual runtime registry and owned MC/native encoder receipt adopted atomically without replay, plus selected native ordinary/prepared SSR cleanup. Scheduling/ref/lock/DP/firmware execution primitives remain modeled. No new caller integration, active START/UP, late peer/tail SSR extension, public backend activation or phone/RF/Apple proof.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
