"""Offline checks for the preparation script; never contact a production VM."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'ops/prepare-v1.3.0.sh'
COMMIT = 'cf7052fdb83de595c0c956270073d3ac2f150b48'


class PrepareScriptTests(unittest.TestCase):
    def test_shell_and_embedded_python_syntax(self):
        subprocess.run(['bash', '-n', str(SCRIPT)], check=True)
        blocks = re.findall(r"<<'PY'\n(.*?)\nPY", SCRIPT.read_text(), re.S)
        self.assertEqual(len(blocks), 2)
        for number, block in enumerate(blocks):
            compile(block, 'embedded-' + str(number), 'exec')

    def test_requires_explicit_pause_confirmation(self):
        result = subprocess.run(['bash', str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('STOP: confirm RIRI AutoTrading paused', result.stdout)

    def test_preparation_contains_no_cutover_command(self):
        code = SCRIPT.read_text()
        self.assertNotRegex(code, r'systemctl\s+(?:restart|stop|start|reload|daemon-reload)\b')
        self.assertNotIn('nginx -', code)
        self.assertIn("RIRI_COMMIT='" + COMMIT + "'", code)
        self.assertIn("RIRI_STATE_DIR=state, OPENAI_API_KEY=''", code)

    def test_offline_staging_process_and_config_copy(self):
        # Exercise the actual embedded staging program against a disposable
        # copy, with the test interpreter's installed dependencies. No real
        # credentials, journal or production port are used.
        stage = re.findall(r"<<'PY'\n(.*?)\nPY", SCRIPT.read_text(), re.S)[1]
        with tempfile.TemporaryDirectory(prefix='riri-prepare-test-') as temp:
            base = Path(temp) / 'brain'
            shutil.copytree(ROOT / 'apps/brain', base,
                ignore=shutil.ignore_patterns('venv', '__pycache__', 'data', '.env', '*.sqlite3*'))
            (base / 'venv').symlink_to(sys.prefix, target_is_directory=True)
            dummy = ('OPENAI_API_KEY=offline-test-only\n'
                     'RIRI_STATE_DIR=/var/lib/riri\n'
                     'RIRI_DASHBOARD_API_KEY=' + 'd' * 64 + '\n'
                     'RIRI_MT5_API_KEY=' + 'm' * 64 + '\n')
            (base / '.env').write_text(dummy)
            result = subprocess.run([sys.executable, '-', '/old/brain', COMMIT],
                input=stage, cwd=base, env=os.environ.copy(),
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('STAGING_VERSION=1.3.0', result.stdout)
            self.assertIn('STAGING_STOPPED', result.stdout)
            self.assertNotIn('d' * 64, result.stdout + result.stderr)
            self.assertTrue((base / '.deploy-prepared.json').is_file())
            self.assertIn('offline-test-only', (base / '.env').read_text())
            self.assertFalse((base / 'data').exists())


if __name__ == '__main__':
    unittest.main()
