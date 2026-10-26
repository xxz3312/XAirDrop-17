"""Run the component test script against a fake sysfs and module commands."""
import hashlib
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

P = 'opairshare_wonder_provider'
Q = 'opairshare_route_b_probe'
HASHES = {
    P: '8b1c55b4d98d2867209671e47b4e2b676e64d19553f7e2bf611201dadfc4ab6a',
    Q: '158e250cbef5d64f906758bdb2fea9ca755a9c4aa9ca6c2748ea8e5171ef8ade',
    'wonder': '5270dab5e09c33c39f4b2a70f3ab766cb36cd072bb8464bbe152e8b79e0560a9',
    'mac80211': '01b40a32346277f30b807d31c4acd7011e18c38bdff594282f5e835d40f40dec',
}


class MasterSmokeTests(unittest.TestCase):
    def run_case(self, preloaded=True, **flags):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        modules, net, device, master, phy = [root / n for n in ['modules', 'net', 'device', 'master', 'phy']]
        for d in [modules, net, root / 'bin', root / 'stock']:
            d.mkdir()
        for n in ['qca_cld3_peach_v2', 'cfg80211'] + (['mac80211'] if preloaded else []):
            (modules / n).mkdir()
        (net / 'wlan0').mkdir()
        (root / 'log').write_text('[old] Connected to wlan ver 5 (cur: wonder ver 7)\n')
        script = (Path(__file__).resolve().parents[1] / 'tools/device/popsicle-master-smoke.sh').read_text()
        paths = {'/sys/module/': str(modules) + '/', '/sys/class/net': str(net),
                 '/sys/class/ieee80211/wonder': str(phy),
                 '/sys/bus/platform/devices/qcom,cnss-vendor-wlan-wonder': str(device),
                 '/sys/bus/platform/devices/wonder': str(master),
                 '/proc/sys/net/wonder/wonder_enable': str(root / 'absent-node'),
                 '/data/local/tmp': str(root / 'tmp'), '/sdcard/Download': str(root / 'reports')}
        for a, b in paths.items():
            script = script.replace(a, b)
        for n, digest in HASHES.items():
            data = ('mock ' + n).encode()
            dest = root / 'stock/mac80211.ko' if n == 'mac80211' else root / (n + '.ko')
            dest.write_bytes(data)
            script = script.replace(digest, hashlib.sha256(data).hexdigest())
        for path in ['/vendor/lib/modules/mac80211.ko', '/vendor_dlkm/lib/modules/mac80211.ko',
                     '/system_dlkm/lib/modules/mac80211.ko']:
            script = script.replace(path, str(root / 'stock/mac80211.ko'))
        note_data = b'mock stock build-id note'
        script = script.replace('899f5b3a74a889052e6cd74bf50381e29d67fcd156b09bdfe9baf01add52a7aa',
                                hashlib.sha256(note_data).hexdigest())
        if preloaded:
            note = modules / 'mac80211/notes/.note.gnu.build-id'
            note.parent.mkdir()
            note.write_bytes(b'wrong note' if flags.get('BAD_MAC_NOTE') else note_data)
        if flags.get('BAD_MAC_FILE'):
            (root / 'stock/mac80211.ko').write_bytes(b'wrong file')
        (root / 'run-test.sh').write_text(script)
        insmod = '''n=$(basename "$1" .ko)
echo "load:$n" >> "$TRACE"
[ "${FAIL_LOAD:-none}" != "$n" ] || exit 1
if [ "$n" = opairshare_route_b_probe ]; then
    count=0; [ ! -f "$COUNT" ] || count=$(cat "$COUNT")
    count=$((count + 1)); echo "$count" > "$COUNT"
    if [ "${FAIL_RELOAD:-0}" = 1 ] && [ "$count" = 2 ]; then exit 1; fi
fi
mkdir "$MODULES/$n"
if [ "$n" = mac80211 ]; then
    mkdir "$MODULES/$n/notes"
    printf 'mock stock build-id note' > "$MODULES/$n/notes/.note.gnu.build-id"
fi
case "$n" in
 opairshare_wonder_provider) mkdir "$DEVICE" ;;
 wonder)
    if [ "${NO_DRIVER:-0}" = 1 ]; then
        echo '[new] WARNING: CPU: 0 at net/mac80211/main.c:1234 ieee80211_alloc_hw_nm+0x10' >> "$LOG"
        exit 0
    fi
    mkdir -p "$MASTER/driver" "$PHY"
    [ "${NEW_INTERFACE:-0}" = 0 ] || mkdir "$NET/unexpected"
    [ "${SILENT_BIND:-0}" = 0 ] || exit 0
    echo '[first] Connected to wlan ver 5 (cur: wonder ver 7)' >> "$LOG" ;;
 opairshare_route_b_probe)
    if [ -d "$MODULES/wonder" ]; then
        echo '[second] Connected to wlan ver 5 (cur: wonder ver 7)' >> "$LOG"
    fi ;;
esac'''
        rmmod = '''echo "unload:$1" >> "$TRACE"
[ "${FAIL_UNLOAD:-none}" != "$1" ] || exit 1
rm -rf "$MODULES/$1"
case "$1" in
 wonder)
    rm -rf "$MASTER" "$PHY" "$NET/unexpected" ;;
 opairshare_route_b_probe)
    if [ -d "$MODULES/wonder" ]; then echo '[new] Unregistered vendor operations.' >> "$LOG"; fi ;;
 opairshare_wonder_provider) rmdir "$DEVICE" ;;
esac'''
        commands = {'id': 'echo 0', 'uname': 'echo 6.12.69-android16-6-g43b5ab7e247d-abogki558343811-4k',
                    'getprop': 'case "$1" in ro.product.device) echo popsicle;; *) echo OS4.0.5.0.XPBCNXM;; esac',
                    'dmesg': 'cat "$LOG"', 'insmod': insmod, 'rmmod': rmmod}
        for n, body in commands.items():
            p = root / 'bin' / n
            p.write_text('#!/bin/sh\n' + body + '\n')
            p.chmod(0o700)
        env = dict(os.environ, PATH=str(root / 'bin') + ':' + os.environ['PATH'],
                   TRACE=str(root / 'trace'), MODULES=str(modules), NET=str(net),
                   DEVICE=str(device), MASTER=str(master), PHY=str(phy), LOG=str(root / 'log'),
                   COUNT=str(root / 'count'), **flags)
        r = subprocess.run(['sh', root / 'run-test.sh'], env=env,
                           capture_output=True, text=True, timeout=15)
        calls = (root / 'trace').read_text().splitlines() if (root / 'trace').exists() else []
        archives = list((root / 'reports').glob('*.tar.gz'))
        self.assertEqual(len(archives), 1, r.stdout + r.stderr)
        with tarfile.open(archives[0]) as t:
            self.assertFalse(any(n.endswith('.ko') for n in t.getnames()))
            report = t.extractfile('result.txt').read().decode()
            if flags.get('NO_DRIVER') == '1':
                self.assertIn('WARNING: CPU: 0 at net/mac80211/main.c',
                              t.extractfile('dmesg-after.txt').read().decode())
        return r, calls, report, (modules / 'mac80211').exists()

    def test_preloaded_dependency_identity_must_match(self):
        for flag in ['BAD_MAC_FILE', 'BAD_MAC_NOTE']:
            r, calls, report, mac = self.run_case(**{flag: '1'})
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(calls, [])  # No candidate loads, no preexisting unload.
            self.assertIn('FAIL_OR_INTERRUPTED', report)
            self.assertTrue(mac)

    def test_bind_unbind_rebind_and_dependency_order(self):
        r, calls, report, mac = self.run_case()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls, ['load:' + P, 'load:' + Q, 'load:wonder', 'unload:' + Q,
                                 'load:' + Q, 'unload:wonder', 'unload:' + Q, 'unload:' + P])
        self.assertIn('PASS_MASTER_BIND_UNBIND_REBIND', report)
        self.assertTrue(mac)  # Preexisting dependency remains untouched.

    def test_only_our_stock_dependency_is_unloaded(self):
        r, calls, report, mac = self.run_case(preloaded=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls[0], 'load:mac80211')
        self.assertEqual(calls[-1], 'unload:mac80211')
        self.assertIn('mac_loaded_by_test=1', report)
        self.assertFalse(mac)

    def test_insmod_success_without_probe_or_fresh_bind_is_failure(self):
        for flags in [{'NO_DRIVER': '1'}, {'SILENT_BIND': '1'}]:
            r, calls, report, _ = self.run_case(**flags)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('unload:wonder', calls)
            self.assertIn('FAIL_OR_INTERRUPTED', report)

    def test_rebind_failure_cleans_master_and_provider(self):
        r, calls, report, _ = self.run_case(FAIL_RELOAD='1')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(calls[-2:], ['unload:wonder', 'unload:' + P])
        self.assertIn('master_still_owned=0', report)

    def test_master_unload_failure_preserves_all_dependencies(self):
        r, calls, report, _ = self.run_case(FAIL_UNLOAD='wonder')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(calls[-1], 'unload:wonder')
        self.assertIn('master_still_owned=1', report)
        self.assertIn('probe_still_owned=1', report)
        self.assertIn('provider_still_owned=1', report)

    def test_unexpected_interface_stops_test(self):
        r, calls, report, _ = self.run_case(NEW_INTERFACE='1')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(calls[-3:], ['unload:wonder', 'unload:' + Q, 'unload:' + P])
        self.assertIn('FAIL_OR_INTERRUPTED', report)


if __name__ == '__main__':
    unittest.main()
