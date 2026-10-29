"""Run the actual Android shell script with command/filesystem models, no radio."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MOCK = r'''#!/usr/bin/env python3
import os,sys,pathlib,time,shutil,json
r=pathlib.Path(os.environ['MODEL_ROOT']);cmd=pathlib.Path(sys.argv[0]).name;a=sys.argv[1:]
mode=os.environ.get('CASE',''); events=r/'events'
def event(s):
 with events.open('a') as f:f.write(s+'\n')
if cmd=='id':print(0)
elif cmd=='sha256sum':sys.exit(1 if mode=='checksum' else 0)
elif cmd=='sleep':time.sleep(.02)
elif cmd=='dmesg':print('modeled kernel log')
elif cmd=='ip':event('ip '+' '.join(a))
elif cmd=='iw':
 if a==['dev','wlan0','link']:
  n=r/'freq_calls'; count=int(n.read_text()) if n.exists() else 0;n.write_text(str(count+1))
  if mode!='disconnected':print('freq: '+('5785' if mode=='channel' and count else '5240'))
 elif a==['dev','wlan0','info']:print('wiphy 0')
 elif 'add' in a:
  event('monitor_add');(r/'sys/class/net/xfbtmon0').mkdir()
 elif 'del' in a:
  event('monitor_del');shutil.rmtree(r/'sys/class/net/xfbtmon0')
elif cmd=='action-tx-0051':
 if a[0]=='inject':
  event('inject');(r/'injected').touch();sys.exit(1 if mode=='inject_fail' else 0)
 event('relay')
 if mode=='early_exit':sys.exit(1)
 print('{"event":"relay_ready","mode":"token_feedback","transport":"vendor_action"}',flush=True)
 for i in range(150):
  if (r/'injected').exists():break
  time.sleep(.01)
 else:sys.exit(1)
 print('{"event":"vendor_action_tx_status","native_status":0,"bytes":45,"freq":5240}')
 print('{"event":"feedback_complete","token":"256","outcome":'+('2' if mode=='bad_outcome' else '1')+'}')
 print('{"event":"feedback_summary","completed":1,"failed":0,"rejected":0,"reported":1,"channel_queue_resets":1}')
else:pass
'''
HELPER = r'''#!/bin/sh
if [ "$1" = start ]; then
 echo start >> "$MODEL_ROOT/events"
 [ "$CASE" != setup_fail ] || exit 1
 mkdir "$MODEL_ROOT/sys/module/wonder"
else
 echo stop >> "$MODEL_ROOT/events"
 [ "$CASE" != stop_fail ] || exit 1
 rmdir "$MODEL_ROOT/sys/module/wonder"
fi
'''

class RunnerTest(unittest.TestCase):
    def run_case(self, case=''):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp)
            for d in ['bin','sys/module/qca_cld3_peach_v2/parameters','sys/class/net', 'data/local/tmp','bundle']:
                (r/d).mkdir(parents=True,exist_ok=True)
            (r/'sys/module/qca_cld3_peach_v2/parameters/mishare_action_tx').write_text('Y')
            if case=='existing':(r/'sys/module/wonder').mkdir()
            if case=='existing_monitor':(r/'sys/class/net/xfbtmon0').mkdir()
            if case=='lock':(r/'data/local/tmp/xairdrop-vendor-feedback.lock').mkdir()
            for cmd in ['id','iw','ip','sha256sum','insmod','rmmod','dmesg','sleep','action-tx-0051']:
                p=r/'bin'/cmd;p.write_text(MOCK);p.chmod(0o755)
            b=r/'bundle'
            for name in ['wonder.ko','action-vendor.bin','SHA256SUMS']:(b/name).touch()
            (b/'action-tx-0051').symlink_to(r/'bin/action-tx-0051')
            (b/'popsicle-rx-start.sh').write_text(HELPER)
            script=(ROOT/'tools/device/popsicle-vendor-feedback-test.sh').read_text()
            script=script.replace('/sys/',str(r/'sys')+'/').replace('/data/local/tmp/',str(r/'data/local/tmp')+'/')
            (r/'run.sh').write_text(script)
            env=dict(os.environ,MODEL_ROOT=tmp,CASE=case,PATH=str(r/'bin')+':'+os.environ['PATH'])
            result=subprocess.run(['sh',str(r/'run.sh'),str(b),str(r/'logs')],env=env,capture_output=True,text=True,timeout=10)
            events=(r/'events').read_text().splitlines() if (r/'events').exists() else []
            return result,events,(r/'sys/class/net/xfbtmon0').exists(),(r/'sys/module/wonder').exists()

    def test_success_one_frame_cleanup_order(self):
        result,events,mon,wonder=self.run_case()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(events.count('inject'),1)
        self.assertLess(events.index('stop'),events.index('monitor_del'))
        self.assertFalse(mon or wonder)
        self.assertIn('TOKEN_TEST_PASS',result.stdout)

    def test_preflight_never_changes_existing_resources(self):
        for case in ['existing','existing_monitor','checksum','disconnected','lock']:
            with self.subTest(case=case):
                result,events,_,_=self.run_case(case)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(events,[])

    def test_channel_change_and_early_exit_do_not_inject(self):
        for case in ['channel','early_exit']:
            with self.subTest(case=case):
                result,events,mon,wonder=self.run_case(case)
                self.assertNotEqual(result.returncode,0)
                self.assertNotIn('inject',events)
                self.assertFalse(mon or wonder)

    def test_failed_injection_and_bad_ack_evidence_fail(self):
        for case in ['inject_fail','bad_outcome']:
            with self.subTest(case=case):
                result,events,mon,wonder=self.run_case(case)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(events.count('inject'),1)
                self.assertFalse(mon or wonder)

    def test_start_failure_removes_owned_monitor(self):
        result,events,mon,wonder=self.run_case('setup_fail')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('monitor_del',events)
        self.assertFalse(mon or wonder)

    def test_stop_failure_preserves_bound_monitor(self):
        result,events,mon,wonder=self.run_case('stop_fail')
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn('monitor_del',events)
        self.assertTrue(mon and wonder)
        self.assertIn('CLEANUP_FAILED',result.stderr)

if __name__=='__main__':unittest.main()
