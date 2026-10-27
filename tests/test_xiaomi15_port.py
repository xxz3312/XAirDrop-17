from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/xiaomi15'))
from port import VENDOR,PKG,reference_inputs,adapt_bridge,adapt_broker,adapt_wifi,patch_wifi,wifi_class_fingerprint


def k0():
    fields='\n'.join('.field public '+p for p in ['a:Landroid/net/wifi/WifiManager;','b:I','c:I','d:Ljava/lang/String;','e:Z'])
    return '.class public final La/k0;\n'+fields+'\n'+''.join('.method public final '+name+'\n    .locals 0\n    return-void\n.end method\n' for name in ['b()Z','e()Z','d()V'])


class Xiaomi15PortTests(unittest.TestCase):
    def source(self,name):return (VENDOR/'src'/PKG/(name+'.java')).read_text()
    def test_pinned_reference_really_uses_ndi_raw(self):
        _,route=reference_inputs();p=route['reference_driver']['module_parameters']
        self.assertEqual(p['passthru_fwtype'],'7');self.assertEqual(p['passthru_awdl_wmi_raw'],'1')
        self.assertEqual(p['passthru_ndi_peer'],'1');self.assertEqual(p['passthru_ndi_no_up'],'1')
    def test_client_no_network_agent_or_unsafe_local_fallback(self):
        s=adapt_bridge(self.source('Bridge'))
        self.assertNotIn('Network acquire()',s);self.assertNotIn('wifi.disableNetwork',s)
        self.assertIn('NetworkBroker.WIFI_HOLD',s);self.assertIn('wifiSocket = s;',s)
        self.assertIn('broker is not root',s);self.assertIn('field.setAccessible(true)',s)
    def test_broker_native_network_path_removed(self):
        s=adapt_broker(self.source('NetworkBroker'))
        for token in ['agentClass','Class.forName("a.p0")','private static Network acquire','task.get(','WIFI_LEAVE']:self.assertNotIn(token,s)
        self.assertIn('if (!WIFI_HOLD.equals(command))',s)
        self.assertIn('uid % 100000 != appId',s)
        self.assertLess(s.index('startup Wi-Fi restore:'),s.index('accept.start();'))
        self.assertIn('private static synchronized String acquireWifiHold()',s)
    def test_partial_wifi_errors_keep_recovery_record(self):
        s=adapt_wifi(self.source('WifiControl'))
        self.assertIn('/data/adb/xairdrop17/wifi-left',s)
        self.assertLess(s.index('ERROR restore incomplete'),s.index('STATE.delete()'))
        self.assertIn('ERROR partial leave',s);self.assertIn('ERROR recovery pending while Wi-Fi is connected',s)
    def test_native_reconnect_is_preserved_with_finally(self):
        s=patch_wifi(k0());self.assertIn('.method private final xairdrop17Reconnect()V',s)
        self.assertIn('.catchall',s);self.assertEqual(s.count('->restoreWifi()V'),2)
        self.assertEqual(s.count('.method public final d()V'),1)
    def test_already_patched_or_field_drift_rejected(self):
        with self.assertRaises(ValueError):patch_wifi(patch_wifi(k0()))
        with self.assertRaises(ValueError):patch_wifi(k0().replace('b:I','b:J'))
    def test_wifi_class_check_ignores_order_but_keeps_instructions(self):
        a='.class public La/k0;\n.method public a()V\n    return-void\n.end method\n'
        b='.method public b()I\n    const/4 v0, 0x0\n    return v0\n.end method\n'
        self.assertEqual(wifi_class_fingerprint(a+b),wifi_class_fingerprint('.class public La/k0;\n'+b+a.split('\n',1)[1]))
        self.assertNotEqual(wifi_class_fingerprint(a+b),wifi_class_fingerprint((a+b).replace('const/4 v0, 0x0','const/4 v0, 0x1')))
    def test_reference_adaptation_rejects_drift(self):
        with self.assertRaises(ValueError):adapt_broker(self.source('NetworkBroker').replace('"xairdrop.xos0"','"changed"'))


if __name__=='__main__':unittest.main()
