#!/usr/bin/env python3
"""Execute the production fixed-rate submitter with modeled native APIs only."""
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
typedef uint16_t u16;
typedef uint32_t u32;
#define ETH_ALEN 6
#define BIT(n) (1U << (n))
#define QDF_PASSTHRU_MODE 17
#define WLAN_VDEV_MLME_TYPE_NDI 58
#define WMI_RATE_PREAMBLE_HT 17
#define WMI_RATE_PREAMBLE_VHT 19
#define WMI_RATE_PREAMBLE_HE 23
#define WMI_RATE_PREAMBLE_EHT 29
#define VDEV_CMD 97
#define wmi_vdev_param_fixed_rate 101
#define wmi_vdev_param_sgi 103
#define wmi_vdev_param_chwidth 107
#include "wlan_hdd_mishare_rate.h"
struct vdev_mlme_obj;
struct wlan_objmgr_vdev {int refs,mode;u8 id;struct vdev_mlme_obj *mlme;void *psoc;};
struct vdev_mlme_obj {struct wlan_objmgr_vdev *vdev;void *ext_vdev_ptr;struct {struct {u8 type,subtype;} generic;} mgmt;};
static struct vdev_mlme_obj *wlan_vdev_mlme_get_cmpt_obj(struct wlan_objmgr_vdev *v){assert(v->refs);return v->mlme;}
static int wlan_vdev_mlme_get_opmode(struct wlan_objmgr_vdev *v){assert(v->refs);return v->mode;}
static u8 wlan_vdev_get_id(struct wlan_objmgr_vdev *v){assert(v->refs);return v->id;}
static int hdd_assemble_rate_code(u8 pre,u8 nss,u8 mcs){return (pre<<16)|(nss<<8)|mcs;}
#define QDF_MODULE_ID_WMA 61
struct iface_model {struct wlan_objmgr_vdev *vdev;};
static struct iface_model interfaces[64];
struct wma_model {void *psoc,*wmi_handle;struct iface_model *interfaces;u8 max_bssid;};
typedef struct wma_model *tp_wma_handle;
static struct wma_model wma;
static bool use_mc,wma_present=true,wma_valid=true;
static void *cds_get_context(int id){assert(id==61);return wma_present?&wma:NULL;}
static void *wlan_vdev_get_psoc(struct wlan_objmgr_vdev *v){return v->psoc;}
static bool wma_is_vdev_valid(u8 id){assert(id<64);return wma_valid;}
static int qdf_status_to_os_return(int s){return s;}
static unsigned calls,fail_at;
static int fail_error;
static u32 want_rate,want_gi;
static struct wlan_objmgr_vdev *target;
static const struct wondertap_fixed_tx_rate_params *params;
static struct mishare_rate_submission *receipt;
static int modeled_send(int id,int cmd,u32 value,int kind){
 const int commands[]={101,103,107};const u32 values[]={want_rate,want_gi,0};
 assert(calls<3 && id==target->id && kind==97 && cmd==commands[calls] && value==values[calls] && "EXPECTED_RATE_ORDER");
 assert(receipt->busy && receipt->attempted && !receipt->complete && receipt->vdev_id==id && "EXPECTED_RATE_RECEIPT");
 assert(receipt->attempted_mask==((1U<<(calls+1))-1) && receipt->submitted_mask==((1U<<calls)-1) && "EXPECTED_RATE_RECEIPT");
 unsigned before=calls;
 assert(mishare_rate_submit(target,params,receipt)==-EINPROGRESS && calls==before && "EXPECTED_RATE_REENTRANT");
 calls++;
 return calls==fail_at?fail_error:0;
}
static int wma_cli_set_command(int id,int cmd,u32 value,int kind){assert(!use_mc && "EXPECTED_RATE_NO_NESTED_QUEUE");return modeled_send(id,cmd,value,kind);}
static int wma_vdev_set_param(void *handle,u32 id,u32 cmd,u32 value){assert(use_mc && handle==wma.wmi_handle && "EXPECTED_RATE_DIRECT_WMI");return modeled_send(id,cmd,value,97);}
#include "wma_mishare_rate.h"
#include "wlan_hdd_mishare_rate.c"
static void run_case(struct wlan_objmgr_vdev *v,struct wondertap_fixed_tx_rate_params *p,unsigned fail,bool mc){
 struct mishare_rate_submission r={0};struct wondertap_fixed_tx_rate_params saved=*p;
 use_mc=mc;target=v;params=p;receipt=&r;calls=0;fail_at=fail;fail_error=fail==1?-EIO:fail==2?-ENOSPC:-ESHUTDOWN;
 int (*submit)(struct wlan_objmgr_vdev *,const struct wondertap_fixed_tx_rate_params *,struct mishare_rate_submission *)=mc?mishare_rate_submit_mc:mishare_rate_submit;
 int ret=submit(v,p,&r);
 assert(ret==(fail?fail_error:0) && r.first_error==ret && !r.busy && r.complete==!fail && "EXPECTED_RATE_ERROR");
 assert(calls==(fail?fail:3) && r.attempted_mask==((1U<<calls)-1) && r.submitted_mask==((1U<<(calls-(fail!=0)))-1) && "EXPECTED_RATE_ERROR");
 unsigned before=calls;
 assert(submit(v,p,&r)==(fail?fail_error:-EALREADY) && calls==before && "EXPECTED_RATE_REPLAY");
 assert(submit(NULL,NULL,&r)==(fail?fail_error:-EALREADY) && calls==before && "EXPECTED_RATE_REPLAY");
 assert(!memcmp(p,&saved,sizeof(saved)));
}
int main(void){
 struct wlan_objmgr_vdev v={.refs=1,.mode=17,.id=42};v.psoc=&v;wma.interfaces=interfaces;wma.psoc=&v;wma.wmi_handle=&wma;wma.max_bssid=64;wma.interfaces[42].vdev=&v;
 struct vdev_mlme_obj m={.vdev=&v,.ext_vdev_ptr=&v,.mgmt.generic.type=58};v.mlme=&m;
 struct wondertap_fixed_tx_rate_params p={.preamble=WONDERTAP_RATE_PREAMBLE_HE,.nss=1},bad;
 struct mishare_rate_submission r={0},zero=r;
 assert(mishare_rate_submit(&v,&p,NULL)==-EINVAL);
 assert(mishare_rate_submit(NULL,&p,&r)==-EINVAL && !memcmp(&r,&zero,sizeof(r)));
 assert(mishare_rate_submit(&v,NULL,&r)==-EINVAL && !memcmp(&r,&zero,sizeof(r)));
 const u8 limits[]={0,7,9,11,13},native[]={0,17,19,23,29};
 for(unsigned pre=1;pre<=4;pre++)for(unsigned nss=1;nss<=2;nss++)for(unsigned gi=0;gi<=4;gi++)for(unsigned edge=0;edge<2;edge++){
  if((pre<=2 && gi>1)||(pre>=3 && gi==1))continue;
  p.preamble=pre;p.nss=nss;p.gi=gi;p.mcs=edge?limits[pre]:0;
  want_rate=(native[pre]<<16)|((nss-1)<<8)|p.mcs;want_gi=gi==1?1:gi==3?2:gi==4?3:0;
  for(unsigned fail=0;fail<=3;fail++)for(unsigned mc=0;mc<2;mc++)run_case(&v,&p,fail,mc);
 }
 for(unsigned fault=0;fault<14;fault++){
  p=(struct wondertap_fixed_tx_rate_params){.preamble=WONDERTAP_RATE_PREAMBLE_HE,.nss=1};bad=p;
  int expected=-EOPNOTSUPP;
  switch(fault){
   case 0:bad.preamble=(enum wondertap_rate_preamble)-1;expected=-EINVAL;break;
   case 1:bad.preamble=WONDERTAP_RATE_PREAMBLE_MAX;expected=-EINVAL;break;
   case 2:bad.bw=(enum wondertap_rate_bw)-1;expected=-EINVAL;break;
   case 3:bad.gi=(enum wondertap_rate_gi)-1;expected=-EINVAL;break;
   case 4:bad.nss=0;expected=-EINVAL;break;
   case 5:bad.nss=9;expected=-EINVAL;break;
   case 6:bad.nss=3;break;
   case 7:bad.bw=WONDERTAP_RATE_BW_40;break;
   case 8:bad.preamble=WONDERTAP_RATE_PREAMBLE_LEGACY;break;
   case 9:bad.preamble=WONDERTAP_RATE_PREAMBLE_HT;bad.mcs=8;break;
   case 10:bad.preamble=WONDERTAP_RATE_PREAMBLE_VHT;bad.mcs=10;break;
   case 11:bad.mcs=12;break;
   case 12:bad.preamble=WONDERTAP_RATE_PREAMBLE_EHT;bad.mcs=14;break;
   case 13:bad.gi=WONDERTAP_RATE_GI_SHORT;break;
  }
  calls=0;r=zero;
  assert(mishare_rate_submit(&v,&bad,&r)==expected && !calls && !memcmp(&r,&zero,sizeof(r)) && "EXPECTED_RATE_PREFLIGHT");
 }
 p=(struct wondertap_fixed_tx_rate_params){.preamble=WONDERTAP_RATE_PREAMBLE_HT,.nss=1,.gi=WONDERTAP_RATE_GI_0_8_US};
 assert(mishare_rate_submit(&v,&p,&r)==-EOPNOTSUPP && !calls && "EXPECTED_RATE_PREFLIGHT");p.gi=0;
 for(unsigned fault=0;fault<6;fault++){
  struct vdev_mlme_obj foreign=m;calls=0;r=zero;
  if(fault==0)v.mode=1;
  if(fault==1)v.mlme=NULL;
  if(fault==2)m.vdev=NULL;
  if(fault==3)m.ext_vdev_ptr=NULL;
  if(fault==4)m.mgmt.generic.type=9;
  if(fault==5)m.mgmt.generic.subtype=1;
  assert(mishare_rate_submit(&v,&p,&r)==-EOPNOTSUPP && !calls && !memcmp(&r,&zero,sizeof(r)) && "EXPECTED_RATE_PARENT");
  m=foreign;v.mode=17;v.mlme=&m;
 }
 calls=0;
 for(unsigned fault=0;fault<8;fault++){
  if(fault==0)wma_present=false;
  if(fault==1)wma.psoc=NULL;
  if(fault==2)wma.interfaces[42].vdev=NULL;
  if(fault==3)wma.max_bssid=42;
  if(fault==4)wma_valid=false;
  if(fault==5)wma.wmi_handle=NULL;
  u32 cmd=fault==6?999:103,value=fault==7?4:0;
  assert(mishare_ndi_rate_command(&v,cmd,value)<0 && !calls && "EXPECTED_NATIVE_RATE_PARENT");
  wma_present=wma_valid=true;wma.psoc=&v;wma.interfaces[42].vdev=&v;wma.max_bssid=64;wma.wmi_handle=&wma;
 }
 assert(mishare_ndi_rate_command(&v,107,1)==-EOPNOTSUPP && !calls);
 assert(v.refs==1);
 puts("MISHARE_FIXED_RATE_FIXTURE_PASS_ONLY");return 0;
}
'''


def main():
    production=ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_rate.c'
    original=production.read_text()
    headers={'wma_mishare_rate.h':ROOT/'kernel/popsicle-hdd/wma_mishare_rate.h',
             'wlan_hdd_mishare_rate.h':ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_rate.h',
             'wlan_hdd_mishare_wonder_api.h':ROOT/'kernel/provider/wondertap.h'}
    mutations=[
        ('if (receipt->attempted)', 'if (false && receipt->attempted)'),
        ('if (ret)\n        goto finish;', 'if (false && ret)\n        goto finish;'),
        ('case WONDERTAP_RATE_GI_1_6_US: *gi = 2;', 'case WONDERTAP_RATE_GI_1_6_US: *gi = 3;'),
        ('preamble, p->nss - 1, p->mcs', 'preamble, p->nss, p->mcs'),
        ('WONDERTAP_RATE_BW_20);', 'WONDERTAP_RATE_BW_40);'),
        ('receipt->attempted_mask |= BIT(2);', 'receipt->submitted_mask |= BIT(2); receipt->attempted_mask |= BIT(2);'),
    ]
    native_mutations=[
        ('wma->psoc != wlan_vdev_get_psoc(vdev)', '(false && wma->psoc != wlan_vdev_get_psoc(vdev))'),
        ('wma->interfaces[id].vdev != vdev', '(false && wma->interfaces[id].vdev != vdev)'),
        ('!wma_is_vdev_valid(id)', '(false && !wma_is_vdev_valid(id))'),
        ('return qdf_status_to_os_return(wma_vdev_set_param(', 'return 0 * qdf_status_to_os_return(wma_vdev_set_param('),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        for name in ['wlan_objmgr_vdev_obj.h','wlan_vdev_mlme_api.h','wlan_vdev_mlme.h','wlan_hdd_main.h','wma_api.h','linux/if_ether.h']:
            (d/name).write_text('/* Native primitives modeled in harness. */\n')
        (d/'wlan_hdd_mishare_ndi.h').write_text('int mishare_ndi_rate_command(struct wlan_objmgr_vdev *,u32,u32);\n')
        (d/'linux/errno.h').write_text('#include_next <linux/errno.h>\n')
        for name,path in headers.items():(d/name).write_bytes(path.read_bytes())
        source=d/'test.c';source.write_text(HARNESS);body=d/production.name;body.write_text(original)
        exe=d/'test'
        command=['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+tmp,str(source),'-o',str(exe)]
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks='+('1' if os.environ.get('GITHUB_ACTIONS')=='true' else '0')+':abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        subprocess.run(command,check=True)
        result=subprocess.check_output([exe],text=True,env=env,timeout=10).strip()
        for needle,replacement in mutations:
            assert needle in original,needle
            body.write_text(original.replace(needle,replacement))
            subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=10)
            assert bad.returncode == -6 and 'EXPECTED_RATE_' in bad.stderr,(needle,bad.returncode,bad.stderr[-1200:])
        body.write_text(original)
        native_original=headers['wma_mishare_rate.h'].read_text()
        for needle,replacement in native_mutations:
            assert native_original.count(needle)==1,needle
            (d/'wma_mishare_rate.h').write_text(native_original.replace(needle,replacement))
            subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=10)
            assert bad.returncode == -6 and ('EXPECTED_RATE_' in bad.stderr or 'EXPECTED_NATIVE_RATE_' in bad.stderr),(needle,bad.returncode,bad.stderr[-1400:])
    report=ROOT/'.popsicle-ci/artifacts/reports/mishare-rate-fixture.json'
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps({'status':result,'mutation_controls':len(mutations),'native_wma_mutation_controls':len(native_mutations),'rate_scenarios':384,
        'production_sha256':hashlib.sha256(original.encode()).hexdigest(),
        'header_sha256':{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in headers.items()},
        'limitations':'Production executor and private native WMA helper with modeled VDEV/MLME, WMA binding, native rate encoder and WMI/CLI submissions. No firmware ACK, parent lifetime, platform rate capability, regulatory permission, radio or Apple certification. Local leak detection disabled for ptrace host; Actions enables it.'},indent=2)+'\n')
    print(result)


if __name__=='__main__':main()
