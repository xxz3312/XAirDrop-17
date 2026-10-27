#!/usr/bin/env python3
"""Actions-only execution of target WMA peer create/delete/detach and UP functions.

Native WMA functions and shared predicate are extracted verbatim. Object access,
peer transport, capability bits and callbacks are mocked; no firmware execution.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from passthru_mode_fixture import function, enum
from popsicle_backend_audit import PIN

WMA = 'qcacld-3.0/core/wma/src/wma_dev_if.c'
UTIL = 'qcacld-3.0/core/wma/src/wma_utils.c'
HEADER = 'qcacld-3.0/core/wma/inc/wma_mishare_ndi.h'
MLME = 'qcacld-3.0/components/mlme/core/src/wlan_mlme_vdev_mgr_interface.c'

STUBS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define QDF_IS_STATUS_ERROR(s) ((s) != QDF_STATUS_SUCCESS)
#define QDF_MODULE_ID_WMA 1
#define wma_err(...) ((void)0)
#define wma_debug(...) ((void)0)
#define wmi_service_nan_data 1
#define wmi_service_sync_delete_cmds 2
#define WMI_PEER_TYPE_DEFAULT 0
#define QDF_SELF_PEER_DEL_FAILED 1
#define QDF_DEL_SELF_STA_FAILED 2
struct qdf_mac_addr { uint8_t bytes[6]; };
struct wlan_objmgr_vdev {
 int mode; uint8_t id;
 struct { uint8_t macaddr[6],mldaddr[6]; } vdev_mlme;
};
struct wlan_objmgr_peer { int unused; };
struct vdev_mlme_obj {
 struct wlan_objmgr_vdev *vdev; void *ext_vdev_ptr;
 struct { struct { uint32_t type,subtype; } generic; } mgmt;
 struct { struct { int assoc_id; } sta; } proto;
};
struct del_vdev_params { struct wlan_objmgr_vdev *vdev; uint8_t vdev_id; uint8_t self_mac_addr[6]; QDF_STATUS status; };
struct wma_txrx_node {
 struct wlan_objmgr_vdev *vdev; uint32_t type,sub_type;
 bool is_del_sta_deferred,vdev_active; struct del_vdev_params *del_staself_req;
};
struct wma { struct wma_txrx_node interfaces[32]; uint8_t max_bssid; void *wmi_handle; };
typedef struct wma *tp_wma_handle;
static struct wma context;
static bool have_context=true,nan_cap=true,sync_cap=true,peer_exists,obj_fail;
static int creates,removes,obj_creates,obj_removes,detach_calls,delete_responses,recoveries,up_calls;
static QDF_STATUS create_status,remove_status,detach_status,check_status,up_status;
static tp_wma_handle cds_get_context(int module) { assert(module==1);return have_context?&context:NULL; }
static int wlan_vdev_mlme_get_opmode(struct wlan_objmgr_vdev *v) { assert(v);return v->mode; }
static uint8_t wlan_vdev_get_id(struct wlan_objmgr_vdev *v) { assert(v);return v->id; }
static bool wmi_service_enabled(void *h,int service) { assert(h==&context);return service==1?nan_cap:sync_cap; }
static bool qdf_is_macaddr_zero(struct qdf_mac_addr *a) { return !memcmp(a->bytes,(uint8_t[6]){0},6); }
static QDF_STATUS wma_create_peer(tp_wma_handle w,uint8_t *mac,void *unused,int type,uint8_t id,void *unused2,bool flag) {
 assert(w==&context && mac && !unused && type==WMI_PEER_TYPE_DEFAULT && id<32 && !unused2 && !flag);
 creates++;return create_status;
}
static bool wma_objmgr_peer_exist(tp_wma_handle w,uint8_t *mac,uint8_t *id) { assert(w && mac && id);return peer_exists; }
static struct wlan_objmgr_peer *wma_create_objmgr_peer(tp_wma_handle w,uint8_t id,uint8_t *mac,int type,uint8_t *self) {
 static struct wlan_objmgr_peer peer;assert(w && id<32 && mac && type==WMI_PEER_TYPE_DEFAULT && self);
 obj_creates++;return obj_fail?NULL:&peer;
}
static void wma_remove_objmgr_peer(tp_wma_handle w,struct wlan_objmgr_vdev *v,uint8_t *mac) { assert(w && v && mac);obj_removes++; }
static QDF_STATUS wma_self_peer_remove(tp_wma_handle w,struct del_vdev_params *p) { assert(w && p);removes++;return remove_status; }
static QDF_STATUS wma_handle_vdev_detach(tp_wma_handle w,struct del_vdev_params *p) { assert(w && p);detach_calls++;return detach_status; }
static void mlme_vdev_self_peer_delete_resp(struct del_vdev_params *p) { assert(p);delete_responses++; }
static void cds_trigger_recovery(int reason) { assert(reason==1 || reason==2);recoveries++; }
static QDF_STATUS wma_check_for_deferred_peer_delete(tp_wma_handle w,struct del_vdev_params *p) { assert(w && p);return check_status; }
static QDF_STATUS vdev_mgr_up_send(struct vdev_mlme_obj *m) { assert(m && m->vdev);up_calls++;return up_status; }
'''
HARNESS = r'''
static struct wlan_objmgr_vdev v,foreign;
static struct vdev_mlme_obj m;
static struct del_vdev_params request;
static void setup(int mode,int type) {
 context=(struct wma){.max_bssid=32};context.wmi_handle=&context;
 v=(struct wlan_objmgr_vdev){.mode=mode,.id=3,.vdev_mlme={.macaddr={2,1,2,3,4,5}}};
 m=(struct vdev_mlme_obj){.vdev=&v,.ext_vdev_ptr=&v,.mgmt={.generic={.type=type}},.proto={.sta={.assoc_id=99}}};
 context.interfaces[3]=(struct wma_txrx_node){.vdev=&v,.type=type,.vdev_active=true};
 request=(struct del_vdev_params){.vdev=&v,.vdev_id=3};
 have_context=nan_cap=sync_cap=true;peer_exists=obj_fail=false;
 creates=removes=obj_creates=obj_removes=detach_calls=delete_responses=recoveries=up_calls=0;
 create_status=remove_status=detach_status=check_status=up_status=QDF_STATUS_SUCCESS;
}
int main(void) {
 /* All native host modes/types/subtypes must preserve the native predicate. */
 for(int mode=0;mode<QDF_MAX_NO_OF_MODE;mode++)for(int type=0;type<16;type++)for(int sub=0;sub<8;sub++) {
  setup(mode,type);
  bool native=mlme_vdev_uses_self_peer(type,sub);
  assert(wma_mishare_uses_self_peer(&v,type,sub)==(native || (mode==QDF_PASSTHRU_MODE && type==WMI_VDEV_TYPE_NDI)));
 }
 assert(!wma_mishare_pas_ndi(NULL,WMI_VDEV_TYPE_NDI));
 setup(QDF_PASSTHRU_MODE,WMI_VDEV_TYPE_NDI);nan_cap=false;
 assert(wma_vdev_self_peer_create(&m)==QDF_STATUS_E_NOSUPPORT && !creates && !obj_creates);
 nan_cap=true;create_status=QDF_STATUS_E_FAILURE;
 assert(wma_vdev_self_peer_create(&m)==create_status && creates==1);
 create_status=QDF_STATUS_SUCCESS;
 assert(wma_vdev_self_peer_create(&m)==QDF_STATUS_SUCCESS && creates==2 && !obj_creates);
 assert(wma_vdev_detach(&request)==QDF_STATUS_SUCCESS && removes==1 && !detach_calls && !delete_responses);
 /* With sync delete unavailable, native detach sends its immediate response. */
 setup(QDF_PASSTHRU_MODE,WMI_VDEV_TYPE_NDI);sync_cap=false;
 assert(wma_vdev_detach(&request)==QDF_STATUS_SUCCESS && removes==1 && detach_calls==1 && delete_responses==1);
 /* Delete failure keeps native recovery, never silently claims success. */
 setup(QDF_PASSTHRU_MODE,WMI_VDEV_TYPE_NDI);remove_status=QDF_STATUS_E_FAILURE;
 assert(wma_vdev_detach(&request)==QDF_STATUS_E_INVAL && removes==1 && detach_calls==1 && delete_responses==1 && recoveries==1);
 setup(QDF_PASSTHRU_MODE,WMI_VDEV_TYPE_NDI);context.interfaces[3].is_del_sta_deferred=true;
 assert(wma_vdev_detach(&request)==QDF_STATUS_SUCCESS && !removes && !detach_calls);
 /* Ordinary NDI remains outside the PAS self-peer extension. */
 setup(QDF_NDI_MODE,WMI_VDEV_TYPE_NDI);
 assert(wma_vdev_self_peer_create(&m)==QDF_STATUS_SUCCESS && !creates && !obj_creates);
 assert(wma_vdev_detach(&request)==QDF_STATUS_SUCCESS && !removes && detach_calls==1 && delete_responses==1);
 setup(QDF_STA_MODE,WMI_VDEV_TYPE_STA);
 assert(wma_vdev_self_peer_create(&m)==QDF_STATUS_SUCCESS && !creates && obj_creates==1);
 assert(wma_vdev_detach(&request)==QDF_STATUS_SUCCESS && !removes && obj_removes==1);
 setup(QDF_MONITOR_MODE,WMI_VDEV_TYPE_MONITOR);
 assert(wma_vdev_self_peer_create(&m)==QDF_STATUS_SUCCESS && creates==1);
 assert(wma_vdev_detach(&request)==QDF_STATUS_SUCCESS && removes==1 && !detach_calls);
 /* UP acknowledges only a bound PAS+NDI context and never sends WMI UP. */
 setup(QDF_PASSTHRU_MODE,WMI_VDEV_TYPE_NDI);
 assert(wma_mon_mlme_vdev_up_send(&m,0,NULL)==QDF_STATUS_SUCCESS && !up_calls && m.proto.sta.assoc_id==99);
 m.ext_vdev_ptr=NULL;
 assert(wma_mon_mlme_vdev_up_send(&m,0,NULL)==QDF_STATUS_E_INVAL && !up_calls);
 m.ext_vdev_ptr=&v;context.interfaces[3].vdev=&foreign;
 assert(wma_mon_mlme_vdev_up_send(&m,0,NULL)==QDF_STATUS_E_INVAL && !up_calls);
 context.interfaces[3].vdev=&v;context.interfaces[3].type=WMI_VDEV_TYPE_MONITOR;
 assert(wma_mon_mlme_vdev_up_send(&m,0,NULL)==QDF_STATUS_E_INVAL && !up_calls);
 setup(QDF_PASSTHRU_MODE,9);m.ext_vdev_ptr=NULL;
 assert(wma_mon_mlme_vdev_up_send(&m,0,NULL)==QDF_STATUS_E_INVAL && !up_calls);
 m.ext_vdev_ptr=&v;
 assert(wma_mon_mlme_vdev_up_send(&m,0,NULL)==QDF_STATUS_E_INVAL && !up_calls);
 setup(QDF_MONITOR_MODE,WMI_VDEV_TYPE_MONITOR);up_status=QDF_STATUS_E_FAILURE;
 assert(wma_mon_mlme_vdev_up_send(&m,0,NULL)==up_status && up_calls==1 && !m.proto.sta.assoc_id);
 assert(wma_mon_mlme_vdev_up_send(NULL,0,NULL)==QDF_STATUS_E_INVAL);
 m.vdev=NULL;assert(wma_mon_mlme_vdev_up_send(&m,0,NULL)==QDF_STATUS_E_INVAL);
 m.vdev=&v;v.id=32;assert(wma_mon_mlme_vdev_up_send(&m,0,NULL)==QDF_STATUS_E_INVAL && up_calls==1);
 puts("MISHARE_WMA_NDI_COMPAT_FIXTURE_PASS_ONLY");
}
'''

def fixture(root):
    read=lambda n:(root/n).read_text()
    status=re.search(r'typedef enum\s*\{[^}]+\}\s*QDF_STATUS;',read('qca-wifi-host-cmn/qdf/inc/qdf_status.h'),re.S)[0]
    fw=read('fw-api/fw/wmi_unified.h')
    macros='\n'.join(re.findall(r'^#define (?:WMI_VDEV_TYPE_\w+|WMI_UNIFIED_VDEV_SUBTYPE_P2P_DEVICE)\s+0x[0-9a-fA-F]+',fw,re.M))
    macros='\n'.join('#define '+x for x in macros.splitlines())
    code='#include <stdbool.h>\n#include <stdint.h>\n'+status+'\n'+enum(read('qca-wifi-host-cmn/qdf/inc/qdf_types.h'),'QDF_OPMODE')+'\n'+macros+'\n'+STUBS
    code+='\n'+function(read(MLME),'mlme_vdev_uses_self_peer')+'\n'
    code+='\n'.join(l for l in read(HEADER).splitlines() if not l.startswith('#include'))+'\n'
    for n in ['wma_vdev_self_peer_create','wma_vdev_self_peer_delete','wma_vdev_detach']:
        code+='\n'+function(read(WMA),n)+'\n'
    code+=function(read(UTIL),'wma_mon_mlme_vdev_up_send')+'\n'+HARNESS
    return code


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':
        raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:
        raise ValueError('Unexpected source revision')
    source=fixture(root)
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'test.c').write_text(source);exe=d/'test'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-g','-fsanitize=address,undefined',str(d/'test.c'),'-o',str(exe)],check=True)
        output=subprocess.check_output([exe],text=True,timeout=30,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    if output.strip()!='MISHARE_WMA_NDI_COMPAT_FIXTURE_PASS_ONLY':raise ValueError('Unexpected fixture output')
    return {'status':output.strip(),'source_commit':PIN,'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'source_sha256':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in [WMA,UTIL,HEADER,MLME]},
            'checks':['all native opmodes/types/subtypes retain original self-peer decisions','NAN capability rejection before create','create transport error propagation','PAS NDI peer create and sync delete waiting','no-sync immediate native detach response','delete failure recovery retained','deferred delete respected','native NDI/STA/monitor unchanged','PAS NDI host-only UP requires exact bound interface and legacy extension','invalid UP inputs rejected and monitor transport errors propagated'],
            'limitations':'Extracted actual native WMA peer create/delete/detach and UP functions with object, capability, transport and callbacks mocked. START/channel/MAC response changes receive full WLAN compile checks only. No actual peer lifecycle, firmware responses, vdev construction, scheduler, SSR or radio validation. Host-only owner still cannot activate an NDI session.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
