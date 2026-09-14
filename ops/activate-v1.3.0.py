#!/usr/bin/env python3
"""Activate the prepared RIRI backend only. Never enables MT5 AutoTrading."""
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import pwd
import shlex
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener
from uuid import uuid4

from dotenv import dotenv_values

COMMIT = 'cf7052fdb83de595c0c956270073d3ac2f150b48'
OLD_COMMIT = '06351d708cd8c27d36186e2b3237afd23827efd8'
SERVICE = 'riri-api'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


@dataclass(frozen=True)
class Layout:
    old: Path = Path('/opt/riri-releases/v1.2.0/apps/brain')
    new: Path = Path('/opt/riri-releases/v1.3.0/apps/brain')
    state: Path = Path('/var/lib/riri')
    unit: Path = Path('/etc/systemd/system/riri-api.service')
    dropins: Path = Path('/etc/systemd/system/riri-api.service.d')
    backups: Path = Path('/opt/riri-backups')


class Cutover:
    def __init__(self, layout=None):
        self.paths = layout or Layout()
        self.dropin = self.paths.dropins / 'zzzzzzz-v1.3.0.conf'
        self.backup = None
        self.stopped = False
        self.installed = False
        self.opener = build_opener(ProxyHandler({}))
        self.old_cfg = {}
        self.new_cfg = {}

    @staticmethod
    def command(args, timeout=60):
        return subprocess.run(args, check=True, text=True, capture_output=True,
                              timeout=timeout).stdout.strip()

    def control(self, action):
        args = ['systemctl', action]
        if action != 'daemon-reload':
            args.append(SERVICE)
        return self.command(args)

    def show(self, prop):
        return self.command(['systemctl', 'show', SERVICE, '--no-pager', '--value', '-p', prop])

    def api(self, path, key=None, public=False, timeout=5):
        origin = 'https://api-riri.albiagent.com' if public else 'http://127.0.0.1:8000'
        request = Request(origin + path, headers={'Authorization': 'Bearer ' + key} if key else {})
        try:
            with self.opener.open(request, timeout=timeout) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            return exc.code, None

    def no_open_positions(self):
        code, snapshot = self.api('/dashboard/latest', self.old_cfg['RIRI_DASHBOARD_API_KEY'])
        require(code == 200 and isinstance(snapshot, dict), 'Market snapshot unavailable.')
        market = snapshot.get('market') or {}
        positions = market.get('positions')
        age = int(time.time()) - int(market.get('market_time') or 0)
        require(isinstance(positions, list) and 0 <= age <= 30,
                'Fresh positions unavailable; keep old EA attached and AutoTrading paused.')
        require(str(market.get('account_id')) == '112052965' and
                market.get('terminal_id') == 'MetaQuotes-Demo', 'Unexpected MT5 account/server.')
        require(all('magic_number' in p for p in positions), 'Cannot verify ownership of all positions.')
        own = [p for p in positions if p.get('symbol') == 'XAUUSD' and int(p['magic_number']) == 20260701]
        require(not own, 'Active RIRI positions remain; cutover stopped.')
        print(f'OPEN_RIRI_POSITIONS=0 LAST_MARKET_AGE_SECONDS={age}', flush=True)

    def preflight(self):
        p = self.paths
        require(socket.gethostname().split('.')[0] == 'riri-prod-01', 'Unexpected host.')
        require(self.show('ActiveState') == 'active', 'RIRI is not active.')
        require(self.show('WorkingDirectory') == str(p.old), 'Active release is not v1.2.0.')
        require(self.show('EnvironmentFiles') == f'{p.old}/.env (ignore_errors=no)',
                'Unexpected effective EnvironmentFiles; no configuration changed.')
        require(not self.show('Environment'), 'Inline service Environment requires inspection; do not print secrets.')
        require(not self.show('UnsetEnvironment'), 'UnsetEnvironment overrides require inspection.')
        require(p.unit.is_file() and p.dropins.is_dir(), 'Expected systemd unit/drop-ins missing.')
        require(not self.dropin.exists() and not self.dropin.is_symlink(), 'v1.3 drop-in already exists.')
        for path in shlex.split(self.show('DropInPaths')):
            require(Path(path).name < self.dropin.name, 'A later systemd override would take precedence.')
        require(p.state.resolve() == p.state and p.state.is_dir(), 'Unexpected/missing shared state directory.')
        user = self.show('User')
        owner = pwd.getpwnam(user)
        for folder, expected in ((p.old, OLD_COMMIT), (p.new, COMMIT)):
            git = ['runuser', '-u', user, '--', 'git', '-C', str(folder)]
            require(self.command(git + ['rev-parse', 'HEAD']) == expected,
                    'Release commit differs from the verified commit.')
            self.command(git + ['diff', '--exit-code', 'HEAD', '--'])
            require((folder / 'venv/bin/uvicorn').is_file(), 'Release uvicorn missing.')
        prepared = json.loads((p.new / '.deploy-prepared.json').read_text())
        require(prepared.get('commit') == COMMIT and prepared.get('old_directory') == str(p.old)
                and prepared.get('state_directory') == str(p.state), 'Staging manifest mismatch.')
        self.old_cfg = dotenv_values(p.old / '.env')
        self.new_cfg = dotenv_values(p.new / '.env')
        require(self.old_cfg.get('APP_VERSION') == '1.2.0', 'Old version configuration mismatch.')
        require(self.new_cfg.get('APP_VERSION') == '1.3.0', 'New version configuration mismatch.')
        for cfg in (self.old_cfg, self.new_cfg):
            require(cfg.get('RIRI_STATE_DIR') == str(p.state), 'Shared state path changed.')
        for key in ('OPENAI_API_KEY', 'RIRI_DASHBOARD_API_KEY', 'RIRI_MT5_API_KEY'):
            require(bool(self.new_cfg.get(key)) and self.new_cfg[key] == self.old_cfg.get(key),
                    'Credential differs from the active release: ' + key)
        for key, value in {'AI_MIN_CALL_INTERVAL_SECONDS': '60',
                           'AI_EVENT_MIN_INTERVAL_SECONDS': '30', 'AI_PRICE_CHANGE_ATR': '0.25'}.items():
            require(self.new_cfg.get(key) == value, 'Prepared AI gate configuration changed: ' + key)
        env_stat = (p.new / '.env').stat()
        require(env_stat.st_uid == owner.pw_uid and env_stat.st_mode & 0o077 == 0,
                'New .env ownership/permissions differ from the service user.')
        for name in ('journal.sqlite3', 'signals.sqlite3', 'market_state.sqlite3', 'snapshots.sqlite3'):
            require((p.state / name).is_file(), 'Missing durable database: ' + name)
        code, status = self.api('/status', self.old_cfg['RIRI_DASHBOARD_API_KEY'])
        require(code == 200 and status.get('version') == '1.2.0', 'Active API version check failed.')
        self.no_open_positions()

    def backup_configuration(self):
        p = self.paths
        p.backups.mkdir(parents=True, exist_ok=True)
        self.backup = p.backups / ('pre-v1.3.0-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                                   + '-' + uuid4().hex[:8])
        self.backup.mkdir(mode=0o700)
        size = sum(f.stat().st_size for f in p.state.rglob('*') if f.is_file())
        require(shutil.disk_usage(self.backup).free > size * 1.2 + 64 * 1024 * 1024,
                'Not enough free disk space for the state backup.')
        shutil.copy2(p.unit, self.backup / p.unit.name)
        shutil.copytree(p.dropins, self.backup / 'riri-api.service.d', symlinks=True)
        for version, folder in (('v1.2.0', p.old), ('v1.3.0', p.new)):
            target = self.backup / (version + '.env')
            shutil.copy2(folder / '.env', target)
            target.chmod(0o600)
        metadata = {name: self.show(name) for name in
                    ('WorkingDirectory', 'EnvironmentFiles', 'ExecStart', 'DropInPaths', 'User')}
        metadata.update(old_commit=OLD_COMMIT, new_commit=COMMIT, state=str(p.state))
        (self.backup / 'service-before.json').write_text(json.dumps(metadata, indent=2))
        print('BACKUP_DIR=' + str(self.backup), flush=True)

    @staticmethod
    def journal_rows(path, before_id=None):
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=10) as db:
            if before_id is not None:
                return db.execute('SELECT COUNT(*) FROM journal WHERE id<=?', (before_id,)).fetchone()[0]
            return db.execute('SELECT COUNT(*), COALESCE(MAX(id), 0) FROM journal').fetchone()

    def backup_state(self):
        require(self.show('ActiveState') == 'inactive', 'Service did not stop; state backup aborted.')
        # Preserve all files INCLUDING WAL/SHM as one stopped-service snapshot.
        destination = self.backup / 'state'
        shutil.copytree(self.paths.state, destination, symlinks=True)
        for path in destination.glob('*.sqlite3'):
            with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=10) as db:
                require(db.execute('PRAGMA quick_check').fetchall() == [('ok',)],
                        'Backup integrity check failed: ' + path.name)
        self.journal_count, self.journal_last_id = self.journal_rows(destination / 'journal.sqlite3')
        (self.backup / 'journal-before.json').write_text(json.dumps({
            'count': self.journal_count, 'last_id': self.journal_last_id}))
        print(f'STATE_BACKUP_OK JOURNAL_ROWS_BEFORE={self.journal_count}', flush=True)

    def install_override(self):
        p = self.paths
        self.override = ('[Service]\nWorkingDirectory=' + str(p.new) + '\n'
            'EnvironmentFile=\nEnvironmentFile=' + str(p.new / '.env') + '\n'
            'ExecStart=\nExecStart=' + str(p.new / 'venv/bin/uvicorn') +
            ' main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=127.0.0.1\n')
        # Publish a fully written file atomically, without replacing an
        # existing operator override. Temporary name is not a .conf file.
        temporary = p.dropins / ('.riri-v130-' + uuid4().hex + '.tmp')
        try:
            with temporary.open('x') as file:
                file.write(self.override)
                file.flush()
                os.fsync(file.fileno())
            temporary.chmod(0o644)
            os.link(temporary, self.dropin)
            self.installed = True
        except BaseException:
            if self.dropin.exists() and temporary.exists() and os.path.samefile(temporary, self.dropin):
                self.installed = True
            raise
        finally:
            temporary.unlink(missing_ok=True)

    def wait_health(self):
        deadline = time.monotonic() + 50
        while time.monotonic() < deadline:
            try:
                if self.api('/health', timeout=2) == (200, {'status': 'healthy'}):
                    return
            except (URLError, TimeoutError, ValueError):
                pass
            time.sleep(0.5)
        raise RuntimeError('Local health check timed out.')

    def verify(self, rollback=False):
        folder = self.paths.old if rollback else self.paths.new
        cfg = self.old_cfg if rollback else self.new_cfg
        version = '1.2.0' if rollback else '1.3.0'
        require(self.show('WorkingDirectory') == str(folder) and self.show('ActiveState') == 'active',
                'Effective service directory/state mismatch.')
        require(self.show('EnvironmentFiles') == f'{folder}/.env (ignore_errors=no)',
                'Effective EnvironmentFiles mismatch after reload.')
        pid = int(self.show('MainPID'))
        require(pid > 0 and Path(f'/proc/{pid}/cwd').resolve() == folder,
                'Running process does not use the expected release directory.')
        code, status = self.api('/status', cfg['RIRI_DASHBOARD_API_KEY'])
        require(code == 200 and status.get('version') == version, 'Authenticated version check failed.')
        if not rollback:
            require(self.api('/ready') == (200, {'status': 'ready'}), 'Local readiness failed.')
            require(self.api('/status')[0] == 401, 'Local status accepted missing credentials.')
            for endpoint, expected in (('/health', 200), ('/ready', 200), ('/status', 401)):
                code, _ = self.api(endpoint, public=True, timeout=10)
                require(code == expected, 'Public ' + endpoint + ' check failed: HTTP ' + str(code))
            retained = self.journal_rows(self.paths.state / 'journal.sqlite3', self.journal_last_id)
            require(retained == self.journal_count, 'Historical journal row count changed; verify backup.')
            print(f'JOURNAL_ROWS_RETAINED={retained}', flush=True)
            print('PRODUCTION_VERSION=1.3.0 PUBLIC_HEALTH=200 PUBLIC_READY=200 PUBLIC_UNAUTHENTICATED_STATUS=401', flush=True)

    def rollback(self):
        if self.installed:
            if self.dropin.exists():
                require(self.dropin.read_text() == self.override,
                        'Override changed concurrently; automatic rollback stopped for inspection.')
                self.dropin.rename(self.backup / 'failed-v1.3.0.conf')
            self.control('daemon-reload')
        # The migration only adds a column. Do not roll back/delete journal data.
        self.control('restart')
        self.wait_health()
        self.verify(rollback=True)
        print('ROLLBACK_V1_2_0_OK; state was not overwritten; backup retained.', flush=True)

    def activate(self):
        try:
            self.preflight()
            self.backup_configuration()
            self.no_open_positions()  # recheck immediately before stopping
            self.stopped = True  # recover even if systemctl stop times out
            self.control('stop')
            self.backup_state()
            self.install_override()
            self.control('daemon-reload')
            require(self.show('WorkingDirectory') == str(self.paths.new), 'New override did not take effect.')
            self.control('start')
            self.wait_health()
            self.verify()
            (self.backup / 'deployment-success.txt').write_text(COMMIT + '\n')
            print('RIRI_V1_3_0_PRODUCTION_OK', flush=True)
            print('KEEP_AUTOTRADING_PAUSED; compile/install matching EA v1.3.0 next.', flush=True)
            return 0
        except BaseException as exc:
            print('DEPLOY_STOPPED: ' + type(exc).__name__ + ': ' + str(exc), file=sys.stderr, flush=True)
            if self.stopped:
                try:
                    self.rollback()
                except BaseException as error:
                    print('ROLLBACK_FAILED: ' + type(error).__name__ + ': ' + str(error), file=sys.stderr, flush=True)
                    print('Keep trading paused. Inspect: sudo systemctl status riri-api --no-pager -l', file=sys.stderr)
            if self.backup:
                print('BACKUP_DIR=' + str(self.backup), flush=True)
            return 1


def main():
    if sys.argv[1:] != ['--paused-no-position'] or os.geteuid() != 0:
        print('Usage: sudo /opt/riri-releases/v1.3.0/apps/brain/venv/bin/python activate-v1.3.0.py --paused-no-position')
        return 1
    os.umask(0o077)
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Interrupted; attempt service rollback.')
    signal.signal(signal.SIGTERM, interrupted)
    with open('/run/lock/riri-deploy.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('STOP: another RIRI deployment is running.')
            return 1
        return Cutover().activate()


if __name__ == '__main__':
    raise SystemExit(main())
