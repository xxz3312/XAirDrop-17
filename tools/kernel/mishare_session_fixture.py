#!/usr/bin/env python3
"""Actions-only owned MC PE request lifecycle with modeled native PE allocation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import mishare_context_fixture as ctx
from popsicle_backend_audit import PIN
ROOT=Path(__file__).resolve().parents[2]
API='qcacld-3.0/core/mac/src/pe/lim/lim_api.c'
SESSION='qcacld-3.0/core/mac/src/pe/lim/lim_session.c'
BASE={'qcacld-3.0/core/mac/inc/sir_api.h': '9fb44b38354e76b381684dd4c58a59b65512cba78b1b9a0e6f717cc814173534', 'qcacld-3.0/core/mac/src/pe/include/lim_global.h': '0bcd7f9f7c0a08ef2f882e838d0f24a05a73b222991529565e9bfebd55636256', 'qcacld-3.0/core/mac/src/pe/include/lim_session.h': 'dca4ab4eb5403f4e1c92e899eb05ffd26f283a799f99c8025414075b8a99765c', 'qcacld-3.0/core/mac/src/pe/lim/lim_session.c': 'c9f55bb5ffd34a6d1259c2a920efab9c2c2ee10bd7b7d005e58b5eda8bd958be', 'qcacld-3.0/core/mac/src/pe/lim/lim_api.c': 'a197a9fa7b615060d16a1c89319c0f023cef6adb8504e0533ff4449589310fb9'}

def source_guard(root):
    for name,h in BASE.items():
        s=(root/name).read_text()
        s=re.sub(r'\n/\* MISHARE_BEGIN:\w+ \*/\n.*?/\* MISHARE_END:\w+ \*/\n','',s,flags=re.S)
        if name==API:
            s=s.replace('#include "wlan_hdd_mishare_ndi.h"\n#include <linux/errno.h>\n#include "scheduler_api.h"\n','')
            s=s.rstrip()+'\n'
        if name.endswith('sir_api.h'):
            s=s.replace('\n\t/* Private host PE role; never a firmware VDEV type. */\n\teSIR_MISHARE_PAS_MODE,','')
        if name.endswith('lim_global.h'):
            s=s.replace('\teLIM_NDI_ROLE,\n\teLIM_MISHARE_PAS_ROLE','\teLIM_NDI_ROLE')
        if name.endswith('lim_session.h'):
            s=s.replace('\n\t/* Owned PE identity; zero for every ordinary session. */\n\tvoid *mishare_owner;','')
        if hashlib.sha256(s.encode()).hexdigest()!=h:
            raise ValueError('Ordinary native source changed outside PE additions: '+name)

STUBS=r'''
#define QDF_MAC_ADDR_SIZE 6
#define QDF_MODULE_ID_PE 4
#define QDF_MODULE_ID_HDD 5
#define QDF_MODULE_ID_TARGET_IF 6
#define WLAN_LEGACY_MAC_ID 4
#define QDF_DRIVER_TYPE_MFG 1
#define ANI_DRIVER_TYPE(m) ((m)->driver_type)
#define SIR_SAP_MAX_NUM_PEERS 32
#define eSIR_MISHARE_PAS_MODE 5
#define eLIM_MISHARE_PAS_ROLE 7
struct pe_session {bool valid;struct wlan_objmgr_vdev *vdev;void *mishare_owner;u8 bssId[6],self_mac_addr[6];int bssType,limSystemRole;};
struct mac_context {struct wlan_objmgr_psoc *psoc;int driver_type;struct {struct pe_session *gpSession;unsigned maxBssId,max_sta_of_pe_session;} lim;};
struct scheduler_msg {void *bodyptr;QDF_STATUS (*callback)(struct scheduler_msg*);QDF_STATUS (*flush_callback)(struct scheduler_msg*);};
static struct pe_session pe_slot;
static struct mac_context pe_mac;
static struct scheduler_msg pe_pending;
static bool pe_alloc_fail,pe_queue_fail,pe_early,pe_no_mac,pe_idxpool_fail,pe_create_fail;
static unsigned pe_request_allocs,pe_posts,pe_creates,pe_deletes;
static void *pe_request_ptr;
static void *qdf_mem_malloc(size_t n) {if(pe_alloc_fail)return NULL;assert(!pe_request_ptr);void *p=calloc(1,n);assert(p);pe_request_allocs++;pe_request_ptr=p;return p;}
static void pe_qdf_mem_free(void *p) {assert(p==pe_request_ptr && pe_request_allocs==1);pe_request_ptr=NULL;pe_request_allocs--;free(p);}
static int qdf_mem_cmp(const void *a,const void *b,size_t n) {return memcmp(a,b,n);}
static void sir_copy_mac_addr(u8 *d,const u8 *s) {memcpy(d,s,6);}
static struct mac_context *pe_cds_get_context(int id) {assert(id==4);return pe_no_mac?NULL:&pe_mac;}
#define cds_get_context pe_cds_get_context
static struct pe_session *pe_find_session_by_vdev_id(struct mac_context *m,u8 id) {assert(m==&pe_mac && id==7);return pe_slot.valid?&pe_slot:NULL;}
static struct pe_session *pe_find_session_by_bssid(struct mac_context *m,u8 *b,u8 *id) {assert(m==&pe_mac && b && id);return pe_slot.valid && !memcmp(pe_slot.bssId,b,6)?&pe_slot:NULL;}
static struct pe_session *pe_create_session(struct mac_context *m,u8 *bssid,u8 *id,unsigned count,int bssType,u8 vdev_id) {
 assert(!lock_depth && m==&pe_mac && id && count==32 && bssType==5 && vdev_id==7 && !pe_slot.valid);pe_creates++;
 if(pe_create_fail)return NULL;
 struct pe_session *session_ptr=&pe_slot;memset(session_ptr,0,sizeof(*session_ptr));
 assert(!wlan_objmgr_vdev_try_get_ref(last_vdev,4));session_ptr->vdev=last_vdev;session_ptr->bssType=bssType;memcpy(session_ptr->bssId,bssid,6);
 NATIVE_PE_IDENTITY
 if(pe_idxpool_fail) {
  NATIVE_PE_FAILED_REF
  session_ptr->valid=false;return NULL;
 }
 session_ptr->valid=true;return session_ptr;
}
static void pe_delete_session(struct mac_context *m,struct pe_session *s) {
 assert(!lock_depth && m==&pe_mac && s==&pe_slot && s->valid && s->vdev==last_vdev);pe_deletes++;
 struct wlan_objmgr_vdev *v=s->vdev;s->valid=false;s->vdev=NULL;wlan_objmgr_vdev_release_ref(v,4);
}
static QDF_STATUS scheduler_post_message(int from,int dest,int queue,struct scheduler_msg *msg) {
 assert(!lock_depth && from==5 && dest==4 && queue==6 && !pe_pending.bodyptr && msg->bodyptr && msg->callback && msg->flush_callback);pe_posts++;
 if(pe_queue_fail)return QDF_STATUS_E_FAILURE;
 pe_pending=*msg;
 if(pe_early) {struct scheduler_msg m=pe_pending;pe_pending.bodyptr=NULL;assert(!m.callback(&m) && !m.bodyptr && !pe_request_allocs);}
 return QDF_STATUS_SUCCESS;
}
#define qdf_mem_free pe_qdf_mem_free
NATIVE_PE_HELPERS
#undef qdf_mem_free
#undef cds_get_context
static void run_pe(bool flush) {
 struct scheduler_msg m=pe_pending;assert(m.bodyptr);pe_pending.bodyptr=NULL;
 assert(!(flush?m.flush_callback(&m):m.callback(&m)) && !m.bodyptr && !pe_request_allocs);
}
'''
HARNESS=r'''
static void reset_pe(void) {
 reset_context();assert(!pe_pending.bodyptr && !pe_request_allocs);
 memset(&pe_slot,0,sizeof(pe_slot));pe_mac=(struct mac_context){.psoc=&psoc,.lim={.gpSession=&pe_slot,.maxBssId=1,.max_sta_of_pe_session=32}};
 pe_alloc_fail=pe_queue_fail=pe_early=pe_no_mac=pe_idxpool_fail=pe_create_fail=false;
 pe_posts=pe_creates=pe_deletes=0;
}
static struct mishare_runtime_owner *prepared(void) {
 struct mishare_runtime_owner *o=NULL;assert(!create(&o) && !mishare_runtime_ndi_create(o,1,1) && !mishare_runtime_ndi_prepare(o));return o;
}
int main(void) {
 struct mishare_runtime_owner *o=NULL;
 assert(mishare_runtime_ndi_session(NULL)==-EINVAL);
 reset_pe();assert(!create(&o) && mishare_runtime_ndi_session(o)==-EBUSY && !pe_posts);assert(!mishare_runtime_destroy(&o));
 for(int fault=0;fault<6;fault++) {
  reset_pe();o=prepared();
  pe_alloc_fail=fault==0;pe_queue_fail=fault==1;
  if(fault==2)fail_ref_at=ref_calls+1;
  pe_create_fail=fault==3;pe_idxpool_fail=fault==4;
  int ret=mishare_runtime_ndi_session(o);
  if(fault<3)assert(ret<0 && ret!=-EINPROGRESS && !pe_pending.bodyptr);
  else {
   assert(ret==-EINPROGRESS && last_vdev->refs==5);
   assert(mishare_runtime_destroy(&o)==-EINPROGRESS && !ctx_delete_calls && !wire_deletes && !dp_detaches);
   run_pe(fault==5);
  }
  assert(state(o).ndi.pe_completed && !state(o).ndi.pe_ready && !state(o).ndi.blocked && last_vdev->refs==4 && !pe_slot.valid);
  assert(mishare_runtime_ndi_session(o)==-EBUSY);pe_alloc_fail=pe_queue_fail=false;context_end(&o);
 }
 reset_pe();o=prepared();assert(mishare_runtime_ndi_session(o)==-EINPROGRESS);
 struct wlan_objmgr_psoc wrong={9};
 mishare_runtime_ndi_pe_event(&wrong,7,o,true,1,0);mishare_runtime_ndi_pe_event(&psoc,8,o,true,1,0);mishare_runtime_ndi_pe_event(&psoc,7,(void*)1,true,1,0);
 assert(!state(o).ndi.pe_completed && !state(o).ndi.blocked);
 run_pe(false);assert(state(o).ndi.pe_ready && state(o).ndi.pe_submitted && pe_slot.mishare_owner==o && pe_creates==1 && last_vdev->refs==5);
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && pe_pending.bodyptr && !ctx_delete_calls && last_vdev->refs==6);
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && !ctx_delete_calls && !wire_deletes);
 run_pe(false);assert(state(o).ndi.pe_delete_completed && pe_deletes==1 && !pe_slot.valid && last_vdev->refs==4);
 context_end(&o);assert(!pe_request_allocs);
 /* MC may finish before scheduler_post returns; peer teardown still waits for
  * the serialized owner call to finish and a later destroy poll. */
 reset_pe();o=prepared();pe_early=true;
 assert(mishare_runtime_ndi_session(o)==-EINPROGRESS && state(o).ndi.pe_ready && state(o).ndi.pe_completed && !pe_pending.bodyptr);
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && state(o).ndi.pe_delete_submitted && state(o).ndi.pe_delete_completed && !ctx_delete_calls);
 context_end(&o);
 /* Existing foreign PE state is not adopted or destroyed. */
 reset_pe();o=prepared();pe_slot.valid=true;pe_slot.vdev=(void*)1;pe_slot.mishare_owner=(void*)2;
 assert(mishare_runtime_ndi_session(o)==-EINPROGRESS);run_pe(false);
 assert(state(o).ndi.pe_error==-EEXIST && !state(o).ndi.pe_ready && !pe_creates && !pe_deletes && pe_slot.vdev==(void*)1);
 context_end(&o);assert(pe_slot.valid && !pe_deletes);pe_slot.valid=false;
 for(int fault=0;fault<9;fault++) {
  reset_pe();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=prepared();
   assert(mishare_runtime_ndi_session(o)==-EINPROGRESS);run_pe(false);
   if(fault==0)pe_queue_fail=true;
   if(fault==1)pe_slot.mishare_owner=(void*)1;
   if(fault==2)pe_slot.bssType=0;
   if(fault==3)pe_slot.limSystemRole=0;
   if(fault==4)pe_slot.valid=false;
   if(fault==5)pe_no_mac=true;
   if(fault==6)pe_slot.bssId[0]^=2;
   if(fault==7)mishare_runtime_ndi_pe_event(&psoc,7,o,true,1,0); /* duplicate */
   int ret=mishare_runtime_destroy(&o);
   if(fault==0 || fault==7)assert(ret==-EUCLEAN);
   else {assert(ret==-EINPROGRESS && pe_pending.bodyptr);run_pe(fault==8);}
   assert(mishare_runtime_destroy(&o)==-EUCLEAN && o && !ctx_delete_calls && !wire_deletes && !dp_detaches && !delete_calls && last_vdev->refs==5 && !pe_deletes);
   _Exit(0); /* quarantine intentionally retains live PE/native resources */
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 puts("MISHARE_OWNED_PE_SESSION_FIXTURE_PASS_ONLY");
}
'''

def fixture(root):
    source_guard(root)
    native=ctx.block((root/API).read_text(),'pe_helpers')
    session=(root/SESSION).read_text()
    stubs=STUBS.replace('NATIVE_PE_HELPERS',native).replace('NATIVE_PE_IDENTITY',ctx.block(session,'pe_identity')).replace('NATIVE_PE_FAILED_REF',ctx.block(session,'pe_failed_ref'))
    src=ctx.fixture(root)
    # MAC ID is a separately modeled native reference class, not HDD/WMA.
    src=src.replace('(id==1 || id==3)','(id==1 || id==3 || id==4)').replace('(id==1 || id==2 || id==3)','(id==1 || id==2 || id==3 || id==4)')
    start=src.index('/* PE_TRANSPORT_STUBS */');end=src.index('/* END_PE_TRANSPORT_STUBS */',start)+len('/* END_PE_TRANSPORT_STUBS */')
    src=src[:start]+stubs+src[end:]
    return src[:src.index('int main(void) {')]+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('Unexpected revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_osif_priv.h','qdf_status.h']:(d/n).write_text('/* platform model */\n')
        (d/'owner.c').write_text(source);exe=d/'owner'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),str(d/'owner.c'),'-o',str(exe)],check=True)
        out=subprocess.check_output([exe],text=True,timeout=30,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    if out.strip()!='MISHARE_OWNED_PE_SESSION_FIXTURE_PASS_ONLY':raise ValueError('Unexpected fixture output')
    return {'status':out.strip(),'source_commit':PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),'native_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in BASE},'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h']},'ordinary_native_sources_after_removing_additions_match':BASE,'checks':['queued MC request owns a distinct MAC VDEV ref and a flush callback','allocation/ref/queue rejection is before publication and releases local resources','owner waits for actual create/delete callback, not queue acceptance','owned constructor failure insertion releases MAC ref on idxpool failure','foreign PE session is not adopted/deleted','stable owner, PSOC, VDEV ID, session pointer, role and MAC identity checked','early callback is retained; teardown advances only after serialized post returns','PE deletion precedes peer/VDEV/DP teardown','delete queue/flush/context/identity failures and duplicate matching replies quarantine'], 'limitations':'Actual production owner plus extracted native request/MC/flush/identity/failure-ref helpers execute under ASan/UBSan. Scheduler queue/primitives and full native pe_create_session/pe_delete_session are modeled boundaries; only their bounded owned insertions execute. Ordinary native source hashes are compared after removing those additions. No real MC scheduling/races, native PE allocator/destructor execution, firmware, START/STOP/channel, TX/RX, SSR/remove or runtime backend caller is certified.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
