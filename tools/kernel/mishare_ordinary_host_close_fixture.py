#!/usr/bin/env python3
"""Actual ordinary host idle close after native raw START/UP/STOP/DOWN."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
import mishare_down_host_close_fixture as previous
import mishare_native_cleanup_fixture as cleanup
import mishare_native_engine_fixture as engine
from mishare_recovery_fixture import function
ROOT=previous.ROOT
CALLER=r'''
static int ordinary_poll(struct mishare_runtime_owner **o) {
 assert(o && !health_recovering && !composite_rtnl &&
  (composite_closed?!*o:(*o==composite_host.runtime)) && "EXPECTED_ORDINARY_OWNER");
 int r=mishare_wonder_host_idle_prepare_locked(&health);
 *o=composite_closed?NULL:composite_host.runtime;
 assert(!composite_rtnl && "EXPECTED_ORDINARY_UNLOCK");return r;
}
'''
CASES=r'''
static void ordinary_case(unsigned freq,unsigned initial,bool early,unsigned modes,unsigned fault) {
 clean_modes=modes;clean_fault=fault;
 struct mishare_runtime_owner *o=ordinary_ready(freq,initial,early,early);
 assert(ordinary_poll(&o)==-EINPROGRESS && "EXPECTED_ORDINARY_PE_POST");
 assert(o && !o->radio && pe_pending.bodyptr && !health_recovering &&
  !state(o).quiesced && !state(o).recovery_window && !state(o).recovery_down_observed &&
  "EXPECTED_ORDINARY_DOWN_TO_PE");
 clean_end(&o);
 if(fault) {
  assert(o && composite_host.runtime==o && composite_host_storage && composite_adapter_storage &&
   terminal_sync && terminal_device_pins==1 && terminal_psoc_pins==1 && terminal_pdev_pins==1 &&
   !composite_closed && !state(o).recovery_window && !state(o).quiesced &&
   "EXPECTED_ORDINARY_FAILURE_RETAINS_HOST");return;
 }
 assert(!o && composite_closed && !mishare_hosts && !composite_host_storage &&
  !composite_adapter_storage && !terminal_sync && !terminal_registered && !terminal_device_pins &&
  !terminal_psoc_pins && !terminal_pdev_pins && !module_refs && terminal_step==8 &&
  clean_sm_destroys==1 && down_runtime_sm_frees==1 && !reset_force_detaches && !reset_wmi_calls &&
  "EXPECTED_ORDINARY_COMPLETE");
}
static void ordinary_cases(void) {
 for(unsigned band=0;band<2;band++)for(unsigned initial=0;initial<2;initial++)
 for(unsigned early=0;early<2;early++)for(unsigned modes=0;modes<32;modes++) {
  pid_t c=fork();assert(c>=0);if(!c){ordinary_case(band?5240:2437,
   initial?WLAN_VDEV_SS_IDLE:0,!!early,modes,0);_Exit(0);}
  int s;assert(waitpid(c,&s,0)==c && WIFEXITED(s) && !WEXITSTATUS(s) && "EXPECTED_ORDINARY_CHILD");
 }
 for(unsigned fault=1;fault<=6;fault++) {
  pid_t c=fork();assert(c>=0);if(!c){ordinary_case(5240,0,false,0,fault);_Exit(0);}
  int s;assert(waitpid(c,&s,0)==c && WIFEXITED(s) && !WEXITSTATUS(s) && "EXPECTED_ORDINARY_FAULT_CHILD");
 }
}
'''
def fixture(root):
    source,exits,stubbed=previous.fixture(root)
    def once(old,new):
        nonlocal source
        assert source.count(old)==1,old
        source=source.replace(old,new,1)
    once('static void finish_dp(void) {',cleanup.EARLY+'\nstatic void finish_dp(void) {\n if(clean_active && !clean_peer_gone) {clean_dp_deferred=true;return;}')
    native='\n'.join(function((root/cleanup.previous.WMA).read_text(),n) for n in ['wma_remove_objmgr_peer','wma_remove_peer'])
    delete=function(source,'mishare_ndi_self_peer_delete')
    once(delete,cleanup.PEER.replace('NATIVE_PEER_FUNCTIONS',native)+'\n#define wma_remove_peer clean_native_remove_peer\n'+delete+'\n#undef wma_remove_peer\n')
    body=function(source,'down_runtime_sm_free')
    once(body,'static void ordinary_component_sm(struct wlan_objmgr_vdev *);\n'+body.replace('{','{\n if(clean_active){ordinary_component_sm(v);down_runtime_sm_frees++;return;}',1))
    ready=re.findall(r'^static struct mishare_runtime_owner \*down_runtime_ready\(.*?^\}',source,re.M|re.S)
    assert len(ready)==1
    ready=ready[0];ordinary=ready[:ready.index(' assert(mishare_runtime_quiesce_psoc(')]+' return o;\n}\n'
    ordinary=ordinary.replace('down_runtime_ready(', 'ordinary_ready(',1).replace(' composite_bind(o);\n','',1)
    ordinary=ordinary.replace('attach_engine(o);','attach_engine(o);composite_bind(o);',1)
    ordinary=ordinary.replace('mishare_runtime_destroy(&o)','ordinary_poll(&o)')
    close=function(source,'mishare_wonder_host_stop_ready_locked')
    once(close,close.replace('ASSERT_RTNL();','assert(composite_transition && !lock_depth);',1))
    host=(ROOT/previous.previous.HOST).read_text()
    selected=function(host,'mishare_wonder_host_idle_prepare_locked')
    component=function(cleanup.FINAL,'clean_component_sm').replace('clean_component_sm(', 'ordinary_component_sm(',1)
    blocked=function(cleanup.FINAL,'clean_blocked').replace('mishare_runtime_destroy(&o)','ordinary_poll(&o)')
    end=function(cleanup.FINAL,'clean_end').replace('mishare_runtime_destroy(o)','ordinary_poll(o)')
    wait='assert(ordinary_poll(o)==-EINPROGRESS && !dp_detaches && !delete_calls);reply();'
    assert end.count(wait)==1
    end=end.replace(wait,'assert(ordinary_poll(o)==-EINPROGRESS && !dp_detaches && !delete_calls && "EXPECTED_ORDINARY_DELETE_ACK");reply();',1)
    pos=source.index('static struct mishare_runtime_owner *down_runtime_ready(')
    source=source[:pos]+selected+'\n'+CALLER+component+'\n'+blocked+'\n'+end+'\n'+ordinary+source[pos:]
    main=function(source,'main')
    once(main,CASES+'\nint main(void) {ordinary_cases();engine_contract();puts("MISHARE_PINNED_NATIVE_SM_ENGINE_FIXTURE_PASS_ONLY");return 0;}\n')
    return source,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
    runtime=(ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_runtime.c').read_text()
    body=function(runtime,'mishare_runtime_ndi_drain')
    controls=[
      ('if (ndi->peer_created && (!ndi->peer_delete_submitted ||\n                              !ndi->peer_delete_replied))',
       'if (false && ndi->peer_created && (!ndi->peer_delete_submitted ||\n                              !ndi->peer_delete_replied))','EXPECTED_PEER_ACK_BEFORE_VDEV_DELETE'),
      ('if (!ndi->delete_submitted || !ndi->delete_replied)',
       'if (false && (!ndi->delete_submitted || !ndi->delete_replied))','EXPECTED_ORDINARY_DELETE_ACK'),
    ]
    override=directory/'wlan_hdd_mishare_runtime.c'
    try:
        for old,new,marker in controls:
            assert body.count(old)==1,old
            override.write_text(runtime.replace(body,body.replace(old,new,1),1));c_file.write_text(source)
            subprocess.run(command,check=True)
            bad=subprocess.run([directory/'engine'],capture_output=True,text=True,env=env,timeout=60)
            assert bad.returncode==-6 and marker in bad.stderr,(marker,bad.returncode,bad.stderr[-1800:])
    finally:override.unlink(missing_ok=True)

def audit(root):
    r=engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    host=(ROOT/previous.previous.HOST).read_text()
    r.update(status='MISHARE_ORDINARY_HOST_NATIVE_CLOSE_COMPOSITE_PASS_ONLY',combinations=256,
      retained_faults=6,ack_gate_mutations=2,
      host_idle_sha256=hashlib.sha256(function(host,'mishare_wonder_host_idle_prepare_locked').encode()).hexdigest(),
      native_peer_sha256={n:hashlib.sha256(function((root/cleanup.previous.WMA).read_text(),n).encode()).hexdigest() for n in ['wma_remove_peer','wma_remove_objmgr_peer']},
      limitations='Actual host idle/destroy plus runtime/radio/native SM/WMA/PE destructor and ordinary peer/VDEV DELETE notification paths execute together without SSR/window adoption. Physical DP peer unmap/object reference helpers, firmware delivery, factory, adapter/sync/parent/module primitives remain explicit models; not full native peer object-manager/firmware/kernel race or phone/RF/Apple certification. Configured START/public init stays closed.')
    return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
