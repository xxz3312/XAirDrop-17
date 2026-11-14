#!/usr/bin/env python3
"""Internal exact host START gate through native START/UP and 0209 close."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import mishare_configured_host_close_fixture as prior
from mishare_recovery_fixture import function
ROOT=prior.ROOT

EXTRA=r'''
static bool configured210_recovery;
static int configured210_context_error;
static bool configured210_recovering(void) {return configured210_recovery;}
static int configured210_validate(void *hdd) {assert(hdd==&psoc);return configured210_context_error;}
'''
WRAPPER=r'''
static int configured210_submit(struct configured209_host *h,const struct mishare_init_request *q,u8 n2,u8 n5) {
 assert(!configured209_rtnl);configured209_rtnl=true;
 int ret=configured210_production_start(h,q,n2,n5);
 configured209_rtnl=false;return ret;
}
'''
ADMISSION=r'''
 struct wondertap_init_params params={0};struct mishare_init_request request;
 params.channel.freq=freq;params.tx_rate=prestart_params;
 memcpy(params.mac_addr,mac,6);memcpy(params.bssid,mac,6);memcpy(params.country_code,"CN",3);
 params.data_retry_limit=retry_data;params.mgmt_retry_limit=retry_mgmt;
 assert(!mishare_init_parse(&params,&request));
 configured210_recovery=false;configured210_context_error=0;
 if(launch_fault) {
  int expected=-EUCLEAN;
  struct configured209_host *target=&host;const struct mishare_init_request *q=&request;
  switch(launch_fault) {
  case 1:target=NULL;expected=-EINVAL;break;
  case 2:q=NULL;expected=-EINVAL;break;
  case 3:configured209_parent_error=-ENODEV;expected=-ENODEV;break;
  case 4:configured210_recovery=true;expected=-ESHUTDOWN;break;
  case 5:configured210_context_error=-EIO;expected=-EIO;break;
  case 6:netdev.running=true;expected=-EBUSY;break;
  case 7:host.session.closing=true;expected=-ESHUTDOWN;break;
  case 8:request.params.tx_rate.mcs--;break;
  case 9:o->state.start_preview.committed=false;expected=-EINPROGRESS;break;
  case 10:o->state.retry.receipt.submitted_mask^=1;break;
  case 11:host.runtime=NULL;expected=-EINPROGRESS;break;
  case 12:adapter.event_flags=1UL<<1;expected=-EBUSY;break;
  case 13:link.link_flags[0]=1UL<<2;expected=-EBUSY;break;
  }
  struct mishare_runtime_status before=state(o);
  assert(configured210_submit(target,q,1,2)==expected &&
   !memcmp(&before,&o->state,sizeof(before)) && !o->radio && !radio_starts && !radio_stops &&
   !pe_deletes && !dp_detaches && "EXPECTED_CONFIGHOST210_START_REFUSAL");return;
 }
'''
CASES=r'''
static void configured210_admissions(void) {
 const unsigned faults[]={8,1,2,3,4,5,6,7,9,10,11,12,13};
 for(unsigned index=0;index<13;index++) {
  unsigned fault=faults[index];
  pid_t child=fork();assert(child>=0);if(!child) {
   retry_data=5;retry_mgmt=3;retry_failure=retry_fault=0;retry_inline=false;
   configured210_case(5240,0,false,0,0,fault);_Exit(0);
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) &&
   "EXPECTED_CONFIGHOST210_ADMISSION_CHILD");
 }
}
'''

def fixture(root):
    source,exits,stubbed=prior.fixture(root)
    host=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_host.c').read_text()
    launch=function(host,'mishare_wonder_host_launch_check_locked')
    start=function(host,'mishare_wonder_host_configured_start_locked')
    source=source.replace('struct configured209_host {','struct configured209_host {\n void *hdd;struct mishare_prestart prestart;',1)
    mark='#define SME_SESSION_OPENED 2\n'
    assert source.count(mark)==1
    setup=EXTRA+'''\n#define cds_is_driver_recovering configured210_recovering
#define wlan_hdd_validate_context configured210_validate
#define mishare_wonder_host_launch_check_locked configured210_production_launch
#define mishare_wonder_host_configured_start_locked configured210_production_start
'''
    source=source.replace(mark,mark+setup+launch+'\n'+start+'\n',1)
    mark='#pragma pop_macro("SME_SESSION_OPENED")'
    source=source.replace(mark,'''#undef mishare_wonder_host_configured_start_locked
#undef mishare_wonder_host_launch_check_locked
#undef wlan_hdd_validate_context
#undef cds_is_driver_recovering
'''+mark,1)
    old=function(source,'configured209_case')
    case=old.replace('configured209_case(', 'configured210_case(',1).replace('unsigned cleanup_fault)', 'unsigned cleanup_fault,unsigned launch_fault)',1)
    case=case.replace('.adapter=&adapter,.session=session,.runtime=o', '.hdd=&psoc,.prestart=control,.adapter=&adapter,.session=session,.runtime=o',1)
    case=case.replace('configured209_active=&host;prestart_session=&host.session;', 'configured209_active=&host;prestart_control=&host.prestart;prestart_session=&host.session;',1)
    mark=' if(guard) {';assert case.count(mark)==1;case=case.replace(mark,ADMISSION+mark,1)
    # Both the ordinary and SSR guard enter START through the exact host gate.
    needle='mishare_runtime_configured_start(o,freq)';assert case.count(needle)==2
    case=case.replace(needle,'configured210_submit(&host,&request,1,2)')
    needle=' assert(configured209_close(&o)==-EINPROGRESS && o && host.session.closing &&'
    assert case.count(needle)==1
    case=case.replace(needle,''' assert(configured210_submit(&host,&request,1,2)==-EBUSY && radio_starts==0 &&
  "EXPECTED_CONFIGHOST210_NO_REPLAY");
'''+needle,1)
    source=source.replace(old,WRAPPER+case,1)
    cases=function(source,'configured209_cases').replace('configured209_cases(', 'configured210_cases(',1)
    cases=cases.replace('configured209_case(band?5240:2437,mode,!!early,0,0)', 'configured210_case(band?5240:2437,mode,!!early,0,0,0)')
    cases=cases.replace('configured209_case(5240,0,false,guard,fault)', 'configured210_case(5240,0,false,guard,fault,0)')
    source=source.replace(function(source,'configured209_cases'),cases+'\n'+CASES,1)
    main=function(source,'main');source=source.replace(main,main.replace('configured209_cases();','configured210_cases();configured210_admissions();'),1)
    return source,exits,stubbed


def controls(directory,c_file,command,env,source,root):
    host=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_host.c').read_text()
    body=function(host,'mishare_wonder_host_configured_start_locked')
    old='if (ret)';assert body.count(old)==1
    changed=source.replace(body,body.replace(old,'if (false && ret)',1),1)
    c_file.write_text(changed);subprocess.run(command,check=True)
    bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=90)
    assert bad.returncode!=0 and 'EXPECTED_CONFIGHOST210_' in bad.stderr,(bad.returncode,bad.stderr[-2000:])


def audit(root):
    engine=prior.prior.prior.previous.ordinary.previous.ordinary.cleanup.engine
    r=engine.audit(root,fixture_builder=fixture,extra_audit=controls)
    r.update(status='MISHARE_CONFIGURED_HOST_START_NATIVE_FIXTURE_PASS_ONLY',native_host_start_close_cycles=512,
      start_admission_refusals=13,close_refusals=6,cleanup_faults=6,new_mutations=1,
      production_host_start_sha256=hashlib.sha256(function((ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_host.c').read_text(),'mishare_wonder_host_configured_start_locked').encode()).hexdigest(),
      limitations='Exact host launch/start and close bodies with real configured runtime/native SM and ordinary cleanup. Host object/parent/RTNL/HDD primitives are models. Frozen complete request/current native policy are separately checked in the full host/request-bridge model; this is not one native factory/typed bridge end-to-end proof. WMI/firmware and parent lifetime coordinator, active configured SSR/remove, managed/public launch and phone RF/Apple remain unqualified.')
    return r

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
