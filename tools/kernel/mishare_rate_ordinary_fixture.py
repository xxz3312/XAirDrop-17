#!/usr/bin/env python3
"""Actions-only pre-START configured ordinary DELETE through native cleanup bodies."""
import argparse
import json
import subprocess
from pathlib import Path
import mishare_native_cleanup_fixture as cleanup
import mishare_rate_reset_fixture as rate
from mishare_recovery_fixture import function

ROOT = cleanup.engine.ROOT
HARNESS = r'''
static void configured_ordinary_cycle(unsigned freq,unsigned failure,unsigned mode,unsigned fault) {
 reset_pe_test();radio_native_substate=0;
 struct mishare_runtime_owner *o=configured_rate(freq,failure);
 struct mishare_runtime_rate_status before=state(o).rate;
 attach_engine(o);clean_modes=mode;clean_fault=fault;
 assert(!state(o).ndi.radio_requested && !state(o).ndi.start_plan_requested && !radio_starts && !radio_stops && !radio_downs);
 assert(mishare_runtime_ndi_start_plan(o)==-EOPNOTSUPP && mishare_runtime_ndi_start(o)==-EOPNOTSUPP);
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && state(o).rate.ordinary_admitted &&
  !state(o).rate.ordinary_completed && pe_pending.bodyptr && "EXPECTED_RATE_ORDINARY_BEGIN");
 rate_history(o,before);
 configured_clean_end(&o);
 assert(!radio_starts && !radio_stops && !radio_downs && !reset_force_detaches && !reset_wmi_calls && "EXPECTED_RATE_ORDINARY_NO_RADIO_RESET");
 if(!fault)assert(!o && !mishare_runtime_owners && !allocations && !objects_live && "EXPECTED_RATE_ORDINARY_FINAL");
 else {assert(o && state(o).rate.ordinary_completed==(fault==6) && "EXPECTED_RATE_ORDINARY_FAULT_RETAIN");rate_history(o,before);}
}
static void ordinary_rate_cases(void) {
 for(unsigned band=0;band<2;band++)for(unsigned failure=0;failure<4;failure++)for(unsigned mode=0;mode<32;mode++) {
  pid_t child=fork();assert(child>=0);if(!child){configured_ordinary_cycle(band?5240:2437,failure,mode,0);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 for(unsigned fault=1;fault<=6;fault++)for(unsigned failure=0;failure<4;failure++) {
  pid_t child=fork();assert(child>=0);if(!child){configured_ordinary_cycle(5240,failure,0,fault);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 for(unsigned fault=0;fault<5;fault++) {
  pid_t child=fork();assert(child>=0);if(!child){
   reset_pe_test();struct mishare_runtime_owner *o=configured_rate(5240,2);
   if(fault==0)o->state.work_pending=1;
   if(fault==1)o->state.rate.integrity_error=true;
   if(fault==2)o->state.ndi.start_plan_requested=true;
   if(fault==3)mishare_runtime_quiesce_psoc(&psoc,MISHARE_QUIESCE_SSR);
   if(fault==4)o->state.rate.ordinary_completed=true;
   int expected=fault==0?-EINPROGRESS:fault==1||fault==4?-EUCLEAN:-EOPNOTSUPP;
   assert(mishare_runtime_destroy(&o)==expected && o && !pe_pending.bodyptr && !pe_deletes && !wire_deletes && !dp_detaches && "EXPECTED_RATE_ORDINARY_REFUSAL");_Exit(0);
  }int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
}
'''


def fixture(root):
    source, exits, stubbed = cleanup.fixture(root)
    helpers = rate.HARNESS[:rate.HARNESS.index('int main(void) {')]
    tail = function(source, 'clean_end')
    configured = tail.replace('clean_end(', 'configured_clean_end(', 1)
    configured = cleanup.owner.replace_once(configured,
        'state(*o).radio.down_accepted && state(*o).radio.phase==MISHARE_RADIO_DOWN && ',
        '!state(*o).ndi.radio_requested && !state(*o).ndi.start_plan_requested && ')
    # Native/context failure retains ownership even if native resource cleanup
    # already completed and only host logical delete was rejected.
    configured = configured.replace('if(hold) {\n  assert(ret==', 'if(hold) {\n  assert(state(*o).rate.ordinary_completed && "EXPECTED_RATE_ORDINARY_COMPLETION");\n  assert(ret==')
    configured = configured.replace('clean_active=true;', 'struct mishare_runtime_rate_status original_rate=state(*o).rate;clean_active=true;', 1)
    configured = configured.replace('assert(state(*o).rate.ordinary_completed', 'rate_history(*o,original_rate);\n  assert(state(*o).rate.ordinary_completed', 1)
    main = function(source, 'main')
    source = cleanup.owner.replace_once(source, main,
        helpers + '\n' + configured + '\n' + HARNESS + '\n' + main.replace('engine_contract();', 'ordinary_rate_cases();engine_contract();', 1))
    return source, exits, stubbed


def negative_controls(directory, c_file, command, env, source, root):
    target = source.replace(function(source, 'main'), 'int main(void) {configured_ordinary_cycle(5240,2,8,0);return 0;}', 1)
    c_file.write_text(target)
    subprocess.run(command, check=True)
    subprocess.run([directory/'engine'], check=True, timeout=60, env=env)
    runtime = (ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_runtime.c').read_text()
    override = directory/'wlan_hdd_mishare_runtime.c'
    drain = function(runtime, 'mishare_runtime_ndi_drain')
    controls = [
        ('entry->state.rate.ordinary_admitted = true;', 'entry->state.rate.ordinary_admitted = false;'),
        ('entry->state.rate.ordinary_completed = true;', 'entry->state.rate.ordinary_completed = false;'),
        ('if (ndi->peer_created && (!ndi->peer_delete_submitted ||\n                              !ndi->peer_delete_replied)) {', 'if (false) {'),
    ]
    try:
        for needle, replacement in controls:
            changed = cleanup.owner.replace_once(drain, needle, replacement)
            override.write_text(cleanup.owner.replace_once(runtime, drain, changed))
            subprocess.run(command, check=True)
            bad = subprocess.run([directory/'engine'], capture_output=True, text=True, timeout=60, env=env)
            assert bad.returncode == -6 and ('EXPECTED_RATE_ORDINARY_' in bad.stderr or 'EXPECTED_PEER_ACK_BEFORE_VDEV_DELETE' in bad.stderr), (bad.returncode, bad.stderr[-2000:])
    finally:
        override.unlink(missing_ok=True)


def audit(root):
    report = cleanup.engine.audit(root, fixture_builder=fixture, extra_audit=negative_controls)
    report['status'] = 'MISHARE_RATE_ORDINARY_FIXTURE_PASS_ONLY'
    report['configured_combinations'] = 256
    report['configured_retention_faults'] = 24
    report['admission_refusals'] = 5
    report['configured_native_mutations'] = 3
    report['limitations'] = ('Production rate registry with modeled WMI receipts; pre-START ordinary PE/native WMA peer/DELETE/DP wrappers, native PE destructor and SM lifetime execute. '
        'Physical transport, firmware ACK origins, peer refs/unmap/DP callback dependency and component destructor caller remain modeled. '
        'Parents retained by fixture; no automatic native parent lease, mixed SSR/ordinary cleanup, START/UP with configured rate, firmware, RF or Apple certification.')
    return report


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
