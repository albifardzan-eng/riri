#!/usr/bin/env bash
# Runs as the existing deployment user. Host bootstrap is deliberately separate.
set -Eeuo pipefail
revision=${1:?commit SHA required}
[[ "$revision" =~ ^[a-f0-9]{40}$ ]] || exit 64
: "${RIRI_RELEASE_ROOT:?set a dedicated release directory}"
: "${RIRI_ACTIVE_LINK:?set the symlink used by riri-api WorkingDirectory}"
: "${RIRI_ENV_FILE:?set the existing server-side environment file}"
: "${RIRI_STATE_DIR:?set a persistent directory outside releases}"
: "${RIRI_PUBLIC_ORIGIN:?set the HTTPS API origin}"
[[ "$RIRI_PUBLIC_ORIGIN" == https://* ]] || exit 64
[[ -L "$RIRI_ACTIVE_LINK" && -f "$RIRI_ENV_FILE" && -d "$RIRI_STATE_DIR" ]] || exit 65
exec 9>"$RIRI_RELEASE_ROOT/.deploy.lock"
flock -n 9 || exit 75
release="$RIRI_RELEASE_ROOT/$revision"
previous=$(readlink -f "$RIRI_ACTIVE_LINK")
[[ ! -e "$release" ]] || { echo 'Release already exists; refusing overwrite'; exit 65; }
# Receive only a git archive from the trusted CI run; no .env or runtime state.
mkdir -p "$release"
tar -xf - -C "$release" --no-same-owner --no-same-permissions
python3 -m venv "$release/.venv"
"$release/.venv/bin/pip" install --requirement "$release/apps/brain/requirements.txt"
(
  cd "$release/apps/brain"
  "$release/.venv/bin/python" -m unittest discover -s tests -v
)
ln -s "$RIRI_ENV_FILE" "$release/apps/brain/.env"
printf '%s\n' "$revision" > "$release/REVISION"
switch_release() {
  ln -s "$1" "$RIRI_ACTIVE_LINK.next"
  mv -Tf "$RIRI_ACTIVE_LINK.next" "$RIRI_ACTIVE_LINK"
  sudo -n systemctl restart riri-api
}
rollback() {
  echo 'Health check failed; restoring previous release'
  switch_release "$previous"
}
trap rollback ERR
switch_release "$release"
RIRI_EXPECTED_REVISION="$revision" python3 - <<'PY'
import json, os, time, urllib.request
origin=os.environ['RIRI_PUBLIC_ORIGIN'].rstrip('/')
for attempt in range(10):
    try:
        for root in ('http://127.0.0.1:8000', origin):
            for endpoint, expected in (('/health','healthy'),('/ready','ready')):
                with urllib.request.urlopen(root+endpoint, timeout=5) as r:
                    payload=json.load(r)
                    if payload.get('status') != expected: raise ValueError('unhealthy')
                    if endpoint=='/health' and payload.get('revision') != os.environ['RIRI_EXPECTED_REVISION']:
                        raise ValueError('wrong release is serving traffic')
        break
    except Exception:
        if attempt == 9: raise
        time.sleep(2)
PY
trap - ERR
printf 'Deployed %s\n' "$revision"
