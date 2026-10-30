"""Execute the production controller with modeled commands and counters."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MOCK = r'''#!/bin/sh
params="$MODEL_ROOT/sys/module/qca_cld3_peach_v2/parameters"
case "${0##*/}" in
id) echo 0 ;;
sha256sum) [ "$CASE" != checksum_fail ] ;;
dmesg) echo modeled_kernel ;;
sleep) /bin/sleep 0.005 ;;
cmd)
 echo "cmd $*" >> "$MODEL_ROOT/events"
 case "$2" in
 help) [ "$CASE" = no_scan ] || echo 'start-scan list-scan-results' ;;
 start-scan) [ "$CASE" != scan_fail ] ;;
 list-scan-results) echo 'cached results only' ;;
 esac ;;
iw)
 if [ "$3" = disconnect ]; then
  echo disconnect >> "$MODEL_ROOT/events"
  [ "$CASE" != disconnect_fail ] || exit 95
  touch "$MODEL_ROOT/disconnected"
  if [ "$CASE" = reset ]; then echo N > "$params/mishare_mgmt_rx"; fi
  exit 0
 fi
 if [ "$3" = link ]; then
  if [ -f "$MODEL_ROOT/disconnected" ]; then
   n=$(cat "$MODEL_ROOT/link_count" 2>/dev/null || echo 0)
   n=$((n+1)); echo "$n" > "$MODEL_ROOT/link_count"
   if [ "$CASE" = no_rejoin ] || { [ "$CASE" != no_transition ] && [ "$n" -le 2 ]; }; then
    echo 'Not connected.'; exit 0
   fi
   if [ "$CASE" != zero_growth ]; then
    if [ "$CASE" = counters_backwards ]; then wma=1; else wma=8; fi
    printf 'register_ml_default=1\nregister_submitted=1\npe_inserted=1\nwma_events=%s\nowner_active=1\n' "$wma" > "$params/mishare_mgmt_rx_diag"
   fi
  fi
  freq=5240.0; addr=00:11:22:33:44:55
  [ "$CASE" != wrong_freq ] || freq=5745.0
  if [ "$CASE" = wrong_ap ] && [ -f "$MODEL_ROOT/disconnected" ]; then addr=00:11:22:33:44:66; fi
  echo "Connected to $addr (on wlan0)"
  echo " freq: $freq"
 fi ;;
action-tx-0063)
 echo listener >> "$MODEL_ROOT/events"
 [ "$CASE" != tool_fail ] || exit 2
 echo '{"event":"awdl_mgmt_ready","registration_acknowledged":true}'
 echo '{"event":"awdl_mgmt_rx_summary","events":0,"parsed":0}' ;;
esac
'''

class ControlTest(unittest.TestCase):
    def run_case(self, case='', reconnect=True):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for d in ['bin','bundle','sys/module/qca_cld3_peach_v2/parameters','data/local/tmp']:
                (p/d).mkdir(parents=True)
            params=p/'sys/module/qca_cld3_peach_v2/parameters'
            (params/'mishare_mgmt_rx').write_text('Y')
            (params/'mishare_mgmt_rx_diag').write_text('register_ml_default=1\nregister_submitted=1\npe_inserted=1\nwma_events=5\nowner_active=1\n')
            for name in ['id','sha256sum','dmesg','sleep','cmd','iw','action-tx-0063']:
                f=p/('bundle' if name.startswith('action-tx') else 'bin')/name
                f.write_text(MOCK);f.chmod(0o755)
            source=(ROOT/'tools/device/popsicle-rx-control-0063.sh').read_text().replace('/sys/',str(p/'sys')+'/').replace('/data/local/tmp/',str(p/'data/local/tmp')+'/')
            (p/'test.sh').write_text(source)
            args=['sh',str(p/'test.sh'),str(p/'bundle'),str(p/'logs'),'5240']
            if reconnect:args.append('--reconnect')
            r=subprocess.run(args,env=dict(os.environ,PATH=str(p/'bin')+':'+os.environ['PATH'],MODEL_ROOT=tmp,CASE=case),capture_output=True,text=True,timeout=10)
            events=(p/'events').read_text().splitlines() if (p/'events').exists() else []
            files={f.name:f.read_text() for f in (p/'logs').glob('*.txt')}
            self.assertFalse((p/'data/local/tmp/xairdrop-mgmt-rx.lock').exists())
            return r,events,files

    def test_growth_during_reconnect_is_not_airdrop_success(self):
        r,e,f=self.run_case()
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(e.count('disconnect'),1)
        self.assertEqual(e.count('listener'),1)
        self.assertIn('phase=reconnect wma_events_delta=3 verdict=WMA_GROWTH_OBSERVED',f['summary.txt'])
        self.assertIn('phase=scan wma_events_delta=0 verdict=INCONCLUSIVE',f['summary.txt'])
        self.assertIn('airdrop_verified=false',f['result.txt'])

    def test_no_flag_never_disconnects(self):
        r,e,f=self.run_case(reconnect=False)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertNotIn('disconnect',e)
        self.assertIn('SKIPPED_NO_EXPLICIT_FLAG',f['summary.txt'])

    def test_preflight_never_mutates_radio(self):
        for case in ['checksum_fail','wrong_freq']:
            with self.subTest(case=case):
                r,e,_=self.run_case(case)
                self.assertNotEqual(r.returncode,0)
                self.assertFalse(e)

    def test_scan_unsupported_or_failed_does_not_claim_scan_execution(self):
        for case in ['no_scan','scan_fail']:
            with self.subTest(case=case):
                r,e,f=self.run_case(case,reconnect=False)
                self.assertEqual(r.returncode,0,r.stderr)
                self.assertIn('scan_execution_confirmed=false',f['scan-status.txt'])
                if case=='no_scan':self.assertFalse(any('start-scan' in x for x in e))

    def test_zero_growth_remains_inconclusive(self):
        r,_,f=self.run_case('zero_growth')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('phase=reconnect wma_events_delta=0 verdict=INCONCLUSIVE',f['summary.txt'])

    def test_invalid_controls_stop_before_awdl(self):
        for case in ['disconnect_fail','reset','counters_backwards','wrong_ap','no_rejoin','no_transition']:
            with self.subTest(case=case):
                r,e,_=self.run_case(case)
                self.assertNotEqual(r.returncode,0)
                self.assertEqual(e.count('disconnect'),1)
                self.assertNotIn('listener',e)

    def test_listener_failure_is_preserved(self):
        r,e,f=self.run_case('tool_fail')
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(e.count('listener'),1)
        self.assertIn('last_phase=awdl',f['result.txt'])

if __name__=='__main__':unittest.main()
