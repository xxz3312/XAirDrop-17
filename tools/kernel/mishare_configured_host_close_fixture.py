#!/usr/bin/env python3
"""Production host VDEV close -> configured STOP/DOWN -> native retirement."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import mishare_configured_radio_fixture as prior
from mishare_recovery_fixture import function
ROOT=prior.ROOT
MODEL=r'''
struct configured209_dev {bool running;};
struct configured209_link {unsigned long link_flags;};
struct configured209_adapter {
 struct configured209_dev *dev;struct configured209_link *deflink;unsigned long event_flags;
};
struct configured209_host {
 struct configured209_adapter *adapter;struct mishare_session session;
 struct mishare_runtime_owner *runtime;
};
static struct configured209_host *configured209_active;
static bool configured209_rtnl;
static int configured209_parent_error;
static int configured209_parent(struct configured209_host *h) {
 assert(configured209_rtnl && h==configured209_active && "EXPECTED_CONFIGHOST209_PARENT_SCOPE");
 return configured209_parent_error;
}
static bool configured209_running(struct configured209_dev *d) {return d->running;}
static bool configured209_bit(unsigned bit,const unsigned long *p) {return !!(*p&(1UL<<bit));}
#pragma push_macro("ASSERT_RTNL")
#pragma push_macro("mishare_wonder_host")
#pragma push_macro("mishare_wonder_host_vdev_destroy_locked")
#pragma push_macro("mishare_host_parent_identity")
#pragma push_macro("netif_running")
#pragma push_macro("test_bit")
#pragma push_macro("DEVICE_IFACE_OPENED")
#pragma push_macro("SME_SESSION_OPENED")
#undef ASSERT_RTNL
#undef mishare_wonder_host
#undef mishare_wonder_host_vdev_destroy_locked
#undef mishare_host_parent_identity
#undef netif_running
#undef test_bit
#undef DEVICE_IFACE_OPENED
#undef SME_SESSION_OPENED
#define ASSERT_RTNL() assert(configured209_rtnl)
#define mishare_wonder_host configured209_host
#define mishare_wonder_host_vdev_destroy_locked configured209_production_close
#define mishare_host_parent_identity configured209_parent
#define netif_running configured209_running
#define test_bit configured209_bit
#define DEVICE_IFACE_OPENED 1
#define SME_SESSION_OPENED 2
PRODUCTION_CLOSE
#pragma pop_macro("SME_SESSION_OPENED")
#pragma pop_macro("DEVICE_IFACE_OPENED")
#pragma pop_macro("test_bit")
#pragma pop_macro("netif_running")
#pragma pop_macro("mishare_host_parent_identity")
#pragma pop_macro("mishare_wonder_host_vdev_destroy_locked")
#pragma pop_macro("mishare_wonder_host")
#pragma pop_macro("ASSERT_RTNL")
static int configured209_close(struct mishare_runtime_owner **slot) {
 assert(slot && configured209_active && !configured209_rtnl &&
  *slot==configured209_active->runtime && "EXPECTED_CONFIGHOST209_OWNER_SLOT");
 configured209_rtnl=true;
 int ret=configured209_production_close(configured209_active);
 configured209_rtnl=false;
 *slot=configured209_active->runtime;
 return ret;
}
'''
TAIL=r'''
 struct configured209_dev netdev={0};struct configured209_link link={0};
 struct configured209_adapter adapter={.dev=&netdev,.deflink=&link};
 struct configured209_host host={.adapter=&adapter,.session=session,.runtime=o};
 configured209_active=&host;prestart_session=&host.session;configured209_parent_error=0;configured209_rtnl=false;
 assert(!mishare_runtime_configured_drain(NULL) &&
  mishare_runtime_configured_drain((void*)1)==-ENOENT &&
  !mishare_runtime_configured_drain(o) && !pe_pending.bodyptr && !radio_starts &&
  "EXPECTED_CONFIGHOST209_PREFIX_ONLY");
 if(guard) {
  int expected=guard==1||guard==5?-EUCLEAN:guard==6?-ESHUTDOWN:-EBUSY;
  if(guard==1)configured209_parent_error=-EUCLEAN;
  if(guard==2)netdev.running=true;
  if(guard==3)adapter.event_flags=1UL<<1;
  if(guard==4)link.link_flags=1UL<<2;
  if(guard==5)o->state.configured_radio.returned=true;
  if(guard==6) {
   assert(mishare_runtime_configured_start(o,freq)==-EINPROGRESS);
   mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_SSR);
  }
  assert(configured209_close(&o)==expected && o && host.runtime==o &&
   !pe_pending.bodyptr && !pe_deletes && !dp_detaches && !radio_stops &&
   "EXPECTED_CONFIGHOST209_GUARD_RETAIN");
  if(guard<5)assert(!host.session.closing && "EXPECTED_CONFIGHOST209_GUARD_BEFORE_CLOSE");
  else assert(host.session.closing && "EXPECTED_CONFIGHOST209_CLOSE_MONOTONIC");
  return;
 }
 radio_early_start=radio_early_stop=inline_rate;
 assert(mishare_runtime_configured_start(o,freq)==-EINPROGRESS);
 assert(configured209_close(&o)==-EINPROGRESS && o && host.session.closing &&
  !state(o).configured_radio.stop_requested && !state(o).radio.closing &&
  !pe_pending.bodyptr && !radio_stops && "EXPECTED_CONFIGHOST209_WAIT_START");
 radio_run(false);
 if(!inline_rate)assert(radio_reply_start(0)==QDF_STATUS_SUCCESS);
 radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_UP && radio_starts==1);
 assert(configured209_close(&o)==-EINPROGRESS && o && o->radio &&
  state(o).configured_radio.stop_requested && !pe_pending.bodyptr && !pe_deletes &&
  "EXPECTED_CONFIGHOST209_STOP_BEFORE_PE");
 assert(configured209_close(&o)==-EINPROGRESS && !pe_pending.bodyptr &&
  "EXPECTED_CONFIGHOST209_STOP_WORK_BARRIER");
 radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_WAIT_STOP && radio_stops==1 && !radio_downs &&
  configured209_close(&o)==-EINPROGRESS && !pe_pending.bodyptr &&
  "EXPECTED_CONFIGHOST209_STOP_ACK_BARRIER");
 if(!inline_rate)assert(radio_reply_stop()==QDF_STATUS_SUCCESS);
 radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_DOWN && state(o).radio.down_accepted);
 prestart_owner=NULL;prestart_control=NULL;prestart_session=NULL;
 clean_modes=mode;clean_fault=cleanup_fault;
 assert(configured209_close(&o)==-EINPROGRESS && o && host.runtime==o && !o->radio &&
  state(o).configured_radio.stopped && pe_pending.bodyptr &&
  "EXPECTED_CONFIGHOST209_PE_AFTER_DOWN");
 configured209_clean_end(&o);
 if(cleanup_fault)assert(o && host.runtime==o && host.session.closing &&
  "EXPECTED_CONFIGHOST209_FAILURE_RETAIN");
 else assert(!o && !host.runtime && host.session.closing &&
  !objects_live && !allocations && !module_refs && !engine_allocations && !dp_objects &&
  !stats_live && !timers_live && radio_starts==1 && radio_stops==1 && radio_downs==1 &&
  "EXPECTED_CONFIGHOST209_COMPLETE");
}
static void configured209_cases(void) {
 const u8 pairs[][2]={{0,0},{5,0},{0,3},{5,3}};
 for(unsigned band=0;band<2;band++)for(unsigned pair=0;pair<4;pair++)
 for(unsigned early=0;early<2;early++)for(unsigned mode=0;mode<32;mode++) {
  pid_t child=fork();assert(child>=0);if(!child) {
   retry_data=pairs[pair][0];retry_mgmt=pairs[pair][1];retry_failure=retry_fault=0;retry_inline=!!early;
   configured209_case(band?5240:2437,mode,!!early,0,0);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) &&
   "EXPECTED_CONFIGHOST209_CYCLE_CHILD");
 }
 for(unsigned guard=0;guard<=6;guard++)for(unsigned fault=0;fault<=6;fault++) {
  if((!guard && !fault) || (guard && fault))continue;
  pid_t child=fork();assert(child>=0);if(!child) {
   retry_data=5;retry_mgmt=3;retry_failure=retry_fault=0;retry_inline=false;
   configured209_case(5240,0,false,guard,fault);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) &&
   "EXPECTED_CONFIGHOST209_FAULT_CHILD");
 }
}
'''

def fixture(root):
    source,exits,stubbed=prior.fixture(root)
    host=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_host.c').read_text()
    close=function(host,'mishare_wonder_host_vdev_destroy_locked')
    clean=function(source,'configured208_clean_end').replace('configured208_clean_end(', 'configured209_clean_end(',1)
    clean=clean.replace('mishare_runtime_destroy(o)','configured209_close(o)')
    old=function(source,'configured208_case')
    prefix=old[:old.index(' struct mishare_runtime_status prepared=state(o);')]
    prefix=prefix.replace('static void configured208_case(unsigned freq,unsigned mode,bool inline_rate,unsigned admission,unsigned radio_fault,unsigned cleanup_fault)',
                          'static void configured209_case(unsigned freq,unsigned mode,bool inline_rate,unsigned guard,unsigned cleanup_fault)',1)
    assert 'configured209_case(' in prefix
    main=function(source,'main')
    addition=MODEL.replace('PRODUCTION_CLOSE',close,1)+'\n'+clean+'\n'+prefix+TAIL
    source=source.replace(main,main.replace('int main(void)','int previous_configured209_main(void)',1)+'\n'+addition+'''
int main(void) {
 configured209_cases();engine_contract();puts("MISHARE_PINNED_NATIVE_SM_ENGINE_FIXTURE_PASS_ONLY");return 0;
}
''',1)
    return source,exits,stubbed


def controls(directory,c_file,command,env,source,root):
    host=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_host.c').read_text()
    body=function(host,'mishare_wonder_host_vdev_destroy_locked')
    changed_sources=[]
    for old,new in [
        ('ret = mishare_runtime_configured_drain(host->runtime);','ret = 0;'),
        ('ret = mishare_host_parent_identity(host);','ret = 0 * mishare_host_parent_identity(host);'),
    ]:
        assert body.count(old)==1,old
        changed_sources.append(source.replace(body,body.replace(old,new,1),1))
    for changed in changed_sources:
        c_file.write_text(changed);subprocess.run(command,check=True)
        bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=90)
        assert bad.returncode==-6 and 'EXPECTED_CONFIGHOST209_' in bad.stderr,(bad.returncode,bad.stderr[-2500:])
    runtime=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_runtime.c').read_text()
    body=function(runtime,'mishare_runtime_configured_drain');old='ret = c->returned ||';assert body.count(old)==1
    override=directory/'wlan_hdd_mishare_runtime.c'
    try:
        override.write_text(runtime.replace(body,body.replace(old,'ret = false ||',1),1));c_file.write_text(source)
        subprocess.run(command,check=True)
        bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=90)
        assert bad.returncode==-6 and 'EXPECTED_CONFIGHOST209_' in bad.stderr,(bad.returncode,bad.stderr[-2500:])
    finally:override.unlink(missing_ok=True)


def audit(root):
    engine=prior.prior.previous.ordinary.previous.ordinary.cleanup.engine
    r=engine.audit(root,fixture_builder=fixture,extra_audit=controls)
    host=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_host.c').read_text()
    r.update(status='MISHARE_CONFIGURED_HOST_CLOSE_NATIVE_FIXTURE_PASS_ONLY',configured_host_cycles=512,
      parent_adapter_record_refusals=6,cleanup_faults=6,new_mutations=3,
      production_host_close_sha256=hashlib.sha256(function(host,'mishare_wonder_host_vdev_destroy_locked').encode()).hexdigest(),
      limitations='Exact production host VDEV-close body routes into actual runtime/controller/native SM and ordinary PE-peer-DELETE-DP cleanup. Host object, RTNL/parent identity and adapter flags are explicit model primitives here; complete host factory/adapter release remain separately regressed, not one configured end-to-end native factory proof. Firmware delivery, WMI execution, primitive refs/locks/unmap remain modeled. Public init, native parent/firmware lease coordination and active configured SSR/remove recovery stay closed; no phone RF or Apple proof.')
    return r

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
