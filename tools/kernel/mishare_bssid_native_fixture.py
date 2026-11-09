#!/usr/bin/env python3
"""Actions-only owned MLME BSSID binding through native prestart/cleanup."""
import argparse
import json
import subprocess
from pathlib import Path
import mishare_prestart_native_fixture as previous
from mishare_recovery_fixture import function
ROOT=previous.ROOT
CASES=r'''
static void bssid_extra_cases(void) {
 for(unsigned fault=0;fault<10;fault++) {
  pid_t child=fork();assert(child>=0);if(!child) {
   reset_pe_test();radio_native_substate=0;
   struct mishare_runtime_owner *o=NULL;assert(!create(&o));
   u8 wanted[6]={0,0x25,0,0xff,0x94,0x73};
   if(fault==1)o->referenced=false;
   if(fault==2)o->state.draining=true;
   if(fault==3)o->state.ndi.active=true;
   if(fault==4)last_vdev->mlme->mgmt.generic.subtype=1;
   if(fault==5)last_vdev->mlme->mgmt.generic.type=WLAN_VDEV_MLME_TYPE_NDI;
   if(fault==6)last_vdev->mlme->vdev=NULL;
   if(fault==7)ch_state=WLAN_VDEV_S_START;
   if(fault==8)mark_closed(o);
   if(fault==9) {
    assert(!mishare_runtime_bssid_bind(o,wanted));last_vdev->mlme->mgmt.generic.bssid[5]^=1;
   }
   int expected=fault==0?0:fault==2||fault==8?-ESHUTDOWN:fault==3?-EBUSY:-EUCLEAN;
   assert(mishare_runtime_bssid_bind(o,wanted)==expected && "EXPECTED_BSSID_NATIVE_ADMISSION");
   if(fault>=4 && fault!=8)assert(state(o).bssid.requested && state(o).bssid.error==-EUCLEAN && state(o).blocked && state(o).ndi.blocked &&
    mishare_runtime_bssid_bind(o,wanted)==-EUCLEAN && "EXPECTED_BSSID_NATIVE_STICKY");
   if(!fault) {
    assert(state(o).bssid.applied && !memcmp(last_vdev->mlme->mgmt.generic.bssid,wanted,6) && "EXPECTED_BSSID_NATIVE_WRITE");
    u8 changed[6];memcpy(changed,wanted,6);changed[5]^=1;
    assert(mishare_runtime_bssid_bind(o,changed)==-EBUSY && !memcmp(state(o).bssid.value,wanted,6) &&
     !memcmp(last_vdev->mlme->mgmt.generic.bssid,wanted,6) && "EXPECTED_BSSID_NATIVE_IMMUTABLE");
    assert(!mishare_runtime_bssid_bind(o,wanted) && !mishare_runtime_destroy(&o) && !o && !objects_live &&
     "EXPECTED_BSSID_NATIVE_PURE_HOST_RETIRE");
   }
   _Exit(0); /* Fault cases preserve the deliberately invalid/ambiguous owner. */
  }
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 pid_t child=fork();assert(child>=0);if(!child) {
  reset_pe_test();struct mishare_runtime_owner *o=NULL;assert(!create(&o));u8 zero[6]={0};
  assert(!wlan_objmgr_vdev_try_get_ref(last_vdev,WLAN_LEGACY_MAC_ID));
  assert(!mishare_runtime_work_get(last_vdev,o));
  assert(mishare_runtime_bssid_bind(o,zero)==-EINPROGRESS && !state(o).bssid.requested && "EXPECTED_BSSID_NATIVE_WORK_WAIT");
  mishare_runtime_work_put(last_vdev,o);wlan_objmgr_vdev_release_ref(last_vdev,WLAN_LEGACY_MAC_ID);
  assert(!mishare_runtime_bssid_bind(o,zero) && state(o).bssid.applied && !mishare_runtime_destroy(&o) && !o &&
   "EXPECTED_BSSID_NATIVE_ZERO_METADATA");_Exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
}
'''


def fixture(root):
    source,exits,stubbed=previous.fixture(root)
    once=previous.ordinary.cleanup.owner.replace_once
    cycle=function(source,'prestart_native_cycle')
    needle=' assert(!create(&o));'
    changed=once(cycle,needle,needle+'''
 u8 bound_bssid[6]={0,0x25,0,0xff,0x94,0x73};
 assert(!mishare_runtime_bssid_bind(o,bound_bssid) && state(o).bssid.requested && state(o).bssid.applied &&
  !memcmp(last_vdev->mlme->mgmt.generic.bssid,bound_bssid,6) && !state(o).ndi.active &&
  "EXPECTED_BSSID_NATIVE_BEFORE_CREATE");''')
    source=once(source,cycle,changed)
    poll=function(source,'prestart_poll')
    source=once(source,poll,once(poll,' return mishare_prestart_step(','''
 if(prestart_owner && state(prestart_owner).bssid.requested) {
  int ret=mishare_runtime_bssid_bind(prestart_owner,state(prestart_owner).bssid.value);
  if(ret)return ret;
  assert(state(prestart_owner).bssid.applied && !memcmp(last_vdev->mlme->mgmt.generic.bssid,state(prestart_owner).bssid.value,6) &&
   "EXPECTED_BSSID_NATIVE_SURVIVES_PREPARATION");
 }
 return mishare_prestart_step('''))
    main=function(source,'main');source=once(source,main,CASES+'\n'+main.replace('prestart_native_cases();','bssid_extra_cases();prestart_native_cases();',1))
    return source,exits,stubbed


def negative_controls(directory,c_file,command,env,source,root):
    once=previous.ordinary.cleanup.owner.replace_once
    runtime=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_runtime.c').read_text()
    bind=function(runtime,'mishare_runtime_bssid_bind')
    controls=[
        once(bind,'memcpy(m->mgmt.generic.bssid, b->value, ETH_ALEN);','(void)b; /* negative: no native BSSID write */'),
        once(bind,'memcmp(b->value, bssid, ETH_ALEN)','false'),
        once(bind,'memcmp(m->mgmt.generic.bssid, b->value, ETH_ALEN)','false'),
    ]
    for changed in controls:
        c_file.write_text(once(source,function(source,'main'),'int main(void) {bssid_extra_cases();return 0;}'))
        override=directory/'wlan_hdd_mishare_runtime.c';override.unlink(missing_ok=True)
        subprocess.run(command,check=True);subprocess.run([directory/'engine'],check=True,env=env,timeout=60)
        try:
            override.write_text(once(runtime,bind,changed));subprocess.run(command,check=True)
            bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=60)
            assert bad.returncode==-6 and 'EXPECTED_BSSID_NATIVE_' in bad.stderr,(bad.returncode,bad.stderr[-2000:])
        finally:override.unlink(missing_ok=True)


def audit(root):
    r=previous.ordinary.cleanup.engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    r.update(status='MISHARE_BSSID_NATIVE_FIXTURE_PASS_ONLY',bssid_prestart_combinations=512,publication_and_retention_cases=12,bssid_edge_cases=11,bssid_native_mutations=3)
    r['limitations']='Actual owned MLME BSSID write/readback and runtime ownership with native prestart/ordinary cleanup selected bodies; write before firmware CREATE, unchanged PE MAC identity. Executor, transport and physical primitives modeled. BSSID is host metadata only, not firmware/radio/filter/RF acceptance. No public managed init, parent lease, retry/aggregation application, START/UP or Apple proof.'
    return r


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
