#!/usr/bin/env python3
"""Actual host factory and native VDEV constructor through ordinary native close."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
import mishare_ordinary_host_close_fixture as previous
from mishare_recovery_fixture import function
ROOT=previous.ROOT
HOST='kernel/popsicle-hdd/wlan_hdd_mishare_host.c'
ADDED=['mishare_host_track','mishare_wonder_host_create_locked','mishare_wonder_host_vdev_create_locked']
PRIMITIVES=r'''
static struct mishare_wonder_host *factory_owner;
static void factory_meta_free(void *p,bool tracked) {
 assert(lock_depth==(tracked?1:0) && p==composite_host_storage && !mishare_hosts &&
  !terminal_device_pins && !terminal_psoc_pins && !terminal_pdev_pins && !terminal_sync &&
  !terminal_registered && !composite_adapter_storage && !objects_live && !allocations &&
  module_refs==1 && "EXPECTED_FACTORY_ROLLBACK_FREE");
 free(p);composite_host_storage=NULL;
}
static void *factory_meta_alloc(size_t n,int flags) {
 ASSERT_RTNL();assert(n==sizeof(struct mishare_wonder_host) && flags==GFP_KERNEL &&
  !composite_host_storage && module_refs==1 && "EXPECTED_FACTORY_MODULE_FIRST");
 if(factory_fault==4)return NULL;
 composite_host_storage=calloc(1,n);assert(composite_host_storage);return composite_host_storage;
}
static void factory_untracked_free(void *p) {factory_meta_free(p,false);}
static struct hdd_adapter *hdd_get_adapter(struct hdd_context *h,int mode) {
 ASSERT_RTNL();assert(h==&health && mode==QDF_PASSTHRU_MODE);
 return factory_fault==2?(void*)1:composite_adapter_storage;
}
static int osif_vdev_sync_create(struct device *d,struct osif_vdev_sync **slot) {
 ASSERT_RTNL();assert(d==&composite_device && slot && !*slot &&
  terminal_device_pins==1 && terminal_psoc_pins==1 && terminal_pdev_pins==1 &&
  "EXPECTED_FACTORY_PINS");
 assert(mishare_hosts==composite_host_storage && composite_host_storage->hdd==&health &&
  "EXPECTED_FACTORY_TRACKED");
 if(factory_fault==9)return -ENOMEM;
 terminal_sync=calloc(1,sizeof(*terminal_sync));assert(terminal_sync);*slot=terminal_sync;return 0;
}
static struct hdd_adapter *hdd_mishare_host_adapter_open(struct hdd_context *h,u8 *address) {
 ASSERT_RTNL();assert(h==&health && address && terminal_sync && !terminal_registered &&
  mishare_hosts==composite_host_storage && !composite_adapter_storage &&
  "EXPECTED_FACTORY_ADAPTER_ORDER");
 if(factory_fault==10)return NULL;
 composite_adapter_storage=calloc(1,sizeof(*composite_adapter_storage));assert(composite_adapter_storage);
 composite_adapter.dev=calloc(1,sizeof(*composite_adapter.dev));assert(composite_adapter.dev);
 composite_adapter.deflink=calloc(1,sizeof(*composite_adapter.deflink));assert(composite_adapter.deflink);
 composite_adapter.dev->ieee80211_ptr=&wdev;memcpy(composite_adapter.mac_addr.bytes,address,6);
 return composite_adapter_storage;
}
FACTORY_FUNCTIONS
static int factory_runtime_create(struct mishare_runtime_owner **out) {
 assert(out && !*out && !factory_owner && !mishare_hosts && !composite_rtnl &&
  "EXPECTED_FACTORY_FRESH_SCOPE");
 health.parent_dev=&composite_device;health.pdev=&pdev;
 composite_rtnl=true;factory_constructing=true;
 module_going=factory_fault==3;
 int r=mishare_wonder_host_create_locked(&health,mac,&factory_owner);
 factory_constructing=false;
 if(r){rtnl_unlock();return r;}
 assert(factory_owner==composite_host_storage && factory_owner==mishare_hosts &&
  factory_owner->adapter==composite_adapter_storage && factory_owner->sync==terminal_sync &&
  terminal_registered==terminal_sync && !factory_owner->runtime &&
  "EXPECTED_FACTORY_SLOT");
 if(factory_fault==11)fail_alloc_at=alloc_calls+1;
 if(factory_fault==12){create_fault=2;defer_ref=1;}
 if(factory_fault==14)factory_owner->session.closing=true;
 r=mishare_wonder_host_vdev_create_locked(factory_owner);*out=factory_owner->runtime;
 if(!factory_fault)assert(!r && *out && last_vdev &&
  last_vdev->osif.wdev==composite_adapter.dev->ieee80211_ptr &&
  last_vdev->osif.legacy_osif_priv==composite_adapter.deflink &&
  "EXPECTED_FACTORY_RUNTIME");
 rtnl_unlock();return r;
}
'''
FAULTS=r'''
static void factory_failure(unsigned fault) {
 reset_pe_test();factory_selected=true;factory_fault=fault;
 if(fault==13)health_recovering=true;
 struct mishare_runtime_owner *o=NULL;
 int r=factory_runtime_create(&o);
 if(fault<=10 || fault==13) {
  assert(r<0 && !o && !factory_owner && !mishare_hosts && !composite_host_storage &&
   !composite_adapter_storage && !terminal_sync && !terminal_registered &&
   !terminal_device_pins && !terminal_psoc_pins && !terminal_pdev_pins &&
   !module_refs && !objects_live && !allocations && !mishare_runtime_owners &&
   "EXPECTED_FACTORY_COMPLETE_ROLLBACK");return;
 }
 assert(factory_owner==composite_host_storage && factory_owner==mishare_hosts &&
  terminal_device_pins==1 && terminal_psoc_pins==1 && terminal_pdev_pins==1 &&
  terminal_sync && terminal_registered==terminal_sync && composite_adapter_storage &&
  "EXPECTED_FACTORY_RUNTIME_FAILURE_HOST_RETAINED");
 factory_bare_close=true;
 if(fault==12) {
  assert(r==-EINPROGRESS && o && factory_owner->runtime==o && objects_live==1 &&
   state(o).draining && !state(o).freed && module_refs==2 &&
   "EXPECTED_FACTORY_PARTIAL_NATIVE_OWNER");
  struct wlan_objmgr_vdev *held=last_vdev;composite_rtnl=true;
  assert(mishare_wonder_host_destroy_locked(&factory_owner)==-EINPROGRESS &&
   factory_owner==composite_host_storage && factory_owner->runtime==o &&
   !composite_closed && terminal_device_pins==1 && "EXPECTED_FACTORY_PARTIAL_WAIT");
  rtnl_unlock();wlan_objmgr_vdev_release_ref(held,2);
  assert(state(o).freed && !objects_live && "EXPECTED_FACTORY_REAL_FINAL_FREE");
 } else assert(r<0 && !o && !factory_owner->runtime && module_refs==1 &&
  "EXPECTED_FACTORY_EMPTY_NATIVE_FAILURE");
 composite_rtnl=true;
 assert(!mishare_wonder_host_destroy_locked(&factory_owner) && !factory_owner &&
  composite_closed && !mishare_hosts && !composite_host_storage && !composite_adapter_storage &&
  !terminal_sync && !terminal_registered && !terminal_device_pins && !terminal_psoc_pins &&
  !terminal_pdev_pins && !module_refs && !objects_live && !allocations &&
  "EXPECTED_FACTORY_FAILED_CONSTRUCTOR_RETIRED");
 rtnl_unlock();
}
static void factory_failures(void) {
 for(unsigned fault=1;fault<=14;fault++) {
  pid_t c=fork();assert(c>=0);if(!c){factory_failure(fault);_Exit(0);}
  int s;assert(waitpid(c,&s,0)==c && WIFEXITED(s) && !WEXITSTATUS(s) && "EXPECTED_FACTORY_FAILURE_CHILD");
 }
}
'''
def fixture(root):
    source,exits,stubbed=previous.fixture(root)
    def once(old,new):
        nonlocal source
        assert source.count(old)==1,old
        source=source.replace(old,new,1)
    once('static int create(struct mishare_runtime_owner **o) { return mishare_runtime_create(&pdev,mac,&pdev,&wdev,o); }',
      'static bool factory_selected,factory_constructing,factory_bare_close;\nstatic unsigned factory_fault;\nstatic void factory_meta_free(void *,bool);\nstatic int factory_runtime_create(struct mishare_runtime_owner **);\nstatic int create(struct mishare_runtime_owner **o) {return factory_selected?factory_runtime_create(o):mishare_runtime_create(&pdev,mac,&pdev,&wdev,o);}')
    once('struct net_device {bool running;};','struct net_device {bool running;struct wireless_dev *ieee80211_ptr;};')
    once('struct hdd_adapter {struct net_device *dev;struct link_info *deflink;unsigned long event_flags;};',
      'struct hdd_adapter {struct net_device *dev;struct link_info *deflink;unsigned long event_flags;struct {u8 bytes[6];} mac_addr;};')
    once('static struct device *get_device(struct device *d) {',
      'static struct device *get_device(struct device *d) {\n if(factory_constructing && factory_fault==5)return NULL;')
    for name,condition,ret in [('wlan_objmgr_psoc_try_get_ref','factory_fault==6','QDF_STATUS_E_FAILURE'),
                              ('terminal_pdev_get','factory_fault==7','QDF_STATUS_E_FAILURE')]:
        body=function(source,name);once(body,body.replace('{','{\n if(factory_constructing && '+condition+')return '+ret+';',1))
    once('static struct wlan_objmgr_psoc *terminal_pdev_psoc(struct wlan_objmgr_pdev *p) {return p->psoc;}',
      'static struct wlan_objmgr_psoc *terminal_pdev_psoc(struct wlan_objmgr_pdev *p) {return factory_constructing && factory_fault==8?&composite_foreign_psoc:p->psoc;}')
    for name,check,action in [
      ('terminal_pdev_put','terminal_pdev_pins==1 && terminal_psoc_pins==1 && terminal_device_pins==1','terminal_pdev_pins=0;'),
      ('wlan_objmgr_psoc_release_ref','!terminal_pdev_pins && terminal_psoc_pins==1 && terminal_device_pins==1','terminal_psoc_pins=0;'),
      ('put_device','!terminal_pdev_pins && !terminal_psoc_pins && terminal_device_pins==1','terminal_device_pins=0;')]:
        body=function(source,name);once(body,body.replace('{','{\n if(factory_constructing){assert('+check+' && "EXPECTED_FACTORY_PIN_ROLLBACK");'+action+'return;}',1))
    body=function(source,'osif_vdev_sync_destroy')
    once(body,body.replace('{','{\n if(factory_constructing){ASSERT_RTNL();assert(s==terminal_sync && !terminal_registered && !composite_adapter_storage && "EXPECTED_FACTORY_SYNC_ROLLBACK");free(s);terminal_sync=NULL;return;}',1))
    body=function(source,'osif_vdev_sync_register')
    once(body,body.replace('{','{\n if(factory_constructing){ASSERT_RTNL();assert(d==composite_adapter.dev && s==terminal_sync && !terminal_registered && mishare_hosts==composite_host_storage && "EXPECTED_FACTORY_REGISTER");terminal_registered=s;return;}',1))
    body=function(source,'terminal_metadata_free')
    once(body,body.replace('{','{\n if(factory_constructing){factory_meta_free(p,true);return;}',1))
    once('down_runtime_sm_frees==1 &&\n  composite_host_storage',
      '(down_runtime_sm_frees==1 || (factory_bare_close && !down_runtime_sm_frees && !engine_allocations)) &&\n  composite_host_storage')
    once('static int wlan_hdd_validate_context(struct hdd_context *h) {ASSERT_RTNL();assert(h==&health);return 0;}',
      'static int wlan_hdd_validate_context(struct hdd_context *h) {ASSERT_RTNL();assert(h==&health);return factory_constructing && factory_fault==1?-ENODEV:0;}')
    host=(ROOT/HOST).read_text()
    funcs=function(host,'mishare_host_track')+'\n#define kzalloc factory_meta_alloc\n#define kfree factory_untracked_free\n'+function(host,'mishare_wonder_host_create_locked')+'\n#undef kfree\n#undef kzalloc\n'+function(host,'mishare_wonder_host_vdev_create_locked')
    pos=source.index('static void composite_bind(')
    source=source[:pos]+PRIMITIVES.replace('FACTORY_FUNCTIONS',funcs)+source[pos:]
    body=function(source,'composite_bind')
    early='''
 if(factory_selected) {
  assert(factory_owner==composite_host_storage && mishare_hosts==factory_owner &&
   factory_owner->runtime==o && !factory_owner->idle_owned && "EXPECTED_FACTORY_HANDOFF_SOURCE");
  composite_rtnl=true;
  assert(!mishare_wonder_host_handoff_idle_locked(&factory_owner) && !factory_owner &&
   composite_host.runtime==o && composite_host.idle_owned && "EXPECTED_FACTORY_HANDOFF");
  rtnl_unlock();return;
 }
'''
    once(body,body.replace('{','{'+early,1))
    body=function(source,'ordinary_case');once(body,body.replace('{','{\n factory_selected=true;',1))
    main=function(source,'main');once(main,FAULTS+main.replace(' ordinary_cases();',' factory_failures();ordinary_cases();',1))
    return source,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
    for old,new,marker in [('*owner = host;','/* omit host slot publication */','EXPECTED_FACTORY_SLOT'),
       ('mishare_host_track(host, hdd);','/* omit registry publication */','EXPECTED_FACTORY_TRACKED'),
       ('ret = mishare_host_pin_parents(host, hdd);','ret = 0;','EXPECTED_FACTORY_PINS')]:
        body=function(source,'mishare_wonder_host_create_locked');assert body.count(old)==1,old
        c_file.write_text(source.replace(body,body.replace(old,new,1),1));subprocess.run(command,check=True)
        bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=60)
        assert bad.returncode==-6 and marker in bad.stderr,(marker,bad.returncode,bad.stderr[-1800:])

def audit(root):
    r=previous.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    host=(ROOT/HOST).read_text()
    r.update(status='MISHARE_FACTORY_NATIVE_FULL_LIFECYCLE_COMPOSITE_PASS_ONLY',combinations=256,
      constructor_faults=14,factory_mutations=3,
      factory_function_sha256={n:hashlib.sha256(function(host,n).encode()).hexdigest() for n in ADDED},
      limitations='Actual host factory/track/pin, actual host VDEV entry/native runtime constructor, raw native radio ordinary retirement and real host close execute together. Adapter open internals, sync/parent/module primitives, firmware delivery, DP peer unmap and object reference helpers remain models. Partial native constructor uses actual final-free notification and retained host ownership. No configured START/public init, phone/RF/Apple or kernel race certification.')
    return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
