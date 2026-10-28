#!/usr/bin/env python3
"""Actions-only revocation before native DP and pdev parent teardown."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import mishare_recovery_fixture as recovery
from mishare_parent_origins import remove_parent_additions

ROOT = recovery.ROOT
CDS = recovery.CDS
MAIN = recovery.work.shutdown.MAIN
DISPATCHER = 'qca-wifi-host-cmn/init_deinit/dispatcher/src/dispatcher_init_deinit.c'
BASE = {
    CDS: '075238d340c3d3935ac702423d4418d86db428f03fc35278131c4ad980f83147',
    MAIN: 'f9817e1228dfec95551cdb18327e1a4b2b1602dc39f4a3384386d345dd98729d',
    DISPATCHER: 'f712d0c2f95ae6ccf30522885c6d9781ff431a519aaec0960076db4e968fe277',
}
MODELS = r'''
#define OL_TXRX_INVALID_PDEV_ID 255
static struct mishare_runtime_owner *parent_subject;
static unsigned parent_steps;
static void parent_revoked(void) {
 if(parent_subject) {
  assert(state(parent_subject).recovery_window_closed && !state(parent_subject).recovery_window);
  assert(mishare_runtime_reclaim_ndi(&parent_subject)==-ESHUTDOWN);
 }
 parent_steps++;
}
static void cdp_txrx_intr_detach(void *s) {assert(s==&psoc && parent_steps==0);parent_revoked();}
static void qdf_nbuf_stop_replenish_timer(void) {assert(parent_steps==1);parent_revoked();}
static void ucfg_dp_txrx_deinit(void *s) {assert(s==&psoc && parent_steps==2);parent_revoked();}
static void cdp_pdev_deinit(void *s,int id,int force) {assert(s==&psoc && !id && force==1 && parent_steps==3);parent_revoked();}
static void ucfg_dp_txrx_pdev_detach(void *s,int id,int force) {assert(s==&psoc && !id && force==1 && parent_steps==4);parent_revoked();}
static void ucfg_pmo_psoc_set_txrx_pdev_id(struct wlan_objmgr_psoc *p,int id) {assert(p==&psoc && id==255 && parent_steps==5);parent_revoked();}
#define cds_get_context recovery_get_context
NATIVE_DP_CLOSE
#undef cds_get_context
static void ucfg_mlme_pdev_close(struct wlan_objmgr_pdev *p) {assert(p==&pdev && parent_steps==0);parent_revoked();}
NATIVE_HDD_CLOSE
static QDF_STATUS parent_component_close(struct wlan_objmgr_pdev *p) {assert(p==&pdev);parent_revoked();return QDF_STATUS_SUCCESS;}
#define dispatcher_green_ap_pdev_close parent_component_close
#define wlan_mgmt_txrx_pdev_close parent_component_close
#define dispatcher_wifi_radar_pdev_close parent_component_close
#define dispatcher_cfr_pdev_close parent_component_close
#define dispatcher_spectral_pdev_close parent_component_close
#define dispatcher_regulatory_pdev_close parent_component_close
#undef QDF_BUG
#define QDF_BUG(x) assert(x)
NATIVE_DISPATCHER_CLOSE
static void close_parent(int route) {
 parent_steps=0;
 if(route==0) {assert(!cds_dp_close(&psoc) && parent_steps==6);}
 else if(route==1) {hdd_component_pdev_close(&pdev);assert(parent_steps==1);}
 else {assert(!dispatcher_pdev_close(&pdev) && parent_steps==6);}
}
'''
HARNESS = r'''
int main(void) {
 struct mishare_runtime_owner *o=NULL;
 for(int route=0;route<3;route++) {
  reset_recovery();recovery_cds.dp_soc=&psoc;parent_subject=NULL;
  close_parent(route); /* no owner: ordinary parent cleanup still executes */
  for(int phase=0;phase<4;phase++) {
   reset_recovery();pid_t child=fork();assert(child>=0);
   if(!child) {
    recovery_cds.dp_soc=&psoc;o=early_ndi();stop_recovery(o);
    if(phase==1 || phase==2) {
     early_dp=phase==2;assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);
     assert(state(o).recovery_dp_freed==(phase==2));
    }
    if(phase==3) {
     last_vdev->refs++; /* external ref, after successful create */
     assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);finish_dp();
     assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS && state(o).ndi_reclaim_ready && !o->vdev);
    }
    unsigned frees=recovery_timer_frees,detaches=dp_detaches,deletes=delete_calls;
    parent_subject=phase==3?NULL:o;close_parent(route);parent_subject=NULL;
    assert(state(o).recovery_window_closed && !state(o).recovery_window);
    if(phase==1)finish_dp();
    mishare_runtime_recovery_open(&psoc);assert(!state(o).recovery_window);
    if(phase!=3) {
     assert(mishare_runtime_reclaim_ndi(&o)==-ESHUTDOWN);
     assert(recovery_timer_frees==frees && dp_detaches==(int)detaches && delete_calls==(int)deletes);
     assert(o && !wire_deletes && !state(o).ndi.delete_replied);
    } else {
     /* Once physical final-free is all that remains, no parent handle is used. */
     wlan_objmgr_vdev_release_ref(last_vdev,2);
     assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations);
    }
    _Exit(0);
   }
   int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
  }
 }
 /* Exact psoc matching: a foreign teardown cannot revoke this owner. */
 reset_recovery();o=early_ndi();stop_recovery(o);
 struct wlan_objmgr_psoc other={0};mishare_runtime_recovery_close(&other);
 assert(state(o).recovery_window && !state(o).recovery_window_closed);
 assert(mishare_runtime_reclaim_ndi(&o)==-EINPROGRESS);finish_dp();
 assert(!mishare_runtime_reclaim_ndi(&o) && !o && !allocations);
 puts("MISHARE_PARENT_TEARDOWN_REVOKE_FIXTURE_PASS_ONLY");return 0;
}
'''


def fixture(root):
    for path, expected in BASE.items():
        if hashlib.sha256(remove_parent_additions((root/path).read_text()).encode()).hexdigest() != expected:
            raise ValueError('Unbounded parent teardown delta: '+path)
    cds=(root/CDS).read_text();main=(root/MAIN).read_text();dispatcher=(root/DISPATCHER).read_text()
    functions = {
        'NATIVE_DP_CLOSE': recovery.function(cds, 'cds_dp_close'),
        'NATIVE_HDD_CLOSE': recovery.function(main, 'hdd_component_pdev_close'),
        'NATIVE_DISPATCHER_CLOSE': recovery.function(dispatcher, 'dispatcher_pdev_close'),
    }
    for key, first in [('NATIVE_DP_CLOSE','cdp_txrx_intr_detach('),
                       ('NATIVE_HDD_CLOSE','ucfg_mlme_pdev_close('),
                       ('NATIVE_DISPATCHER_CLOSE','dispatcher_green_ap_pdev_close(')]:
        assert functions[key].index('mishare_runtime_recovery_close(')<functions[key].index(first)
    # Complete unchanged HDD stop/error functions establish both parent orderings.
    stop=recovery.function(main, 'hdd_wlan_stop_modules')
    start=recovery.function(main, 'hdd_wlan_start_modules')
    assert stop.index('cds_post_disable()')<stop.index('cds_dp_close(')<stop.index('hdd_component_pdev_close(')<stop.index('dispatcher_pdev_close(')<stop.index('hdd_objmgr_release_and_destroy_pdev(')<stop.index('cds_close(')
    unwind=start[start.index('sched_disable:'):]
    assert unwind.index('cds_post_disable()')<unwind.index('dispatcher_pdev_close(')<unwind.index('hdd_objmgr_release_and_destroy_pdev(')<unwind.index('cds_dp_close(')<unwind.index('cds_close(')
    src=recovery.fixture(root)
    needle='struct cds_context {void *htc_ctx;};';assert src.count(needle)==1
    src=src.replace(needle,'struct cds_context {void *htc_ctx,*dp_soc;};',1)
    model=MODELS
    for name, body in functions.items():model=model.replace(name,body)
    return src[:src.index('int main(void) {')]+model+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':
        raise ValueError('C compilation is restricted to GitHub Actions')
    pin=recovery.work.shutdown.radio.plan.channel.pe.PIN
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=pin:
        raise ValueError('Unexpected revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:
            (d/n).write_text('/* platform model declarations */\n')
        (d/'parent.c').write_text(source);exe=d/'parent'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(d/'parent.c'),'-o',str(exe)],check=True)
        out=subprocess.check_output([exe],text=True,timeout=45,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    if out.strip()!='MISHARE_PARENT_TEARDOWN_REVOKE_FIXTURE_PASS_ONLY':
        raise ValueError('Unexpected fixture output')
    return {'status':out.strip(),'source_commit':pin,
            'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'native_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in BASE},
            'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h']},
            'ordinary_before_parent_sha256':BASE,
            'checks':['complete native CDS DP close revokes before interrupt/timer/DP deinit and pdev detach',
                      'complete native HDD and dispatcher pdev close revoke before component cleanup',
                      'three routes reject not-started, pending-DP and inline-completed pre-host reclaim',
                      'late DP completion and recovery-open cannot reopen revoked admission',
                      'already-started host final-free may finish bookkeeping without parent handle access',
                      'foreign psoc close leaves exact owner window unchanged',
                      'no-owner native cleanup preserves original calls and success'],
            'limitations':'Executes production recovery controller and complete native CDS DP close, HDD component pdev close and dispatcher pdev close under ASan/UBSan. Their called DP, timer, interrupt and component cleanup functions are models; full HDD shutdown/error unwind and hardware are not executed. Source restoration proves only bounded insertions changed. Revocation is not a parent lifetime lease or in-flight reclaim barrier. No automatic recovery caller/coordinator, safe active-owner teardown, prepared/STARTed recovery, psoc reuse or phone operation is certified. Caller must retain and serialize parents across all polls; backend remains disabled.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
