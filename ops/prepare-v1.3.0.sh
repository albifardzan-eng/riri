#!/usr/bin/env bash
# Preparation only: never restart/stop a service, edit Nginx, or touch live DBs.
set -Eeuo pipefail
umask 077

if [[ "${1:-}" != "--paused-no-position" || "$#" != 1 ]]; then
  echo 'STOP: confirm RIRI AutoTrading paused and no active RIRI positions.'
  echo 'Usage: bash prepare-v1.3.0.sh --paused-no-position'
  exit 1
fi

RIRI_SOURCE='/opt/riri'
RIRI_RELEASE='/opt/riri-releases/v1.3.0'
RIRI_COMMIT='cf7052fdb83de595c0c956270073d3ac2f150b48'
RIRI_NEW="$RIRI_RELEASE/apps/brain"

trap 'echo "PREPARATION_STOPPED: production service unchanged; retain any partial release for inspection." >&2' ERR

[[ "$(hostname -s)" == 'riri-prod-01' ]] || { echo 'STOP: unexpected host.'; exit 1; }
sudo -v
[[ "$(sudo systemctl show riri-api --no-pager --value -p ActiveState)" == 'active' ]] || {
  echo 'STOP: riri-api is not active; inspect it before preparing an upgrade.'; exit 1;
}
RIRI_OLD="$(sudo systemctl show riri-api --no-pager --value -p WorkingDirectory)"
case "$RIRI_OLD" in
  /opt/riri/apps/brain|/opt/riri-releases/*/apps/brain) ;;
  *) echo "STOP: unexpected active directory: $RIRI_OLD"; exit 1 ;;
esac
[[ "$(sudo systemctl show riri-api --no-pager --value -p User)" == "$(id -un)" ]] || {
  echo 'STOP: run as the configured riri-api service user, not root.'; exit 1;
}
[[ "$(sudo systemctl show riri-api --no-pager --value -p EnvironmentFiles)" == "$RIRI_OLD/.env (ignore_errors=no)" ]] || {
  echo 'STOP: effective EnvironmentFiles differs; inspect paths, never print secrets.'; exit 1;
}
[[ -f "$RIRI_OLD/.env" && -x "$RIRI_OLD/venv/bin/python" ]] || {
  echo 'STOP: active environment or interpreter missing.'; exit 1;
}
[[ ! -e "$RIRI_RELEASE" && ! -L "$RIRI_RELEASE" ]] || {
  echo 'STOP: v1.3.0 release already exists; do not overwrite it.'; exit 1;
}
case "$(git -C "$RIRI_SOURCE" remote get-url origin)" in
  https://github.com/albifardzan-eng/riri|https://github.com/albifardzan-eng/riri.git|git@github.com:albifardzan-eng/riri.git) ;;
  *) echo 'STOP: source origin is not albifardzan-eng/riri.'; exit 1 ;;
esac
printf 'ACTIVE_DIR=%s\n' "$RIRI_OLD"
git -C "$RIRI_OLD" rev-parse HEAD

# Read only: private config and authenticated local API, without model imports.
"$RIRI_OLD/venv/bin/python" - "$RIRI_OLD" <<'PY'
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener
from dotenv import dotenv_values

base = Path(sys.argv[1])
cfg = dotenv_values(base / '.env')
for key in ('RIRI_DASHBOARD_API_KEY', 'RIRI_MT5_API_KEY'):
    if len(cfg.get(key) or '') < 32:
        raise SystemExit('STOP: required credential missing/invalid: ' + key)
if not cfg.get('OPENAI_API_KEY'):
    raise SystemExit('STOP: OPENAI_API_KEY is not configured. Do not send its value to chat.')
state = Path(cfg.get('RIRI_STATE_DIR') or base / 'data')
if not state.is_absolute():
    state = base / state
if state.resolve() != Path('/var/lib/riri') or not state.is_dir():
    raise SystemExit('STOP: state directory differs from /var/lib/riri; review before proceeding.')
for name in ('journal.sqlite3', 'signals.sqlite3', 'market_state.sqlite3', 'snapshots.sqlite3'):
    if not (state / name).is_file():
        raise SystemExit('STOP: expected durable state missing: ' + name)
opener = build_opener(ProxyHandler({}))
def get(path):
    request = Request('http://127.0.0.1:8000' + path,
        headers={'Authorization': 'Bearer ' + cfg['RIRI_DASHBOARD_API_KEY']})
    try:
        with opener.open(request, timeout=10) as response:
            return json.load(response)
    except HTTPError as exc:
        raise SystemExit('STOP: local API returned HTTP ' + str(exc.code)) from None
    except (URLError, TimeoutError):
        raise SystemExit('STOP: local API unavailable/timed out.') from None
status = get('/status')
snapshot = get('/dashboard/latest')
market = snapshot.get('market') or {}
positions = market.get('positions')
age = int(time.time()) - int(market.get('market_time') or 0)
if not isinstance(positions, list) or not 0 <= age <= 30:
    raise SystemExit('STOP: fresh market/positions unavailable. Keep the old EA attached while paused.')
if any('magic_number' not in p for p in positions):
    raise SystemExit('STOP: cannot identify ownership of every open position.')
own = [p for p in positions if p.get('symbol') == 'XAUUSD' and int(p['magic_number']) == 20260701]
if own:
    raise SystemExit('STOP: snapshot still contains active RIRI positions.')
print('ACTIVE_VERSION=' + str(status.get('version')))
print('OPEN_RIRI_POSITIONS=0')
print('LAST_MARKET_AGE_SECONDS=' + str(age))
print('STATE_DIR=/var/lib/riri (unchanged)')
PY

git -C "$RIRI_SOURCE" fetch origin main
git -C "$RIRI_SOURCE" cat-file -e "${RIRI_COMMIT}^{commit}"
git -C "$RIRI_SOURCE" merge-base --is-ancestor "$RIRI_COMMIT" origin/main
git -C "$RIRI_SOURCE" worktree add --detach "$RIRI_RELEASE" "$RIRI_COMMIT"
python3 -m venv "$RIRI_NEW/venv"
"$RIRI_NEW/venv/bin/python" -m pip install -r "$RIRI_NEW/requirements.txt"
"$RIRI_NEW/venv/bin/python" -m pip check
cd "$RIRI_NEW"
# Tests overwrite state to TemporaryDirectory before importing application code.
env OPENAI_API_KEY='' venv/bin/python -m unittest discover -s tests -v
venv/bin/python -m compileall -q api config models research risk scoring security.py services trader utils main.py tests

# Never modify the active .env; create only the newly prepared release's copy.
install -m 600 "$RIRI_OLD/.env" "$RIRI_NEW/.env"
venv/bin/python - "$RIRI_OLD" "$RIRI_COMMIT" <<'PY'
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener
from dotenv import dotenv_values, set_key

base = Path.cwd()
for key, value in {
    'APP_VERSION': '1.3.0', 'ENVIRONMENT': 'production',
    'RIRI_STATE_DIR': '/var/lib/riri',
    'AI_MIN_CALL_INTERVAL_SECONDS': '60',
    'AI_EVENT_MIN_INTERVAL_SECONDS': '30',
    'AI_PRICE_CHANGE_ATR': '0.25',
}.items():
    set_key(base / '.env', key, value, quote_mode='always')
cfg = dotenv_values(base / '.env')
opener = build_opener(ProxyHandler({}))

with tempfile.TemporaryDirectory(prefix='riri-v130-stage-') as state, \
     tempfile.TemporaryFile(mode='w+t') as logs, socket.socket() as listener:
    stage_env = os.environ.copy()
    stage_env.update({k: v for k, v in cfg.items() if v is not None})
    stage_env.update(RIRI_STATE_DIR=state, OPENAI_API_KEY='',
        RIRI_DASHBOARD_API_KEY=secrets.token_hex(32), RIRI_MT5_API_KEY=secrets.token_hex(32))
    listener.bind(('127.0.0.1', 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    process = subprocess.Popen([str(base / 'venv/bin/python'), '-m', 'uvicorn',
        'main:app', '--fd', str(listener.fileno())], cwd=base, env=stage_env,
        pass_fds=(listener.fileno(),), stdout=logs, stderr=logs)
    try:
        def get(path, headers=None):
            request = Request(f'http://127.0.0.1:{port}' + path, headers=headers or {})
            try:
                with opener.open(request, timeout=2) as response:
                    return response.status, json.load(response)
            except HTTPError as exc:
                return exc.code, json.load(exc)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('staging process exited during startup')
            try:
                if get('/health') == (200, {'status': 'healthy'}):
                    break
            except (URLError, TimeoutError):
                pass
            time.sleep(0.25)
        else:
            raise RuntimeError('staging readiness timed out')
        assert get('/status')[0] == 401, 'missing dashboard credentials were accepted'
        assert get('/execution/pending')[0] == 401, 'missing MT5 credentials were accepted'
        code, status = get('/status', {'Authorization': 'Bearer ' + stage_env['RIRI_DASHBOARD_API_KEY']})
        assert code == 200 and status['version'] == '1.3.0', 'wrong staging version'
        code, body = get('/ready')
        assert code == 503 and body['detail']['missing_configuration'] == ['OPENAI_API_KEY'], \
            'offline staging must report only OpenAI unavailable'
        code, body = get('/execution/pending', {
            'X-RIRI-API-Key': stage_env['RIRI_MT5_API_KEY'],
            'X-RIRI-Account-ID': 'stage-only', 'X-RIRI-Terminal-ID': 'stage-only',
            'X-RIRI-Instance-ID': 'stage-only',
        })
        assert code == 200 and body == {'signal': None}, 'unexpected staging signal'
        print('STAGING_VERSION=' + status['version'])
        print('STAGING_AUTH_OK; OPENAI_DISABLED; TEMPORARY_STATE_ONLY')
    except Exception:
        logs.seek(0)
        print(logs.read()[-6000:], file=sys.stderr)
        raise
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        print('STAGING_STOPPED')

with (base / '.deploy-prepared.json').open('x') as file:
    json.dump({'commit': sys.argv[2], 'old_directory': sys.argv[1],
               'state_directory': '/var/lib/riri', 'version': '1.3.0',
               'prepared_at_epoch': int(time.time())}, file)
PY

git diff --quiet HEAD --
[[ "$(sudo systemctl show riri-api --no-pager --value -p WorkingDirectory)" == "$RIRI_OLD" ]]
[[ "$(sudo systemctl show riri-api --no-pager --value -p ActiveState)" == 'active' ]]
printf 'PREPARED_COMMIT=%s\nPRODUCTION_STILL=%s\n' "$RIRI_COMMIT" "$RIRI_OLD"
echo 'RIRI_V1_3_0_STAGING_OK'
echo 'STOP HERE: do not enable trading or replace the EA until coordinated cutover.'
