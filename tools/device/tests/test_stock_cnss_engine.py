"""Fault injection for an IO-free policy; no insmod/rmmod or phone actions."""
import os
from pathlib import Path
import subprocess
import unittest

ENGINE = Path(__file__).resolve().parents[1] / 'popsicle-stock-cnss-engine.sh'
EFFECTS = ['wifi-off', 'hals-stop', 'remove-wlan', 'insert-provider',
           'insert-wlan', 'hals-start', 'wifi-restore']
MODEL = r'''
C=stock;W=stock;P=absent;WIFI=$BEFORE;HAL=running;PHASE=none
ok(){ [ "$BLOCK" != "$1" ]; }
sc_environment(){ ok environment; }
sc_bundle(){ ok bundle; }
sc_no_other_transaction(){ ok transaction && [ "$PHASE" = none ]; }
sc_original_cnss(){ ok cnss && [ "$C" = stock ]; }
sc_expect_wlan(){ ok "wlan:$1" && [ "$W" = "$1" ]; }
sc_provider_absent(){ ok provider-absent && [ "$P" = absent ]; }
sc_interfaces(){ ok interfaces; }
sc_cnss_holder(){
 ok "cnss-holder:$1" || return 1
 if [ "$W" = absent ];then [ -z "$1" ];else [ "$1" = qca_cld3_peach_v2 ];fi
}
sc_snapshot(){ ok snapshot || return 1;echo SNAPSHOT;PHASE=snapshot; }
sc_journal(){ echo "J:$1";[ "$JFAIL" != "$1" ] || return 1;PHASE=$1; }
sc_wifi_is_off(){ ok wifi-off-observation && [ "$WIFI" = 0 ]; }
sc_hals_are_stopped(){ ok hals-stop-observation && [ "$HAL" = stopped ]; }
sc_wlan_unloadable(){ ok wlan-unloadable; }
sc_wlan_absent(){ [ "$W" = absent ]; }
sc_expect_provider(){ ok provider-identity && [ "$P" = candidate ]; }
sc_hals_are_running(){ ok hals-start-observation && [ "$HAL" = running ]; }
sc_wifi_matches_snapshot(){ ok wifi-restore-observation && [ "$WIFI" = "$BEFORE" ]; }
sc_effect(){
 echo "E:$1"
 case "$1" in
  wifi-off)WIFI=0;;hals-stop)HAL=stopped;;remove-wlan)W=absent;;
  insert-provider)P=candidate;;insert-wlan)W=candidate;;
  hals-start)HAL=running;;wifi-restore)WIFI=$BEFORE;;*)return 99;;
 esac
 # Failure may happen after a real side effect. Never assume rc != 0 means
 # nothing changed; a CNSS identity drift is independently injected too.
 [ "$DRIFT" != "$1" ] || C=unknown
 [ "$FAIL" != "$1" ] || return 7
 return 0
}
'''


class StockCNSSEngineTests(unittest.TestCase):
    def run_model(self, block='', fail='', jfail='', drift='', before='1', tail=''):
        script = MODEL + '\n. "$ENGINE"\n' + r'''
if sc_start_stock_cnss;then result=0;else result=$?;fi
echo "RESULT:$result:$PHASE:$C:$W:$P:$WIFI:$HAL"
''' + tail + '\nexit "$result"\n'
        return subprocess.run(['sh', '-c', script], text=True, capture_output=True,
                              env=dict(os.environ, ENGINE=str(ENGINE), BLOCK=block,
                                       FAIL=fail, JFAIL=jfail, DRIFT=drift, BEFORE=before))

    def effects(self, result):
        return [x[2:] for x in result.stdout.splitlines() if x.startswith('E:')]

    def test_success_retains_cnss_and_restores_original_wifi(self):
        for before in ['0', '1']:
            result = self.run_model(before=before)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(self.effects(result), EFFECTS)
            self.assertIn(f'RESULT:0:active:stock:candidate:candidate:{before}:running', result.stdout)

    def test_intent_return_and_done_surround_each_effect(self):
        lines = self.run_model().stdout.splitlines()
        for i, line in enumerate(lines):
            if line.startswith('E:'):
                effect = line[2:]
                self.assertEqual(lines[i-1], 'J:intent:' + effect)
                self.assertEqual(lines[i+1:i+3], ['J:returned:' + effect + ':0', 'J:done:' + effect])

    def test_preflight_refuses_before_any_runtime_effect(self):
        for block in ['environment', 'bundle', 'transaction', 'cnss', 'wlan:stock',
                      'provider-absent', 'interfaces', 'cnss-holder:qca_cld3_peach_v2',
                      'snapshot']:
            with self.subTest(block=block):
                result = self.run_model(block=block)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.effects(result))

    def test_every_effect_failure_stops_and_records_actual_nonzero_return(self):
        for i, effect in enumerate(EFFECTS):
            result = self.run_model(fail=effect)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.effects(result), EFFECTS[:i+1])
            self.assertIn('J:returned:' + effect + ':7', result.stdout)
            self.assertNotIn('J:done:' + effect, result.stdout)

    def test_each_intent_write_failure_prevents_that_effect(self):
        for i, effect in enumerate(EFFECTS):
            result = self.run_model(jfail='intent:' + effect)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.effects(result), EFFECTS[:i])

    def test_return_or_done_journal_failure_stops_after_current_effect(self):
        for i, effect in enumerate(EFFECTS):
            for journal in ['returned:' + effect + ':0', 'done:' + effect]:
                result = self.run_model(jfail=journal)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.effects(result), EFFECTS[:i+1])

    def test_cnss_identity_drift_stops_immediately_without_next_effect(self):
        for i, effect in enumerate(EFFECTS):
            result = self.run_model(drift=effect)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.effects(result), EFFECTS[:i+1])
            self.assertNotIn('J:done:' + effect, result.stdout)

    def test_readiness_and_identity_failures_block_following_effects(self):
        for block, count in [('wifi-off-observation', 1), ('hals-stop-observation', 2),
                             ('wlan-unloadable', 2), ('cnss-holder:', 3),
                             ('provider-identity', 4), ('wlan:candidate', 5),
                             ('hals-start-observation', 6), ('wifi-restore-observation', 7)]:
            result = self.run_model(block=block)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.effects(result), EFFECTS[:count])

    def test_active_transaction_cannot_be_replayed(self):
        result = self.run_model(tail='sc_start_stock_cnss && exit 90\necho RETRY_REFUSED')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.effects(result), EFFECTS)
        self.assertIn('RETRY_REFUSED', result.stdout)

    def test_prepared_and_active_journal_failures_do_not_announce_success(self):
        for journal, count in [('prepared', 0), ('active', len(EFFECTS))]:
            result = self.run_model(jfail=journal)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.effects(result), EFFECTS[:count])
            self.assertNotIn('RESULT:0:active:', result.stdout)

    def test_effect_allowlist_rejects_cnss_or_restore_commands(self):
        for operation in ['remove-cnss2', 'insert-cnss2', 'live-unload', 'restore', 'remove']:
            script = MODEL + '\n. "$ENGINE"\nsc_change "$OP"\n'
            result = subprocess.run(['sh', '-c', script], text=True, capture_output=True,
                                    env=dict(os.environ, ENGINE=str(ENGINE), BEFORE='1',
                                             BLOCK='', FAIL='', DRIFT='', JFAIL='', OP=operation))
            self.assertEqual(result.returncode, 2)
            self.assertFalse(self.effects(result))

    def test_sourcing_engine_performs_no_actions(self):
        result = subprocess.run(['sh', '-c', '. "$ENGINE"'], text=True, capture_output=True,
                                env=dict(os.environ, ENGINE=str(ENGINE)))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout + result.stderr, '')


if __name__ == '__main__':
    unittest.main()
