"""Execute the read-only native management controller with modeled commands."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
MOCK='''#!/bin/sh
case "${0##*/}" in
id) echo 0 ;;
iw) echo 'freq: 5240' ;;
sha256sum) [ "$CASE" != checksum_fail ] ;;
dmesg) echo modeled_kernel ;;
action-tx-0058)
 echo called >> "$MODEL_ROOT/events"
 echo '{"event":"awdl_mgmt_rx_summary","events":0,"parsed":0,"over_256":0}'
 [ "$CASE" != tool_fail ] ;;
esac
'''
class MgmtRunnerTest(unittest.TestCase):
    def run_case(self,case=''):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp)
            for d in ['bin','bundle','sys/module/qca_cld3_peach_v2/parameters','data/local/tmp']:(r/d).mkdir(parents=True,exist_ok=True)
            params=r/'sys/module/qca_cld3_peach_v2/parameters'
            (params/'mishare_mgmt_rx').write_text('N' if case=='disabled' else 'Y')
            (params/'mishare_mgmt_rx_routed').write_text('0')
            if case=='wonder':(r/'sys/module/wonder').mkdir()
            for name in ['id','iw','sha256sum','dmesg','action-tx-0058']:
                p=(r/'bundle' if name=='action-tx-0058' else r/'bin')/name;p.write_text(MOCK);p.chmod(0o755)
            source=(ROOT/'tools/device/popsicle-mgmt-rx-test.sh').read_text().replace('/sys/',str(r/'sys')+'/').replace('/data/local/tmp/',str(r/'data/local/tmp')+'/')
            (r/'test.sh').write_text(source)
            result=subprocess.run(['sh',str(r/'test.sh'),str(r/'bundle'),str(r/'logs')],env=dict(os.environ,MODEL_ROOT=tmp,CASE=case,PATH=str(r/'bin')+':'+os.environ['PATH']),capture_output=True,text=True,timeout=5)
            called=(r/'events').read_text().splitlines() if (r/'events').exists() else []
            outcome=(r/'logs/result.txt').read_text() if (r/'logs/result.txt').exists() else ''
            return result,called,outcome
    def test_zero_events_is_observation_not_success(self):
        r,c,out=self.run_case();self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(c,['called']);self.assertEqual(out,'exit=0\n');self.assertIn('MGMT_RX_OBSERVATION_COMPLETE',r.stdout)
    def test_requires_enabled_driver_and_no_old_wonder(self):
        for case in ['disabled','wonder']:
            with self.subTest(case=case):
                r,c,_=self.run_case(case);self.assertNotEqual(r.returncode,0);self.assertFalse(c)
    def test_checksum_failure_never_starts_tool(self):
        r,c,out=self.run_case('checksum_fail');self.assertNotEqual(r.returncode,0);self.assertFalse(c);self.assertEqual(out,'exit=1\n')
    def test_failed_tool_is_not_retried(self):
        r,c,out=self.run_case('tool_fail');self.assertNotEqual(r.returncode,0);self.assertEqual(c,['called']);self.assertEqual(out,'exit=1\n');self.assertNotIn('MGMT_RX_OBSERVATION_COMPLETE',r.stdout)
if __name__=='__main__':unittest.main()
