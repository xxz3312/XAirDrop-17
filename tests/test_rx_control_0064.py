"""Run the actual 0064 shell; model UI transitions only after its prompt."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
MOCK=r'''#!/bin/sh
params="$MODEL_ROOT/sys/module/qca_cld3_peach_v2/parameters"
case "${0##*/}" in
id) echo 0 ;;
sha256sum) [ "$CASE" != checksum_fail ] ;;
dmesg) echo model ;;
sleep) /bin/sleep 0.005 ;;
cmd)
 echo "cmd $*" >> "$MODEL_ROOT/events"
 case "$2" in
 help)
  if [ "$CASE" = no_scan ]; then echo 'permission denied'; exit 255; fi
  echo '  start-scan'; echo '  list-scan-results'
  [ "$CASE" != help_255 ] ;;
 start-scan) [ "$CASE" != scan_fail ] ;;
 list-scan-results) echo 'cached results' ;;
 esac
 if [ "$2" = help ] && [ "$CASE" = help_255 ]; then exit 255; fi ;;
iw)
 if [ "$3" = disconnect ]; then echo FORBIDDEN_DISCONNECT >> "$MODEL_ROOT/events"; exit 99; fi
 if [ "$3" = link ]; then
  freq=5240.0;addr=00:11:22:33:44:55
  [ "$CASE" != wrong_freq ] || freq=5745.0
  if [ -f "$MODEL_ROOT/manual-start" ]; then
   n=$(cat "$MODEL_ROOT/link_count" 2>/dev/null || echo 0)
   n=$((n+1));echo "$n" > "$MODEL_ROOT/link_count"
   if [ "$CASE" = reload ]; then
    if [ "$n" -le 2 ]; then echo N > "$params/mishare_mgmt_rx"; else echo Y > "$params/mishare_mgmt_rx"; fi
   fi
   if [ "$CASE" = no_rejoin ] || { [ "$CASE" != no_transition ] && [ "$n" -le 2 ]; }; then echo 'Not connected.';exit 0;fi
   wma=8
   [ "$CASE" != zero_growth ] || wma=5
   [ "$CASE" != reset ] || wma=1
   printf 'register_ml_default=1\nregister_submitted=1\npe_inserted=1\nwma_events=%s\nowner_active=1\n' "$wma" > "$params/mishare_mgmt_rx_diag"
   [ "$CASE" != wrong_ap ] || addr=00:11:22:33:44:66
  fi
  echo "Connected to $addr (on wlan0)";echo " freq: $freq"
 fi ;;
action-tx-0064)
 echo listener >> "$MODEL_ROOT/events"
 [ "$CASE" != tool_fail ] || exit 2
 echo '{"event":"awdl_mgmt_ready","registration_acknowledged":true}'
 echo '{"event":"awdl_mgmt_rx_summary","events":0,"parsed":0}' ;;
esac
'''

class Control64Test(unittest.TestCase):
    def run_case(self,case='',manual=True):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for d in ['bin','bundle','sys/module/qca_cld3_peach_v2/parameters','data/local/tmp']:(p/d).mkdir(parents=True)
            params=p/'sys/module/qca_cld3_peach_v2/parameters'
            (params/'mishare_mgmt_rx').write_text('Y')
            (params/'mishare_mgmt_rx_diag').write_text('register_ml_default=1\nregister_submitted=1\npe_inserted=1\nwma_events=5\nowner_active=1\n')
            for n in ['id','sha256sum','dmesg','sleep','cmd','iw','action-tx-0064']:
                f=p/('bundle' if n.startswith('action-tx') else 'bin')/n;f.write_text(MOCK);f.chmod(0o755)
            source=(ROOT/'tools/device/popsicle-rx-control-0064.sh').read_text()
            # Test-only user stimulus: the mock Wi-Fi changes after the actual prompt.
            lines=source.splitlines()
            for i,line in enumerate(lines):
                if "echo 'MANUAL_RECONNECT:" in line:
                    lines.insert(i+1,'    touch "$MODEL_ROOT/manual-start"');break
            source='\n'.join(lines).replace('/sys/',str(p/'sys')+'/').replace('/data/local/tmp/',str(p/'data/local/tmp')+'/')+'\n'
            (p/'test.sh').write_text(source)
            args=['sh',str(p/'test.sh'),str(p/'bundle'),str(p/'logs'),'5240']
            if manual:args.append('--manual-reconnect')
            r=subprocess.run(args,env=dict(os.environ,PATH=str(p/'bin')+':'+os.environ['PATH'],CASE=case,MODEL_ROOT=tmp),capture_output=True,text=True,timeout=10)
            events=(p/'events').read_text().splitlines() if (p/'events').exists() else []
            files={f.name:f.read_text() for f in (p/'logs').glob('*.txt')}
            self.assertNotIn('FORBIDDEN_DISCONNECT',events)
            self.assertFalse((p/'data/local/tmp/xairdrop-mgmt-rx.lock').exists())
            return r,events,files

    def test_help_255_with_supported_command_still_attempts_scan(self):
        r,e,f=self.run_case('help_255',manual=False)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('cmd wifi start-scan',e)
        self.assertIn('help_rc=255',f['scan-status.txt'])
        self.assertIn('scan_execution_confirmed=false',f['scan-status.txt'])

    def test_manual_transition_and_growth(self):
        r,e,f=self.run_case()
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('phase=manual wma_events_delta=3 verdict=WMA_GROWTH_OBSERVED',f['summary.txt'])
        self.assertIn('automatic_disconnect_issued=false',f['manual-status.txt'])
        self.assertIn('TRANSITION_OBSERVED_CHECK_DELTA',f['result.txt'])
        self.assertEqual(e.count('listener'),1)

    def test_no_manual_flag_is_passive_after_scan(self):
        r,_,f=self.run_case(manual=False)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('manual_status=NOT_REQUESTED',f['result.txt'])
        self.assertNotIn('manual-status.txt',f)

    def test_preflight_failure_does_not_issue_scan(self):
        for case in ['checksum_fail','wrong_freq']:
            with self.subTest(case=case):
                r,e,_=self.run_case(case);self.assertNotEqual(r.returncode,0);self.assertFalse(e)

    def test_unsupported_or_failed_scan_does_not_block_listener(self):
        for case in ['no_scan','scan_fail']:
            with self.subTest(case=case):
                r,e,f=self.run_case(case,manual=False)
                self.assertEqual(r.returncode,0,r.stderr);self.assertIn('listener',e)
                self.assertIn('scan_execution_confirmed=false',f['scan-status.txt'])
                if case=='no_scan':self.assertNotIn('cmd wifi start-scan',e)

    def test_invalid_manual_controls_preserve_earlier_observation(self):
        for case,status in [('reload','INVALID_DRIVER_CHANGED'),('reset','INVALID_COUNTER_RESET'),('no_transition','INCOMPLETE_TRANSITION_NOT_OBSERVED'),('no_rejoin','INCOMPLETE_TRANSITION_NOT_OBSERVED'),('wrong_ap','INCOMPLETE_TRANSITION_NOT_OBSERVED')]:
            with self.subTest(case=case):
                r,e,f=self.run_case(case)
                self.assertEqual(r.returncode,0,r.stderr)
                self.assertIn(status,f['result.txt']);self.assertIn('delta-awdl.txt',f)
                self.assertNotIn('delta-manual.txt',f);self.assertEqual(e.count('listener'),1)

    def test_zero_manual_growth_is_inconclusive(self):
        r,_,f=self.run_case('zero_growth')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('phase=manual wma_events_delta=0 verdict=INCONCLUSIVE',f['summary.txt'])

    def test_listener_failure_stops_before_manual_prompt(self):
        r,e,f=self.run_case('tool_fail')
        self.assertNotEqual(r.returncode,0)
        self.assertIn('last_phase=awdl',f['result.txt']);self.assertNotIn('manual-status.txt',f)

if __name__=='__main__':unittest.main()
