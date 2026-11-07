#!/usr/bin/env python3
"""Actions-only native VDEV timer contract after peer ACK; no runtime admission."""
import argparse
import json
import subprocess
from pathlib import Path
import mishare_rate_late_peer_fixture as previous
from mishare_recovery_fixture import function
ROOT = previous.ROOT
OBSERVE = r'''
static void late_peer_observe(struct mishare_runtime_owner **o) {
 struct mishare_runtime_rate_status before=state(*o).rate;
 assert(ctx_pending && ctx_requests==1 && timers_live && !wire_deletes && !dp_detaches);
 /* Select the real hold-request completion origin on either side of the
  * original SSR fence. This test does not open a native recovery window. */
 if(late_peer_stop_first)ctx_fw_origin(ctx_pending);
 mark_closed(*o);
 if(!late_peer_stop_first)ctx_fw_origin(ctx_pending);
 assert(!stop_mc());
 assert(state(*o).ndi.peer_delete_replied && !ctx_pending && !ctx_requests &&
  !wma_context.wmi_cmd_rsp_wake_lock && timers_live && "EXPECTED_PEER_TIMER_ACK_IS_NOT_TIMER_FREE");
 assert(!mishare_runtime_recovery_candidates(&psoc) && !state(*o).recovery_window);
 assert(mishare_runtime_reclaim_ndi(o)==-EOPNOTSUPP && "EXPECTED_PEER_TIMER_RUNTIME_STAYS_CLOSED");
 /* The prepared DP helper independently refuses a still physical peer.
  * Do not call it in the peer-already-gone case: no DP admission is tested. */
 if(!clean_peer_gone) {
  assert(mishare_ndi_reset_prepared_dp_detach(last_vdev,state(*o).ndi.create.dp_cookie,
   mishare_runtime_ndi_dp_freed,*o)==-EUCLEAN && !dp_detaches && "EXPECTED_PEER_TIMER_PHYSICAL_PEER_GUARD");
 }
 if(late_peer_fault==1)response_timer.rsp_status=1;
 if(late_peer_fault==2)recovery_cancel_drift=true;
 if(late_peer_fault==3)recovery_missing_timer=true;
 if(late_peer_fault==4)response_timer.rt_lock.is_lock_acquired=true;
 if(late_peer_fault==5)response_timer.psoc=NULL;
 if(late_peer_fault==6)response_timer.vdev_id=8;
 if(late_peer_fault==7)response_timer.rsp_timer_inuse=0;
 if(late_peer_fault==8)last_vdev->mlme->mgmt.generic.subtype=1;
 if(late_peer_fault==9)ch_state=3;
 if(late_peer_fault==10)last_vdev->mlme->ext_vdev_ptr=NULL;
 int ret=mishare_ndi_reset_prepared_timer_deinit(last_vdev);
 if(late_peer_fault) {
  assert(ret==-EUCLEAN && timers_live && !recovery_timer_frees && !recovery_rt_frees &&
   recovery_timer_cancels==(late_peer_fault==2?1u:0u) && "EXPECTED_PEER_TIMER_FAULT_RETAIN");
 } else {
  assert(!ret && !timers_live && recovery_timer_cancels==1 && recovery_timer_frees==1 &&
   recovery_rt_frees==1 && !response_timer.psoc && !response_timer.rsp_timer_inuse &&
   "EXPECTED_PEER_TIMER_NATIVE_DRAIN");
  /* Repeated native helper invocation fails rather than freeing twice. */
  assert(mishare_ndi_reset_prepared_timer_deinit(last_vdev)==-EUCLEAN &&
   recovery_timer_cancels==1 && recovery_timer_frees==1 && "EXPECTED_PEER_TIMER_NO_DOUBLE_FREE");
 }
 rate_history(*o,before);
 assert(*o && (*o)->referenced && (*o)->events && state(*o).ndi.active &&
  state(*o).ndi.wma_bound && state(*o).ndi.legacy_ready && objects_live && module_refs==1 &&
  dp_objects && stats_live && !wire_deletes && !dp_detaches && !delete_calls &&
  !state(*o).ndi.delete_pending && !state(*o).ndi.delete_submitted && !state(*o).ndi.delete_replied &&
  !state(*o).host_delete_accepted && !state(*o).rate.ordinary_completed &&
  "EXPECTED_PEER_TIMER_NO_RETIREMENT");
 _Exit(0); /* Helper-contract sandbox. Runtime metadata intentionally not advanced. */
}
'''
CASES = r'''
static void late_peer_cases(void) {
 for(unsigned band=0;band<2;band++)for(unsigned failure=0;failure<4;failure++)for(unsigned mode=0;mode<4;mode++)for(unsigned timing=0;timing<2;timing++) {
  unsigned native_mode=(mode&1?2:0)|(mode&2?8:0);
  pid_t child=fork();assert(child>=0);if(!child){late_peer_cycle(band?5240:2437,failure,native_mode,timing,0);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 for(unsigned fault=1;fault<=10;fault++)for(unsigned timing=0;timing<2;timing++) {
  pid_t child=fork();assert(child>=0);if(!child){late_peer_cycle(5240,2,0,timing,fault);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
}
'''


def fixture(root):
    source, exits, stubbed = previous.fixture(root)
    once = previous.ordinary.cleanup.owner.replace_once
    source = once(source, function(source, 'late_peer_observe'), OBSERVE.strip())
    source = once(source, function(source, 'late_peer_cases'), CASES.strip())
    return source, exits, stubbed


def negative_controls(directory, c_file, command, env, source, root):
    once = previous.ordinary.cleanup.owner.replace_once
    timer = function(source, 'mishare_ndi_reset_prepared_timer_deinit')
    controls = [
        (once(timer, '!= 1 || r->rsp_status ||', '!= 1 || false ||'), 1),
        (once(timer, 'r->vdev_id != id || r->rsp_status ||', 'r->vdev_id != id || false ||'), 2),
        (once(timer, 'target_if_psoc_vdev_rsp_timer_deinit(psoc, id);', '/* negative: no native deinit */'), 0),
    ]
    for modified, fault in controls:
        target = once(source, function(source, 'main'),
                      f'int main(void) {{late_peer_cycle(5240,2,0,false,{fault});return 0;}}')
        c_file.write_text(target)
        subprocess.run(command, check=True)
        subprocess.run([directory/'engine'], check=True, env=env, timeout=60)
        c_file.write_text(once(target, timer, modified))
        subprocess.run(command, check=True)
        bad = subprocess.run([directory/'engine'], capture_output=True, text=True, env=env, timeout=60)
        assert bad.returncode == -6 and 'EXPECTED_PEER_TIMER_' in bad.stderr, (bad.returncode, bad.stderr[-2000:])


def audit(root):
    r = previous.ordinary.cleanup.engine.audit(root, fixture_builder=fixture, extra_audit=negative_controls)
    r.update(status='MISHARE_RATE_PEER_TIMER_CONTRACT_FIXTURE_PASS_ONLY',
             timer_combinations=64, timer_rejection_cases=20, timer_native_mutations=3)
    r['limitations'] = ('Native timer helper contract in isolated retained-owner child processes, real selected peer ACK origin before/after original SSR fence. '
        'No production runtime change, native recovery window, DP admission, context finish or owner retirement. Timer helper alone does not authorize recovery; caller must separately qualify stopped native parents. '
        'Physical primitives/transport/ACK/ref/locks modeled. No configured START/UP, phone/RF/Apple proof.')
    return r


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wlan', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    r = audit(a.wlan)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(r, indent=2)+'\n')
    print(r['status'])
