#!/usr/bin/env python3
"""Actions-only SSR bookkeeping after accepted ordinary host deletion."""
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path
import mishare_completion_fixture as completion
ROOT=completion.ROOT
HARNESS=r'''
static struct mishare_runtime_owner *ordinary_host_wait(int kind) {
 struct mishare_runtime_owner *o=NULL;defer_ref=1;
 if(kind==0)assert(!create(&o));
 else {
  o=kind==2?prepared():early_ndi();
  if(kind==2) {assert(mishare_runtime_destroy(&o)==-EINPROGRESS);ctx_fw_origin(ctx_pending);}
  normal_delete_reply(o);assert(mishare_runtime_destroy(&o)==-EINPROGRESS);finish_dp();
 }
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && o && state(o).host_delete_accepted);
 assert(!o->vdev && !o->referenced && !o->events && !state(o).ndi.active && last_vdev->refs==1);
 return o;
}
int main(void) {
 struct mishare_runtime_owner *o=NULL,*unknown=(void*)1;
 assert(mishare_runtime_reclaim_final(NULL)==-EINVAL && !mishare_runtime_reclaim_final(&o));
 assert(mishare_runtime_reclaim_final(&unknown)==-ENOENT && unknown==(void*)1);
 for(int kind=0;kind<3;kind++) {
  reset_recovery();o=ordinary_host_wait(kind);struct wlan_objmgr_vdev *held=last_vdev;
  assert(mishare_runtime_reclaim_final(&o)==-EUCLEAN && !state(o).freed);
  mark_closed(o);
  assert(mishare_runtime_reclaim_final(&o)==-EINPROGRESS); /* MC not observed */
  assert(!stop_mc());native_recovery_close();
  unsigned deletes=delete_calls,detaches=dp_detaches,wires_before=wire_deletes;
  struct mishare_runtime_reclaim_item item={o,77};
  assert(mishare_runtime_reclaim_batch(&psoc,&item,1)==-EINPROGRESS && item.owner==o && item.result==-EINPROGRESS);
  assert(state(o).recovery_window_closed && !state(o).freed && state(o).blocked && state(o).quiesced==MISHARE_QUIESCE_SSR);
  if(kind==2)assert(state(o).ndi.peer_create_attempted && state(o).ndi.peer_delete_replied && !state(o).ndi.legacy_ready && !state(o).ndi.wma_bound && !ctx_locks);
  void *old=o;wlan_objmgr_vdev_release_ref(held,2);
  assert(state(o).freed && !objects_live);
  if(kind==1) {assert(!mishare_runtime_reclaim_final(&o) && !o);}
  else {assert(!mishare_runtime_reclaim_batch(&psoc,&item,1) && !item.owner);o=NULL;}
  assert(!allocations && delete_calls==(int)deletes && dp_detaches==(int)detaches && wire_deletes==(int)wires_before);
  unknown=old;assert(mishare_runtime_reclaim_final(&unknown)==-ENOENT);
 }
 /* Incomplete provenance, active native handles, accounting, first reason,
  * component veto and late completion errors never authorize retirement. */
 for(int fault=0;fault<9;fault++) {
  reset_recovery();pid_t child=fork();assert(child>=0);
  if(!child) {
   if(fault==0) {assert(!create(&o));mark_closed(o);assert(!stop_mc());}
   else if(fault==1) {defer_ref=1;create_fault=2;assert(create(&o)==-EINPROGRESS);mark_closed(o);assert(!stop_mc());}
   else if(fault==2) {
    assert(!create(&o));leak_component=1;last_vdev->vdev_comp_priv_obj[1]=malloc(1);
    assert(last_vdev->vdev_comp_priv_obj[1] && mishare_runtime_destroy(&o)==-EUCLEAN);
    assert(state(o).host_delete_accepted && state(o).reclaim_error);mark_closed(o);assert(!stop_mc());
   } else {
    o=ordinary_host_wait(0);struct wlan_objmgr_vdev *held=last_vdev;
    mark_closed(o);assert(!stop_mc());
    if(fault==3)o->state.host_delete_accepted=false;
    if(fault==4)o->state.quiesced=MISHARE_QUIESCE_REMOVE;
    if(fault==5)o->state.work_error=-EIO;
    if(fault==6)o->state.recovery_error=-EIO;
    if(fault==7)mishare_runtime_ndi_dp_freed(o);
    if(fault==8)o->events=(void*)1; /* reject metadata without dereference */
    wlan_objmgr_vdev_release_ref(held,2);assert(state(o).freed);
   }
   unsigned deletes=delete_calls,detaches=dp_detaches;
   assert(mishare_runtime_reclaim_final(&o)==-EUCLEAN && o);
   assert(mishare_runtime_reclaim_final(&o)==-EUCLEAN && delete_calls==(int)deletes && dp_detaches==(int)detaches);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 reset_recovery();assert(!create(&o) && !mishare_runtime_destroy(&o));
 puts("MISHARE_HOST_FINAL_BOOKKEEPING_FIXTURE_PASS_ONLY");return 0;
}
'''


def fixture(root):
    src=completion.fixture(root)
    return src[:src.index('int main(void) {')]+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    pin=completion.parent.recovery.work.shutdown.radio.plan.channel.pe.PIN
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=pin:raise ValueError('Unexpected revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:(d/n).write_text('/* platform model declarations */\n')
        (d/'final.c').write_text(source);exe=d/'final'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(d/'final.c'),'-o',str(exe)],check=True)
        out=subprocess.check_output([exe],text=True,timeout=45,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    if out.strip()!='MISHARE_HOST_FINAL_BOOKKEEPING_FIXTURE_PASS_ONLY':raise ValueError('Unexpected fixture output')
    return {'status':out.strip(),'source_commit':pin,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'native_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in completion.parent.BASE},
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h']},
            'checks':['accepted host delete recorded only after logical delete and event/reference surrender','pure host, never-prepared NDI and already normally cleaned prepared context wait for actual final-free','direct and batch retirement after window closure perform no native cleanup or handle getters','unknown and freed opaque tokens compared before dereference','missing acceptance, active handles, constructor NULL provenance and component veto retain diagnosis','SSR first reason, MC drain and sticky completion/accounting/recovery errors required'],
            'limitations':'Executes production final-bookkeeping API/controller and native object-manager final-free under ASan/UBSan. VDEV/component allocation/destruction, QDF/DP/timer and parent lifetimes remain models. Prepared history is allowed only after ordinary WMA/peer/legacy cleanup already finished; this is not prepared/STARTed recovery. Caller must retain exact parents until actual VDEV final-free and serialize all owner/teardown calls. No native deletion or firmware operation is performed by the new API. Address reuse/ABA, module-text lifetime, automatic parent coordinator, safe active-owner unload and phone operation remain unverified; backend stays disabled.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
