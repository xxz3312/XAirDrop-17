"""Execute 0062 shell with modeled radio state; no RF claims."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
MOCK = '''#!/bin/sh
case "${0##*/}" in
id) echo 0 ;;
iw)
 if [ "$3" = link ]; then
  n=$(cat "$MODEL_ROOT/count" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$MODEL_ROOT/count"
  freq=5745.0
  [ "$CASE" != wrong ] || freq=5240.0
  if [ "$CASE" = drift ] && [ "$n" -gt 3 ]; then freq=5220.0; fi
  if [ "$CASE" != disconnected ]; then echo 'Connected to 00:11:22:33:44:55 (on wlan0)'; echo " freq: $freq"; else echo 'Not connected.'; fi
 fi ;;
sha256sum) [ "$CASE" != checksum ] ;;
dmesg) echo model ;;
sleep) /bin/sleep 0.02 ;;
action-tx-0062)
 echo called >> "$MODEL_ROOT/events"
 [ "$CASE" != tool_fail ] || exit 2
 [ "$CASE" != missing ] || exit 0
 echo '{"event":"awdl_mgmt_ready","registration_acknowledged":true}'
 /bin/sleep 0.08
 echo '{"event":"awdl_mgmt_rx_summary","events":0,"parsed":0}' ;;
esac
'''
class ChannelRxTest(unittest.TestCase):
    def run_case(self, case=''):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for d in ['bin','bundle','sys/module/qca_cld3_peach_v2/parameters','data/local/tmp']:
                (p/d).mkdir(parents=True)
            params=p/'sys/module/qca_cld3_peach_v2/parameters'
            (params/'mishare_mgmt_rx').write_text('Y')
            (params/'mishare_mgmt_rx_routed').write_text('0')
            if case != 'missing_diag':
                (params/'mishare_mgmt_rx_diag').write_text('register_submitted=1\npe_inserted=1\npe_check_calls=0\nowner_active=1\nregister_ml_default=1\nwma_events=0\n')
            for name in ['id','iw','sha256sum','dmesg','sleep','action-tx-0062']:
                f=p/('bundle' if name=='action-tx-0062' else 'bin')/name
                f.write_text(MOCK); f.chmod(0o755)
            source=(ROOT/'tools/device/popsicle-mgmt-diag-0062.sh').read_text().replace('/sys/',str(p/'sys')+'/').replace('/data/local/tmp/',str(p/'data/local/tmp')+'/')
            (p/'test.sh').write_text(source)
            r=subprocess.run(['sh',str(p/'test.sh'),str(p/'bundle'),str(p/'logs'),'5745'],env=dict(os.environ,CASE=case,MODEL_ROOT=tmp,PATH=str(p/'bin')+':'+os.environ['PATH']),capture_output=True,text=True,timeout=5)
            calls=(p/'events').read_text().splitlines() if (p/'events').exists() else []
            if case == '':
                self.assertIn('pe_check_calls_delta=0',(p/'logs/diag-delta.txt').read_text())
                self.assertIn('owner_active_after=1',(p/'logs/diag-delta.txt').read_text())
                for n in range(1,4):
                    self.assertTrue((p/f'logs/diag-round-{n}-after.txt').is_file())
            locked=(p/'data/local/tmp/xairdrop-mgmt-rx.lock').exists()
            return r,calls,locked
    def test_three_rounds_zero_is_inconclusive(self):
        r,c,l=self.run_case(); self.assertEqual(r.returncode,0,r.stderr); self.assertEqual(len(c),3); self.assertFalse(l); self.assertIn('Zero frames is inconclusive',r.stdout)
    def test_preflight_blocks(self):
        for case in ['wrong','disconnected','checksum','missing_diag']:
            with self.subTest(case=case):
                r,c,l=self.run_case(case); self.assertNotEqual(r.returncode,0); self.assertFalse(c); self.assertFalse(l)
    def test_abort_and_no_retry(self):
        for case in ['drift','tool_fail','missing']:
            with self.subTest(case=case):
                r,c,l=self.run_case(case); self.assertNotEqual(r.returncode,0); self.assertEqual(len(c),1); self.assertFalse(l); self.assertNotIn('MGMT_DIAG_OBSERVATION_COMPLETE',r.stdout)
if __name__=='__main__': unittest.main()
