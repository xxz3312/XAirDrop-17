"""Execute the real shell controller against modeled Android commands/files."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/device/popsicle-wlan-trial.sh'
NAME = 'qca_cld3_peach_v2'
MOCK = r'''#!/usr/bin/env python3
import json,os,pathlib,sys,shutil
r=pathlib.Path(os.environ['MODEL_ROOT']); f=r/'model.json'; s=json.loads(f.read_text())
cmd=pathlib.Path(sys.argv[0]).name; a=sys.argv[1:]
def save(): f.write_text(json.dumps(s))
def event(x): s['events'].append(x);save()
def module(new):
 (r/'proc/modules').write_text('qca_cld3_peach_v2 100 0 - Live 0\n')
 p=r/'sys/module/qca_cld3_peach_v2/parameters';p.mkdir(parents=True,exist_ok=True)
 if new:(p/'mishare_action_tx').write_text('Y\n');(p/'mishare_raw_tx').write_text('N\n')
 if not(new and s.get('no_wlan')):(r/'sys/class/net/wlan0').mkdir(parents=True,exist_ok=True)
 s['new']=new;save()
if cmd=='id': print(0)
elif cmd=='uname': print('6.12.69-android16-6-test-4k')
elif cmd=='sleep': pass
elif cmd=='getprop':
 if not a: print('[init.svc.vendor.wifi_hal_legacy]: ['+s['hal']+']')
 else: print({'ro.product.device':'popsicle','sys.boot_completed':'1','init.svc.vendor.wifi_hal_legacy':s['hal']}.get(a[0],''))
elif cmd=='cmd': print('unknown' if s.get('unknown_wifi') else 'Wifi is '+('enabled' if s['wifi'] else 'disabled'))
elif cmd=='svc':
 event('wifi:'+a[-1]);s['wifi']=a[-1]=='enable';save()
elif cmd in ('start','stop'):
 event(cmd+':'+a[0]);s['hal']='running' if cmd=='start' else 'stopped';save()
elif cmd=='rmmod':
 if a[0]=='opairshare_wonder_provider':
  event('rmmod:provider')
  if s['new'] or s.get('provider_busy'):sys.exit(1)
  shutil.rmtree(r/'sys/module/opairshare_wonder_provider',ignore_errors=True);sys.exit(0)
 event('rmmod:new' if s['new'] else 'rmmod:stock')
 if s.get('busy') and not s['new']:sys.exit(1)
 if s.get('busy_new') and s['new']:sys.exit(1)
 (r/'proc/modules').write_text('');shutil.rmtree(r/'sys/module/qca_cld3_peach_v2',ignore_errors=True)
 shutil.rmtree(r/'sys/class/net/wlan0',ignore_errors=True)
elif cmd=='insmod':
 if a[0].endswith('/opairshare_wonder_provider.ko'):
  event('insmod:provider')
  if s.get('provider_fail'):sys.exit(1)
  (r/'sys/module/opairshare_wonder_provider').mkdir(parents=True);sys.exit(0)
 new='/bundle/' in a[0];event('insmod:new' if new else 'insmod:stock')
 if new and s.get('load_fail'):sys.exit(1)
 if not new and s.get('restore_fail'):sys.exit(1)
 if new:assert (r/'sys/module/opairshare_wonder_provider').is_dir()
 if new:assert a[1:]==['mishare_action_tx=1','mishare_raw_tx=0']
 module(new)
else: raise AssertionError(cmd)
'''


class TrialTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for path in ['bin', 'dev', 'proc', 'sys/class/net/wlan0', 'bundle/kernel',
                     'vendor_dlkm/lib/modules']:
            (self.root/path).mkdir(parents=True)
        (self.root/'proc/modules').write_text(f'{NAME} 100 0 - Live 0\n')
        self.state = dict(wifi=True, hal='running', new=False, events=[])
        self.save()
        for name in ['id', 'uname', 'sleep', 'getprop', 'cmd', 'svc', 'start', 'stop', 'rmmod', 'insmod']:
            p = self.root/'bin'/name
            p.write_text(MOCK)
            p.chmod(0o755)
        self.bundle = self.root/'bundle'
        module = self.bundle/'kernel'/f'{NAME}.ko'
        module.write_bytes(b'modeled new module')
        (self.root/'vendor_dlkm/lib/modules'/f'{NAME}.ko').write_bytes(b'original module')
        provider = self.bundle/'kernel/opairshare_wonder_provider.ko'
        provider.write_bytes(b'modeled provider')
        (self.bundle/'SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  kernel/'+f.name+'\n' for f in [module, provider]))
        source = SCRIPT.read_text()
        for old, new in [('/system/bin', str(self.root/'bin')), ('/vendor_dlkm', str(self.root/'vendor_dlkm')),
                         ('/vendor/', str(self.root/'vendor')+'/'), ('/sys/', str(self.root/'sys')+'/'),
                         ('/proc/', str(self.root/'proc')+'/'), ('/dev/', str(self.root/'dev')+'/')]:
            source = source.replace(old, new)
        self.script = self.root/'trial.sh'
        self.script.write_text(source)

    def save(self):
        (self.root/'model.json').write_text(json.dumps(self.state))

    def run_trial(self, action):
        env = dict(os.environ, MODEL_ROOT=str(self.root), PATH=str(self.root/'bin')+':'+os.environ['PATH'])
        result = subprocess.run(['sh', str(self.script), action, str(self.bundle)], env=env,
                                capture_output=True, text=True, timeout=20)
        self.state = json.loads((self.root/'model.json').read_text())
        return result

    def test_check_does_not_touch_wifi_or_driver(self):
        r = self.run_trial('check')
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertEqual(self.state['events'], [])

    def test_success_then_restore_previous_wifi_and_hal(self):
        r = self.run_trial('run')
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertTrue(self.state['new'])
        self.assertEqual(self.state['events'][:5], ['insmod:provider', 'wifi:disable', 'stop:vendor.wifi_hal_legacy', 'rmmod:stock', 'insmod:new'])
        r = self.run_trial('restore')
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertFalse(self.state['new'])
        self.assertTrue(self.state['wifi'])
        self.assertEqual(self.state['hal'], 'running')

    def test_provider_failure_never_disrupts_stock_wifi(self):
        self.state['provider_fail'] = True; self.save()
        r = self.run_trial('run')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.state['events'], ['insmod:provider'])
        self.assertTrue(self.state['wifi'])

    def test_missing_provider_rejected_before_changes(self):
        (self.bundle/'kernel/opairshare_wonder_provider.ko').unlink()
        self.assertNotEqual(self.run_trial('run').returncode, 0)
        self.assertEqual(self.state['events'], [])

    def test_existing_provider_is_not_adopted_or_unloaded(self):
        (self.root/'sys/module/opairshare_wonder_provider').mkdir(parents=True)
        self.assertNotEqual(self.run_trial('run').returncode, 0)
        self.assertEqual(self.state['events'], [])

    def test_restore_unloads_provider_after_new_wlan(self):
        self.assertEqual(self.run_trial('run').returncode, 0)
        self.assertEqual(self.run_trial('restore').returncode, 0)
        events=self.state['events']
        self.assertLess(events.index('rmmod:new'), events.index('rmmod:provider'))
        self.assertFalse((self.root/'sys/module/opairshare_wonder_provider').exists())

    def test_load_failure_restores_original_module(self):
        self.state['load_fail'] = True; self.save()
        r = self.run_trial('run')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('STOCK_RESTORED', r.stdout)
        self.assertIn('insmod:stock', self.state['events'])
        self.assertIn('rmmod:provider', self.state['events'])
        self.assertTrue(self.state['wifi'])

    def test_busy_original_never_attempts_new_driver(self):
        self.state['busy'] = True; self.save()
        r = self.run_trial('run')
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn('insmod:new', self.state['events'])
        self.assertIn('STOCK_RESTORED', r.stdout)

    def test_missing_wlan_rolls_back_new_driver(self):
        self.state['no_wlan'] = True; self.save()
        r = self.run_trial('run')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('rmmod:new', self.state['events'])
        self.assertIn('STOCK_RESTORED', r.stdout)

    def test_wonder_prevents_swap(self):
        (self.root/'sys/module/wonder').mkdir(parents=True)
        self.assertNotEqual(self.run_trial('run').returncode, 0)
        self.assertEqual(self.state['events'], [])

    def test_unknown_wifi_prevents_swap(self):
        self.state['unknown_wifi'] = True; self.save()
        self.assertNotEqual(self.run_trial('run').returncode, 0)
        self.assertEqual(self.state['events'], [])

    def test_failed_restore_reports_reboot_and_preserves_state(self):
        self.assertEqual(self.run_trial('run').returncode, 0)
        self.state['busy_new'] = True; self.save()
        r = self.run_trial('restore')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('reboot', r.stdout)
        self.assertTrue((self.root/'dev/xairdrop17-wlan-trial/wifi.before').exists())

    def test_original_disabled_wifi_stays_disabled(self):
        self.state['wifi'] = False; self.save()
        self.assertEqual(self.run_trial('run').returncode, 0)
        self.assertEqual(self.run_trial('restore').returncode, 0)
        self.assertFalse(self.state['wifi'])
        self.assertNotIn('wifi:enable', self.state['events'])

    def test_corrupt_bundle_prevents_driver_changes(self):
        (self.bundle/'kernel'/f'{NAME}.ko').write_bytes(b'corrupt')
        self.assertNotEqual(self.run_trial('run').returncode, 0)
        self.assertEqual(self.state['events'], [])


if __name__ == '__main__':
    unittest.main()
