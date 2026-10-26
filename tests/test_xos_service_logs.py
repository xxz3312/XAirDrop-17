"""Fast-exit service diagnostics must include INFO logs and exclude unrelated text."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / 'tools/device/popsicle-xos-service-smoke.sh').read_text()
COLLECT = SCRIPT[SCRIPT.index('collect_registration_log() {'):SCRIPT.index('\ncollect_registration_log\n')]


class ServiceLogTests(unittest.TestCase):
    def test_info_level_and_process_diagnostics_survive_post_exit_dump(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);(root/'report').mkdir()
            logcat = root/'logcat'
            logcat.write_text('''#!/bin/sh
printf '%s\\n' "$@" > "$CAPTURE_ARGS"
cat <<'LOG'
10-26 18:24:29.100 16613 16613 I DomesticXOsComm: registration failed
10-26 18:24:29.101 9 9 I unrelated: private user text
10-26 18:24:29.102 16613 16613 I libc: process final message
10-26 18:24:29.103 8 8 I servicemanager: registration rejected
10-26 18:24:29.104 9 9 I MiuiDataServiceManagerImpl: unrelated telephony text
LOG
''')
            logcat.chmod(0o700)
            env = dict(os.environ, PATH=str(root)+':'+os.environ.get('PATH',''), CAPTURE_ARGS=str(root/'args'))
            shell = 'work=$1\nstart_time="10-26 18:24:29.000"\nobserved_pid=16613\n'+COLLECT+'\ncollect_registration_log\n'
            subprocess.run(['sh','-c',shell,'test',tmp],env=env,check=True,timeout=3)
            output = (root/'report/registration-log.txt').read_text()
            self.assertIn('registration failed',output)
            self.assertIn('process final message',output)
            self.assertIn('registration rejected',output)
            self.assertNotIn('private user text',output)
            self.assertNotIn('unrelated telephony text',output)
            args=(root/'args').read_text().splitlines()
            self.assertIn('-d',args)
            self.assertIn('*:V',args)
            self.assertIn('10-26 18:24:29.000',args)


if __name__ == '__main__':
    unittest.main()
