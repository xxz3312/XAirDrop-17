#!/usr/bin/env python3
"""Actions-only canonical request bridge and production native-policy preflight."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import mishare_bridge_fixture as legacy
from mishare_recovery_fixture import function
ROOT=legacy.ROOT
MODEL=r'''
static unsigned preflights,prepared_steps;
static int policy_error,prepared_result,bssid_result,retry_result;
static unsigned retry_steps;
static struct mishare_request_bridge *request_control;
int mishare_wonder_host_retry_step_locked(struct mishare_wonder_host *o,u8 d,u8 m) {
 assert(parent_lease && o==&host && request_control && !prepared_result &&
  d==request_control->request.params.data_retry_limit && m==request_control->request.params.mgmt_retry_limit &&
  "EXPECTED_REQUEST_BRIDGE_RETRY_SOURCE");retry_steps++;return retry_result;
}
int mishare_wonder_host_bssid_bind_locked(struct mishare_wonder_host *o,const u8 *b) {assert(o==&host && request_control && b==request_control->request.params.bssid);return bssid_result;}
int mishare_wonder_request_preflight_locked(struct hdd_context *h,const struct mishare_init_request *q,u8 a,u8 b) {
 assert(parent_lease && h==&parent && q && a==1 && b==2);preflights++;return policy_error;
}
int mishare_wonder_host_prestart_step_locked(struct mishare_wonder_host *o,u32 f,u8 a,u8 b,
                                            const struct wondertap_fixed_tx_rate_params *p) {
 assert(parent_lease && o==&host && f==5240 && a==1 && b==2 && request_control &&
  p==&request_control->request.params.tx_rate && "EXPECTED_REQUEST_BRIDGE_FROZEN_SOURCE");
 prepared_steps++;return prepared_result;
}
static struct mishare_init_request input;
static void request_reset(struct mishare_request_bridge *c) {
 memset(c,0,sizeof(*c));reset(&c->bridge);request_control=c;
 preflights=prepared_steps=retry_steps=0;policy_error=bssid_result=retry_result=0;prepared_result=-EINPROGRESS;
 struct wondertap_init_params p={.channel={.freq=5240},.tx_rate={.preamble=WONDERTAP_RATE_PREAMBLE_HT,.nss=1,.mcs=7},
  .mgmt_retry_limit=3,.data_retry_limit=5};
 memcpy(p.mac_addr,mac,6);p.bssid[5]=7;memcpy(p.country_code,"CN",3);assert(!mishare_init_parse(&p,&input));
}
static int request_step(struct mishare_request_bridge *c) {
 return mishare_request_bridge_step_locked(c,&parent,&input,1,2);
}
static void request_cases(void) {
 struct mishare_request_bridge c;
 for(unsigned mode=0;mode<8;mode++) {
  request_reset(&c);input.params.mgmt_retry_limit=(mode&1)?0:3;input.params.data_retry_limit=(mode&2)?0:5;
  if(mode&4){input.params.tx_rate.preamble=WONDERTAP_RATE_PREAMBLE_HE;input.params.tx_rate.mcs=11;}
  assert(request_step(&c)==-EINPROGRESS && c.bound && c.bridge.prestart_mode && c.bridge.attempted &&
   creates==1 && !attaches && !prepared_steps && "EXPECTED_REQUEST_BRIDGE_BIND");
  assert(step(&c.bridge)==-EBUSY && !attaches && !steps && "EXPECTED_REQUEST_BRIDGE_NO_RAW_START");
  assert(request_step(&c)==-EINPROGRESS && attaches==1 && !prepared_steps && "EXPECTED_REQUEST_BRIDGE_ATTACH");
  assert(request_step(&c)==-EINPROGRESS && request_step(&c)==-EINPROGRESS && prepared_steps==2 &&
   creates==1 && attaches==1 && !steps && preflights==4 && "EXPECTED_REQUEST_BRIDGE_PREPARE_ONLY");
  prepared_result=0;retry_result=-EINPROGRESS;
  assert(request_step(&c)==-EINPROGRESS && retry_steps==1 && !steps && "EXPECTED_REQUEST_BRIDGE_RETRY_WAIT");
  retry_result=0;assert(!request_step(&c) && retry_steps==2 && !steps && "EXPECTED_REQUEST_BRIDGE_READY_NOT_INIT");
  destroy_ret=-EINPROGRESS;
  assert(retire(&c.bridge)==-EINPROGRESS && c.bridge.host==&host && request_step(&c)==-ESHUTDOWN &&
   "EXPECTED_REQUEST_BRIDGE_CLOSE");
  destroy_ret=0;assert(!retire(&c.bridge) && !c.bridge.host && c.bridge.retired && "EXPECTED_REQUEST_BRIDGE_RETIRE");
 }
 for(unsigned flags=1;flags<4;flags++) {
  request_reset(&c);input.params.amsdu_enable=flags&1;input.params.ampdu_enable=!!(flags&2);
  assert(request_step(&c)==-EOPNOTSUPP && !c.bound && !c.bridge.attempted && !creates && !preflights &&
   !attaches && !retry_steps && "EXPECTED_REQUEST_BRIDGE_AGGREGATION_REFUSAL");
 }
 request_reset(&c);policy_error=-EOPNOTSUPP;
 assert(request_step(&c)==-EOPNOTSUPP && !c.bound && !c.bridge.attempted && !creates && "EXPECTED_REQUEST_BRIDGE_POLICY_FIRST");
 policy_error=0;assert(request_step(&c)==-EINPROGRESS);unsigned before=preflights;
 for(unsigned field=0;field<15;field++) {
  struct mishare_init_request changed=input;
  switch(field) {
   case 0:changed.params.channel.freq=5180;break;
   case 1:changed.params.channel.bandwidth=WONDERTAP_RATE_BW_40;break;
   case 2:changed.params.tx_rate.preamble=WONDERTAP_RATE_PREAMBLE_HE;break;
   case 3:changed.params.tx_rate.bw=WONDERTAP_RATE_BW_40;break;
   case 4:changed.params.tx_rate.gi=WONDERTAP_RATE_GI_SHORT;break;
   case 5:changed.params.tx_rate.nss=2;break;
   case 6:changed.params.tx_rate.mcs=6;break;
   case 7:changed.params.mac_addr[5]^=1;break;
   case 8:changed.params.bssid[5]^=1;break;
   case 9:memcpy(changed.params.country_code,"JP",3);break;
   case 10:changed.params.mgmt_retry_limit++;break;
   case 11:changed.params.data_retry_limit++;break;
   case 12:changed.params.amsdu_enable=true;break;
   case 13:changed.params.ampdu_enable=true;break;
   case 14:changed.params.rate_adaptation_enable=true;changed.params.tx_rate_mask.max_nss=1;break;
  }
  assert(mishare_request_bridge_step_locked(&c,&parent,&changed,1,2)==-EBUSY &&
   preflights==before && !attaches && "EXPECTED_REQUEST_BRIDGE_IMMUTABLE");
 }
 struct mishare_init_request normalized=input;normalized.params.tx_rate.reserved[0]=99;
 normalized.params.tx_rate_mask.max_mcs=14; /* inactive mask must normalize away */
 assert(mishare_request_bridge_step_locked(&c,&parent,&normalized,1,2)==-EINPROGRESS && attaches==1 && "EXPECTED_REQUEST_BRIDGE_CANONICAL");
 policy_error=-ESHUTDOWN;before=preflights;
 assert(request_step(&c)==-ESHUTDOWN && c.bridge.host==&host && !prepared_steps && "EXPECTED_REQUEST_BRIDGE_POLICY_RECHECK");
 policy_error=0;assert(request_step(&c)==-ESHUTDOWN && preflights==before+1 && "EXPECTED_REQUEST_BRIDGE_POLICY_STICKY");
 assert(!retire(&c.bridge));
 for(unsigned stage=0;stage<3;stage++) {
  request_reset(&c);
  if(stage==0){create_ret=-ENOMEM;retained_create=true;}
  if(stage==1)attach_ret=-EIO;
  if(stage==2)prepared_result=-EUCLEAN;
  for(unsigned i=0;i<stage;i++)assert(request_step(&c)==-EINPROGRESS);
  int expected=stage==0?-ENOMEM:stage==1?-EIO:-EUCLEAN;
  assert(request_step(&c)==expected && c.bridge.host==&host && "EXPECTED_REQUEST_BRIDGE_PARTIAL_OWNER");
  before=creates+attaches+prepared_steps;
  assert(request_step(&c)==expected && before==creates+attaches+prepared_steps && "EXPECTED_REQUEST_BRIDGE_NO_RETRY");
  assert(!retire(&c.bridge) && destroys==1);
 }
 request_reset(&c);assert(request_step(&c)==-EINPROGRESS && request_step(&c)==-EINPROGRESS);
 bssid_result=-EINPROGRESS;
 assert(request_step(&c)==-EINPROGRESS && !prepared_steps && !c.bridge.start_error && "EXPECTED_REQUEST_BRIDGE_BSSID_WAIT");
 bssid_result=0;assert(request_step(&c)==-EINPROGRESS && prepared_steps==1 && "EXPECTED_REQUEST_BRIDGE_BSSID_RESUME");
 bssid_result=-EUCLEAN;
 assert(request_step(&c)==-EUCLEAN && request_step(&c)==-EUCLEAN && prepared_steps==1 && c.bridge.host==&host &&
  "EXPECTED_REQUEST_BRIDGE_BSSID_ERROR_RETAIN");assert(!retire(&c.bridge));
 request_reset(&c);assert(request_step(&c)==-EINPROGRESS && request_step(&c)==-EINPROGRESS);
 prepared_result=0;retry_result=-EIO;
 assert(request_step(&c)==-EIO && retry_steps==1 && c.bridge.host==&host && "EXPECTED_REQUEST_BRIDGE_RETRY_RETAIN");
 retry_result=0;assert(request_step(&c)==-EIO && retry_steps==1 && "EXPECTED_REQUEST_BRIDGE_RETRY_STICKY");
 assert(!retire(&c.bridge));
 request_reset(&c);c.bridge.host=&host;
 assert(request_step(&c)==-EBUSY && !c.bound && !creates && "EXPECTED_REQUEST_BRIDGE_NO_ADOPTION");
 request_reset(&c);assert(request_step(&c)==-EINPROGRESS);c.bridge.freq++;
 assert(request_step(&c)==-EUCLEAN && !attaches && "EXPECTED_REQUEST_BRIDGE_PROJECTION_DRIFT");assert(!retire(&c.bridge));
 request_reset(&c);assert(request_step(&c)==-EINPROGRESS);
 assert(mishare_bridge_handoff_idle_locked(&c.bridge,&parent)==-EINPROGRESS && !c.bridge.host && request_step(&c)==-ESHUTDOWN);
 parent_lease=false;receipt_result=0;assert(!mishare_bridge_retire_locked(&c.bridge,NULL));parent_lease=true;
}
struct mishare_managed_instance {
 struct mishare_request_bridge request_bridge;
 struct mishare_init_request request;
 u8 request_nss_2g,request_nss_5g;
 void *dev;bool busy,request_prepared,pins;
};
struct mishare_bridge_scope {struct hdd_context *hdd;};
static struct mishare_managed_instance managed;
static int managed_scope_error,managed_context_error;
static unsigned managed_claims,managed_releases,managed_scopes,managed_ends;
static bool managed_entered;
static int mishare_instance_claim(void *handle,struct mishare_managed_instance **out) {
 if(handle!=&managed)return -EINVAL;
 if(managed.busy)return -EINPROGRESS;
 assert(managed.pins && "EXPECTED_MANAGED_REQUEST_PINS");managed.busy=true;managed_claims++;*out=&managed;return 0;
}
static void mishare_instance_release(struct mishare_managed_instance *m) {
 assert(m==&managed && m->busy && !managed_entered && "EXPECTED_MANAGED_REQUEST_RELEASE_ORDER");m->busy=false;managed_releases++;
}
static int mishare_bridge_scope_begin(struct mishare_bridge_scope *s,void *d) {
 assert(d==&managed && managed.busy && !managed_entered && "EXPECTED_MANAGED_REQUEST_SCOPE");managed_scopes++;
 if(managed_scope_error)return managed_scope_error;
 managed_entered=true;s->hdd=&parent;return 0;
}
static void mishare_bridge_scope_end(struct mishare_bridge_scope *s) {
 assert(managed_entered && s->hdd==&parent && "EXPECTED_MANAGED_REQUEST_SCOPE_END");managed_entered=false;managed_ends++;
}
static int wlan_hdd_validate_context(struct hdd_context *h) {assert(managed_entered && h==&parent);return managed_context_error;}
MANAGED_FUNCTION
static void managed_request_reset(void) {
 managed=(struct mishare_managed_instance){0};request_reset(&managed.request_bridge);
 managed.dev=&managed;managed.pins=managed.request_prepared=true;managed.request=input;
 managed.request_nss_2g=1;managed.request_nss_5g=2;managed_scope_error=managed_context_error=0;
 managed_claims=managed_releases=managed_scopes=managed_ends=0;managed_entered=false;
}
static int managed_step(void) {
 int ret=mishare_wonder_managed_prestart_step(&managed);
 assert(!managed.busy && !managed_entered && managed_claims==managed_releases && managed.pins &&
  managed_ends==managed_scopes-(managed_scope_error!=0) && "EXPECTED_MANAGED_REQUEST_BALANCE");return ret;
}
static void managed_request_cases(void) {
 for(unsigned mode=0;mode<8;mode++) {
  managed_request_reset();managed.request.params.data_retry_limit=mode&1?0:5;managed.request.params.mgmt_retry_limit=mode&2?0:3;
  if(mode&4){managed.request.params.tx_rate.preamble=WONDERTAP_RATE_PREAMBLE_HE;managed.request.params.tx_rate.mcs=11;}
  assert(managed_step()==-EINPROGRESS && creates==1 && managed.request_bridge.bound && "EXPECTED_MANAGED_REQUEST_CREATE");
  assert(managed_step()==-EINPROGRESS && attaches==1 && "EXPECTED_MANAGED_REQUEST_ATTACH");
  prepared_result=0;retry_result=-EINPROGRESS;
  assert(managed_step()==-EINPROGRESS && retry_steps==1 && "EXPECTED_MANAGED_REQUEST_RETRY_WAIT");
  retry_result=0;assert(!managed_step() && retry_steps==2 && !steps && "EXPECTED_MANAGED_REQUEST_PRESTART_ONLY");
  assert(!retire(&managed.request_bridge.bridge));unsigned before=managed_scopes;
  assert(managed_step()==-ESHUTDOWN && managed_scopes==before && "EXPECTED_MANAGED_REQUEST_CLOSE");
 }
 for(unsigned fault=0;fault<9;fault++) {
  managed_request_reset();int expected=-EBUSY;
  if(fault==0){managed.busy=true;assert(mishare_wonder_managed_prestart_step(&managed)==-EINPROGRESS && !managed_scopes);managed.busy=false;continue;}
  if(fault==1){managed.request_prepared=false;expected=-EINVAL;}
  if(fault==2){managed.request_bridge.bridge.closing=true;expected=-ESHUTDOWN;}
  if(fault==3){managed_scope_error=-EAGAIN;expected=-EAGAIN;}
  if(fault==4){managed_context_error=-ENODEV;expected=-ENODEV;}
  if(fault==5){policy_error=-EOPNOTSUPP;expected=-EOPNOTSUPP;}
  if(fault==6){assert(managed_step()==-EINPROGRESS);managed.request.params.tx_rate.mcs--;}
  if(fault==7){assert(managed_step()==-EINPROGRESS && managed_step()==-EINPROGRESS);prepared_result=0;retry_result=-EIO;expected=-EIO;}
  if(fault==8)managed.request_bridge.bridge.host=&host;
  assert(managed_step()==expected && "EXPECTED_MANAGED_REQUEST_REFUSAL");
  if(fault<6)assert(!managed.request_bridge.bound && !creates && !attaches && "EXPECTED_MANAGED_REQUEST_NO_ALLOCATION");
  if(fault==7){unsigned before=retry_steps;retry_result=0;assert(managed_step()==-EIO && retry_steps==before && managed.request_bridge.bridge.host==&host && "EXPECTED_MANAGED_REQUEST_STICKY_OWNER");}
  managed_scope_error=managed_context_error=policy_error=0;
  if(managed.request_bridge.bridge.host)assert(!retire(&managed.request_bridge.bridge));
 }
}

int main(void) {request_cases();managed_request_cases();assert(!legacy_bridge_main());puts("MISHARE_REQUEST_BRIDGE_FIXTURE_PASS_ONLY");return 0;}
'''
POLICY=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;
#define BIT(n) (1U << (n))
#define ETH_ALEN 6
static bool is_valid_ether_addr(const u8 *m) {return !(m[0]&1) && (m[0]|m[1]|m[2]|m[3]|m[4]|m[5]);}
#include "wlan_hdd_mishare_init.h"
#include "wlan_hdd_mishare_rate.h"
struct hdd_context {void *parent_dev,*psoc,*pdev;};
static struct hdd_context hdd={(void*)1,(void*)2,(void*)3};
static bool trans_owned=true,rtnl_owned=true,recovering,passive;
static int context_error,mode,country_error,channel_state,reads;
static u8 country[3];
#define ASSERT_RTNL() assert(rtnl_owned)
#define QDF_GLOBAL_MISSION_MODE 0
#define CH_WIDTH_20MHZ 0
#define REG_CURRENT_PWR_MODE 0
#define CHANNEL_STATE_ENABLE 1
static void osif_psoc_sync_assert_trans_protected(void *p) {assert(trans_owned && p==hdd.parent_dev);}
static int wlan_hdd_validate_context(struct hdd_context *h) {assert(h==&hdd);return context_error;}
static bool cds_is_driver_recovering(void) {return recovering;}
static int hdd_get_conparam(void) {return mode;}
static int qdf_status_to_os_return(int s) {return s?-EPERM:0;}
static int ucfg_reg_get_current_country(void *p,u8 *out) {assert(p==hdd.psoc && trans_owned && rtnl_owned);reads++;memcpy(out,country,3);return country_error;}
static bool wlan_reg_is_24ghz_ch_freq(u32 f) {return f>=2400 && f<2500;}
static bool wlan_reg_is_5ghz_ch_freq(u32 f) {return f>=4900 && f<5900;}
static int wlan_reg_get_bonded_channel_state_for_pwrmode(void *p,u32 f,int bw,int sec,int power) {assert(p==hdd.pdev && f && !bw && !sec && !power);return channel_state;}
static bool wlan_reg_is_passive_for_freq(void *p,u32 f) {assert(p==hdd.pdev && f);return passive;}
NATIVE_REGULATORY
NATIVE_PREFLIGHT
int main(void) {
 for(unsigned fault=0;fault<16;fault++) {
  struct wondertap_init_params p={.channel={.freq=5240},.tx_rate={.preamble=WONDERTAP_RATE_PREAMBLE_HT,.nss=1,.mcs=7}};
  p.mac_addr[0]=2;memcpy(p.country_code,"CN",3);
  context_error=mode=country_error=reads=0;channel_state=1;recovering=passive=false;memcpy(country,"CN",3);
  if(fault==1)memcpy(country,"JP",3);
  if(fault==2)country_error=1;
  if(fault==3)channel_state=0;
  if(fault==4)passive=true;
  if(fault==5){p.tx_rate.nss=2;p.channel.freq=2437;}
  if(fault==6)p.channel.freq=5955;
  if(fault==7)p.tx_rate.bw=WONDERTAP_RATE_BW_40;
  if(fault==8)context_error=-ENODEV;
  if(fault==9)recovering=true;
  if(fault==10)mode=1;
  if(fault==11){p.rate_adaptation_enable=true;p.tx_rate_mask.max_nss=1;}
  if(fault==12)p.tx_rate.nss=0;
  if(fault==13)p.amsdu_enable=1;
  if(fault==14)p.ampdu_enable=1;
  if(fault==15){p.amsdu_enable=1;p.ampdu_enable=1;}
  struct mishare_init_request q={.params=p};
  int expected=fault==0?0:fault==2?-EPERM:fault==8?-ENODEV:fault==9?-ESHUTDOWN:fault==12?-EINVAL:-EOPNOTSUPP;
  assert(mishare_wonder_request_preflight_locked(&hdd,&q,1,2)==expected && "EXPECTED_REQUEST_NATIVE_POLICY");
  if(!fault){memcpy(country,"JP",3);assert(mishare_wonder_request_preflight_locked(&hdd,&q,1,2)==-EOPNOTSUPP && reads==2 && "EXPECTED_REQUEST_NATIVE_RECHECK");}
 }
 puts("MISHARE_REQUEST_NATIVE_PREFLIGHT_FIXTURE_PASS_ONLY");return 0;
}
'''


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('Compilation runs on Actions')
    prod=ROOT/'kernel/popsicle-hdd'
    decl=legacy.DECL.replace('typedef uint32_t u32;','typedef uint32_t u32;typedef uint16_t u16;\n#define BIT(n) (1U << (n))')
    decl+='\nint mishare_wonder_host_retry_step_locked(struct mishare_wonder_host *,u8,u8);\nint mishare_wonder_host_bssid_bind_locked(struct mishare_wonder_host *,const u8 *);\nstruct mishare_init_request;struct wondertap_fixed_tx_rate_params;\nint mishare_wonder_request_preflight_locked(struct hdd_context *,const struct mishare_init_request *,u8,u8);\nint mishare_wonder_host_prestart_step_locked(struct mishare_wonder_host *,u32,u8,u8,const struct wondertap_fixed_tx_rate_params *);\n'
    code=legacy.HARNESS.replace('#include "wlan_hdd_mishare_bridge.h"','#include "wlan_hdd_mishare_request_bridge.h"').replace('int main(void)','static int legacy_bridge_main(void)',1)+'\n'+MODEL
    host=(prod/'wlan_hdd_mishare_host.c').read_text();reg=function(host,'mishare_init_regulatory_check');pre=function(host,'mishare_wonder_request_preflight_locked')
    managed_function=function(host,'mishare_wonder_managed_prestart_step')
    code=code.replace('MANAGED_FUNCTION',managed_function,1)
    managed_controls=[code.replace('if (!instance->request_prepared)', 'if (false && !instance->request_prepared)',1),
                      code.replace('    mishare_bridge_scope_end(&scope);', '    if (false) mishare_bridge_scope_end(&scope);',1),
                      code.replace('    mishare_instance_release(instance);', '    if (false) mishare_instance_release(instance);',1),
                      code.replace('&instance->request, instance->request_nss_2g', '&instance->request_bridge.request, instance->request_nss_2g',1)]
    policy=POLICY.replace('NATIVE_REGULATORY',reg,1).replace('NATIVE_PREFLIGHT',pre,1)
    bridge=(prod/'wlan_hdd_mishare_bridge.h').read_text();bound=(prod/'wlan_hdd_mishare_request_bridge.h').read_text()
    controls=[
        ('wlan_hdd_mishare_request_bridge.h',bound.replace('!mishare_init_equal(&c->request, &canonical)','false',1)),
        ('wlan_hdd_mishare_request_bridge.h',bound.replace('if (ret)\n        return c->bound ?', 'if (false && ret)\n        return c->bound ?',1)),
        ('wlan_hdd_mishare_bridge.h',bridge.replace('if (b->prestart_mode)','if (false && b->prestart_mode)',1)),
        ('wlan_hdd_mishare_request_bridge.h',bound.replace('b->attempted = true;', 'b->attempted = false;',1)),
        ('wlan_hdd_mishare_request_bridge.h',bound.replace('b->attached = true;', 'b->attached = false;',1)),
    ]
    policies=[policy.replace('ret = mishare_init_aggregation_check(&canonical);', 'ret = 0 * mishare_init_aggregation_check(&canonical);',1),
              policy.replace('ret = mishare_init_regulatory_check(hdd, &canonical, nss_2g, nss_5g);','ret = 0 * mishare_init_regulatory_check(hdd, &canonical, nss_2g, nss_5g);',1),
              policy.replace('if (memcmp(country, p->country_code, 2))','if (false && memcmp(country, p->country_code, 2))',1),
              policy.replace('if (!ret && cds_is_driver_recovering())','if (false && !ret && cds_is_driver_recovering())',1)]
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        for name,text in [('errno.h','#include_next <linux/errno.h>\n'),('string.h','#include <string.h>\n'),('etherdevice.h','/* modeled */\n'),('if_ether.h','#define ETH_ALEN 6\n')]: (d/'linux'/name).write_text(text)
        (d/'wlan_hdd_mishare_host.h').write_text(decl)
        (d/'wlan_hdd_mishare_wonder_api.h').write_bytes((ROOT/'kernel/provider/wondertap.h').read_bytes())
        names=['wlan_hdd_mishare_bridge.h','wlan_hdd_mishare_request_bridge.h','wlan_hdd_mishare_init.h','wlan_hdd_mishare_rate.h']
        for name in names:(d/name).write_bytes((prod/name).read_bytes())
        f=d/'test.c';exe=d/'test';command=['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+tmp,str(f),'-o',str(exe)]
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        def run(text):
            f.write_text(text);subprocess.run(command,check=True);subprocess.run([exe],check=True,env=env,timeout=15)
        run(code)
        for managed_code in managed_controls:
            assert managed_code!=code;f.write_text(managed_code);subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=15)
            assert bad.returncode==-6 and 'EXPECTED_MANAGED_REQUEST_' in bad.stderr,(bad.returncode,bad.stderr[-1500:])
        f.write_text(code)

        for name,text in controls:
            original=(prod/name).read_text();assert text!=original
            (d/name).write_text(text);f.write_text(code);subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=15)
            assert bad.returncode==-6 and 'EXPECTED_REQUEST_BRIDGE_' in bad.stderr,(name,bad.returncode,bad.stderr[-1500:])
            (d/name).write_text(original)
        run(policy)
        for text in policies:
            assert text!=policy;f.write_text(text);subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=15)
            assert bad.returncode==-6 and 'EXPECTED_REQUEST_NATIVE_' in bad.stderr,(bad.returncode,bad.stderr[-1500:])
    out=ROOT/'.popsicle-ci/artifacts/reports/mishare-request-bridge-fixture.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'status':'MISHARE_REQUEST_BRIDGE_AND_PREFLIGHT_FIXTURE_PASS_ONLY','success_modes':8,'immutable_fields':15,'native_policy_cases':16,'bridge_mutations':5,'policy_mutations':len(policies),'managed_success_modes':8,'managed_boundary_cases':9,'managed_mutations':len(managed_controls),'limitations':'Production typed managed coordinator, request/bridge and extracted native-policy functions with modeled host allocation/retirement, instance serialization and regulatory/native scope APIs. Aggregation enables refused before allocation. Host execution is modeled here; no full managed init, parent lease, firmware ACK, START/UP or phone/RF/Apple proof.'},indent=2)+'\n')
    print('MISHARE_REQUEST_BRIDGE_AND_PREFLIGHT_FIXTURE_PASS_ONLY')


if __name__=='__main__':main()
