import json
import os
from pathlib import Path
import subprocess
import tempfile
import signal
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/device/popsicle-session.sh'
MOCK = r'''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
root=Path(os.environ['FAKE_ROOT']);args=sys.argv[1:];cmd=Path(sys.argv[0]).name
if cmd=='fake.py':cmd,args=args[0],args[1:]
with (root/'calls').open('a') as f:f.write(json.dumps([cmd,*args])+'\n')
if cmd=='id':print('0');sys.exit(0)
if cmd=='readlink':print('/devices/native/phy0');sys.exit(0)
if cmd=='cat':
 if args[0].startswith('/sys/module/'):
  print(os.environ.get('RAW_CAP','N'));sys.exit(0)
 print(Path(args[0]).read_text(),end='');sys.exit(0)
if cmd=='ip':sys.exit(0)
if cmd=='iw':
 if args[:3]==['phy','wonder','info']:sys.exit(1)
 if args[0]=='phy' and args[2:]==['interface','add','mon0','type','monitor']:
  (root/'monitor').touch();sys.exit(0)
 if args[:2]==['dev','wlan0'] and args[2:]==['info']:
  print('Interface wlan0\n\ttype managed\n\twiphy 0\n\tchannel 36 (5180 MHz), width: 20 MHz');sys.exit(0)
 if args[:2]==['dev','mon0']:
  if args[2:]==['info']:
   if not (root/'monitor').exists():sys.exit(1)
   print('Interface mon0\n\ttype monitor\n\twiphy 0'+('' if os.environ.get('MON_NO_CHANNEL') else '\n\tchannel 36 (5180 MHz), width: 20 MHz'));sys.exit(0)
  if args[2]=='set':sys.exit(0)
  if args[2:] == ['del']:
   (root/'monitor').unlink();sys.exit(0)
 raise SystemExit('unexpected iw invocation: '+str(args))
if cmd=='rx':
 if args[0]=='start':
  if os.environ.get('FAIL_RX'):sys.exit(8)
  (root/'rx').touch();sys.exit(0)
 if args[0]=='stop':
  if os.environ.get('FAIL_STOP'):sys.exit(7)
  (root/'rx').unlink();sys.exit(0)
 if args[0]=='status':print('rx_status');sys.exit(0)
if cmd=='tx':
 print('{"event":"relay_ready"}',flush=True)
 if os.environ.get('BLOCK_TX'):
  import signal,time
  def stopped(signum,frame):
   with (root/'calls').open('a') as f:f.write(json.dumps(['tx_done'])+'\n')
   sys.exit(0)
  signal.signal(signal.SIGTERM,stopped)
  (root/'tx_ready').touch()
  time.sleep(5)
 if os.environ.get('FAIL_TX'):sys.exit(9)
 print('{"event":"relay_summary","completed":2}');sys.exit(0)
raise SystemExit('unexpected command: '+cmd)
'''

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root/'bin'; self.bin.mkdir()
        self.bundle = self.root/'bundle'; self.bundle.mkdir()
        (self.root/'fake.py').write_text(MOCK)
        for name in ['id', 'iw', 'ip', 'cat', 'readlink']:
            f = self.bin/name; f.write_text(MOCK); f.chmod(0o755)
        helper = '#!/bin/sh\nexec python3 "$FAKE_ROOT/fake.py" '
        for name, mode in [('action-tx', 'tx'), ('popsicle-rx-start.sh', 'rx')]:
            f = self.bundle/name; f.write_text(helper+mode+' "$@"\n'); f.chmod(0o755)
        (self.bundle/'wonder.ko').touch()
        self.env = {**os.environ, 'FAKE_ROOT':str(self.root), 'PATH':str(self.bin)+':'+os.environ['PATH']}
        self.lock = self.root/'lock'

    def run_session(self, *args, env=None):
        return subprocess.run(['sh',str(SCRIPT),'run','--bundle',str(self.bundle),
            '--tx','wlan0','--monitor','mon0','--freq','5180','--lock',str(self.lock),
            *args],env={**self.env,**(env or {})},capture_output=True,text=True,timeout=10)

    def calls(self):
        f=self.root/'calls'
        return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []

    def test_owned_monitor_and_rx_are_released(self):
        r=self.run_session()
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertFalse((self.root/'monitor').exists())
        self.assertFalse((self.root/'rx').exists())
        self.assertFalse(self.lock.exists())
        calls=self.calls()
        self.assertIn(['iw','phy','phy0','interface','add','mon0','type','monitor'],calls)
        self.assertIn(['rx','stop'],calls)
        self.assertIn(['iw','dev','mon0','del'],calls)
        tx=next(c for c in calls if c[0]=='tx')
        self.assertEqual(tx[1],'relay')
        self.assertNotIn('--rewrite-source',tx)
        self.assertFalse(any(c[:3]==['ip','link','set'] and 'wlan0' in c for c in calls))

    def test_borrowed_monitor_is_not_changed_or_deleted(self):
        (self.root/'monitor').touch()
        r=self.run_session()
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertTrue((self.root/'monitor').exists())
        self.assertFalse(any(c[0]=='iw' and ('del' in c or 'set' in c or 'add' in c) for c in self.calls()))

    def test_raw_preflight_before_mutation(self):
        r=self.run_session('--raw')
        self.assertNotEqual(r.returncode,0)
        self.assertIn('patched WLAN',r.stderr)
        self.assertFalse(self.lock.exists())
        self.assertFalse(any(c[0]=='rx' or 'add' in c for c in self.calls()))

    def test_raw_selects_combined_transport(self):
        r=self.run_session('--raw','--rewrite-source',env={'RAW_CAP':'Y'})
        self.assertEqual(r.returncode,0,r.stderr)
        tx=next(c for c in self.calls() if c[0]=='tx')
        self.assertEqual(tx[1],'relay-all')
        self.assertIn('--rewrite-source',tx)

    def test_owned_monitor_can_follow_channel(self):
        r=self.run_session('--follow-channel')
        self.assertEqual(r.returncode,0,r.stderr)
        tx=next(c for c in self.calls() if c[0]=='tx')
        self.assertIn('--follow-channel',tx)
        self.assertEqual(tx[tx.index('--monitor')+1],'mon0')

    def test_borrowed_monitor_requires_explicit_follow_consent(self):
        (self.root/'monitor').touch()
        r=self.run_session('--follow-channel')
        self.assertNotEqual(r.returncode,0)
        self.assertIn('requires --configure-monitor',r.stderr)
        self.assertNotIn(['rx','start'],self.calls())
        self.assertTrue((self.root/'monitor').exists())
        r=self.run_session('--follow-channel','--configure-monitor')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertTrue((self.root/'monitor').exists())

    def test_failed_tool_cleans_up_its_rx_and_monitor(self):
        r=self.run_session(env={'FAIL_TX':'1'})
        self.assertEqual(r.returncode,9,r.stderr)
        self.assertIn(['rx','stop'],self.calls())
        self.assertFalse((self.root/'monitor').exists())
        self.assertFalse(self.lock.exists())

    def test_failed_rx_start_removes_only_its_monitor(self):
        r=self.run_session(env={'FAIL_RX':'1'})
        self.assertEqual(r.returncode,8,r.stderr)
        self.assertFalse((self.root/'monitor').exists())
        self.assertNotIn(['rx','stop'],self.calls())

    def test_failed_rx_stop_retains_parent_monitor(self):
        r=self.run_session(env={'FAIL_STOP':'1'})
        self.assertNotEqual(r.returncode,0)
        self.assertTrue((self.root/'monitor').exists())
        self.assertNotIn(['iw','dev','mon0','del'],self.calls())

    def test_wrong_tx_channel_has_no_resource_mutation(self):
        r=self.run_session('--freq','2412')
        self.assertNotEqual(r.returncode,0)
        self.assertIn('Native TX interface',r.stderr)
        self.assertFalse(self.lock.exists())
        self.assertFalse(any(c[0]=='rx' or 'add' in c for c in self.calls()))

    def test_owned_monitor_without_get_channel_uses_set_result(self):
        r=self.run_session(env={'MON_NO_CHANNEL':'1'})
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('rx_channel_evidence=command_accepted',(self.bundle/'session.log').read_text())

    def test_unknown_borrowed_channel_requires_explicit_configuration(self):
        (self.root/'monitor').touch()
        r=self.run_session(env={'MON_NO_CHANNEL':'1'})
        self.assertNotEqual(r.returncode,0)
        self.assertFalse(any(c[0]=='rx' or 'set' in c for c in self.calls()))
        self.assertTrue((self.root/'monitor').exists())

    def test_explicit_borrowed_monitor_configuration_is_preserved(self):
        (self.root/'monitor').touch()
        r=self.run_session('--configure-monitor',env={'MON_NO_CHANNEL':'1'})
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn(['iw','dev','mon0','set','freq','5180','HT20'],self.calls())
        self.assertTrue((self.root/'monitor').exists())

    def test_signal_stops_owned_child_before_rx_cleanup(self):
        proc=subprocess.Popen(['sh',str(SCRIPT),'run','--bundle',str(self.bundle),
            '--tx','wlan0','--monitor','mon0','--freq','5180','--lock',str(self.lock)],
            env={**self.env,'BLOCK_TX':'1'},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            deadline=time.monotonic()+3
            while not (self.root/'tx_ready').exists() and proc.poll() is None and time.monotonic()<deadline:
                time.sleep(0.01)
            self.assertTrue((self.root/'tx_ready').exists())
            proc.send_signal(signal.SIGTERM)
            _,err=proc.communicate(timeout=5)
            self.assertEqual(proc.returncode,130,err)
            calls=self.calls()
            self.assertLess(calls.index(['tx_done']),calls.index(['rx','stop']))
            self.assertFalse(self.lock.exists())
            self.assertFalse((self.root/'monitor').exists())
        finally:
            if proc.poll() is None:proc.kill();proc.communicate(timeout=5)

    def test_existing_lock_is_not_removed(self):
        self.lock.mkdir();(self.lock/'owner').write_text('foreign')
        r=self.run_session()
        self.assertNotEqual(r.returncode,0)
        self.assertEqual((self.lock/'owner').read_text(),'foreign')
        self.assertFalse(any(c[0]=='rx' or 'add' in c for c in self.calls()))

if __name__=='__main__': unittest.main()
