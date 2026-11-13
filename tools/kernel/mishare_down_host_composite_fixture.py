#!/usr/bin/env python3
"""Actual host handoff/observer/batch and native raw-DOWN retirement composition."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
import mishare_down_runtime_fixture as previous
from mishare_recovery_fixture import function
ROOT=previous.ROOT
HOST='kernel/popsicle-hdd/wlan_hdd_mishare_host.c'
SELECTED=['mishare_host_parent_identity','mishare_wonder_host_handoff_idle_locked',
          'mishare_host_idle_candidate','mishare_wonder_host_down_observe',
          'mishare_wonder_host_reclaim_ssr_locked','mishare_wonder_host_reclaim_handoff_ssr_locked']
PLATFORM=r'''
#include <sched.h>
struct device {int id;};
struct net_device {bool running;};
struct link_info {unsigned long link_flags[1];};
struct hdd_adapter {struct net_device *dev;struct link_info *deflink;unsigned long event_flags;};
SESSION_TYPES
HOST_TYPE
static DEFINE_SPINLOCK(mishare_host_lock);
static struct mishare_wonder_host *mishare_hosts;
static struct mishare_wonder_host composite_host;
static struct device composite_device;
static struct wlan_objmgr_psoc composite_foreign_psoc;
static struct wlan_objmgr_pdev composite_foreign_pdev;
static struct net_device composite_netdev;
static struct link_info composite_link;
static struct hdd_adapter composite_adapter={&composite_netdev,&composite_link,0};
static bool composite_transition=true,composite_rtnl,composite_rtnl_busy;
static bool composite_allow_handoff=true,composite_closed;
static int composite_close_error;
#define DEVICE_IFACE_OPENED 1
#define SME_SESSION_OPENED 2
#define ASSERT_RTNL() assert(composite_transition && composite_rtnl && !lock_depth && "EXPECTED_COMPOSITE_RTNL")
static bool netif_running(struct net_device *d) {assert(d);return d->running;}
static bool test_bit(unsigned n,const unsigned long *bits) {return !!(*bits & (1UL<<n));}
static void osif_psoc_sync_assert_trans_protected(struct device *d) {
 assert(d==&composite_device && composite_transition && !lock_depth && "EXPECTED_COMPOSITE_PARENT");
}
static bool rtnl_trylock(void) {
 assert(composite_transition && !lock_depth && "EXPECTED_COMPOSITE_LOCK_ORDER");
 if(composite_rtnl_busy || composite_rtnl)return false;
 composite_rtnl=true;return true;
}
static void rtnl_unlock(void) {ASSERT_RTNL();composite_rtnl=false;}
static int wlan_hdd_validate_context(struct hdd_context *h) {ASSERT_RTNL();assert(h==&health);return 0;}
static int mishare_wonder_host_stop_ready_locked(struct hdd_context *h) {
 ASSERT_RTNL();assert(h==&health);
 return mishare_hosts || mishare_runtime_psoc_busy(h->psoc)?-EBUSY:0;
}
/* Physical HDD adapter/sync destruction is a named model. The actual host
 * caller may reach it only after the entire real runtime/native graph retired.
 * Full production adapter destructor has separate host fixture coverage. */
static int mishare_wonder_host_destroy_locked(struct mishare_wonder_host **slot) {
 ASSERT_RTNL();assert(slot && *slot==&composite_host && composite_host.idle_owned &&
  composite_host.session.closing && !composite_host.runtime && !mishare_runtime_owners &&
  !objects_live && !allocations && !timers_live && !pe_heap_live && !dp_objects &&
  !mishare_radios && !mishare_event_owners && down_runtime_sm_frees==1 &&
  "EXPECTED_COMPOSITE_HOST_LAST");
 if(composite_close_error)return composite_close_error;
 assert(mishare_hosts==&composite_host && !composite_host.next);
 mishare_hosts=NULL;*slot=NULL;composite_closed=true;return 0;
}
HOST_FUNCTIONS
static void composite_bind(struct mishare_runtime_owner *o) {
 assert(o && !health_recovering && !mishare_hosts && "EXPECTED_COMPOSITE_BIND");
 health.parent_dev=&composite_device;health.pdev=&pdev;
 composite_host=(struct mishare_wonder_host){.psoc=&psoc,.pdev=&pdev,
  .parent_dev=&composite_device,.hdd=&health,.adapter=&composite_adapter,.runtime=o};
 mishare_hosts=&composite_host;
 if(composite_allow_handoff) {
  composite_rtnl=true;struct mishare_wonder_host *caller=&composite_host;
  assert(!mishare_wonder_host_handoff_idle_locked(&caller) && !caller &&
   composite_host.idle_owned && composite_host.runtime==o && composite_host.session.closing &&
   "EXPECTED_COMPOSITE_HANDOFF");
  rtnl_unlock();
 }
}
static int composite_reclaim(struct mishare_runtime_owner **o) {
 assert(o && *o==composite_host.runtime && !composite_rtnl && !lock_depth &&
  "EXPECTED_COMPOSITE_AUTHORITATIVE_SLOT");
 composite_rtnl=true;
 int r=mishare_wonder_host_reclaim_handoff_ssr_locked(&health);
 if((r==-EINPROGRESS || r==-EUCLEAN || r==-ESHUTDOWN) && *o)assert(composite_host.runtime==*o && !composite_closed &&
  "EXPECTED_COMPOSITE_TOKEN_RESTORE");
 *o=composite_host.runtime; /* observation only; host slot drives all cleanup */
 rtnl_unlock();return r;
}
static void *composite_foreign_churn(void *unused) {
 (void)unused;
 for(unsigned n=0;n<2000;n++) {
  struct mishare_wonder_host *p=calloc(1,sizeof(*p));assert(p);p->psoc=&composite_foreign_psoc;
  unsigned long f;spin_lock_irqsave(&mishare_host_lock,f);
  p->next=mishare_hosts;mishare_hosts=p;
  spin_unlock_irqrestore(&mishare_host_lock,f);sched_yield();
  spin_lock_irqsave(&mishare_host_lock,f);
  struct mishare_wonder_host **link=&mishare_hosts;
  while(*link && *link!=p)link=&(*link)->next;
  assert(*link==p);*link=p->next;
  spin_unlock_irqrestore(&mishare_host_lock,f);free(p);
 }
 return NULL;
}
static void composite_observe_churn(void) {
 pthread_t worker;assert(!pthread_create(&worker,NULL,composite_foreign_churn,NULL));
 for(unsigned n=0;n<200;n++)assert(!mishare_wonder_host_down_observe(&psoc) &&
  state(composite_host.runtime).recovery_down_observed && !composite_rtnl &&
  "EXPECTED_COMPOSITE_FOREIGN_CHURN");
 assert(!pthread_join(worker,NULL) && mishare_hosts==&composite_host);
}
'''
FAULTS=r'''
static void composite_fault(unsigned fault) {
 if(fault==0)composite_allow_handoff=false;
 struct mishare_runtime_owner *o=down_runtime_ready(5240,0,false,false),*token=o;
 unsigned cancels=recovery_timer_cancels;
 if(fault==1)health.pdev=&composite_foreign_pdev;
 if(fault==2)composite_rtnl_busy=true;
 if(fault==3)composite_netdev.running=true;
 if(fault==4)composite_adapter.event_flags=1UL<<DEVICE_IFACE_OPENED;
 if(fault==5)composite_link.link_flags[0]=1UL<<SME_SESSION_OPENED;
 if(fault==6)composite_host.session.configured=true;
 if(fault==7)composite_host.prestart.selected=true;
 if(fault==8)o->state.rate.requested=true;
 if(fault==9)(void)mishare_radio_validate(last_vdev->mlme,0,NULL);
 if(fault==10)o->events->txn.serial=1;
 if(fault==11)o->state.work_pending=1;
 if(fault==12)o->state.work_error=-EIO;
 if(fault==13)recovery_bad_reset=true;
 assert(!cds_post_disable());
 if(fault<14) {
  assert(!state(o).recovery_window && state(o).recovery_down_observed==(fault==13) &&
   composite_host.runtime==token && o->radio && timers_live && !pe_deletes && !dp_detaches &&
   !composite_closed && !composite_rtnl && recovery_timer_cancels==cancels &&
   "EXPECTED_COMPOSITE_REFUSAL_RETAINS");return;
 }
 assert(state(o).recovery_window && state(o).recovery_down_observed);
 if(fault==14) {
  down_timer_fault=1;
  assert(composite_reclaim(&o)==-EUCLEAN && o==token && composite_host.runtime==token &&
   state(o).recovery_timer_released && !state(o).ndi.create.timer_ready &&
   o->radio && !pe_deletes && !dp_detaches && !composite_closed &&
   "EXPECTED_COMPOSITE_PARTIAL_TOKEN");
  unsigned after=recovery_timer_cancels;
  assert(composite_reclaim(&o)==-EUCLEAN && o==token && recovery_timer_cancels==after &&
   "EXPECTED_COMPOSITE_NO_RETRY");return;
 }
 assert(composite_reclaim(&o)==-EINPROGRESS && o==token);finish_dp();composite_close_error=-EIO;
 assert(composite_reclaim(&o)==-EIO && !o && !composite_host.runtime && !composite_closed &&
  mishare_hosts==&composite_host && !mishare_runtime_owners && !objects_live &&
  "EXPECTED_COMPOSITE_NATIVE_RETIRED_HOST_RETAINED");
 assert(composite_reclaim(&o)==-EIO && !o && !composite_closed &&
  "EXPECTED_COMPOSITE_CLOSE_FAILURE_RETAINED");
}
static void composite_faults(void) {
 for(unsigned fault=0;fault<16;fault++) {
  pid_t c=fork();assert(c>=0);if(!c){composite_fault(fault);_Exit(0);}
  int s;assert(waitpid(c,&s,0)==c && WIFEXITED(s) && !WEXITSTATUS(s) &&
   "EXPECTED_COMPOSITE_FAULT_CHILD");
 }
}
'''
def fixture(root):
    source,exits,stubbed=previous.fixture(root)
    stub='int mishare_wonder_host_down_observe(struct wlan_objmgr_psoc *p) {return down_host_observer?down_host_observer(p):0;}'
    assert source.count(stub)==1
    source=source.replace(stub,'int mishare_wonder_host_down_observe(struct wlan_objmgr_psoc *);',1)
    needle='static int (*down_host_observer)(struct wlan_objmgr_psoc *);'
    assert source.count(needle)==1
    source=source.replace(needle,'',1)
    old='struct hdd_context {struct wlan_objmgr_psoc *psoc;int driver_status;};'
    assert source.count(old)==1
    source=source.replace(old,old.replace('int driver_status;','int driver_status;struct device *parent_dev;struct wlan_objmgr_pdev *pdev;'),1)
    host=(ROOT/HOST).read_text()
    def decl(text,pattern):
        matches=re.findall(pattern,text,re.M|re.S);assert len(matches)==1,pattern;return matches[0]
    session=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_session.h').read_text()
    prestart=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_prestart.h').read_text()
    types='\n'.join([decl(session,r'^enum mishare_session_stage \{.*?^\};'),
       decl(session,r'^struct mishare_session \{.*?^\};'),decl(prestart,r'^struct mishare_prestart \{.*?^\};')])
    native='\n'.join(function(host,name) for name in SELECTED)
    platform=PLATFORM.replace('SESSION_TYPES',types).replace('HOST_TYPE',decl(host,r'^struct mishare_wonder_host \{.*?^\};')).replace('HOST_FUNCTIONS',native)
    pos=source.index('static struct mishare_runtime_owner *down_runtime_ready(')
    source=source[:pos]+platform+source[pos:]
    needle=' assert(mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_SSR)==1);'
    # Only the new composite raw setup helper is changed; old baseline helpers stay intact.
    ready=decl(source,r'^static struct mishare_runtime_owner \*down_runtime_ready\(.*?^\}')
    assert ready.count(needle)==1
    source=source.replace(ready,ready.replace(needle,' composite_bind(o);\n'+needle,1),1)
    body=function(source,'down_runtime_success')
    a=body.index(' for(unsigned repeat=0;repeat<3;repeat++)')
    b=body.index(' assert(!cds_post_disable()',a)
    replacement=''' assert(!mishare_runtime_recovery_candidates(&psoc) &&
  composite_reclaim(&o)==-EUCLEAN && composite_host.runtime==o &&
  "EXPECTED_COMPOSITE_NO_EARLY_WINDOW");
'''
    changed=body[:a]+replacement+body[b:]
    changed=changed.replace('mishare_runtime_reclaim_ndi(&o)','composite_reclaim(&o)').replace('mishare_runtime_reclaim_final(&o)','composite_reclaim(&o)')
    needle=' struct wlan_objmgr_vdev *held=last_vdev;'
    changed=changed.replace(needle,' if(freq==2437 && !initial && !early_start && !early_stop && !inline_dp && !held_ref)composite_observe_churn();\n'+needle,1)
    changed=changed.replace(' assert(!allocations &&',' assert(composite_closed && !mishare_hosts && !composite_host.runtime && "EXPECTED_COMPOSITE_HOST_RETIRED");\n assert(!allocations &&',1)
    source=source.replace(body,changed,1)
    main=function(source,'main')
    cases=function(source,'down_runtime_cases')
    # Keep the entire 64-way success matrix; its older isolated fault matrix
    # remains in the separate 0179 job. New failures exercise actual host slots.
    a=cases.index(' for(unsigned fault=0;fault<15;fault++)')
    source=source.replace(cases,cases[:a]+'}\n',1)
    source=source.replace(main,FAULTS+main.replace(' down_runtime_cases();',' composite_faults();down_runtime_cases();',1),1)
    return source,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
    controls=[]
    body=function(source,'mishare_wonder_host_handoff_idle_locked')
    controls.append((source.replace(body,body.replace('*owner = NULL;','/* omit caller-token invalidation */',1),1),'EXPECTED_COMPOSITE_HANDOFF'))
    body=function(source,'mishare_wonder_host_reclaim_ssr_locked')
    controls.append((source.replace(body,body.replace('host->runtime = item.owner;','/* omit authoritative token restore */',1),1),'EXPECTED_COMPOSITE_TOKEN_RESTORE'))
    body=function(source,'mishare_wonder_host_down_observe')
    changed=body.replace('if (host->idle_owned && host->runtime','if (true && host->runtime',1).replace('if (!host->idle_owned || !host->runtime ||','if (false || !host->runtime ||',1)
    assert changed!=body
    controls.append((source.replace(body,changed,1),'EXPECTED_COMPOSITE_REFUSAL_RETAINS'))
    for changed,marker in controls:
        c_file.write_text(changed);subprocess.run(command,check=True)
        bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=60)
        assert bad.returncode==-6 and marker in bad.stderr,(marker,bad.returncode,bad.stderr[-1800:])

def audit(root):
    r=previous.previous.previous.previous.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    host=(ROOT/HOST).read_text()
    r.update(status='MISHARE_DOWN_HOST_NATIVE_COMPOSITE_PASS_ONLY',combinations=64,host_faults=16,
      host_mutations=3,foreign_churn_publications=2000,foreign_churn_observations=200,
      actual_host_function_sha256={n:hashlib.sha256(function(host,n).encode()).hexdigest() for n in SELECTED},
      limitations='Actual production host handoff, parent identity, registry selection, DOWN observation, authoritative runtime slot/batch and handoff reclaim execute with actual runtime/native CDS/SM/WMA/retirement in one process. Factory/pins/PSOC transition/RTNL/adapter fields and terminal HDD adapter/sync destruction remain explicit models; no complete HDD factory/destructor, kernel synchronization, physical IRQ/firmware/DP primitives, configured START, phone/RF/Apple proof. Foreign list churn uses pthread registry model and ASan/UBSan, not kernel race certification.')
    return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
