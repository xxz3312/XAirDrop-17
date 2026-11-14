"""Actual shell probe with simulated framework only. No native loading certification."""
import os
from pathlib import Path
import re
import signal
import time
import shutil
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
if os.environ.get('XAIRDROP_REQUIRE_MKSH')=='1' and not shutil.which('mksh'):
    raise RuntimeError('CI requires mksh')

class ProbeTests(unittest.TestCase):
    SHELL='sh'
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.bin=self.root/'bin';self.bin.mkdir()
        self.trace=self.root/'effects';self.wifi=self.root/'wifi';self.scan=self.root/'scan';self.hal=self.root/'hal'
        self.wifi.write_text('enabled');self.scan.write_text('enabled');self.hal.write_text('running')
        for m in ['cnss2','qca_cld3_peach_v2']:
            d=self.root/'sys/module'/m;(d/'notes').mkdir(parents=True)
            (d/'initstate').write_text('live\n');(d/'notes/.note.gnu.build-id').write_text(m+' fixture')
        self.command('id','echo 0')
        self.command('getprop',f'''case "$1" in ro.product.device) echo popsicle;;ro.build.version.incremental) echo OS4.0.6.0.XPBCNXM;;init.svc.vendor.wifi_hal_legacy) cat {self.hal};;*)exit 1;;esac''')
        self.command('sleep','[ "${SIGNAL_WAIT:-0}" != 1 ] || /bin/sleep 0.2;exit 0')
        effect=self.root/'effect.py'
        effect.write_text('''import os,pathlib,sys
r=pathlib.Path(sys.argv[1]);cmd=sys.argv[2];args=sys.argv[3:]
if cmd=='cmd' and args==['wifi','status']:
 assert os.readlink('/proc/self/fd/1').startswith('pipe:')
 if os.environ.get('LATE_RESTART')=='1' and (r/'hal').read_text()=='stopped':
  (r/'hal').write_text('running')
 print('Wifi is '+(r/'wifi').read_text())
 if os.environ.get('UNKNOWN')=='1':print('unknown scan state')
 else:print('Wifi scanning is '+('always available' if (r/'scan').read_text()=='enabled' else 'only available when wifi is enabled'))
 sys.exit(0)
with (r/'effects').open('a') as f:f.write(cmd+' '+ ' '.join(args)+'\\n')
if cmd=='cmd':
 assert args[:2] in (['wifi','set-scan-always-available'],['wifi','set-wifi-enabled']) and len(args)==3
 p=r/('scan' if args[1]=='set-scan-always-available' else 'wifi');p.write_text(args[2])
 if os.environ.get('FAIL_AFTER')==args[1]+':'+args[2]:sys.exit(7)
elif cmd=='stop':
 assert args==['vendor.wifi_hal_legacy'];(r/'hal').write_text('running' if os.environ.get('RESTART')=='1' else 'stopped')
 if os.environ.get('FAIL_STOP')=='1':sys.exit(7)
elif cmd=='start':
 assert args==['vendor.wifi_hal_legacy']
 if os.environ.get('FAIL_RESTORE')=='1':sys.exit(7)
 (r/'hal').write_text('running')
else:raise AssertionError(cmd)
''')
        for cmd in ['cmd','start','stop']:self.command(cmd,f'exec python3 {effect} {self.root} {cmd} "$@"')
        for cmd in ['insmod','rmmod','setprop','mount','reboot']:self.command(cmd,'echo FORBIDDEN >&2;exit 99')
        src=(ROOT/'tools/device/popsicle-hal-probe-0196.sh').read_text().replace('PATH=/system/bin:/system/xbin',f'PATH={self.bin}:/usr/bin:/bin')
        for cmd in ['cmd','start','stop']:src=src.replace('/system/bin/'+cmd,str(self.bin/cmd))
        src=src.replace('/sys/module/',str(self.root)+'/sys/module/')
        self.script=self.root/'probe.sh';self.script.write_text(src)
    def command(self,name,body):
        p=self.bin/name;p.write_text('#!/bin/sh\n'+body+'\n');p.chmod(0o755)
    def run_probe(self,**env):
        r=subprocess.run([self.SHELL,str(self.script)],env=dict(os.environ,**env),capture_output=True,timeout=15)
        self.assertNotIn(b'FORBIDDEN',r.stdout+r.stderr);return r
    def assert_restored(self,wifi='enabled',scan='enabled'):
        self.assertEqual(self.wifi.read_text(),wifi);self.assertEqual(self.scan.read_text(),scan);self.assertEqual(self.hal.read_text(),'running')
    def test_success_keeps_stock_and_restores_both_original_toggles(self):
        for wifi,scan in [('enabled','enabled'),('disabled','enabled'),('enabled','disabled'),('disabled','disabled')]:
            self.wifi.write_text(wifi);self.scan.write_text(scan)
            r=self.run_probe();self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn(b'HAL_STABLE_10_SAMPLES_STOCK_DRIVER_ONLY',r.stdout)
            self.assertIn(b'HAL_PROBE_BASELINE_RESTORED',r.stdout);self.assert_restored(wifi,scan)
    def test_unexpected_hal_restart_is_failure_with_baseline_restored(self):
        r=self.run_probe(RESTART='1');self.assertNotEqual(r.returncode,0)
        self.assertIn(b'HAL_STOP_NOT_CONFIRMED',r.stdout);self.assert_restored()
        self.assertNotIn(b'HAL_STABLE_10_SAMPLES',r.stdout)
    def test_late_restart_during_observation_stops_and_restores(self):
        r=self.run_probe(LATE_RESTART='1');self.assertNotEqual(r.returncode,0)
        self.assertIn(b'HAL_RESTART_OR_FRAMEWORK_STATE_DRIFT',r.stdout);self.assert_restored()
    def test_term_signal_runs_restoration_before_exit(self):
        p=subprocess.Popen([self.SHELL,str(self.script)],env=dict(os.environ,SIGNAL_WAIT='1'),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                if self.trace.exists() and 'stop vendor.wifi_hal_legacy' in self.trace.read_text():break
                time.sleep(0.01)
            else:self.fail('probe did not reach HAL stop')
            p.send_signal(signal.SIGTERM);out,err=p.communicate(timeout=10)
            self.assertEqual(p.returncode,143,out+err);self.assertIn(b'HAL_PROBE_BASELINE_RESTORED',out);self.assert_restored()
        finally:
            if p.poll() is None:p.kill();p.communicate()
    def test_partial_framework_mutation_failure_still_restores(self):
        for op in ['set-scan-always-available:disabled','set-wifi-enabled:disabled']:
            r=self.run_probe(FAIL_AFTER=op);self.assertNotEqual(r.returncode,0);self.assert_restored()
        r=self.run_probe(FAIL_STOP='1');self.assertNotEqual(r.returncode,0);self.assert_restored()
    def test_restore_failure_cannot_report_restoration_success(self):
        r=self.run_probe(FAIL_RESTORE='1');self.assertEqual(r.returncode,2)
        self.assertIn(b'HAL_PROBE_RESTORE_FAILED',r.stdout);self.assertNotIn(b'HAL_PROBE_BASELINE_RESTORED',r.stdout)
    def test_unknown_baseline_or_missing_stock_note_prevents_all_changes(self):
        r=self.run_probe(UNKNOWN='1');self.assertNotEqual(r.returncode,0);self.assertFalse(self.trace.exists())
        (self.root/'sys/module/cnss2/notes/.note.gnu.build-id').unlink()
        r=self.run_probe();self.assertNotEqual(r.returncode,0);self.assertFalse(self.trace.exists())
    def test_probe_has_no_module_loading_or_private_record_mutation_route(self):
        s=(ROOT/'tools/device/popsicle-hal-probe-0196.sh').read_text()
        for forbidden in ['insmod','rmmod','/data/adb','setprop','/dev/block','settings put']:
            self.assertNotIn(forbidden,s)

@unittest.skipUnless(shutil.which('mksh'),'mksh required in CI')
class MkshTests(ProbeTests):SHELL='mksh'

if __name__=='__main__':unittest.main()
