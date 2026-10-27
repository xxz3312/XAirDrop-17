#!/usr/bin/env python3
"""Actions-only execution of native CREATE/DELETE transport code with boundary stubs.

No WMI/kernel execution. Differentially preserves old modes; proves pre-send
rejection where a PASSTHRU delete would be locally synthesized. Transport success
is not firmware CREATE acceptance or safe lifetime/reuse evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from passthru_mode_fixture import QDF, enum, function
from popsicle_backend_audit import PIN

TX = 'qca-wifi-host-cmn/target_if/mlme/vdev_mgr/src/target_if_vdev_mgr_tx_ops.c'
NAMES = ['target_if_vdev_mgr_create_send', 'target_if_vdev_mgr_delete_send']
SUPPORT = r'''
#define QDF_MAC_ADDR_SIZE 6
#define QDF_IS_STATUS_ERROR(s) ((s)!=QDF_STATUS_SUCCESS)
#define QDF_IS_STATUS_SUCCESS(s) ((s)==QDF_STATUS_SUCCESS)
#define mlme_err(...) ((void)0)
#define WLAN_ADDR_COPY(a,b) memcpy(a,b,6)
#define wmi_service_sync_delete_cmds 1
#define WLAN_SOC_F_TESTMODE_ENABLE 2
#define DELETE_RESPONSE_TIMER 100
#define DELETE_RESPONSE_BIT 3
#define DELETE_WAKELOCK 4
struct wlan_objmgr_vdev { enum QDF_OPMODE mode; };
struct wlan_objmgr_psoc { int dummy; };
struct wmi_unified { int dummy; };
struct vdev_create_params { int dummy; };
struct vdev_delete_params { uint8_t vdev_id; };
struct vdev_response_timer { int expire_time; QDF_STATUS timer_status; };
struct wlan_lmac_if_mlme_tx_ops {
 QDF_STATUS (*psoc_vdev_rsp_timer_init)(struct wlan_objmgr_psoc*,uint8_t);
};
struct wlan_lmac_if_mlme_rx_ops {
 struct vdev_response_timer *(*psoc_get_vdev_response_timer_info)(struct wlan_objmgr_psoc*,uint8_t);
};
static struct wlan_objmgr_psoc psoc;
static struct wmi_unified wmi;
static struct vdev_response_timer timer;
static char trace[256];
/* 1: no psoc, 2: no TX ops, 3: no init, 4: no WMI,
 * 5: no RX ops, 6: no timer getter, 7: no timer. */
static int fault, sync_delete, testmode, sends, simulated, timer_calls;
static QDF_STATUS wire_status, init_status;
static void mark(char c) { size_t n=strlen(trace);assert(n+1<sizeof(trace));trace[n]=c;trace[n+1]=0; }
static uint8_t wlan_vdev_get_id(struct wlan_objmgr_vdev *v) { assert(v);return 7; }
static enum QDF_OPMODE wlan_vdev_mlme_get_opmode(struct wlan_objmgr_vdev *v) { return v->mode; }
static struct wlan_objmgr_psoc *wlan_vdev_get_psoc(struct wlan_objmgr_vdev *v) { assert(v);mark('P');return fault==1?NULL:&psoc; }
static QDF_STATUS timer_init(struct wlan_objmgr_psoc *p,uint8_t id) { assert(p==&psoc && id==7);mark('I');timer_calls++;return init_status; }
static struct wlan_lmac_if_mlme_tx_ops tx={timer_init};
static struct wlan_lmac_if_mlme_tx_ops *wlan_mlme_get_lmac_tx_ops(struct wlan_objmgr_psoc *p) { assert(p==&psoc);mark('T');tx.psoc_vdev_rsp_timer_init=fault==3?NULL:timer_init;return fault==2?NULL:&tx; }
static struct wmi_unified *target_if_vdev_mgr_wmi_handle_get(struct wlan_objmgr_vdev *v) { assert(v);mark('W');return fault==4?NULL:&wmi; }
static uint8_t mac[6]={2,1,2,3,4,5};
static uint8_t *wlan_vdev_mlme_get_macaddr(struct wlan_objmgr_vdev *v) { assert(v);return mac; }
static QDF_STATUS wmi_unified_vdev_create_send(struct wmi_unified *w,uint8_t *a,struct vdev_create_params *p) { assert(w==&wmi && !memcmp(a,mac,6) && p);mark('C');sends++;return wire_status; }
static struct vdev_response_timer *get_timer(struct wlan_objmgr_psoc *p,uint8_t id) { assert(p==&psoc && id==7);mark('G');return fault==7?NULL:&timer; }
static struct wlan_lmac_if_mlme_rx_ops rx={get_timer};
static struct wlan_lmac_if_mlme_rx_ops *target_if_vdev_mgr_get_rx_ops(struct wlan_objmgr_psoc *p) { mark('R');if(!p)return NULL;assert(p==&psoc);rx.psoc_get_vdev_response_timer_info=fault==6?NULL:get_timer;return fault==5?NULL:&rx; }
static bool wmi_service_enabled(struct wmi_unified *w,int service) { assert(w==&wmi && service==1);return sync_delete; }
static bool wlan_psoc_nif_feat_cap_get(struct wlan_objmgr_psoc *p,int cap) { assert(p==&psoc && cap==2);return testmode; }
static void target_if_vdev_mgr_rsp_timer_start(struct wlan_objmgr_psoc *p,struct vdev_response_timer *t,int bit) { assert(p==&psoc && t==&timer && bit==3 && t->expire_time==100);mark('A'); }
static void target_if_wake_lock_timeout_acquire(struct wlan_objmgr_psoc *p,int lock) { assert(p==&psoc && lock==4);mark('L'); }
static void target_if_acquire_vdev_cmd_rt_lock(struct vdev_response_timer *t) { assert(t==&timer);mark('K'); }
static QDF_STATUS wmi_unified_vdev_delete_send(struct wmi_unified *w,uint8_t id) { assert(w==&wmi && id==7);mark('D');sends++;return wire_status; }
static void target_if_release_vdev_cmd_rt_lock(struct wlan_objmgr_psoc *p,uint8_t id) { assert(p==&psoc && id==7);mark('k'); }
static QDF_STATUS target_if_vdev_mgr_rsp_timer_stop(struct wlan_objmgr_psoc *p,struct vdev_response_timer *t,int bit) { assert(p==&psoc && t==&timer && bit==3);mark('a');return QDF_STATUS_SUCCESS; }
static void target_if_wake_lock_timeout_release(struct wlan_objmgr_psoc *p,int lock) { assert(p==&psoc && lock==4);mark('l'); }
/* This boundary represents either the immediate or scheduler-posted fallback.
 * Its scheduler execution and downstream callbacks are NOT executed here. */
static void target_if_vdev_mgr_delete_rsp_handler(struct wlan_objmgr_psoc *p,uint8_t id,struct wlan_lmac_if_mlme_rx_ops *r) { assert(p==&psoc && id==7 && r==&rx);mark('S');simulated++; }
static void reset(void) { trace[0]=0;sends=simulated=timer_calls=0;memset(&timer,0,sizeof(timer)); }
'''
HARNESS = r'''
int main(void) {
 struct wlan_objmgr_vdev v={.mode=QDF_PASSTHRU_MODE};
 struct vdev_create_params cp={0};struct vdev_delete_params dp={.vdev_id=7};
 wire_status=init_status=QDF_STATUS_SUCCESS;sync_delete=1;
 reset();assert(target_if_vdev_mgr_create_send(NULL,&cp)==QDF_STATUS_E_INVAL && !trace[0]);
 reset();assert(target_if_vdev_mgr_create_send(&v,NULL)==QDF_STATUS_E_INVAL && !trace[0]);
 reset();assert(target_if_vdev_mgr_delete_send(NULL,&dp)==QDF_STATUS_E_INVAL && !trace[0]);
 reset();assert(target_if_vdev_mgr_delete_send(&v,NULL)==QDF_STATUS_E_INVAL && !trace[0]);
 /* Both disqualifying capabilities reject BEFORE WMI/timer/locks/fallback. */
 for(sync_delete=0;sync_delete<2;sync_delete++)for(testmode=0;testmode<2;testmode++) {
  if(sync_delete && !testmode)continue;
  reset();assert(target_if_vdev_mgr_create_send(&v,&cp)==QDF_STATUS_E_NOSUPPORT);
  assert(!strcmp(trace,"PTW") && !sends && !timer_calls && !simulated);
  reset();assert(target_if_vdev_mgr_delete_send(&v,&dp)==QDF_STATUS_E_NOSUPPORT);
  assert(!strcmp(trace,"WP") && !sends && !timer_calls && !simulated);
 }
 sync_delete=1;testmode=0;
 /* Missing dependencies must not dereference a missing psoc or send. */
 for(fault=1;fault<=7;fault++) {
  reset();QDF_STATUS c=target_if_vdev_mgr_create_send(&v,&cp);
  if(fault<=4)assert(c==QDF_STATUS_E_INVAL && !sends);
  else assert(c==QDF_STATUS_SUCCESS && sends==1);
  reset();QDF_STATUS d=target_if_vdev_mgr_delete_send(&v,&dp);
  if(fault==1)assert(d==QDF_STATUS_E_NOSUPPORT && !sends);
  else if(fault>=4)assert(d==QDF_STATUS_E_INVAL && !sends);
  else assert(d==QDF_STATUS_SUCCESS && sends==1);
 }
 fault=0;
 /* CREATE has NO firmware ACK here. It sends BEFORE timer initialization,
  * and timer init runs even if the WMI send fails. Keep this risk explicit. */
 for(int w=0;w<2;w++)for(int t=0;t<2;t++) {
  wire_status=w?QDF_STATUS_E_IO:QDF_STATUS_SUCCESS;
  init_status=t?QDF_STATUS_E_NOMEM:QDF_STATUS_SUCCESS;
  QDF_STATUS expected=w?wire_status:init_status;
  reset();assert(target_if_vdev_mgr_create_send(&v,&cp)==expected);
  assert(!strcmp(trace,"PTWCI") && sends==1 && timer_calls==1 && !simulated);
 }
 init_status=QDF_STATUS_SUCCESS;
 /* An accepted DELETE waits for a real ACK; a send error cancels host
  * timer/locks, but this does not certify firmware deletion or lifetime. */
 for(int w=0;w<2;w++) {
  wire_status=w?QDF_STATUS_E_IO:QDF_STATUS_SUCCESS;
  reset();assert(target_if_vdev_mgr_delete_send(&v,&dp)==wire_status);
  assert(!strcmp(trace,w?"WPRGALKDkal":"WPRGALKD") && sends==1 && !simulated);
 }
 /* Preserve return values, ordering and fallback behavior of all 17 old
  * modes across capabilities, native errors and dependency failures. */
 unsigned compared=0;
 for(int mode=0;mode<17;mode++)for(sync_delete=0;sync_delete<2;sync_delete++)
 for(testmode=0;testmode<2;testmode++)for(fault=0;fault<=7;fault++)
 for(int w=0;w<2;w++)for(int t=0;t<2;t++) {
  v.mode=mode;wire_status=w?QDF_STATUS_E_IO:QDF_STATUS_SUCCESS;init_status=t?QDF_STATUS_E_NOMEM:QDF_STATUS_SUCCESS;
  for(int command=0;command<2;command++) {
   reset();QDF_STATUS before=command?old_target_if_vdev_mgr_delete_send(&v,&dp):old_target_if_vdev_mgr_create_send(&v,&cp);
   char saved[256];strcpy(saved,trace);int a=sends,b=simulated,c=timer_calls;struct vdev_response_timer saved_timer=timer;
   reset();QDF_STATUS after=command?target_if_vdev_mgr_delete_send(&v,&dp):target_if_vdev_mgr_create_send(&v,&cp);
   assert(before==after && !strcmp(saved,trace) && a==sends && b==simulated && c==timer_calls);
   assert(saved_timer.expire_time==timer.expire_time && saved_timer.timer_status==timer.timer_status);compared++;
  }
 }
 assert(compared==4352);
 puts("MISHARE_CREATE_DELETE_PREFLIGHT_FIXTURE_PASS_ONLY");return 0;
}
'''


def fixture(root):
    read=lambda p:(root/p).read_text()
    before=subprocess.check_output(['git','-C',str(root),'show',f'{PIN}:{TX}'],text=True)
    after=read(TX)
    # This file had no changes in patches 0001-0011. Exact removal prevents
    # the tests from overlooking any unrelated transport edits.
    guard=re.compile(r'\n\t/\* PASSTHRU teardown must not rely.*?\n\t\treturn QDF_STATUS_E_NOSUPPORT;\n',re.S)
    stripped,count=guard.subn('',after)
    if count!=2 or stripped!=before:raise ValueError('Unexpected TX changes outside the two guards')
    status=re.search(r'typedef enum\s*\{[^}]+\}\s*QDF_STATUS;',read('qca-wifi-host-cmn/qdf/inc/qdf_status.h'),re.S)[0]
    code='#include <assert.h>\n#include <stdint.h>\n#include <stdbool.h>\n#include <stdio.h>\n#include <string.h>\n'
    code+=enum(read(QDF),'QDF_OPMODE')+'\n'+status+'\n'+SUPPORT
    for name in NAMES:
        code+='\n'+function(before,name).replace(name,'old_'+name)+'\n'
        code+='\n'+function(after,name)+'\n'
    return code+HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('Unexpected source commit')
    source=fixture(root)
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'transport.c';p.write_text(source);exe=Path(tmp)/'transport'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-g','-fsanitize=address,undefined',str(p),'-o',str(exe)],check=True)
        output=subprocess.check_output([exe],text=True,timeout=20,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
        if output.strip()!='MISHARE_CREATE_DELETE_PREFLIGHT_FIXTURE_PASS_ONLY':raise ValueError('Unexpected output')
    return {'status':'MISHARE_CREATE_DELETE_PREFLIGHT_FIXTURE_PASS_ONLY','source_commit':PIN,
      'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),'tx_source_sha256':hashlib.sha256((root/TX).read_bytes()).hexdigest(),
      'legacy_mode_differential_cases':4352,'passthru_requires':['sync_delete_cmds capability','testmode disabled'],
      'checks':['two guards are the only TX source edits','invalid inputs rejected','PASSTHRU unsupported delete rejected before commands/timers/locks','CREATE send precedes timer initialization even on send error','CREATE return failure can occur after WMI accepted','DELETE accepted keeps native completion pending','DELETE send error cancels native timer/locks','old 17 modes preserve returns and side effects across dependencies/capabilities/errors'],
      'limitations':'Actual complete native CREATE/DELETE transport functions with mocked WMI, object getters, timers, locks and fallback dispatch. No firmware acknowledgments, scheduler execution, timer lifetime, delete-origin tracking, safe ID reuse, runtime owner binding or AirDrop certification. The MLME PASSTHRU create gate still rejects before this transport.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
