#!/usr/bin/env python3
"""Production retry executor + pinned SME/WMA loops; WMI send boundary modeled."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef int QDF_STATUS;
typedef int wmi_vdev_custom_sw_retry_type_t;
#define QDF_STATUS_SUCCESS 0
#define QDF_STATUS_E_FAILURE (-EIO)
#define QDF_IS_STATUS_ERROR(s) ((s)!=0)
#define BIT(n) (1U<<(n))
#define QDF_PASSTHRU_MODE 17
#define WLAN_VDEV_MLME_TYPE_NDI 58
#define QDF_MODULE_ID_WMA 61
#define WMI_VDEV_CUSTOM_SW_RETRY_TYPE_AGGR 3
#define WMI_VDEV_CUSTOM_SW_RETRY_TYPE_NONAGGR 7
#define WMI_AC_MAX 4
#define sme_err(...) ((void)0)
#include "wlan_hdd_mishare_retry.h"
struct vdev_mlme_obj;
struct wlan_objmgr_vdev {int mode;u8 id;void *psoc;struct vdev_mlme_obj *mlme;};
struct vdev_mlme_obj {struct wlan_objmgr_vdev *vdev;void *ext_vdev_ptr;struct {struct {u8 type,subtype;} generic;} mgmt;};
struct iface {struct wlan_objmgr_vdev *vdev;};
struct wma_model {void *psoc,*wmi_handle;struct iface *interfaces;u8 max_bssid;};
typedef struct wma_model *tp_wma_handle;
static struct wma_model wma;
static bool present=true,valid=true;
static struct iface interfaces[64];
static void *cds_get_context(int id){assert(id==61);return present?&wma:NULL;}
static u8 wlan_vdev_get_id(struct wlan_objmgr_vdev *v){return v->id;}
static void *wlan_vdev_get_psoc(struct wlan_objmgr_vdev *v){return v->psoc;}
static struct vdev_mlme_obj *wlan_vdev_mlme_get_cmpt_obj(struct wlan_objmgr_vdev *v){return v->mlme;}
static int wlan_vdev_mlme_get_opmode(struct wlan_objmgr_vdev *v){return v->mode;}
static bool wma_is_vdev_valid(u8 id){assert(id<64);return valid;}
static int qdf_status_to_os_return(int s){return s;}
static unsigned calls,fail_at;
static u8 data,mgmt;
static struct wlan_objmgr_vdev *target;
static struct mishare_retry_submission *receipt;
static int wma_set_sw_retry_by_qos(tp_wma_handle h,u8 id,int type,u32 ac,u32 value){
 unsigned group=data && calls<4?0:1;
 assert(h==&wma && id==42 && ac==calls%4 && value==(group?mgmt:data) && type==(group?7:3) && "EXPECTED_RETRY_MAPPING");
 assert(receipt->busy && receipt->attempted && !receipt->complete && receipt->vdev_id==42 && "EXPECTED_RETRY_RECEIPT");
 assert(receipt->attempted_mask & BIT(group));
 assert(mishare_retry_submit_mc(target,255,255,receipt)==-EINPROGRESS && "EXPECTED_RETRY_REENTRY");
 calls++;
 return calls==fail_at?-ENOSPC:0;
}
NATIVE_FUNCTIONS
#include "wlan_hdd_mishare_retry.c"
int main(void){
 struct wlan_objmgr_vdev v={.mode=17,.id=42};v.psoc=&v;
 struct vdev_mlme_obj m={.vdev=&v,.ext_vdev_ptr=&v,.mgmt.generic.type=58};v.mlme=&m;
 wma=(struct wma_model){.psoc=&v,.wmi_handle=&wma,.interfaces=interfaces,.max_bssid=64};interfaces[42].vdev=&v;
 struct mishare_retry_submission r={0},zero=r;target=&v;receipt=&r;
 const u8 values[]={0,1,15,255};unsigned cases=0;
 for(unsigned d=0;d<4;d++)for(unsigned g=0;g<4;g++){
  data=values[d];mgmt=values[g];unsigned total=4*((data!=0)+(mgmt!=0));
  for(unsigned failure=0;failure<=total;failure++){
   r=zero;calls=0;fail_at=failure;
   int ret=mishare_retry_submit_mc(&v,data,mgmt,&r);
   assert(ret==(failure?-ENOSPC:0) && r.first_error==ret && r.complete==!failure && !r.busy && "EXPECTED_RETRY_ERROR");
   assert(calls==(failure?failure:total) && r.data_limit==data && r.mgmt_limit==mgmt && "EXPECTED_RETRY_STOP");
   unsigned attempted=0,submitted=0,skipped=0;
   for(unsigned group=0;group<2;group++){
    unsigned count=group?mgmt:data;
    unsigned start=group && data?4:0;
    if(failure && failure<=start)break;
    if(!count){skipped|=BIT(group);continue;}
    attempted|=BIT(group);
    if(!failure || failure>start+4)submitted|=BIT(group);
   }
   assert(r.attempted_mask==attempted && r.submitted_mask==submitted && r.skipped_mask==skipped && "EXPECTED_RETRY_MASK");
   unsigned before=calls;
   assert(mishare_retry_submit_mc(NULL,0,0,&r)==(failure?-ENOSPC:-EALREADY) && calls==before && "EXPECTED_RETRY_REPLAY");
   cases++;
  }
 }
 for(unsigned fault=0;fault<15;fault++){
  r=zero;calls=0;struct wlan_objmgr_vdev savedv=v;struct vdev_mlme_obj savedm=m;struct wma_model savedw=wma;
  if(fault==0)present=false;if(fault==1)wma.psoc=NULL;if(fault==2)wma.interfaces=NULL;
  if(fault==3)wma.wmi_handle=NULL;if(fault==4)wma.max_bssid=42;if(fault==5)interfaces[42].vdev=NULL;
  if(fault==6)valid=false;if(fault==7)v.mode=1;if(fault==8)v.mlme=NULL;
  if(fault==9)m.vdev=NULL;if(fault==10)m.ext_vdev_ptr=NULL;if(fault==11)m.mgmt.generic.type=9;
  if(fault==12)m.mgmt.generic.subtype=1;
  int ret=mishare_retry_submit_mc(fault==13?NULL:&v,1,1,fault==14?NULL:&r);
  assert(ret<0 && !calls && !memcmp(&r,&zero,sizeof(r)) && "EXPECTED_RETRY_ADMISSION");
  present=valid=true;v=savedv;m=savedm;wma=savedw;interfaces[42].vdev=&v;
 }
 printf("MISHARE_RETRY_FIXTURE_PASS_ONLY cases=%u admission=15\n",cases);return 0;
}
'''

def function(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]

def source(wlan):
    native = function((wlan/'qcacld-3.0/core/wma/src/wma_features.c').read_text(), 'QDF_STATUS wma_set_vdev_sw_retry_th(')
    native += '\n' + function((wlan/'qcacld-3.0/core/sme/src/common/sme_api.c').read_text(), 'QDF_STATUS sme_set_vdev_sw_retry(')
    return HARNESS.replace('NATIVE_FUNCTIONS', native, 1)

def main():
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert os.environ.get('GITHUB_ACTIONS')=='true', 'Native compilation runs on Actions only'
    production=ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_retry.c';original=production.read_text()
    mutations=[('if (receipt->attempted)', 'if (false && receipt->attempted)'),
               ('if (!value)', 'if (false && !value)'),
               ('if (ret)\n            break;', 'if (false && ret)\n            break;'),
               ('group ? WMI_VDEV_CUSTOM_SW_RETRY_TYPE_NONAGGR :', 'group ? WMI_VDEV_CUSTOM_SW_RETRY_TYPE_AGGR :'),
               ('wma->interfaces[id].vdev != vdev', '(false && wma->interfaces[id].vdev != vdev)'),
               ('receipt->submitted_mask |= BIT(group);', 'receipt->submitted_mask |= BIT(0);')]
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        for name in ['linux/types.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme_api.h','wlan_vdev_mlme.h','wlan_hdd_main.h','wma.h','wma_api.h','wma_internal.h','sme_api.h']:(d/name).write_text('/* modeled boundary */\n')
        (d/'linux/errno.h').write_text('#include_next <linux/errno.h>\n')
        (d/'wlan_hdd_mishare_retry.h').write_bytes((ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_retry.h').read_bytes())
        (d/'test.c').write_text(source(a.wlan));body=d/production.name;body.write_text(original)
        exe=d/'test';cmd=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+tmp,str(d/'test.c'),'-o',str(exe)]
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        subprocess.run(cmd,check=True);result=subprocess.check_output([exe],env=env,text=True,timeout=10).strip()
        for needle,replacement in mutations:
            assert original.count(needle)==1,needle
            body.write_text(original.replace(needle,replacement,1));subprocess.run(cmd,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=10)
            assert bad.returncode==-6 and 'EXPECTED_RETRY_' in bad.stderr,(needle,bad.returncode,bad.stderr[-1400:])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps({'status':result,'mutations':len(mutations),'production_sha256':hashlib.sha256(original.encode()).hexdigest(),'limitations':'Actual production executor and pinned SME/WMA group loop; WMI per-AC send boundary modeled. No firmware ACK, radio, automatic work/lifetime integration or phone proof.'},indent=2)+'\n');print(result)
if __name__=='__main__':main()
