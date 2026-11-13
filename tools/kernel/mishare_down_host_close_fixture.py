#!/usr/bin/env python3
"""Actual terminal host close/unpin/free composed with native raw-DOWN retirement."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
import mishare_down_host_composite_fixture as previous
from mishare_recovery_fixture import function
ROOT=previous.ROOT
ADDED=['mishare_host_pin_parents','mishare_host_unpin_parents',
       'mishare_host_free_tracked','mishare_wonder_host_destroy_locked']
PRIMITIVES=r'''
struct osif_vdev_sync {int id;};
static struct osif_vdev_sync *terminal_sync,*terminal_registered;
static struct osif_vdev_sync terminal_foreign_sync;
static unsigned terminal_device_pins,terminal_psoc_pins,terminal_pdev_pins,terminal_step;
static struct device *get_device(struct device *d) {
 assert(d==&composite_device && !terminal_device_pins && !lock_depth);terminal_device_pins++;return d;
}
static QDF_STATUS wlan_objmgr_psoc_try_get_ref(struct wlan_objmgr_psoc *p,int id) {
 assert(p==&psoc && id==WLAN_HDD_ID_OBJ_MGR && terminal_device_pins==1 && !terminal_psoc_pins);
 terminal_psoc_pins++;return QDF_STATUS_SUCCESS;
}
static QDF_STATUS terminal_pdev_get(struct wlan_objmgr_pdev *p,int id) {
 assert(p==&pdev && id==WLAN_HDD_ID_OBJ_MGR && terminal_psoc_pins==1 && !terminal_pdev_pins);
 terminal_pdev_pins++;return QDF_STATUS_SUCCESS;
}
static struct wlan_objmgr_psoc *terminal_pdev_psoc(struct wlan_objmgr_pdev *p) {return p->psoc;}
static void terminal_native_retired(void) {
 assert(!mishare_runtime_owners && !objects_live && !allocations && !timers_live && !pe_heap_live &&
  !dp_objects && !mishare_radios && !mishare_event_owners && down_runtime_sm_frees==1 &&
  composite_host_storage && !composite_host.runtime && module_refs==1 &&
  "EXPECTED_TERMINAL_RUNTIME_FIRST");
}
static struct osif_vdev_sync *osif_vdev_sync_unregister(struct net_device *d) {
 ASSERT_RTNL();terminal_native_retired();assert(d==composite_adapter.dev &&
  terminal_device_pins==1 && terminal_psoc_pins==1 && terminal_pdev_pins==1 && !terminal_step &&
  "EXPECTED_TERMINAL_UNREGISTER");
 struct osif_vdev_sync *s=terminal_registered;terminal_registered=NULL;
 if(composite_close_error)s=&terminal_foreign_sync;
 if(s==terminal_sync && composite_host.sync==terminal_sync)terminal_step=1;
 return s;
}
static void osif_vdev_sync_register(struct net_device *d,struct osif_vdev_sync *s) {
 ASSERT_RTNL();assert(d==composite_adapter.dev && s && !terminal_registered && !terminal_step &&
  "EXPECTED_TERMINAL_REGISTRY_RESTORE");terminal_registered=s;
}
static void osif_vdev_sync_wait_for_ops(struct osif_vdev_sync *s) {
 ASSERT_RTNL();terminal_native_retired();assert(s==terminal_sync && !terminal_registered &&
  terminal_step==1 && "EXPECTED_TERMINAL_WAIT_ORDER");terminal_step=2;
}
static void hdd_close_adapter(struct hdd_context *h,struct hdd_adapter *a,bool locked) {
 ASSERT_RTNL();terminal_native_retired();assert(h==&health && a==composite_adapter_storage && locked &&
  terminal_step==2 && terminal_device_pins==1 && terminal_psoc_pins==1 && terminal_pdev_pins==1 &&
  "EXPECTED_TERMINAL_CLOSE_ORDER");
 free(a->dev);free(a->deflink);free(a);composite_adapter_storage=NULL;terminal_step=3;
}
static void osif_vdev_sync_destroy(struct osif_vdev_sync *s) {
 ASSERT_RTNL();assert(s==terminal_sync && !terminal_registered && !composite_adapter_storage &&
  terminal_step==3 && "EXPECTED_TERMINAL_SYNC_LAST");free(s);terminal_sync=NULL;terminal_step=4;
}
static void terminal_pdev_put(struct wlan_objmgr_pdev *p,int id) {
 ASSERT_RTNL();assert(p==&pdev && id==WLAN_HDD_ID_OBJ_MGR && terminal_step==4 &&
  terminal_pdev_pins==1 && terminal_psoc_pins==1 && terminal_device_pins==1 &&
  "EXPECTED_TERMINAL_PIN_ORDER");terminal_pdev_pins=0;terminal_step=5;
}
static void wlan_objmgr_psoc_release_ref(struct wlan_objmgr_psoc *p,int id) {
 ASSERT_RTNL();assert(p==&psoc && id==WLAN_HDD_ID_OBJ_MGR && terminal_step==5 &&
  !terminal_pdev_pins && terminal_psoc_pins==1 && terminal_device_pins==1 &&
  "EXPECTED_TERMINAL_PIN_ORDER");terminal_psoc_pins=0;terminal_step=6;
}
static void put_device(struct device *d) {
 ASSERT_RTNL();assert(d==&composite_device && terminal_step==6 && !terminal_pdev_pins &&
  !terminal_psoc_pins && terminal_device_pins==1 && "EXPECTED_TERMINAL_PIN_ORDER");
 terminal_device_pins=0;terminal_step=7;
}
static void terminal_metadata_free(void *p) {
 assert(lock_depth==1 && p==composite_host_storage && !mishare_hosts && terminal_step==7 &&
  !terminal_device_pins && !terminal_psoc_pins && !terminal_pdev_pins &&
  !composite_adapter_storage && !terminal_sync && !terminal_registered && module_refs==1 &&
  "EXPECTED_TERMINAL_METADATA_LAST");
 free(p);composite_host_storage=NULL;composite_closed=true;terminal_step=8;
}
'''
EXTRA=r'''
static void terminal_registry_fault(unsigned kind) {
 struct mishare_runtime_owner *o=down_runtime_ready(5240,0,false,false);
 assert(!cds_post_disable() && state(o).recovery_window);
 assert(composite_reclaim(&o)==-EINPROGRESS);finish_dp();
 if(kind==0)terminal_registered=NULL;
 else composite_host.sync=&terminal_foreign_sync;
 assert(composite_reclaim(&o)==-EIO && !o && composite_host_storage && !composite_host.runtime &&
  composite_adapter_storage && terminal_sync && !composite_closed && !terminal_step &&
  terminal_device_pins==1 && terminal_psoc_pins==1 && terminal_pdev_pins==1 && module_refs==1 &&
  !objects_live && !mishare_runtime_owners &&
  terminal_registered==(kind?terminal_sync:NULL) && "EXPECTED_TERMINAL_MISMATCH_RETAIN");
 assert(composite_reclaim(&o)==-EIO && !terminal_step && composite_host_storage &&
  terminal_device_pins==1 && terminal_psoc_pins==1 && terminal_pdev_pins==1 &&
  "EXPECTED_TERMINAL_MISMATCH_REPEAT");
}
static void terminal_registry_faults(void) {
 for(unsigned kind=0;kind<2;kind++) {
  pid_t c=fork();assert(c>=0);if(!c){terminal_registry_fault(kind);_Exit(0);}
  int s;assert(waitpid(c,&s,0)==c && WIFEXITED(s) && !WEXITSTATUS(s) && "EXPECTED_TERMINAL_FAULT_CHILD");
 }
}
'''
def fixture(root):
    source,exits,stubbed=previous.fixture(root)
    host=(ROOT/previous.HOST).read_text()
    def once(old,new):
        nonlocal source
        assert source.count(old)==1,old
        source=source.replace(old,new,1)
    once('static struct mishare_wonder_host composite_host;',
         'static struct mishare_wonder_host *composite_host_storage;\n#define composite_host (*composite_host_storage)')
    once('static struct net_device composite_netdev;\nstatic struct link_info composite_link;\nstatic struct hdd_adapter composite_adapter={&composite_netdev,&composite_link,0};',
         'static struct hdd_adapter *composite_adapter_storage;\n#define composite_adapter (*composite_adapter_storage)\n#define composite_netdev (*composite_adapter.dev)\n#define composite_link (*composite_adapter.deflink)')
    modeled=function(source,'mishare_wonder_host_destroy_locked')
    pins='\n'.join(function(host,n) for n in ADDED[:2])
    # Route only these newly selected parent primitives to their independent
    # ledger; existing native WMA/PDEV primitive models are unchanged.
    pins='''#define wlan_objmgr_pdev_try_get_ref terminal_pdev_get
#define wlan_objmgr_pdev_release_ref terminal_pdev_put
#define wlan_pdev_get_psoc terminal_pdev_psoc
'''+pins+'''
#undef wlan_objmgr_pdev_try_get_ref
#undef wlan_objmgr_pdev_release_ref
#undef wlan_pdev_get_psoc
'''
    free='\n#define kfree terminal_metadata_free\n'+function(host,'mishare_host_free_tracked')+'\n#undef kfree\n'
    actual=PRIMITIVES+pins+free+'\nstatic int mishare_host_parent_identity(struct mishare_wonder_host *);\n'+function(host,'mishare_wonder_host_destroy_locked')
    once(modeled,actual)
    bind=function(source,'composite_bind')
    setup=''' assert(try_module_get(THIS_MODULE));
 composite_host_storage=calloc(1,sizeof(*composite_host_storage));assert(composite_host_storage);
 composite_adapter_storage=calloc(1,sizeof(*composite_adapter_storage));assert(composite_adapter_storage);
 composite_adapter.dev=calloc(1,sizeof(*composite_adapter.dev));assert(composite_adapter.dev);
 composite_adapter.deflink=calloc(1,sizeof(*composite_adapter.deflink));assert(composite_adapter.deflink);
 terminal_sync=calloc(1,sizeof(*terminal_sync));assert(terminal_sync);terminal_registered=terminal_sync;
'''
    changed=bind.replace(' composite_host=(struct mishare_wonder_host)',setup+' composite_host=(struct mishare_wonder_host)',1)
    changed=changed.replace(' mishare_hosts=&composite_host;',
      ' composite_host.sync=terminal_sync;assert(!mishare_host_pin_parents(&composite_host,&health));\n mishare_hosts=&composite_host;',1)
    once(bind,changed)
    once('*o=composite_host.runtime; /* observation only; host slot drives all cleanup */',
         '*o=composite_closed?NULL:composite_host.runtime; /* authoritative slot may now be physically freed */')
    once('assert(composite_closed && !mishare_hosts && !composite_host.runtime && "EXPECTED_COMPOSITE_HOST_RETIRED")',
         'assert(composite_closed && !mishare_hosts && !composite_host_storage && !composite_adapter_storage && !terminal_sync && !terminal_registered && !terminal_device_pins && !terminal_psoc_pins && !terminal_pdev_pins && !module_refs && terminal_step==8 && "EXPECTED_TERMINAL_COMPLETE")')
    fault=function(source,'composite_fault')
    changed=fault.replace('"EXPECTED_COMPOSITE_NATIVE_RETIRED_HOST_RETAINED");',
      '"EXPECTED_COMPOSITE_NATIVE_RETIRED_HOST_RETAINED");\n assert(terminal_registered==&terminal_foreign_sync && !terminal_step && terminal_device_pins==1 && terminal_psoc_pins==1 && terminal_pdev_pins==1 && module_refs==1 && "EXPECTED_TERMINAL_REGISTRY_RESTORE");',1)
    once(fault,changed)
    main=function(source,'main')
    once(main,EXTRA+main.replace(' composite_faults();',' terminal_registry_faults();composite_faults();',1))
    return source,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
    controls=[]
    def mutate(name,old,new,marker):
        body=function(source,name);assert body.count(old)==1,old
        controls.append((source.replace(body,body.replace(old,new,1),1),marker))
    mutate('mishare_wonder_host_destroy_locked','osif_vdev_sync_wait_for_ops(sync);','/* omit native sync drain */','EXPECTED_TERMINAL_CLOSE_ORDER')
    mutate('mishare_wonder_host_destroy_locked','osif_vdev_sync_destroy(sync);','/* omit sync release */','EXPECTED_TERMINAL_PIN_ORDER')
    mutate('mishare_wonder_host_destroy_locked','mishare_host_unpin_parents(host);','/* omit parent puts */','EXPECTED_TERMINAL_METADATA_LAST')
    mutate('mishare_wonder_host_destroy_locked','module_put(THIS_MODULE);','/* omit host module put */','EXPECTED_TERMINAL_COMPLETE')
    mutate('mishare_wonder_host_destroy_locked','osif_vdev_sync_register(adapter->dev, sync);','(void)sync;','EXPECTED_TERMINAL_MISMATCH_RETAIN')
    mutate('mishare_host_free_tracked','kfree(host);','(void)host;','EXPECTED_TERMINAL_COMPLETE')
    for changed,marker in controls:
        # Healthy matrix first for terminal-order controls; registry mismatch
        # remains first for its own precise restoration mutation assertion.
        if marker!='EXPECTED_TERMINAL_MISMATCH_RETAIN':
            main=function(changed,'main')
            changed=changed.replace(main,main.replace(' terminal_registry_faults();composite_faults();down_runtime_cases();',
              ' down_runtime_cases();terminal_registry_faults();composite_faults();',1),1)
        c_file.write_text(changed);subprocess.run(command,check=True)
        bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=60)
        assert bad.returncode==-6 and marker in bad.stderr,(marker,bad.returncode,bad.stderr[-1800:])

def audit(root):
    r=previous.previous.previous.previous.previous.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    host=(ROOT/previous.HOST).read_text()
    r.update(status='MISHARE_DOWN_REAL_HOST_CLOSE_COMPOSITE_PASS_ONLY',combinations=64,
      inherited_host_faults=16,new_terminal_faults=2,terminal_mutations=6,
      selected_host_function_sha256={n:hashlib.sha256(function(host,n).encode()).hexdigest() for n in previous.SELECTED+ADDED},
      limitations='Actual production host destroy, parent pin/unpin and tracked metadata retirement now execute with the previous actual host/runtime/native CDS/SM composition. Physical adapter/sync/reference/module APIs and initial factory construction are explicit models; heap adapter/netdev/link/sync/metadata are actually freed under ASan. No complete native HDD factory/adapter body, Linux loader/ref concurrency, hardware IRQ/firmware/DP primitives, configured START, phone/RF/Apple certification.')
    return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
