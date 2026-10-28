#!/usr/bin/env python3
"""Actions-only explicit SSR batch recovery; no automatic parent coordinator."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import mishare_parent_fixture as parent
ROOT=parent.ROOT
HARNESS=r'''
static void batch_fence(unsigned count) {
 assert(mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_SSR)==count);
 health_recovering=true;assert(!cds_post_disable());
}
static struct mishare_runtime_owner *batch_host(u8 suffix) {
 struct mishare_runtime_owner *o=NULL;u8 addr[6]={2,3,4,5,6,suffix};
 assert(!mishare_runtime_create(&pdev,addr,&pdev,&wdev,&o));return o;
}
int main(void) {
 struct mishare_runtime_reclaim_item items[2]={{NULL,77},{NULL,88}},before[2];
 struct mishare_runtime_owner *a,*b;struct wlan_objmgr_psoc other={9};
 reset_recovery();
 assert(mishare_runtime_reclaim_batch(NULL,items,2)==-EINVAL);
 assert(mishare_runtime_reclaim_batch(&psoc,NULL,1)==-EINVAL);
 assert(mishare_runtime_reclaim_batch(&psoc,(void*)1,MISHARE_RUNTIME_RECLAIM_BATCH_MAX+1)==-E2BIG);
 assert(!mishare_runtime_reclaim_batch(&psoc,NULL,0));
 struct mishare_runtime_reclaim_item empty[MISHARE_RUNTIME_RECLAIM_BATCH_MAX]={{0}};
 assert(!mishare_runtime_reclaim_batch(&psoc,empty,MISHARE_RUNTIME_RECLAIM_BATCH_MAX));
 /* Coverage/duplicate/foreign/stale checks leave authoritative slots untouched. */
 a=batch_host(7);struct wlan_objmgr_vdev *held=last_vdev;
 assert(!wlan_objmgr_vdev_try_get_ref(held,1));b=batch_host(8);
 items[0]=(struct mishare_runtime_reclaim_item){a,77};items[1]=(struct mishare_runtime_reclaim_item){b,88};
 memcpy(before,items,sizeof(items));
 assert(mishare_runtime_reclaim_batch(&psoc,NULL,0)==-EBUSY);
 assert(mishare_runtime_reclaim_batch(&psoc,items,1)==-EBUSY && !memcmp(before,items,sizeof(items)));
 items[1].owner=a;assert(mishare_runtime_reclaim_batch(&psoc,items,2)==-EEXIST && items[0].result==77 && items[1].result==88);items[1].owner=b;
 assert(mishare_runtime_reclaim_batch(&other,items,2)==-EXDEV && !memcmp(before,items,sizeof(items)));
 items[1].owner=(void*)1;assert(mishare_runtime_reclaim_batch(&psoc,items,2)==-ENOENT && items[1].owner==(void*)1 && items[1].result==88);items[1].owner=b;
 assert(mishare_runtime_reclaim_batch(&psoc,items,2)==-ESHUTDOWN && !memcmp(before,items,sizeof(items)) && !delete_calls);
 /* A real outstanding work reservation prevents every native reclaim action. */
 assert(!mishare_runtime_work_get(held,a));batch_fence(2);
 assert(mishare_runtime_reclaim_batch(&psoc,items,2)==-EINPROGRESS && !memcmp(before,items,sizeof(items)) && !delete_calls);
 mishare_runtime_work_put(held,a);
 assert(mishare_runtime_reclaim_batch(&psoc,items,2)==-EINPROGRESS && items[0].owner==a && !items[1].owner && items[0].result==-EINPROGRESS && !items[1].result);
 assert(objects_live==1 && state(a).draining && !state(a).freed);
 wlan_objmgr_vdev_release_ref(held,2);
 assert(!mishare_runtime_reclaim_batch(&psoc,items,2) && !items[0].owner && !items[0].result && !objects_live && !allocations);
 items[0].owner=a;assert(mishare_runtime_reclaim_batch(&psoc,items,2)==-ENOENT);items[0].owner=NULL;
 assert(!mishare_runtime_reclaim_batch(&psoc,items,2));
 /* Mixed early NDI + host, reordered table and inline/deferred DP completion. */
 for(int inline_cb=0;inline_cb<2;inline_cb++) {
  reset_recovery();a=early_ndi();b=batch_host(8);batch_fence(2);early_dp=inline_cb;
  items[0]=(struct mishare_runtime_reclaim_item){b,0};items[1]=(struct mishare_runtime_reclaim_item){a,0};
  assert(mishare_runtime_reclaim_batch(&psoc,items,2)==-EINPROGRESS && !items[0].owner && items[1].owner==a);
  assert(!items[0].result && items[1].result==-EINPROGRESS && !wire_deletes && dp_detaches==1 && !timers_live);
  if(!inline_cb) {assert(mishare_runtime_reclaim_batch(&psoc,items,2)==-EINPROGRESS);finish_dp();}
  assert(!mishare_runtime_reclaim_batch(&psoc,items,2) && !items[1].owner && !allocations && !objects_live && !dp_objects);
 }
 /* Prepared resources can coexist with a successfully reclaimed host. Error
  * is reported, never hidden by the later successful slot or partial cleanup. */
 reset_recovery();pid_t child=fork();assert(child>=0);
 if(!child) {
  a=prepared();b=batch_host(8);batch_fence(2);
  items[0]=(struct mishare_runtime_reclaim_item){a,0};items[1]=(struct mishare_runtime_reclaim_item){b,0};
  assert(mishare_runtime_reclaim_batch(&psoc,items,2)==-EUCLEAN && items[0].owner==a && !items[1].owner && items[0].result==-EUCLEAN && !items[1].result);
  assert(!dp_detaches && !wire_deletes && state(a).ndi.wma_bound && state(a).ndi.peer_created);
  assert(mishare_runtime_reclaim_batch(&psoc,items,2)==-EUCLEAN && objects_live==1);_Exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 /* Sticky accounting/reclaim errors and non-SSR first reason fail preflight. */
 for(int fault=0;fault<4;fault++) {
  reset_recovery();child=fork();assert(child>=0);
  if(!child) {
   a=batch_host(7);batch_fence(1);
   if(fault==0)a->state.work_error=-EIO;
   if(fault==1)a->state.reclaim_error=-EIO;
   if(fault==2)a->state.recovery_error=-EIO;
   if(fault==3)a->state.quiesced=MISHARE_QUIESCE_REMOVE;
   items[0]=(struct mishare_runtime_reclaim_item){a,77};
   assert(mishare_runtime_reclaim_batch(&psoc,items,1)==(fault==3?-ESHUTDOWN:-EUCLEAN));
   assert(items[0].owner==a && items[0].result==77 && !delete_calls && !dp_detaches);_Exit(0);
  }
  assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 /* Closing a native parent window between polls cannot be bypassed by batch. */
 reset_recovery();child=fork();assert(child>=0);
 if(!child) {
  a=early_ndi();batch_fence(1);items[0]=(struct mishare_runtime_reclaim_item){a,0};
  assert(mishare_runtime_reclaim_batch(&psoc,items,1)==-EINPROGRESS);
  native_recovery_close();finish_dp();
  assert(mishare_runtime_reclaim_batch(&psoc,items,1)==-ESHUTDOWN && items[0].result==-ESHUTDOWN && items[0].owner==a && !delete_calls);_Exit(0);
 }
 assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 reset_recovery();assert(!mishare_runtime_reclaim_batch(&psoc,NULL,0));
 puts("MISHARE_SSR_BATCH_RECLAIM_FIXTURE_PASS_ONLY");return 0;
}
'''


def fixture(root):
    src=parent.fixture(root)
    replacements={
        'int mode,refs,dead,vdev_lock;':'int mode,refs,dead,vdev_lock;u8 batch_id;',
        '(void)v;return 7;':'return v->batch_id;',
        'static struct wlan_objmgr_vdev *last_vdev;':'static struct wlan_objmgr_vdev *last_vdev;\nstatic struct wlan_objmgr_vdev *batch_vdevs[64];',
        'last_vdev=v;objects_live++;':'last_vdev=v;objects_live++;assert(object_calls<=64);batch_vdevs[object_calls-1]=v;v->batch_id=(u8)(object_calls+6);',
        'if(p==last_vdev){objects_live--;final_free_calls++;last_vdev=NULL;}':'for(unsigned i=0;i<64;i++){if(p==batch_vdevs[i]){objects_live--;final_free_calls++;batch_vdevs[i]=NULL;if(p==last_vdev)last_vdev=NULL;break;}}',
    }
    for old,new in replacements.items():
        if src.count(old)!=1:raise ValueError('Changed multi-vdev model boundary: '+old)
        src=src.replace(old,new,1)
    return src[:src.index('int main(void) {')]+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    pin=parent.recovery.work.shutdown.radio.plan.channel.pe.PIN
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=pin:raise ValueError('Unexpected revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:(d/n).write_text('/* platform model declarations */\n')
        (d/'batch.c').write_text(source);exe=d/'batch'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(d/'batch.c'),'-o',str(exe)],check=True)
        out=subprocess.check_output([exe],text=True,timeout=45,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    if out.strip()!='MISHARE_SSR_BATCH_RECLAIM_FIXTURE_PASS_ONLY':raise ValueError('Unexpected fixture output')
    return {'status':out.strip(),'source_commit':pin,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'native_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in parent.BASE},
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h']},
            'checks':['bounded opaque-token and exact-psoc validation before dereference','complete table coverage including pending physical final-free; duplicate/stale/foreign/missing entries do not mutate','SSR-first fence, sticky errors and owned MC reservations checked before every batch step','multiple distinct modeled VDEVs preserve their own object/event final-free identities','mixed host and early NDI release with reordered slots and inline/delayed DP callbacks','successful slots clear; pending/unsupported slots retain authoritative handles and individual results','earlier error is not hidden by later success; no fabricated native DELETE acknowledgment','parent-window revocation between polls remains effective; zero only after exact psoc registry empties'],
            'limitations':'Runs production batch/controller, existing native timer/DP wrapper and object-manager final-free under ASan/UBSan. Multi-vdev allocation/IDs, component/DP storage free, QDF scheduling and parent lifetimes are models. No automatic caller or outer HDD async pause is implemented. The caller must own all authoritative slots, retain exact parents and serialize every create/destroy/reclaim/teardown throughout polling. Preflight validates identity/coverage/accounting, not all native per-owner states; admitted steps may partially succeed and retain errors. Empty registry is an instant observation, not a lifetime lease, safe module unload or firmware proof. Prepared/STARTed recovery, psoc address reuse and phone operation remain unverified; backend stays disabled.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
