"""Local cutover failure drills with fake systemd and disposable SQLite state."""
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('riri_activation', ROOT / 'ops/activate-v1.3.0.py')
activation = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = activation
spec.loader.exec_module(activation)


class FakeCutover(activation.Cutover):
    def __init__(self, layout):
        super().__init__(layout)
        self.active = 'active'
        self.loaded = layout.old
        self.actions = []
        self.failure = None

    def preflight(self):
        if self.failure == 'preflight':
            raise RuntimeError('preflight rejected')
        self.old_cfg = self.new_cfg = {'RIRI_DASHBOARD_API_KEY': 'offline-dummy'}

    def no_open_positions(self):
        if self.failure == 'positions':
            raise RuntimeError('position still open')

    def show(self, prop):
        return {'WorkingDirectory': str(self.loaded), 'ActiveState': self.active,
                'EnvironmentFiles': str(self.loaded / '.env') + ' (ignore_errors=no)',
                'ExecStart': 'fake uvicorn', 'DropInPaths': '', 'User': 'fake'}[prop]

    def control(self, action):
        self.actions.append(action)
        if action == 'stop':
            self.active = 'inactive'
        elif action == 'daemon-reload':
            self.loaded = self.paths.new if self.dropin.exists() else self.paths.old
        elif action in {'start', 'restart'}:
            self.active = 'active'

    def wait_health(self):
        pass

    def verify(self, rollback=False):
        if not rollback and self.failure == 'verify':
            # A new record written after migration must survive rollback.
            with sqlite3.connect(self.paths.state / 'journal.sqlite3') as db:
                db.execute("INSERT INTO journal(payload) VALUES ('new-runtime-event')")
            raise RuntimeError('simulated public readiness failure')
        expected = self.paths.old if rollback else self.paths.new
        activation.require(self.loaded == expected and self.active == 'active', 'wrong fake process state')
        if not rollback:
            retained = self.journal_rows(self.paths.state / 'journal.sqlite3', self.journal_last_id)
            activation.require(retained == self.journal_count, 'old journal rows lost')


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='riri-cutover-test-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.layout = activation.Layout(old=root / 'old', new=root / 'new', state=root / 'state',
            unit=root / 'systemd/riri-api.service', dropins=root / 'systemd/riri-api.service.d',
            backups=root / 'backups')
        for path in (self.layout.old, self.layout.new, self.layout.state, self.layout.dropins):
            path.mkdir(parents=True)
        self.layout.unit.write_text('[Service]\nUser=original-user\n')
        (self.layout.dropins / 'zzzzzz-v1.2.0.conf').write_text('[Service]\nWorkingDirectory=old\n')
        for directory in (self.layout.old, self.layout.new):
            (directory / '.env').write_text('DO_NOT_PRINT=secret-test-value\n')
        self.writer = sqlite3.connect(self.layout.state / 'journal.sqlite3')
        self.writer.execute('PRAGMA journal_mode=WAL')
        self.writer.execute('CREATE TABLE journal(id INTEGER PRIMARY KEY, payload TEXT)')
        self.writer.executemany('INSERT INTO journal(payload) VALUES (?)', [('trade-A',), ('trade-B',)])
        self.writer.commit()
        self.addCleanup(self.writer.close)
        self.cutover = FakeCutover(self.layout)

    def run_cutover(self):
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            result = self.cutover.activate()
        self.assertNotIn('secret-test-value', output.getvalue())
        return result, output.getvalue()

    def test_success_copies_wal_history_and_preserves_original_overrides(self):
        self.assertTrue((self.layout.state / 'journal.sqlite3-wal').is_file())
        code, output = self.run_cutover()
        self.assertEqual(code, 0, output)
        self.assertEqual(self.cutover.actions, ['stop', 'daemon-reload', 'start'])
        self.assertEqual(self.cutover.journal_rows(self.cutover.backup / 'state/journal.sqlite3'), (2, 2))
        self.assertTrue((self.layout.dropins / 'zzzzzz-v1.2.0.conf').is_file())
        text = self.cutover.dropin.read_text()
        self.assertIn('EnvironmentFile=\nEnvironmentFile=', text)
        self.assertIn('--host 127.0.0.1 --port 8000', text)
        self.assertEqual(self.cutover.backup.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.cutover.backup / 'v1.2.0.env').stat().st_mode & 0o777, 0o600)

    def test_verification_failure_rolls_service_back_without_overwriting_new_journal(self):
        self.cutover.failure = 'verify'
        code, output = self.run_cutover()
        self.assertEqual(code, 1)
        self.assertIn('ROLLBACK_V1_2_0_OK', output)
        self.assertEqual(self.cutover.loaded, self.layout.old)
        self.assertFalse(self.cutover.dropin.exists())
        self.assertTrue((self.cutover.backup / 'failed-v1.3.0.conf').is_file())
        self.assertEqual(self.cutover.journal_rows(self.layout.state / 'journal.sqlite3'), (3, 3))
        self.assertEqual(self.cutover.journal_rows(self.cutover.backup / 'state/journal.sqlite3'), (2, 2))

    def test_failed_state_backup_recovers_old_service_before_installing_override(self):
        with patch.object(self.cutover, 'backup_state', side_effect=OSError('simulated disk full')):
            code, output = self.run_cutover()
        self.assertEqual(code, 1)
        self.assertIn('ROLLBACK_V1_2_0_OK', output)
        self.assertEqual(self.cutover.actions, ['stop', 'restart'])
        self.assertFalse(self.cutover.dropin.exists())

    def test_preflight_or_position_failure_never_stops_production(self):
        for failure in ('preflight', 'positions'):
            self.cutover.failure = failure
            code, _ = self.run_cutover()
            self.assertEqual(code, 1)
            self.assertEqual(self.cutover.actions, [])
            self.assertFalse(self.cutover.dropin.exists())

    def test_atomic_override_failure_does_not_leave_a_partial_conf(self):
        with patch.object(activation.os, 'fsync', side_effect=OSError('write failure')):
            code, output = self.run_cutover()
        self.assertEqual(code, 1)
        self.assertIn('ROLLBACK_V1_2_0_OK', output)
        self.assertFalse(self.cutover.dropin.exists())
        self.assertFalse(list(self.layout.dropins.glob('*.tmp')))

    def test_existing_operator_override_is_never_overwritten(self):
        self.cutover.dropin.write_text('operator-file')
        with self.assertRaises(FileExistsError):
            self.cutover.install_override()
        self.assertEqual(self.cutover.dropin.read_text(), 'operator-file')
        self.assertFalse(self.cutover.installed)


if __name__ == '__main__':
    unittest.main()
