"""Host tests for actual adapter helpers. Android calls are replaced in shell."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

IO = Path(__file__).resolve().parents[1] / 'popsicle-stock-cnss-io.sh'


class StockCNSSIOTests(unittest.TestCase):
    def shell(self, code, **env):
        return subprocess.run(['sh', '-c', '. "$IO"\nSC_LOG=\n' + code],
                              text=True, capture_output=True,
                              env=dict(os.environ, IO=str(IO), **env))

    def test_wifi_parser_rejects_transport_error_and_unknown_text(self):
        for output, rc, expected in [('Wifi is enabled\nconnected', '0', '1'),
                                     ('Wifi is disabled', '0', '0'),
                                     ('Wifi is enabled', '1', None),
                                     ('Failed transaction', '1', None),
                                     ('unknown', '0', None)]:
            result = self.shell('sc_android(){ printf "%s\\n" "$OUT";return "$RC"; };sc_wifi_state',
                                OUT=output, RC=rc)
            self.assertEqual(result.returncode == 0, expected is not None)
            self.assertEqual(result.stdout.strip(), expected or '')

    def test_framework_capture_uses_pipe_for_stdout_and_stderr_and_retains_rc(self):
        result = self.shell(r'''
fake(){
 case "$(readlink /proc/$$/fd/1)" in *) ;; esac
 python3 -c 'import os,sys;assert os.readlink("/proc/self/fd/1").startswith("pipe:");assert os.readlink("/proc/self/fd/2").startswith("pipe:");print("out");print("err",file=sys.stderr)'
 return 7
}
sc_capture fake
''')
        self.assertEqual(result.returncode, 7)
        self.assertIn('out', result.stderr)
        self.assertIn('err', result.stderr)
        self.assertNotIn('AssertionError', result.stderr)

    def test_capture_failure_after_command_does_not_report_success(self):
        result = self.shell('sc_log(){ return 1; };ok(){ return 0; };sc_capture ok')
        self.assertNotEqual(result.returncode, 0)

    def test_hash_or_manifest_read_error_cannot_match_empty_strings(self):
        for code in ['sc_hash(){ return 1; };sc_key(){ return 1; };',
                     'sc_hash(){ echo value; };sc_key(){ return 1; };',
                     'sc_hash(){ return 1; };sc_key(){ echo value; };',
                     'sc_hash(){ echo wrong; };sc_key(){ echo value; };']:
            self.assertNotEqual(self.shell(code + 'sc_hash_matches unused unused').returncode, 0)
        self.assertEqual(self.shell('sc_hash(){ echo value; };sc_key(){ echo value; };sc_hash_matches unused unused').returncode, 0)

    def test_manifest_requires_one_nonempty_two_column_key(self):
        for content, expected in [('key\tvalue\n', 'value'), ('key\tvalue\nother\tx\n', 'value'),
                                  ('key\ta\nkey\tb\n', None), ('key\t\n', None),
                                  ('key\tvalue\textra\n', None), ('other\tx\n', None)]:
            with tempfile.TemporaryDirectory() as folder:
                Path(folder, 'deployment.tsv').write_text(content)
                result = self.shell('sc_key key', SC_BUNDLE=folder)
                self.assertEqual(result.returncode == 0, expected is not None)
                self.assertEqual(result.stdout.strip(), expected or '')

    def test_private_check_handles_android_mode_text_and_owner(self):
        for mode, accepted in [('700', True), ('600', True), ('755', True), ('644', True),
                               ('1700', True), ('777', False), ('775', False),
                               ('646', False), ('7x0', False), ('70', False)]:
            result = self.shell('stat(){ if [ "$2" = %u ];then echo "$OWNER";else echo "$MODE";fi; };sc_private /nonexistent-fixture', MODE=mode, OWNER='0')
            self.assertEqual(result.returncode == 0, accepted, mode)
        result = self.shell('stat(){ if [ "$2" = %u ];then echo 2000;else echo 700;fi; };sc_private /nonexistent-fixture')
        self.assertNotEqual(result.returncode, 0)

    def test_hal_names_are_arguments_not_shell_text(self):
        for name, valid in [('vendor.wifi_hal_legacy', True), ('vendor.wifi_hal', True),
                            ('vendor.wifi_hal;reboot', False), ('vendor.wifi_hal x', False),
                            ('other', False), ('', False), ('vendor.wifi_hal/../init', False)]:
            self.assertEqual(self.shell('sc_valid_hal "$NAME"', NAME=name).returncode == 0, valid)

    def test_getprop_failure_is_not_an_empty_successful_hal_inventory(self):
        for check in ['sc_hals', 'sc_hals_are_stopped', 'sc_hals_are_running']:
            result = self.shell('getprop(){ return 1; };sc_wait_hals(){ return 0; };' + check)
            self.assertNotEqual(result.returncode, 0)

    def test_large_property_dump_works_with_external_printf_and_sorted_hal_names(self):
        result = self.shell(r'''
printf(){ /usr/bin/printf "$@"; }
getprop(){ python3 -c '[print("[unrelated.%d]: [%s]"%(i,"x"*200)) for i in range(12000)]; print("[init.svc.vendor.wifi_hal_z]: [running]"); print("[init.svc.vendor.wifi_hal_legacy]: [running]"); print("[init.svc.vendor.wifi_hal_stopped]: [stopped]"); print("[init.svc_debug_pid.vendor.wifi_hal_legacy]: [123]")'; }
sc_hals
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().splitlines(), ['vendor.wifi_hal_legacy', 'vendor.wifi_hal_z'])

    def test_stream_receipt_failure_or_duplicate_is_not_a_valid_inventory(self):
        for body in ["echo '[init.svc.vendor.wifi_hal_legacy]: [running]';return 7",
                     "echo 'SC_GETPROP_RC:0'",
                     "echo 'SC_GETPROP_RC:bad'"]:
            result = self.shell('getprop(){ ' + body + '; };sc_hals')
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(result.stdout)

    def test_stream_filter_or_sort_failure_is_propagated(self):
        for tool in ['sed', 'sort']:
            result = self.shell("getprop(){ echo '[init.svc.vendor.wifi_hal_legacy]: [running]'; };" + tool + '(){ return 1; };sc_hals')
            self.assertNotEqual(result.returncode, 0)

    def test_valid_empty_hal_inventory_is_distinct_from_read_failure(self):
        result = self.shell("getprop(){ echo '[unrelated]: [value]'; };sc_hals")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(result.stdout.strip())

    def test_runtime_module_commands_have_fixed_targets_and_no_parameters(self):
        prefix = '''
SC_WLAN=qca_cld3_peach_v2;SC_PROVIDER=opairshare_wonder_provider;SC_BUNDLE=/private/bundle
sc_original_cnss(){ return 0; };sc_wifi_is_off(){ return 0; };sc_hals_are_stopped(){ return 0; }
sc_expect_wlan(){ return 0; };sc_wlan_unloadable(){ return 0; };sc_wlan_absent(){ return 0; }
sc_provider_absent(){ return 0; };sc_expect_provider(){ return 0; }
sc_capture(){ printf '%s\\n' "$*"; }
'''
        for operation, expected in [('remove-wlan', '/system/bin/rmmod qca_cld3_peach_v2'),
                                    ('insert-provider', '/system/bin/insmod /private/bundle/kernel/opairshare_wonder_provider.ko'),
                                    ('insert-wlan', '/system/bin/insmod /private/bundle/kernel/qca_cld3_peach_v2.ko')]:
            result = self.shell(prefix + 'sc_effect "$OP"', OP=operation)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), expected)
        for operation in ['insert-cnss2', 'remove-cnss2', 'restore', 'live-unload']:
            result = self.shell(prefix + 'sc_effect "$OP"', OP=operation)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(result.stdout)

    def test_module_effect_is_blocked_when_wifi_or_hal_is_not_quiet(self):
        for blocked in ['sc_wifi_is_off', 'sc_hals_are_stopped', 'sc_original_cnss']:
            result = self.shell('sc_original_cnss(){ return 0; };sc_wifi_is_off(){ return 0; };sc_hals_are_stopped(){ return 0; };sc_capture(){ echo UNEXPECTED; };' + blocked + '(){ return 1; };sc_effect insert-wlan')
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('UNEXPECTED', result.stdout)


if __name__ == '__main__':
    unittest.main()
