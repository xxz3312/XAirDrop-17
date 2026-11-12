#!/usr/bin/env python3
"""Native CDS scheduling of raw DOWN observation; host boundary explicitly modeled."""
import argparse
import json
import subprocess
from pathlib import Path
import mishare_down_runtime_fixture as previous
from mishare_recovery_fixture import function
ROOT=previous.ROOT
CALLER=r'''
static struct mishare_runtime_owner *automatic_owner;
static unsigned automatic_calls;
static bool automatic_refuse,automatic_after;
static int automatic_observe(struct wlan_objmgr_psoc *p) {
 assert(p==&psoc && automatic_owner && state(automatic_owner).mc_drained &&
  recovery_isr_off && recovery_htc_off && recovery_rx_off &&
  !state(automatic_owner).recovery_window && automatic_owner->radio && timers_live &&
  !pe_deletes && !dp_detaches && "EXPECTED_DOWN_AUTO_NATIVE_ORDER");
 automatic_calls++;
 if(automatic_refuse && !automatic_after)return -EAGAIN;
 int r=mishare_runtime_fenced_down_prepare(automatic_owner);
 if(r)return r;
 return automatic_refuse?-EAGAIN:0;
}
static void automatic_refusal(bool after) {
 struct mishare_runtime_owner *o=down_runtime_ready(5240,0,false,false);
 automatic_owner=o;automatic_refuse=true;automatic_after=after;down_host_observer=automatic_observe;
 assert(!cds_post_disable() && automatic_calls==1 && !state(o).recovery_window &&
  state(o).recovery_down_observed==after && o->radio && timers_live && !pe_deletes &&
  !dp_detaches && "EXPECTED_DOWN_AUTO_REFUSAL");
 assert(mishare_runtime_reclaim_ndi(&o)==(after?-EINPROGRESS:-EUCLEAN) &&
  o->radio && timers_live && "EXPECTED_DOWN_AUTO_NO_CLEANUP");
}
'''
def fixture(root):
    source,exits,stubbed=previous.fixture(root)
    # Place the caller after the raw DOWN setup helper, before success harness.
    pos=source.index('static void down_runtime_success(')
    source=source[:pos]+CALLER+source[pos:]
    body=function(source,'down_runtime_success')
    a=body.index(' for(unsigned repeat=0;repeat<3;repeat++)')
    b=body.index(' assert(!cds_post_disable()',a)
    replacement=''' automatic_owner=o;down_host_observer=automatic_observe;
 assert(!mishare_runtime_recovery_candidates(&psoc) &&
  mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && timers_live &&
  "EXPECTED_DOWN_AUTO_NOT_ADOPTED_EARLY");
'''
    changed=body[:a]+replacement+body[b:]
    changed=changed.replace('assert(!cds_post_disable() && state(o).recovery_window &&',
      'assert(!cds_post_disable() && automatic_calls==1 && state(o).recovery_down_observed && state(o).recovery_window &&',1)
    source=source.replace(body,changed,1)
    main=function(source,'main')
    extra='''
 for(unsigned after=0;after<2;after++) {
  pid_t c=fork();assert(c>=0);if(!c){automatic_refusal(!!after);_Exit(0);}
  int s;assert(waitpid(c,&s,0)==c && WIFEXITED(s) && !WEXITSTATUS(s) && "EXPECTED_DOWN_AUTO_REFUSAL_CHILD");
 }
'''
    source=source.replace(main,main.replace(' down_runtime_cases();',extra+' down_runtime_cases();',1),1)
    return source,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
    body=function(source,'mishare_cds_recovery_window')
    needle='mishare_wonder_host_down_observe(wma->psoc) ||'
    assert body.count(needle)==1
    for replacement in ['false ||','(0 * mishare_wonder_host_down_observe(wma->psoc)) ||']:
        c_file.write_text(source.replace(body,body.replace(needle,replacement,1),1))
        subprocess.run(command,check=True)
        bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=60)
        assert bad.returncode==-6 and 'EXPECTED_DOWN_AUTO_' in bad.stderr,(bad.returncode,bad.stderr[-2000:])

def audit(root):
    r=previous.previous.previous.previous.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    r.update(status='MISHARE_DOWN_AUTO_CDS_FIXTURE_PASS_ONLY',automatic_combinations=64,
      native_observer_refusals=2,native_observer_mutations=2,
      limitations='Actual pinned CDS schedules observation after native stop and before candidate qualification; host registry boundary is explicitly modeled. Actual host C/identity/handoff/RTNL/runtime-call propagation is tested separately with a modeled runtime. No claim of full native host+radio composition, configured START, physical firmware/IRQ/DP primitives or phone/Apple proof.')
    return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
