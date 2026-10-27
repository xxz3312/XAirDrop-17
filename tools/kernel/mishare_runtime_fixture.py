#!/usr/bin/env python3
"""Actions-only host owner / event registry / native final-free boundary tests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from passthru_mode_fixture import function
from popsicle_backend_audit import PIN
ROOT=Path(__file__).resolve().parents[2]
OBJ='qca-wifi-host-cmn/umac/cmn_services/obj_mgr/src/wlan_objmgr_vdev_obj.c'
COMMON=r'''
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>
#include "wlan_hdd_mishare_runtime.h"
#include "wlan_hdd_mishare_events.h"
#define QDF_STATUS_SUCCESS 0
#define QDF_STATUS_E_FAILURE 1
#define QDF_STATUS_E_BUSY 2
#define QDF_STATUS_COMP_DISABLED 3
#define QDF_STATUS_E_INVAL 4
#define QDF_PASSTHRU_MODE 17
#define WLAN_HDD_ID_OBJ_MGR 1
#define WLAN_UMAC_MAX_COMPONENTS 4
#define WLAN_VDEV_MLME_TYPE_PASSTHRU 9
#define GFP_KERNEL 0
#define ETH_ALEN 6
#define WARN_ON(x) (x)
#define obj_mgr_err(...) ((void)0)
typedef int QDF_STATUS;
#define DEFINE_SPINLOCK(name) pthread_mutex_t name=PTHREAD_MUTEX_INITIALIZER
static _Thread_local int lock_depth;
#define spin_lock_irqsave(lock,flags) do { (flags)=0;assert(!lock_depth);assert(!pthread_mutex_lock(lock));lock_depth++; } while(0)
#define spin_unlock_irqrestore(lock,flags) do { (void)(flags);assert(lock_depth==1);lock_depth--;assert(!pthread_mutex_unlock(lock)); } while(0)
struct wlan_objmgr_psoc { int id; };
struct wlan_objmgr_pdev { struct wlan_objmgr_psoc *psoc; };
struct wireless_dev { int dummy; };
struct vdev_osif_priv { struct wireless_dev *wdev;void *legacy_osif_priv; };
struct vdev_mlme_obj { struct wlan_objmgr_vdev *vdev;void *ext_vdev_ptr;struct { struct { u8 type,subtype; } generic; } mgmt; };
struct wlan_objmgr_vdev {
 struct wlan_objmgr_pdev *pdev;u8 mac[6];int mode,refs,dead,vdev_lock;
 struct { void *bss_chan,*des_chan; } vdev_mlme;
 void *vdev_comp_priv_obj[4];QDF_STATUS obj_status[4];struct vdev_osif_priv osif;
 struct vdev_mlme_obj *mlme;
};
struct wlan_vdev_create_params { int opmode;size_t size_vdev_priv;void *legacy_osif;u8 macaddr[6],mataddr[6],mldaddr[6];unsigned flags; };
static int allocations,alloc_calls,fail_alloc_at,create_fault,ref_calls,fail_ref_at;
static int object_calls,objects_live,delete_calls,delete_fail,defer_ref,leak_component,detach_fail;
static int final_free_calls,detach_calls;
static struct wlan_objmgr_vdev *last_vdev;
static void *kzalloc(size_t n,int flags) { (void)flags;assert(!lock_depth);alloc_calls++;if(alloc_calls==fail_alloc_at)return NULL;allocations++;return calloc(1,n); }
static void kfree(void *p) { assert(!lock_depth);if(p)allocations--;free(p); }
static bool is_valid_ether_addr(const u8 *a) { u8 any=0;for(int i=0;i<6;i++)any|=a[i];return any && !(a[0]&1); }
static bool ether_addr_equal(const u8 *a,const u8 *b) { return !memcmp(a,b,6); }
static void ether_addr_copy(u8 *a,const u8 *b) { memcpy(a,b,6); }
static struct wlan_objmgr_psoc *wlan_pdev_get_psoc(struct wlan_objmgr_pdev *p) { return p->psoc; }
static struct wlan_objmgr_pdev *wlan_vdev_get_pdev(struct wlan_objmgr_vdev *v) { return v->pdev; }
static struct wlan_objmgr_psoc *wlan_vdev_get_psoc(struct wlan_objmgr_vdev *v) { return v->pdev->psoc; }
static int wlan_vdev_mlme_get_opmode(struct wlan_objmgr_vdev *v) { return v->mode; }
static u8 wlan_vdev_get_id(struct wlan_objmgr_vdev *v) { (void)v;return 7; }
static u8 *wlan_vdev_mlme_get_macaddr(struct wlan_objmgr_vdev *v) { return v->mac; }
static struct vdev_mlme_obj *wlan_vdev_mlme_get_cmpt_obj(struct wlan_objmgr_vdev *v) { return v->mlme; }
static struct vdev_osif_priv *wlan_vdev_get_ospriv(struct wlan_objmgr_vdev *v) { return &v->osif; }
static void simulated_component_destroy(struct wlan_objmgr_vdev *v);
static int wlan_objmgr_vdev_try_get_ref(struct wlan_objmgr_vdev *v,int id) { assert(!lock_depth && id==1);ref_calls++;if(v->dead || ref_calls==fail_ref_at)return -1;v->refs++;return 0; }
static void wlan_objmgr_vdev_release_ref(struct wlan_objmgr_vdev *v,int id) { assert(!lock_depth && (id==1 || id==2) && v->refs>0);v->refs--;if(!v->refs){assert(v->dead);simulated_component_destroy(v);} }
static QDF_STATUS wlan_objmgr_vdev_obj_delete(struct wlan_objmgr_vdev *v) { assert(!lock_depth && v && !v->dead);delete_calls++;if(delete_fail)return QDF_STATUS_E_FAILURE;v->dead=1;assert(v->refs>0);v->refs--;if(!v->refs)simulated_component_destroy(v);return QDF_STATUS_SUCCESS; }
static struct wlan_objmgr_vdev *wlan_objmgr_vdev_obj_create(struct wlan_objmgr_pdev*,struct wlan_vdev_create_params*);
#include "wlan_hdd_mishare_txn.c"
#include "wlan_hdd_mishare_events.c"
#include "wlan_hdd_mishare_runtime.c"
/* Native final free is executed below; component teardown / parent list / lock
 * primitives are models. No component handler, native lock or scheduler runs. */
static QDF_STATUS wlan_objmgr_pdev_vdev_detach(struct wlan_objmgr_pdev *p,struct wlan_objmgr_vdev *v) { assert(p==v->pdev);detach_calls++;return detach_fail?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS; }
static QDF_STATUS wlan_objmgr_psoc_vdev_detach(struct wlan_objmgr_psoc *p,struct wlan_objmgr_vdev *v) { assert(p==v->pdev->psoc);detach_calls++;return QDF_STATUS_SUCCESS; }
static void wlan_objmgr_vdev_trace_del_ref_list(struct wlan_objmgr_vdev *v) { assert(v->refs==0); }
static void wlan_objmgr_vdev_trace_deinit_lock(struct wlan_objmgr_vdev *v) { assert(v->refs==0); }
static void qdf_spinlock_destroy(int *lock) { (void)lock;assert(!lock_depth); }
static void wlan_destroy_vdev_mlo_lock(struct wlan_objmgr_vdev *v) { assert(v->refs==0); }
static void qdf_mem_free(void *p) { assert(!lock_depth);if(p==last_vdev){objects_live--;final_free_calls++;last_vdev=NULL;}free(p); }
NATIVE_FREE
static void simulated_component_destroy(struct wlan_objmgr_vdev *v) {
 assert(!lock_depth && !v->refs && v->dead);
 if(v->mlme){free(v->mlme);v->mlme=NULL;v->vdev_comp_priv_obj[0]=NULL;}
 if(!leak_component && v->vdev_comp_priv_obj[1]){free(v->vdev_comp_priv_obj[1]);v->vdev_comp_priv_obj[1]=NULL;}
 (void)wlan_objmgr_vdev_obj_free(v);
}
static struct wlan_objmgr_vdev *wlan_objmgr_vdev_obj_create(struct wlan_objmgr_pdev *p,struct wlan_vdev_create_params *params) {
 assert(!lock_depth && params->opmode==17 && params->size_vdev_priv==sizeof(struct vdev_osif_priv));
 assert(!params->flags && !memcmp(params->mldaddr,(u8[6]){0},6) && !memcmp(params->mataddr,(u8[6]){0},6));
 object_calls++;if(create_fault==1)return NULL;
 struct wlan_objmgr_vdev *v=calloc(1,sizeof(*v));assert(v);last_vdev=v;objects_live++;
 v->pdev=p;v->mode=17;v->refs=1;memcpy(v->mac,params->macaddr,6);
 v->vdev_mlme.bss_chan=malloc(1);v->vdev_mlme.des_chan=malloc(1);assert(v->vdev_mlme.bss_chan && v->vdev_mlme.des_chan);
 v->osif.legacy_osif_priv=params->legacy_osif;
 ALLOCATION_HOOK
 assert(mishare_runtime_owners && mishare_runtime_owners->state.allocated);
 v->mlme=calloc(1,sizeof(*v->mlme));assert(v->mlme);v->mlme->vdev=v;v->mlme->mgmt.generic.type=9;
 v->vdev_comp_priv_obj[0]=v->mlme;
 if(defer_ref)v->refs++; /* A real reference that must drain after logical delete. */
 if(create_fault==2){assert(!wlan_objmgr_vdev_obj_delete(v));return NULL;}
 if(create_fault==3)v->mlme->mgmt.generic.type=2;
 if(create_fault==4){v->obj_status[1]=QDF_STATUS_E_INVAL;v->vdev_comp_priv_obj[1]=malloc(1);assert(v->vdev_comp_priv_obj[1]);}
 return v;
}
'''
HARNESS=r'''
static struct wlan_objmgr_psoc psoc={1};static struct wlan_objmgr_pdev pdev={&psoc};static struct wireless_dev wdev;
static const u8 mac[6]={2,3,4,5,6,7};
static void reset(void) {
 assert(!objects_live && !allocations && !mishare_runtime_owners && !mishare_event_owners);
 alloc_calls=fail_alloc_at=create_fault=ref_calls=fail_ref_at=object_calls=delete_calls=delete_fail=defer_ref=leak_component=detach_fail=0;
}
static int create(struct mishare_runtime_owner **o) { return mishare_runtime_create(&pdev,mac,&pdev,&wdev,o); }
static struct mishare_runtime_status state(struct mishare_runtime_owner *o) { struct mishare_runtime_status s;assert(!mishare_runtime_snapshot(o,&s));return s; }
int main(void) {
 struct mishare_runtime_owner *o=NULL,*other=NULL;
 assert(mishare_runtime_destroy(NULL)==-EINVAL && !mishare_runtime_destroy(&o));
 assert(mishare_runtime_create(NULL,mac,&pdev,&wdev,&o)==-EINVAL);
 assert(mishare_runtime_create(&pdev,NULL,&pdev,&wdev,&o)==-EINVAL);
 assert(mishare_runtime_create(&pdev,mac,NULL,&wdev,&o)==-EINVAL);
 assert(mishare_runtime_create(&pdev,mac,&pdev,NULL,&o)==-EINVAL);
 assert(mishare_runtime_snapshot(NULL,NULL)==-EINVAL);
 reset();fail_alloc_at=1;assert(create(&o)==-ENOMEM && !o && !objects_live);
 reset();create_fault=1;assert(create(&o)==-EIO && !o && object_calls==1);
 reset();assert(!create(&o) && o && objects_live==1 && allocations==2 && last_vdev->refs==3);
 assert(last_vdev->osif.wdev==&wdev && last_vdev->osif.legacy_osif_priv==&pdev);
 assert(state(o).allocated && !state(o).freed && !state(o).draining && !state(o).blocked);
 assert(create(&o)==-EBUSY && create(&other)==-EEXIST && !other);
 mishare_runtime_freed(&psoc,1);assert(!state(o).freed);
 /* A recycled object address cannot stand in for the stable owner token. */
 mishare_runtime_freed(&psoc,(unsigned long)last_vdev);assert(!state(o).freed);
 assert(!mishare_runtime_destroy(&o) && !o && delete_calls==1 && !objects_live && !allocations);
 assert(!mishare_runtime_destroy(&o));
 /* Binding failure reverses both observer and owner references before free. */
 reset();fail_ref_at=1;assert(create(&o)==-EIO && !o && !objects_live && !allocations);
 reset();fail_ref_at=2;assert(create(&o)==-ENODEV && !o && !objects_live && !allocations);
 reset();fail_alloc_at=2;assert(create(&o)==-ENOMEM && !o && !objects_live && !allocations);
 reset();create_fault=3;assert(create(&o)==-EIO && !o && !objects_live && !allocations);
 /* Normal destruction cannot free the adapter while another ref remains. */
 reset();defer_ref=1;assert(!create(&o));struct wlan_objmgr_vdev *v=last_vdev;
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && o && allocations==1 && v->refs==1);
 assert(state(o).draining && !state(o).freed && !mishare_event_owners);
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && delete_calls==1);
 wlan_objmgr_vdev_release_ref(v,2);assert(!objects_live && state(o).freed);
 assert(!mishare_runtime_destroy(&o) && !o && !allocations);
 /* Constructor NULL can leave an asynchronously referenced partial object. */
 reset();create_fault=2;defer_ref=1;assert(create(&o)==-EINPROGRESS && o && objects_live==1);
 v=last_vdev;assert(v->refs==1 && state(o).create_error==-EIO && state(o).draining);
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && delete_calls==1);
 wlan_objmgr_vdev_release_ref(v,2);assert(state(o).freed && !objects_live);
 assert(!mishare_runtime_destroy(&o) && !allocations);
 /* Failed component aggregation must not free a still-attached private object.
  * The modeled native component drain/retry below is not a production reset API. */
 reset();create_fault=4;leak_component=1;int detaches=detach_calls;
 assert(create(&o)==-EUCLEAN && o && objects_live==1 && state(o).blocked && detach_calls==detaches);
 assert(mishare_runtime_destroy(&o)==-EUCLEAN && !state(o).freed);
 v=last_vdev;free(v->vdev_comp_priv_obj[1]);v->vdev_comp_priv_obj[1]=NULL;
 assert(wlan_objmgr_vdev_obj_free(v)==QDF_STATUS_SUCCESS && state(o).freed && !state(o).blocked);
 assert(!mishare_runtime_destroy(&o) && !allocations);
 /* Parent-detach failure retains the owner until actual final free completes. */
 reset();assert(!create(&o));detach_fail=1;
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && o && objects_live==1);
 detach_fail=0;assert(wlan_objmgr_vdev_obj_free(last_vdev)==QDF_STATUS_SUCCESS);
 assert(!mishare_runtime_destroy(&o) && !allocations);
 /* Unknown delete failure cannot justify dropping either owned reference.
  * Deliberate quarantine has no recovery API: isolate the retained resources
  * in a child and assert retention, rather than inventing refcount resets. */
 reset();pid_t child=fork();assert(child>=0);
 if(!child){assert(!create(&o));delete_fail=1;v=last_vdev;assert(mishare_runtime_destroy(&o)==-EUCLEAN && state(o).blocked && v->refs==3 && allocations==2 && objects_live==1);_Exit(0);}
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0);
 reset();assert(final_free_calls>0);
 puts("MISHARE_RUNTIME_HOST_OWNER_FIXTURE_PASS_ONLY");return 0;
}
'''


def fixture(root):
    text=(root/OBJ).read_text()
    before=subprocess.check_output(['git','-C',str(root),'show',f'{PIN}:{OBJ}'],text=True)
    # No other patch changes this core source. Verify the three exact origins.
    stripped=text.replace('#include "wlan_hdd_mishare_runtime.h"\n','')
    stripped=stripped.replace('\tunsigned long mishare_owner_token;\n\tbool mishare_passthru;\n','')
    for pattern in [r'\n\tmishare_passthru = .*?\n\t\treturn QDF_STATUS_E_BUSY;\n',
                    r'\t/\* Signal only after components, parent lists, locks and storage are gone\. \*/.*?mishare_runtime_freed\(psoc, mishare_owner_token\);\n\n',
                    r'\n\t/\* Capture failed/partial construction before any component can attach\. \*/\n\tmishare_runtime_allocated\(vdev\);\n']:
        stripped,count=re.subn(pattern,'',stripped,flags=re.S)
        if count!=1:raise ValueError('Object manager origin changed')
    if stripped!=before:raise ValueError('Unexpected object-manager edits outside ownership hooks')
    native=function(text,'wlan_objmgr_vdev_obj_free')
    if native.index('mishare_runtime_prepare_free')>native.index('wlan_objmgr_pdev_vdev_detach'):raise ValueError('Free veto after detach')
    if native.index('mishare_runtime_freed')<native.index('qdf_mem_free(vdev);'):raise ValueError('Completion before free')
    create=text[text.index('struct wlan_objmgr_vdev *wlan_objmgr_vdev_obj_create('):]
    if create.index('mishare_runtime_allocated')>create.index('/* Invoke registered create handlers */'):raise ValueError('Allocation observed too late')
    return COMMON.replace('NATIVE_FREE',native).replace('ALLOCATION_HOOK','mishare_runtime_allocated(vdev);'.replace('vdev','v'))+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('Native compilation runs only on Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('Unexpected source commit')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_osif_priv.h']:(d/n).write_text('/* boundary declarations */\n')
        p=d/'owner.c';p.write_text(source);exe=d/'owner'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),str(p),'-o',str(exe)],check=True)
        out=subprocess.check_output([exe],text=True,timeout=20,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
        if out.strip()!='MISHARE_RUNTIME_HOST_OWNER_FIXTURE_PASS_ONLY':raise ValueError('Unexpected test output')
    names=['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_events.c','wlan_hdd_mishare_events.h','wlan_hdd_mishare_txn.c','wlan_hdd_mishare_txn.h']
    return {'status':'MISHARE_RUNTIME_HOST_OWNER_FIXTURE_PASS_ONLY','source_commit':PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),'object_manager_sha256':hashlib.sha256((root/OBJ).read_bytes()).hexdigest(),'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in names},
      'checks':['native origin edits exclusively restored to pinned baseline','allocation observation before component dispatch','free veto before parent detach','completion strictly after native storage free','actual production owner/events/transaction C','owned and observer references unwind outside registry lock','constructor NULL before and after observation','duplicate owner and duplicate MAC rejection','reference/bind/allocation and MLME validation failures','nonblocking delayed-reference cleanup retains owner','failed attached component quarantines before free/ID detach','parent detach failure retains owner','unknown delete failure retains all references in isolated child'],
      'limitations':'Owner, event and transaction C plus complete native final-free function with object-manager creation/components/ref/synchronization/parent-detach stubs. No full object-manager/component construction or native locking/scheduler, actual recovery/drain, ID reuse, firmware, module load or radio certification. Quarantined child intentionally retains resources until process exit; modeled component/parent cleanup retry does not certify a production recovery API.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
