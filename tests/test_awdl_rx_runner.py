"""Execute receive controller with modeled Android interfaces and tool results."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_vendor_feedback_runner import MOCK, HELPER

ROOT=Path(__file__).resolve().parents[1]
RX_TOOL='''#!/bin/sh
printf '%s\\n' "$1" >> "$MODEL_ROOT/events"
if [ "$1" = capture-start ]; then
    [ "$4" = --operating-mode ] || exit 2
    case "$5" in lpc|occ) ;; *) exit 2 ;; esac
    [ "$CASE" != capture_fail ] || exit 1
else
    [ "$CASE" != listen_fail ] || exit 1
    echo '{"event":"awdl_rx_summary","observed":0}'
fi
'''

class RxRunnerTest(unittest.TestCase):
    def run_case(self,case='',mode='lpc'):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp)
            for d in ['bin','sys/class/net','sys/module','data/local/tmp','bundle']:(r/d).mkdir(parents=True,exist_ok=True)
            for cmd in ['id','iw','ip','sha256sum','insmod','rmmod','dmesg']:
                p=r/'bin'/cmd;p.write_text(MOCK.replace('xfbtmon0','xawdlmon0'));p.chmod(0o755)
            b=r/'bundle'
            for f in ['wonder.ko','SHA256SUMS']:(b/f).touch()
            (b/'popsicle-rx-start.sh').write_text(HELPER.replace('else\n', 'elif [ "$1" = status ]; then\n echo modeled_RX_status\nelse\n'))
            (b/'action-tx-0055').write_text(RX_TOOL);(b/'action-tx-0055').chmod(0o755)
            if case=='existing':(r/'sys/module/wonder').mkdir()
            if case=='p2p_up':
                (r/'sys/class/net/p2p0').mkdir();(r/'sys/class/net/p2p0/flags').write_text('0x1003')
            source=(ROOT/'tools/device/popsicle-awdl-rx-test.sh').read_text().replace('/sys/',str(r/'sys')+'/').replace('/data/local/tmp/',str(r/'data/local/tmp')+'/')
            (r/'run.sh').write_text(source)
            result=subprocess.run(['sh',str(r/'run.sh'),str(b),str(r/'logs'),mode],env=dict(os.environ,MODEL_ROOT=tmp,CASE=case,PATH=str(r/'bin')+':'+os.environ['PATH']),capture_output=True,text=True,timeout=5)
            events=(r/'events').read_text().splitlines() if (r/'events').exists() else []
            return result,events,(r/'sys/class/net/xawdlmon0').exists(),(r/'sys/module/wonder').exists()

    def test_zero_observations_is_completed_not_discovery(self):
        result,events,mon,wonder=self.run_case()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(events.count('awdl-listen'),1)
        self.assertNotIn('inject',events)
        self.assertLess(events.index('stop'),events.index('monitor_del'))
        self.assertFalse(mon or wonder)
        self.assertIn('RX_OBSERVATION_COMPLETE',result.stdout)
        self.assertNotIn('TEST_PASS',result.stdout)

    def test_failures_cleanup_owned_resources(self):
        for case in ['capture_fail','setup_fail','listen_fail']:
            with self.subTest(case=case):
                result,events,mon,wonder=self.run_case(case)
                self.assertNotEqual(result.returncode,0)
                self.assertFalse(mon or wonder)
                self.assertNotIn('RX_OBSERVATION_COMPLETE',result.stdout)
                if case!='listen_fail':self.assertNotIn('awdl-listen',events)

    def test_unknown_resources_and_p2p_are_not_changed(self):
        for case in ['existing','p2p_up','checksum','disconnected']:
            with self.subTest(case=case):
                result,events,_,_=self.run_case(case)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(events,[])

    def test_explicit_occ_does_not_transmit(self):
        result,events,mon,wonder=self.run_case(mode='occ')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(events.count('capture-start'),1)
        self.assertNotIn('inject',events)
        self.assertFalse(mon or wonder)

    def test_invalid_mode_stops_before_mutation(self):
        result,events,mon,wonder=self.run_case(mode='invalid')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(events,[])
        self.assertFalse(mon or wonder)

    def test_stop_failure_keeps_bound_monitor(self):
        result,events,mon,wonder=self.run_case('stop_fail')
        self.assertNotEqual(result.returncode,0)
        self.assertTrue(mon and wonder)
        self.assertNotIn('monitor_del',events)

if __name__=='__main__':unittest.main()
