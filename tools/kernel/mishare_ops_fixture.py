#!/usr/bin/env python3
"""Actions-only typed PASSTHRU table and native host component create/destroy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from passthru_mode_fixture import enum, function, QDF, MLME
from popsicle_backend_audit import PIN
HEADER='qca-wifi-host-cmn/umac/mlme/include/wlan_vdev_mlme.h'
OBJ='qca-wifi-host-cmn/umac/mlme/mlme_objmgr/dispatcher/src/wlan_vdev_mlme_main.c'
CM='qca-wifi-host-cmn/umac/mlme/connection_mgr/core/src/wlan_cm_main.c'
COMMON=r'''
struct wlan_objmgr_psoc { int id; };
struct wlan_objmgr_pdev { struct wlan_objmgr_psoc *psoc; };
struct wlan_objmgr_vdev { struct { enum QDF_OPMODE vdev_opmode; } vdev_mlme; struct { uint8_t vdev_id; } vdev_objmgr; struct vdev_mlme_obj *component; };
struct vdev_ratemask_params { int dummy; };
#define WLAN_VDEV_RATEMASK_TYPE_MAX 1
#define WLAN_MD_OBJMGR_VDEV_MLME 1
#define WLAN_UMAC_COMP_MLME 1
#define QDF_TIMER_TYPE_WAKE_APPS 1
#define QDF_IS_STATUS_ERROR(s) ((s)!=QDF_STATUS_SUCCESS)
static int wlan_psoc_get_id(struct wlan_objmgr_psoc *p) { return p->id; }
#define mlme_err(...) ((void)wlan_psoc_get_id)
#define mlme_debug(...) ((void)0)
static enum QDF_OPMODE wlan_vdev_mlme_get_opmode(struct wlan_objmgr_vdev *v) { return v->vdev_mlme.vdev_opmode; }
static uint8_t wlan_vdev_get_id(struct wlan_objmgr_vdev *v) { return v->vdev_objmgr.vdev_id; }
'''
SUPPORT=r'''
static char trace[128];static int fault,live,sm_live,timer_live;static QDF_STATUS timer_status;
static void mark(char c) { size_t n=strlen(trace);assert(n+1<sizeof(trace));trace[n]=c;trace[n+1]=0; }
static struct wlan_objmgr_psoc psoc={1};
static struct wlan_objmgr_pdev pdev={&psoc};
static struct wlan_objmgr_pdev *wlan_vdev_get_pdev(struct wlan_objmgr_vdev *v) { assert(v);return &pdev; }
static struct wlan_objmgr_psoc *wlan_pdev_get_psoc(struct wlan_objmgr_pdev *p) { return p->psoc; }
static QDF_STATUS timer_inuse(struct wlan_objmgr_psoc *p,uint8_t id) { assert(p && id==7);mark('T');return timer_status; }
struct wlan_lmac_if_mlme_tx_ops { QDF_STATUS (*psoc_vdev_rsp_timer_inuse)(struct wlan_objmgr_psoc*,uint8_t); };
static struct wlan_lmac_if_mlme_tx_ops txops={timer_inuse};
static struct wlan_lmac_if_mlme_tx_ops *wlan_mlme_get_lmac_tx_ops(struct wlan_objmgr_psoc *p) { assert(p);return &txops; }
struct pdev_mlme_obj { QDF_STATUS (*mlme_register_ops)(struct vdev_mlme_obj*); };
static QDF_STATUS register_ops(struct vdev_mlme_obj *m) { mark('R');return mlme_register_vdev_mgr_ops(m); }
static struct pdev_mlme_obj pdev_mlme={register_ops};
static struct pdev_mlme_obj *wlan_pdev_mlme_get_cmpt_obj(struct wlan_objmgr_pdev *p) { assert(p);return &pdev_mlme; }
static void *qdf_mem_malloc(size_t n) { mark('M');if(fault==1)return NULL;live++;return calloc(1,n); }
static void qdf_mem_free(void *p) { assert(p && !timer_live && !((struct vdev_mlme_obj*)p)->vdev->component);mark('F');live--;free(p); }
static void wlan_minidump_log(void *p,size_t n,struct wlan_objmgr_psoc *s,int kind,const char *name) { assert(p && n && s && name); }
static void wlan_minidump_remove(void *p,size_t n,struct wlan_objmgr_psoc *s,int kind,const char *name) { assert(p && n && s && name); }
static QDF_STATUS mlme_vdev_sm_create(struct vdev_mlme_obj *m) { mark('S');assert(m->ops==&passthru_mlme_ops);if(fault==2)return QDF_STATUS_E_FAILURE;m->sm_hdl=malloc(1);assert(m->sm_hdl);sm_live++;return QDF_STATUS_SUCCESS; }
static QDF_STATUS mlme_vdev_sm_destroy(struct vdev_mlme_obj *m) { mark('s');assert(m->sm_hdl && sm_live==1);free(m->sm_hdl);m->sm_hdl=NULL;sm_live--;return QDF_STATUS_SUCCESS; }
static QDF_STATUS wlan_cm_init(struct vdev_mlme_obj *m) { mark('C');return cm_gate(wlan_vdev_mlme_get_opmode(m->vdev)); }
static QDF_STATUS wlan_cm_deinit(struct vdev_mlme_obj *m) { mark('c');return cm_gate(wlan_vdev_mlme_get_opmode(m->vdev)); }
static QDF_STATUS mlme_vdev_ops_ext_hdl_create(struct vdev_mlme_obj *vdev_mlme) {
 mark('E');assert(vdev_mlme->ops==&passthru_mlme_ops);
 CREATE_GATE
 abort();
}
static struct vdev_mlme_obj *wlan_vdev_mlme_get_cmpt_obj(struct wlan_objmgr_vdev *v) { return v->component; }
static struct wlan_objmgr_psoc *wlan_vdev_get_psoc(struct wlan_objmgr_vdev *v) { assert(v);return &psoc; }
static void mlme_vdev_reconfig_timer_cb(void *arg) { abort(); }
static void qdf_timer_init(void *a,int *b,void (*c)(void*),void *d,int e) { assert(!*b && !timer_live);mark('i');*b=1;timer_live++; }
static void qdf_timer_free(int *p) { assert(*p && timer_live==1);mark('f');*p=0;timer_live--; }
static void wlan_objmgr_vdev_component_obj_attach(struct wlan_objmgr_vdev *v,int type,void *p,QDF_STATUS s) { assert(!v->component && p && s==QDF_STATUS_SUCCESS);mark('A');v->component=p; }
static void wlan_objmgr_vdev_component_obj_detach(struct wlan_objmgr_vdev *v,int type,void *p) { assert(v->component==p);mark('a');v->component=NULL; }
static QDF_STATUS mlme_vdev_ops_ext_hdl_post_create(struct vdev_mlme_obj *m) { assert(m->vdev->component==m);mark('P');return fault==3?QDF_STATUS_E_FAILURE:QDF_STATUS_SUCCESS; }
static QDF_STATUS vdev_mgr_delete_send(struct vdev_mlme_obj *m) { abort(); }
static void mlme_wma_vdev_detach_handler(uint8_t id) { abort(); }
static void mlme_ext_handler_destroy(struct vdev_mlme_obj *m) { abort(); }
DESTROY_FUNCTION
static QDF_STATUS mlme_vdev_ops_ext_hdl_destroy(struct vdev_mlme_obj *m) { mark('D');return vdevmgr_mlme_ext_hdl_destroy(m); }
static void qdf_mem_set(void *p,size_t n,int byte) { assert(p && n && byte==0xff);mark('Z');memset(p,byte,n); }
'''
HARNESS=r'''
static void reset(int f,QDF_STATUS status) { assert(!live && !sm_live && !timer_live);fault=f;timer_status=status;trace[0]=0; }
static void host_cycle(struct wlan_objmgr_vdev *v,QDF_STATUS status) {
 reset(0,status);
 assert(mlme_vdev_obj_create_handler(v,NULL)==QDF_STATUS_SUCCESS);
 assert(!strcmp(trace,"TMRSCEiAPZ") && live==1 && sm_live==1 && timer_live==1);
 assert(v->component && v->component->ops==&passthru_mlme_ops && !v->component->ext_vdev_ptr);
 assert(v->component->mgmt.generic.type==9 && !v->component->mgmt.generic.subtype);
 assert((unsigned)v->component->mgmt.rate_info.ratemask_params[0].dummy==0xffffffffU);
 assert(mlme_vdev_obj_destroy_handler(v,NULL)==QDF_STATUS_SUCCESS);
 assert(!strcmp(trace,"TMRSCEiAPZfcsDaF") && !v->component && !live && !sm_live && !timer_live);
 assert(mlme_vdev_obj_destroy_handler(v,NULL)==QDF_STATUS_SUCCESS);
}
int main(void) {
 struct wlan_objmgr_vdev v={.vdev_mlme={.vdev_opmode=QDF_PASSTHRU_MODE},.vdev_objmgr={.vdev_id=7}};
 struct vdev_mlme_obj m={.vdev=&v,.ops=&sta_mlme_ops,.sm_hdl=(void*)1};
 assert(mlme_register_vdev_mgr_ops(&m)==QDF_STATUS_SUCCESS && m.ops==&passthru_mlme_ops);
 CALLBACK_TESTS
 assert(m.sm_hdl==(void*)1 && m.ops==&passthru_mlme_ops);
 assert(cm_gate(QDF_PASSTHRU_MODE)==QDF_STATUS_SUCCESS);
 assert(cm_gate(QDF_STA_MODE)==QDF_STATUS_E_FAILURE && cm_gate(QDF_P2P_CLIENT_MODE)==QDF_STATUS_E_FAILURE);
 reset(0,QDF_STATUS_SUCCESS);assert(mlme_vdev_obj_create_handler(NULL,NULL)==QDF_STATUS_E_FAILURE && !trace[0]);
 assert(mlme_vdev_obj_destroy_handler(NULL,NULL)==QDF_STATUS_E_FAILURE);
 assert(vdevmgr_mlme_ext_hdl_destroy(NULL)==QDF_STATUS_E_INVAL);
 m.vdev=NULL;assert(vdevmgr_mlme_ext_hdl_destroy(&m)==QDF_STATUS_E_INVAL);m.vdev=&v;
 m.ext_vdev_ptr=(void*)1;assert(vdevmgr_mlme_ext_hdl_destroy(&m)==QDF_STATUS_E_BUSY);m.ext_vdev_ptr=NULL;
 host_cycle(&v,QDF_STATUS_SUCCESS);host_cycle(&v,QDF_STATUS_E_ALREADY);
 reset(1,QDF_STATUS_SUCCESS);assert(mlme_vdev_obj_create_handler(&v,NULL)==QDF_STATUS_E_NOMEM);assert(!strcmp(trace,"TM") && !v.component && !live && !sm_live);
 reset(2,QDF_STATUS_SUCCESS);assert(mlme_vdev_obj_create_handler(&v,NULL)==QDF_STATUS_E_FAILURE);assert(!strcmp(trace,"TMRSF") && !v.component && !live && !sm_live);
 reset(3,QDF_STATUS_SUCCESS);assert(mlme_vdev_obj_create_handler(&v,NULL)==QDF_STATUS_E_FAILURE);assert(!strcmp(trace,"TMRSCEiAPfDacsF") && !v.component && !live && !sm_live && !timer_live);
 reset(0,QDF_STATUS_E_BUSY);assert(mlme_vdev_obj_create_handler(&v,NULL)==QDF_STATUS_E_FAILURE);assert(!strcmp(trace,"T") && !v.component && !live && !sm_live);
 puts("MISHARE_DEDICATED_OPS_FIXTURE_PASS_ONLY");return 0;
}
'''



def inputs(root):
    read=lambda p:(root/p).read_text()
    header=read(HEADER);struct=re.search(r'struct vdev_mlme_ops\s*\{.*?\n\};',header,re.S)[0]
    fields=re.findall(r'(QDF_STATUS|void)\s*\(\*(\w+)\)\s*\((.*?)\);',struct,re.S)
    if len(fields)!=32:raise ValueError('Review changed callback inventory')
    text=read(MLME);start=text.index('/* Dedicated host-only PASSTHRU table.')
    end=re.search(r'static struct vdev_mlme_ops passthru_mlme_ops = \{.*?\n\};',text,re.S).end()
    table=text[start:end]
    gate=re.search(r'\tif \(wlan_vdev_mlme_get_opmode\(vdev_mlme->vdev\) == QDF_PASSTHRU_MODE\) \{.*?\n\t\}',function(text,'vdevmgr_mlme_ext_hdl_create'),re.S)[0]
    cm_guard=r'if \(op_mode != QDF_STA_MODE && op_mode != QDF_P2P_CLIENT_MODE\)\s+return QDF_STATUS_SUCCESS;'
    cm_init=re.search(cm_guard,function(read(CM),'wlan_cm_init'))[0]
    cm_deinit=re.search(cm_guard,function(read(CM),'wlan_cm_deinit'))[0]
    if cm_init!=cm_deinit:raise ValueError('CM init/deinit mode guards diverged')
    return struct,fields,table,gate,cm_init


def fixture(root):
    read=lambda p:(root/p).read_text()
    struct,fields,table,gate,cm_guard=inputs(root)
    status=re.search(r'typedef enum\s*\{[^}]+\}\s*QDF_STATUS;',read('qca-wifi-host-cmn/qdf/inc/qdf_status.h'),re.S)[0]
    code='#include <assert.h>\n#include <stdint.h>\n#include <stdbool.h>\n#include <stdlib.h>\n#include <stdio.h>\n#include <string.h>\n'
    code+=enum(read(QDF),'QDF_OPMODE')+'\n'+status+'\n#define WLAN_VDEV_MLME_TYPE_PASSTHRU 9\n'
    for name in ['beacon_update_op','vdev_cmd_type']:code+=enum(read(HEADER),name)+'\n'
    for name in ['vdev_mlme_obj','wlan_objmgr_vdev','vdev_stop_response','vdev_start_response','peer_delete_all_response','ml_rv_info']:code+='struct '+name+';\n'
    code+=struct+'\n'+COMMON
    code+='struct vdev_mlme_obj { struct wlan_objmgr_vdev *vdev;struct vdev_mlme_ops *ops;void *sm_hdl;void *ext_vdev_ptr;int ml_reconfig_timer;struct { struct { uint8_t type,subtype; } generic;struct { struct vdev_ratemask_params ratemask_params[1]; } rate_info; } mgmt; };\n'
    code+='static struct vdev_mlme_ops sta_mlme_ops,ap_mlme_ops,mon_mlme_ops;\n'+table+'\n'
    code+=function(read(MLME),'mlme_is_vdev_in_beaconning_mode')+'\n'+function(read(MLME),'mlme_register_vdev_mgr_ops')+'\n'
    code+='static QDF_STATUS cm_gate(enum QDF_OPMODE op_mode) {\n'+cm_guard+'\nreturn QDF_STATUS_E_FAILURE;\n}\n'
    code+=SUPPORT.replace('CREATE_GATE',gate).replace('DESTROY_FUNCTION',function(read(MLME),'vdevmgr_mlme_ext_hdl_destroy'))+'\n'+function(read(OBJ),'mlme_vdev_obj_create_handler')+'\n'+function(read(OBJ),'mlme_vdev_obj_destroy_handler')+'\n'
    tests=[]
    for ret,name,args in fields:
        values=[]
        for arg in args.split(','):
            if re.search(r'\bvdev_mlme\s*$',arg):values.append('&m')
            elif '*' in arg:values.append('NULL')
            else:values.append('0')
        call='m.ops->'+name+'('+','.join(values)+')'
        tests.append('assert(m.ops->'+name+');\n'+('assert('+call+'==QDF_STATUS_E_NOSUPPORT);' if ret=='QDF_STATUS' else call+';'))
    return code+HARNESS.replace('CALLBACK_TESTS','\n'.join(tests))


def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('Unexpected source commit')
    source=fixture(root)
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'ops.c';p.write_text(source);exe=Path(tmp)/'ops'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-g','-fsanitize=address,undefined',str(p),'-o',str(exe)],check=True)
        output=subprocess.check_output([exe],text=True,timeout=15,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
        if output.strip()!='MISHARE_DEDICATED_OPS_FIXTURE_PASS_ONLY':raise ValueError('Unexpected output')
    _,fields,_,_,_=inputs(root)
    return {'status':'MISHARE_DEDICATED_OPS_FIXTURE_PASS_ONLY','source_commit':PIN,
      'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
      'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [MLME,HEADER,OBJ,CM]},
      'callback_count':len(fields),'status_callbacks_explicitly_unsupported':sum(ret=='QDF_STATUS' for ret,_,_ in fields),'void_callbacks_no_completion':sum(ret=='void' for ret,_,_ in fields),
      'callbacks':[name for _,name,_ in fields],
      'checks':['dedicated table selected','every callback nonnull and typed','all status callbacks NOSUPPORT','void notifications do not mutate model','native CM init/deinit guards skip PASSTHRU','actual object-create/destroy handlers attach and reclaim host-only MLME without commands','context allocation failure','SM allocation failure','timer already/busy paths','post-create failure reverses reconfig timer/extension/component/SM/context','host-only destroy never sends firmware DELETE'],
      'limitations':'Actual typed production table/registration and full object-create handler with SM/allocation/component stubs, actual CM mode guards and actual ext-create host branch and full ext-destroy function. Not full CM/SM/timer execution, native locking/IRQ, full object-manager vdev construction, command binding, WMI or AirDrop certification.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
