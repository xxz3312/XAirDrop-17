"""Exercise process ownership cleanup against harmless copied host sleep executables."""
from pathlib import Path
import shutil
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / 'tools/device/popsicle-xos-service-smoke.sh').read_text()
CLEANUP = SCRIPT[SCRIPT.index('owns_service() {'):SCRIPT.index("trap 'cleanup; exit 130'")]


@unittest.skipUnless(os.environ.get('GITHUB_ACTIONS') == 'true', 'real process ownership checks run on GitHub Ubuntu')
class ServiceCleanupTests(unittest.TestCase):
    def test_own_child_is_stopped(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            shutil.copy('/bin/sleep', stage / 'DomesticXOsComm')
            shell = 'stage=$1\nservice_pid=\nlog_pid=\n' + CLEANUP + '''
"$stage/DomesticXOsComm" 30 &
service_pid=$!
trap 'kill "$service_pid" 2>/dev/null; wait "$service_pid" 2>/dev/null' 0
sleep 0.1
owns_service || exit 2
cleanup
if kill -0 "$service_pid" 2>/dev/null; then exit 3; fi
wait "$service_pid" 2>/dev/null
exit 0
'''
            result = subprocess.run(['sh', '-c', shell, 'test', str(stage)], capture_output=True, timeout=8)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_unrelated_executable_is_not_killed(self):
        with tempfile.TemporaryDirectory() as tmp:
            other = subprocess.Popen(['/bin/sleep', '30'])
            try:
                shell = 'stage=$1\nservice_pid=$2\nlog_pid=\n' + CLEANUP + '\ncleanup\n'
                subprocess.run(['sh', '-c', shell, 'test', tmp, str(other.pid)], check=True, timeout=3)
                self.assertIsNone(other.poll())
            finally:
                other.terminate();other.wait(timeout=3)


if __name__ == '__main__':
    unittest.main()
