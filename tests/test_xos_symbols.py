"""Symbol versions, IFUNC and visibility must not create false ABI findings."""
import sys
import json
import re
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/xos'))
from compare_device import symbol_sets


class XosSymbolsTests(unittest.TestCase):
    def test_linker_guard_uses_captured_executable_not_ld_android_stub(self):
        root = Path(__file__).resolve().parents[1]
        profile = json.loads((root / 'tools/xos/device-profile.json').read_text())
        scripts = [(root / 'tools/device' / name).read_text() for name in ('popsicle-xos-linker-audit.sh', 'popsicle-xos-loader-smoke.sh', 'popsicle-xos-service-smoke.sh')]
        for script in scripts:
            self.assertIn('check_hash /system/bin/linker64 ' + profile['linker_executable']['sha256'], script)
            self.assertNotIn('check_hash /system/bin/linker64 ' + profile['ld_android_stub']['sha256'], script)
        script = scripts[0]
        guards = re.findall(r'^check_hash /system/bin/linker64 ([0-9a-f]{64}) ', script, re.M)
        self.assertEqual(guards, [profile['linker_executable']['sha256']])
        self.assertNotEqual(guards[0], profile['ld_android_stub']['sha256'])

    def test_empty_undefined_row_does_not_consume_next_symbol(self):
        strong, weak, exports = symbol_sets("""
  0: 0000000000000000 0 NOTYPE LOCAL DEFAULT UND
  1: 0000000000000000 0 FUNC GLOBAL DEFAULT UND real@ABI (2)
""")
        self.assertEqual(strong, {'real@ABI'})
        self.assertEqual(weak, set())
        self.assertEqual(exports, set())

    def test_android_ifunc_exports_and_versioned_import(self):
        strong, weak, exports = symbol_sets('''
  1: 0000000000000000 0 FUNC GLOBAL DEFAULT UND memcpy@LIBC (2)
  2: 00000000000ea468 100 <OS specific>: 10 GLOBAL DEFAULT 16 memcpy@@LIBC
''')
        self.assertEqual(strong, {'memcpy@LIBC'})
        self.assertEqual(weak, set())
        self.assertEqual(exports, {'memcpy', 'memcpy@LIBC'})

    def test_nondefault_version_does_not_supply_bare_symbol(self):
        _, _, exports = symbol_sets(' 3: 0000000000001000 4 FUNC GLOBAL DEFAULT 8 foo@OLD\n')
        self.assertEqual(exports, {'foo@OLD'})
        self.assertNotIn('foo@NEW', exports)

    def test_hidden_and_local_definitions_are_not_exported(self):
        _, _, exports = symbol_sets('''
  1: 0000000000001000 4 FUNC GLOBAL HIDDEN 8 hidden
  2: 0000000000001004 4 FUNC LOCAL DEFAULT 8 local
  3: 0000000000001008 4 FUNC WEAK PROTECTED 8 visible
''')
        self.assertEqual(exports, {'visible'})

    def test_weak_import_is_separate_from_required_import(self):
        strong, weak, _ = symbol_sets('''
  1: 0000000000000000 0 FUNC WEAK DEFAULT UND optional
  2: 0000000000000000 0 FUNC GLOBAL DEFAULT UND required@ABI (2)
''')
        self.assertEqual(strong, {'required@ABI'})
        self.assertEqual(weak, {'optional'})


if __name__ == '__main__':
    unittest.main()
