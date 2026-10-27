#!/usr/bin/env python3
"""Actions-only complete native START/STOP decoder and response-handler fixture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import mishare_events_fixture as events
ROOT = events.ROOT
TLV = 'qca-wifi-host-cmn/wmi/src/wmi_unified_vdev_tlv.c'


def function(text, name):
    match = re.search(r'(?:static (?:int|QDF_STATUS)\s+)' + re.escape(name) + r'\([^;]*?\n\{.*?^\}', text, re.M | re.S)
    if not match:
        raise ValueError('Missing native function: ' + name)
    return match[0]


STUBS = r'''
#include <string.h>
typedef int QDF_STATUS;
typedef void *ol_scn_t;
#define QDF_STATUS_E_INVAL 1
#define QDF_IS_STATUS_ERROR(s) ((s)!=0)
#define qdf_mem_zero(p,n) memset(p,0,n)
#define wmi_err(...) ((void)0)
#define mlme_err(...) ((void)0)
#define WLAN_VDEV_TARGET_IF_ID WLAN_HDD_ID_OBJ_MGR
#define START_RESPONSE_BIT 1
#define RESTART_RESPONSE_BIT 2
#define STOP_RESPONSE_BIT 3
#define START_WAKELOCK 4
enum QDF_OPMODE { QDF_MAX_NO_OF_MODE=0,QDF_MONITOR_MODE=1,QDF_SAP_MODE=2,QDF_P2P_GO_MODE=3 };
struct wmi_unified { int unused; };
typedef struct {
 uint32_t vdev_id,requestor_id,resp_type,status,chain_mask,smps_mode,mac_id;
 uint32_t cfgd_tx_streams,cfgd_rx_streams,max_allowed_tx_power,min_device_tx_pwr_valid,min_device_tx_pwr;
} wmi_vdev_start_response_event_fixed_param;
typedef struct { uint32_t vdev_id; } wmi_vdev_stopped_event_fixed_param;
typedef struct {wmi_vdev_start_response_event_fixed_param *fixed_param;} WMI_VDEV_START_RESP_EVENTID_param_tlvs;
typedef struct {wmi_vdev_stopped_event_fixed_param *fixed_param;} WMI_VDEV_STOPPED_EVENTID_param_tlvs;
struct vdev_response_timer {int unused;};
struct wlan_lmac_if_mlme_rx_ops {
 struct vdev_response_timer *(*psoc_get_vdev_response_timer_info)(struct wlan_objmgr_psoc*,uint32_t);
 QDF_STATUS (*vdev_mgr_start_response)(struct wlan_objmgr_psoc*,struct vdev_start_response*);
 QDF_STATUS (*vdev_mgr_stop_response)(struct wlan_objmgr_psoc*,struct vdev_stop_response*);
};
static struct wlan_objmgr_psoc native_psoc={1};
static struct wlan_objmgr_vdev native_vdev={.psoc=&native_psoc,.id=7,.mode=QDF_PASSTHRU_MODE};
static struct wmi_unified native_wmi;
static struct vdev_response_timer native_timer;
static unsigned timer_lookups,timer_stops,last_timer,wake_releases,rt_releases,obj_lookups;
static bool no_psoc,no_ops,no_wmi,no_timer,no_vdev,timer_fail;
static QDF_STATUS callback_status;
static int qdf_status_to_os_return(QDF_STATUS s) {return s?-EINVAL:0;}
static struct vdev_response_timer *get_timer(struct wlan_objmgr_psoc *p,uint32_t id) {
 assert(p==&native_psoc && id<=255);timer_lookups++;return no_timer || id!=7?NULL:&native_timer;
}
static QDF_STATUS start_callback(struct wlan_objmgr_psoc *p,struct vdev_start_response *r) {
 assert(p==&native_psoc && r->vdev_id==7);legacy_calls++;return callback_status;
}
static QDF_STATUS stop_callback(struct wlan_objmgr_psoc *p,struct vdev_stop_response *r) {
 assert(p==&native_psoc && r->vdev_id==7);legacy_calls++;return callback_status;
}
static struct wlan_lmac_if_mlme_rx_ops native_ops={get_timer,start_callback,stop_callback};
static struct wlan_objmgr_psoc *target_if_get_psoc_from_scn_hdl(ol_scn_t s) {assert(s);return no_psoc?NULL:&native_psoc;}
static struct wlan_lmac_if_mlme_rx_ops *target_if_vdev_mgr_get_rx_ops(struct wlan_objmgr_psoc *p) {assert(p==&native_psoc);return no_ops?NULL:&native_ops;}
static struct wmi_unified *get_wmi_unified_hdl_from_psoc(struct wlan_objmgr_psoc *p) {assert(p==&native_psoc);return no_wmi?NULL:&native_wmi;}
static unsigned wlan_psoc_get_id(struct wlan_objmgr_psoc *p) {return p->id;}
static struct wlan_objmgr_vdev *wlan_objmgr_get_vdev_by_id_from_psoc(struct wlan_objmgr_psoc *p,u8 id,int tag) {
 assert(p==&native_psoc && tag==WLAN_VDEV_TARGET_IF_ID);obj_lookups++;
 if(no_vdev || id!=7)
  return NULL;
 native_vdev.refs++;return &native_vdev;
}
static QDF_STATUS target_if_vdev_mgr_rsp_timer_stop(struct wlan_objmgr_psoc *p,struct vdev_response_timer *t,unsigned bit) {
 assert(p==&native_psoc && t==&native_timer);timer_stops++;last_timer=bit;return timer_fail?1:0;
}
static void target_if_wake_lock_timeout_release(struct wlan_objmgr_psoc *p,unsigned tag) {assert(p==&native_psoc && tag==4);wake_releases++;}
static void target_if_release_vdev_cmd_rt_lock(struct wlan_objmgr_psoc *p,u8 id) {assert(p==&native_psoc && id==7);rt_releases++;}
'''
HARNESS = r'''
static struct mishare_vdev_txn state(struct mishare_event_owner *o) {struct mishare_vdev_txn s;assert(!mishare_events_snapshot(o,&s));return s;}
static void reset(void) {
 assert(!allocations && !native_vdev.refs && !mishare_event_owners);
 no_psoc=no_ops=no_wmi=no_timer=no_vdev=timer_fail=false;
 timer_lookups=timer_stops=last_timer=wake_releases=rt_releases=obj_lookups=legacy_calls=0;
 callback_status=0;native_vdev.mode=QDF_PASSTHRU_MODE;
 native_ops.vdev_mgr_start_response=start_callback;native_ops.vdev_mgr_stop_response=stop_callback;
}
static int send_start(uint32_t id,uint32_t type,uint32_t status) {
 wmi_vdev_start_response_event_fixed_param fixed={.vdev_id=id,.resp_type=type,.status=status};
 WMI_VDEV_START_RESP_EVENTID_param_tlvs tlv={&fixed};
 return target_if_vdev_mgr_start_response_handler(&native_psoc,(uint8_t*)&tlv,sizeof(tlv));
}
static int send_stop(uint32_t id) {
 wmi_vdev_stopped_event_fixed_param fixed={id};WMI_VDEV_STOPPED_EVENTID_param_tlvs tlv={&fixed};
 return target_if_vdev_mgr_stop_response_handler(&native_psoc,(uint8_t*)&tlv,sizeof(tlv));
}
static struct mishare_event_owner *begin_start(void) {
 struct mishare_event_owner *o=NULL;u64 ticket;assert(!mishare_events_bind(&native_vdev,&o));
 assert(!mishare_events_begin(o,MISHARE_TXN_START,&ticket));assert(!mishare_events_submitted(o,ticket,MISHARE_TXN_ACCEPTED));return o;
}
int main(void) {
 /* Reject before any timer lookup, reference acquisition or PM mutation. */
 const uint32_t bad_ids[]={256,263,65543,UINT32_MAX};
 for(unsigned i=0;i<sizeof(bad_ids)/sizeof(*bad_ids);i++) {
  reset();struct mishare_event_owner *o=begin_start();
  assert(send_start(bad_ids[i],0,0)==-EINVAL && send_stop(bad_ids[i])==-EINVAL);
  assert(!timer_lookups && !timer_stops && !obj_lookups && !wake_releases && !rt_releases && !legacy_calls);
  assert(state(o).pending==MISHARE_TXN_START && !state(o).replied);mishare_events_unbind(&o);
 }
 const uint32_t bad_types[]={2,255,UINT32_MAX};
 for(unsigned i=0;i<sizeof(bad_types)/sizeof(*bad_types);i++) {
  reset();struct mishare_event_owner *o=begin_start();native_vdev.mode=QDF_MONITOR_MODE;
  assert(send_start(7,bad_types[i],0)==-EINVAL);
  assert(!timer_lookups && !timer_stops && !wake_releases && !rt_releases && !legacy_calls && !state(o).replied);mishare_events_unbind(&o);
 }
 reset();struct vdev_start_response decoded;uint32_t stopped;
 WMI_VDEV_START_RESP_EVENTID_param_tlvs empty_start={0};WMI_VDEV_STOPPED_EVENTID_param_tlvs empty_stop={0};
 assert(extract_vdev_start_resp_tlv(&native_wmi,NULL,&decoded)==1);
 assert(extract_vdev_start_resp_tlv(&native_wmi,&empty_start,NULL)==1);
 assert(extract_vdev_start_resp_tlv(&native_wmi,&empty_start,&decoded)==1);
 assert(extract_vdev_stopped_param_tlv(&native_wmi,NULL,&stopped)==1);
 assert(extract_vdev_stopped_param_tlv(&native_wmi,&empty_stop,NULL)==1);
 assert(extract_vdev_stopped_param_tlv(&native_wmi,&empty_stop,&stopped)==1);
 assert(target_if_vdev_mgr_start_response_handler(NULL,(uint8_t*)&empty_start,0)==-EINVAL);
 assert(target_if_vdev_mgr_stop_response_handler(NULL,(uint8_t*)&empty_stop,0)==-EINVAL);
 assert(target_if_vdev_mgr_start_response_handler(&native_psoc,NULL,0)==-EINVAL);
 assert(target_if_vdev_mgr_stop_response_handler(&native_psoc,NULL,0)==-EINVAL);
 assert(target_if_vdev_mgr_start_response_handler(&native_psoc,(uint8_t*)&empty_start,0)==-EINVAL);
 assert(target_if_vdev_mgr_stop_response_handler(&native_psoc,(uint8_t*)&empty_stop,0)==-EINVAL);
 for(int fault=0;fault<8;fault++) {
  reset();struct mishare_event_owner *o=begin_start();
  no_psoc=fault==0;no_ops=fault==1;no_wmi=fault==2;no_timer=fault==3;no_vdev=fault==4;timer_fail=fault==5;
  if(fault==6)native_ops.vdev_mgr_start_response=NULL;
  if(fault==7)native_ops.vdev_mgr_stop_response=NULL;
  if(fault!=7)assert(send_start(7,0,0)==-EINVAL && !state(o).replied && !legacy_calls && native_vdev.refs==1);
  if(fault!=4 && fault!=6)assert(send_stop(7)==-EINVAL && !legacy_calls);
  mishare_events_unbind(&o);
 }
 reset();struct mishare_event_owner *o=begin_start();
 /* Valid RESTART keeps native behavior but cannot complete owned START. */
 assert(!send_start(7,1,0) && last_timer==RESTART_RESPONSE_BIT && legacy_calls==1 && !state(o).replied);
 assert(!send_start(7,0,0) && last_timer==START_RESPONSE_BIT && state(o).state==MISHARE_TXN_STARTED);
 u64 ticket;assert(!mishare_events_begin(o,MISHARE_TXN_STOP,&ticket));assert(!mishare_events_submitted(o,ticket,MISHARE_TXN_ACCEPTED));
 timer_fail=true;assert(send_stop(7)==-EINVAL && state(o).pending==MISHARE_TXN_STOP);timer_fail=false;
 assert(!send_stop(7) && last_timer==STOP_RESPONSE_BIT && state(o).state==MISHARE_TXN_STOPPED);mishare_events_unbind(&o);
 reset();o=begin_start();assert(!send_start(7,0,WLAN_MLME_HOST_VDEV_START_CHAN_INVALID));
 assert(state(o).state==MISHARE_TXN_QUARANTINED);mishare_events_unbind(&o);
 /* Preserve ordinary unbound callback and PM behavior for valid events. */
 for(int mode=QDF_MONITOR_MODE;mode<=QDF_P2P_GO_MODE;mode++) {
  reset();native_vdev.mode=mode;assert(!send_start(7,0,0));
  assert(wake_releases==1 && rt_releases==1 && legacy_calls==1 && !native_vdev.refs);
  assert(!send_stop(7) && legacy_calls==2);
 }
 reset();o=begin_start();callback_status=1;
 assert(send_start(7,0,0)==-EINVAL && state(o).state==MISHARE_TXN_STARTED);mishare_events_unbind(&o);
 /* 255 is representable, 0 is valid at decode boundary; timer decides existence. */
 for(unsigned id=0;id<=255;id+=255) {
  wmi_vdev_start_response_event_fixed_param fixed={.vdev_id=id,.resp_type=0};WMI_VDEV_START_RESP_EVENTID_param_tlvs tlv={&fixed};
  assert(!extract_vdev_start_resp_tlv(&native_wmi,&tlv,&decoded) && decoded.vdev_id==id);
  wmi_vdev_stopped_event_fixed_param sf={id};WMI_VDEV_STOPPED_EVENTID_param_tlvs st={&sf};
  assert(!extract_vdev_stopped_param_tlv(&native_wmi,&st,&stopped) && stopped==id);
 }
 reset();puts("MISHARE_NATIVE_RESPONSE_HANDLER_FIXTURE_PASS_ONLY");return 0;
}
'''


def fixture(root):
    events.extract_hooks(root)  # Exact ordinary RX preservation, including guard.
    rx = (root / events.RX).read_text()
    tlv = (root / TLV).read_text()
    defs = (root / events.RXDEFS).read_text()
    param = (root / 'qca-wifi-host-cmn/wmi/inc/wmi_unified_param.h').read_text()
    enums = re.search(r'typedef enum \{\s*/\* Event response of START CMD \*/.*?\} WMI_HOST_START_EVENT_PARAM;', param, re.S)[0]
    enums += re.search(r'typedef enum \{\s*/\* Event response of START CMD \*/.*?\} WMI_START_EVENT_PARAM;', (root / 'fw-api/fw/wmi_unified.h').read_text(), re.S)[0]
    enums += re.search(r'enum wlan_mlme_host_vdev_start_status\s*\{.*?\};', (root / events.TXDEFS).read_text(), re.S)[0]
    structs = '\n'.join(re.search(r'struct ' + name + r'\s*\{.*?\};', defs, re.S)[0] for name in ['vdev_start_response','vdev_stop_response'])
    decoders = '\n'.join(function(tlv, name) for name in ['extract_vdev_start_resp_tlv','extract_vdev_stopped_param_tlv'])
    handlers = '\n'.join(function(rx, name) for name in ['target_if_vdev_mgr_start_response_handler','target_if_vdev_mgr_stop_response_handler'])
    wrappers = r'''
static QDF_STATUS wmi_extract_vdev_start_resp(struct wmi_unified *w,void *b,struct vdev_start_response *r) {return extract_vdev_start_resp_tlv(w,b,r);}
static QDF_STATUS wmi_extract_vdev_stopped_param(struct wmi_unified *w,void *b,uint32_t *r) {return extract_vdev_stopped_param_tlv(w,b,r);}
'''
    return events.COMMON + enums + structs + STUBS + decoders + wrappers + handlers + HARNESS


def audit(root):
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip() != events.PIN:
        raise ValueError('Unexpected source commit')
    source = fixture(root)
    production = ROOT / 'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp); (d/'linux').mkdir()
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;\ntypedef uint64_t u64;\n')
        for name in ['linux/bug.h','linux/slab.h','linux/spinlock.h','wlan_objmgr_vdev_obj.h']:
            (d/name).write_text('/* supplied by fixture */\n')
        (d/'test.c').write_text(source); exe=d/'test'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),str(d/'test.c'),'-o',str(exe)],check=True)
        output=subprocess.check_output([exe],text=True,timeout=30,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
        if output.strip() != 'MISHARE_NATIVE_RESPONSE_HANDLER_FIXTURE_PASS_ONLY':
            raise ValueError('Unexpected fixture output')
    return {'status':output.strip(),'source_commit':events.PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'native_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [events.RX,TLV,events.RXDEFS]},
            'checks':['wire ID overflow rejected before narrowing/timer/PM access','unknown START type fails extraction','null fixed TLV/output rejection','complete native START/STOP handlers','native timer failure prevents owned notification','RESTART native callback preserved without completing START','real START rejection quarantines','real START/STOP success','ordinary unbound callbacks and PM release preserved','native callback error does not undo real firmware completion','u8 representable boundaries'],
            'limitations':'Actual complete native decoder/handler and production registry/transaction C. WMI TLV envelope/fixed fields, RX ops, object manager, timer and PM are host models; binary TLV parsing, actual timers, IRQ/MC races, WMI, radio and phone execution are not tested. No new runtime caller or START/STOP submission.'}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
