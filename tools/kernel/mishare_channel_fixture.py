#!/usr/bin/env python3
"""Actions-only native owned channel preparation/MC request fixture."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import re
import subprocess
import tempfile
import mishare_session_fixture as pe
ROOT=Path(__file__).resolve().parents[2]
API=pe.API
BEFORE='76ea35d256592c2944dab21abb85a9e03081bd6cfd2d27d1105a397c4a1015b2'

STUBS=r'''
#define WLAN_UMAC_COMP_POLICY_MGR 1
#define WLAN_UMAC_COMP_SCAN 2
#define WLAN_VDEV_S_INIT 0
#define SCAN_NOT_IN_PROGRESS 0
#define REG_CURRENT_PWR_MODE 0
#define CH_WIDTH_20MHZ 0
#define MLME_DOT11_MODE_11N 4
#define WMA_MAX_TXPOWER_INVALID 127
struct ch_params {int ch_width;uint32_t mhz_freq_seg0,mhz_freq_seg1;u8 center_freq_seg0,sec_ch_offset;};
static bool ch_passive,ch_dfs,ch_invalid,ch_bad_params,ch_scan,ch_bad_des;
static unsigned ch_connections,ch_prepares;
static bool ch_missing_policy,ch_missing_scan;
static void *wlan_objmgr_psoc_get_comp_private_obj(struct wlan_objmgr_psoc *p,int id) {assert(p && (id==1 || id==2));return (id==1?ch_missing_policy:ch_missing_scan)?NULL:p;}
static int ch_power=20;static QDF_STATUS ch_prepare_status;
static bool wlan_reg_is_24ghz_ch_freq(uint32_t f) {return f>=2412 && f<=2484;}
static bool wlan_reg_is_5ghz_ch_freq(uint32_t f) {return f>=5180 && f<=5825;}
static u8 wlan_reg_freq_to_chan(struct wlan_objmgr_pdev *p,uint32_t f) {assert(p);return ch_invalid?0:wlan_reg_is_24ghz_ch_freq(f)?(f-2407)/5:(f-5000)/5;}
static bool wlan_reg_is_passive_or_disable_for_pwrmode(struct wlan_objmgr_pdev *p,uint32_t f,int mode) {assert(p && f && !mode);return ch_passive;}
static bool wlan_reg_is_dfs_for_freq(struct wlan_objmgr_pdev *p,uint32_t f) {assert(p && f);return ch_dfs;}
static unsigned policy_mgr_get_connection_count(struct wlan_objmgr_psoc *p) {assert(p);return ch_connections;}
static int ucfg_scan_get_pdev_status(struct wlan_objmgr_pdev *p) {assert(p);return ch_scan?1:0;}
static int8_t wlan_reg_get_channel_reg_power_for_freq(struct wlan_objmgr_pdev *p,uint32_t f) {assert(p && f);return ch_power;}
static void wlan_reg_set_channel_params_for_pwrmode(struct wlan_objmgr_pdev *p,uint32_t f,uint32_t sec,struct ch_params *c,int mode) {
 assert(p && f && !sec && c->ch_width==0 && !mode);c->mhz_freq_seg0=ch_bad_params?f+20:f;c->center_freq_seg0=wlan_reg_freq_to_chan(p,f);
}
static struct wlan_channel *wlan_vdev_mlme_get_des_chan(struct wlan_objmgr_vdev *v) {return v->vdev_mlme.des_chan;}
static QDF_STATUS lim_pre_vdev_start(struct mac_context *m,struct vdev_mlme_obj *o,struct pe_session *s) {
 assert(!lock_depth && m==&pe_mac && s==&pe_slot && s->vdev==o->vdev && s->valid && !s->ch_width && s->htCapability==1 && !s->vhtCapability && !s->cac_duration_ms);
 assert(s->dot11mode==4 && s->nss==s->vdev_nss && s->nss>=1 && s->nss<=2 && s->maxTxPower==20);
 ch_prepares++;struct wlan_channel *d=o->vdev->vdev_mlme.des_chan;d->ch_freq=s->curr_op_freq;d->ch_width=0;d->ch_cfreq1=ch_bad_des?s->curr_op_freq+20:s->curr_op_freq;
 return ch_prepare_status; /* native function itself is an explicit model */
}
#define cds_get_context pe_cds_get_context
#define qdf_mem_free pe_qdf_mem_free
NATIVE_CHANNEL_HELPERS
#undef qdf_mem_free
#undef cds_get_context
'''
HARNESS=r'''
static void reset_channel(void) {
 reset_pe();pe_mac.pdev=&pdev;ch_passive=ch_dfs=ch_invalid=ch_bad_params=ch_scan=ch_bad_des=false;
 ch_missing_policy=ch_missing_scan=false;ch_connections=ch_prepares=ch_state=0;ch_power=20;ch_prepare_status=QDF_STATUS_SUCCESS;
}
static struct mishare_runtime_owner *with_session(void) {
 struct mishare_runtime_owner *o=prepared();assert(mishare_runtime_ndi_session(o)==-EINPROGRESS);run_pe(false);assert(state(o).ndi.pe_ready);return o;
}
static void channel_end(struct mishare_runtime_owner **o) {
 assert(mishare_runtime_destroy(o)==-EINPROGRESS && pe_pending.bodyptr && !ctx_delete_calls);
 run_pe(false);context_end(o);assert(!ch_connections && !ch_scan && !pe_request_allocs);
}
int main(void) {
 struct mishare_runtime_owner *o=NULL;
 assert(mishare_runtime_ndi_channel(NULL,2437)==-EINVAL);
 reset_channel();o=prepared();assert(mishare_runtime_ndi_channel(o,2437)==-EBUSY && !pe_pending.bodyptr);context_end(&o);
 for(int fault=0;fault<12;fault++) {
  reset_channel();o=with_session();assert(mishare_runtime_ndi_channel(o,0)==-EINVAL);
  pe_alloc_fail=fault==0;pe_queue_fail=fault==1;if(fault==2)fail_ref_at=ref_calls+1;
  ch_passive=fault==3;ch_dfs=fault==4;ch_invalid=fault==5;ch_bad_params=fault==6;
  ch_connections=fault==7;ch_scan=fault==8;ch_power=fault==9?127:20;
  int ret=mishare_runtime_ndi_channel(o,fault==10?5955:2437);
  if(fault<3)assert(ret<0 && ret!=-EINPROGRESS && !pe_pending.bodyptr);
  else {
   assert(ret==-EINPROGRESS && last_vdev->refs==6 && !state(o).ndi.channel_completed);
   assert(mishare_runtime_destroy(&o)==-EINPROGRESS && !state(o).ndi.pe_delete_requested && !ctx_delete_calls && !wire_deletes);
   run_pe(fault==11);
  }
  assert(state(o).ndi.channel_completed && !state(o).ndi.channel_prepared && !state(o).ndi.blocked && !ch_prepares && !pe_slot.curr_op_freq && last_vdev->refs==5);
  assert(mishare_runtime_ndi_channel(o,2437)==-EBUSY);
  pe_alloc_fail=pe_queue_fail=ch_scan=false;ch_connections=0;channel_end(&o);
 }
 for(int band=0;band<2;band++) {
  reset_channel();o=with_session();last_vdev->mlme->proto.generic.nss_5g=2;
  uint32_t freq=band?5745:2437;
  assert(mishare_runtime_ndi_channel(o,freq)==-EINPROGRESS);
  struct wlan_objmgr_psoc wrong={9};
  mishare_runtime_ndi_channel_event(&wrong,7,o,freq,0);mishare_runtime_ndi_channel_event(&psoc,8,o,freq,0);mishare_runtime_ndi_channel_event(&psoc,7,(void*)1,freq,0);
  assert(!state(o).ndi.channel_completed && !state(o).ndi.blocked);
  run_pe(false);assert(state(o).ndi.channel_prepared && state(o).ndi.channel_submitted && ch_prepares==1 && pe_slot.nss==(band?2:1) && pe_slot.curr_op_freq==freq && last_vdev->refs==5);
  assert(mishare_runtime_ndi_channel(o,freq)==-EBUSY && ch_prepares==1);channel_end(&o);
 }
 reset_channel();o=with_session();pe_early=true;
 assert(mishare_runtime_ndi_channel(o,2437)==-EINPROGRESS && state(o).ndi.channel_submitted && state(o).ndi.channel_prepared && !pe_pending.bodyptr);
 pe_early=false;channel_end(&o);
 for(int fault=0;fault<9;fault++) {
  reset_channel();pid_t child=fork();assert(child>=0);
  if(!child) {
   o=with_session();
   if(fault==0)pe_slot.mishare_owner=(void*)1;
   ch_prepare_status=fault==1?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS;
   ch_bad_des=fault==2;ch_state=fault==3?1:0;ch_missing_policy=fault==7;ch_missing_scan=fault==8;
   if(fault==4)last_vdev->mlme->proto.generic.nss_2g=0;
   assert(mishare_runtime_ndi_channel(o,2437)==-EINPROGRESS);
   if(fault==5)mishare_runtime_ndi_channel_event(&psoc,7,o,5180,0); /* same owner wrong expected frequency */
   run_pe(false);
   if(fault==6)mishare_runtime_ndi_channel_event(&psoc,7,o,2437,0); /* duplicate */
   assert(state(o).ndi.blocked && mishare_runtime_destroy(&o)==-EUCLEAN && !ctx_delete_calls && !wire_deletes && !dp_detaches && !delete_calls && last_vdev->refs==5 && !pe_pending.bodyptr);
   _Exit(0); /* no forced cleanup of ambiguous/partially prepared state */
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 puts("MISHARE_OWNED_CHANNEL_PREPARE_FIXTURE_PASS_ONLY");
}
'''

def fixture(root):
    from mishare_radio_origins import remove_radio_additions
    native=pe.ctx.block((root/API).read_text(),'channel_helpers')
    api=remove_radio_additions((root/API).read_text())
    api=re.sub(r'\n/\* MISHARE_BEGIN:start_plan_request \*/\n.*?/\* MISHARE_END:start_plan_request \*/\n', '', api, flags=re.S)
    stripped=api.replace('\n/* MISHARE_BEGIN:channel_helpers */\n'+pe.ctx.block(api,'channel_helpers')+'/* MISHARE_END:channel_helpers */\n','')
    if hashlib.sha256(stripped.encode()).hexdigest()!=BEFORE:raise ValueError('Channel patch changed existing PE API source')
    src=pe.fixture(root)
    src=src.replace('struct wlan_objmgr_vdev {','struct wlan_channel {uint32_t ch_freq,ch_cfreq1,ch_cfreq2;int ch_width;};\nstruct wlan_objmgr_vdev {',1)
    src=src.replace('v->vdev_mlme.des_chan=malloc(1);','v->vdev_mlme.des_chan=calloc(1,sizeof(struct wlan_channel));')
    src=src.replace('struct mac_context {struct wlan_objmgr_psoc *psoc;','struct mac_context {struct wlan_objmgr_pdev *pdev;struct wlan_objmgr_psoc *psoc;',1)
    src=src.replace('struct pe_session {bool valid;','struct pe_session {uint32_t curr_op_freq;int ch_width,ch_center_freq_seg0,ch_center_freq_seg1,htSecondaryChannelOffset,htSupportedChannelWidthSet,htRecommendedTxWidthSet,dot11mode,htCapability,vhtCapability,nss,vdev_nss,maxTxPower,cac_duration_ms;bool valid;',1)
    start=src.index('/* CHANNEL_TRANSPORT_STUBS */');end=src.index('/* END_CHANNEL_TRANSPORT_STUBS */',start)+len('/* END_CHANNEL_TRANSPORT_STUBS */')
    src=src[:start]+STUBS.replace('NATIVE_CHANNEL_HELPERS',native)+src[end:]
    # Existing PE harness helpers are reused; its main remains Actions-only.
    return src[:src.index('int main(void) {')]+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=pe.PIN:raise ValueError('Unexpected revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_osif_priv.h','qdf_status.h']:(d/n).write_text('/* platform model */\n')
        (d/'owner.c').write_text(source);exe=d/'owner'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),str(d/'owner.c'),'-o',str(exe)],check=True)
        out=subprocess.check_output([exe],text=True,timeout=30,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    if out.strip()!='MISHARE_OWNED_CHANNEL_PREPARE_FIXTURE_PASS_ONLY':raise ValueError('Unexpected fixture output')
    return {'status':out.strip(),'source_commit':pe.PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),'native_sha256':{API:hashlib.sha256((root/API).read_bytes()).hexdigest()},'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h']},'pre_channel_native_api_sha256':BEFORE,'checks':['MC request pins VDEV, has flush callback and actual completion','allocation/ref/queue failures release local resources before publication','no peer/PE/VDEV/DP teardown while channel request is pending','invalid/6GHz/passive/disabled/DFS/scan/concurrent/bonding/power rejects before host mutation','per-band validated NSS used for 2.4/5GHz HT20 preparation','stable PE/owner/VDEV/MAC identity and native INIT required','early completion retained until post returns','partial native preparation/error or bad output quarantines','wrong expected frequency/duplicate matching reply quarantines; foreign token/PSOC/ID ignored'],'limitations':'Actual production owner and native owned channel/queue/flush helpers execute with ASan/UBSan. Native regulatory/scan/policy primitives, lim_pre_vdev_start, full PE allocation/destruction and scheduler are modeled boundaries. Native parameter preparation itself is compiled as part of full WLAN but not executed by this fixture. No WMI START/STOP/DOWN, MLME UP state, hardware mode or concurrency lease, firmware acceptance, actual radio or SSR/remove certification. No runtime backend caller is added.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
