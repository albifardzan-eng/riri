# RIRI deployment integration

Status: prepared, not provisioned. GitHub write access works. Production SSH
credentials and host configuration are not available in this session. The
connected Vercel team is `albi-s-agentic`; RIRI's last successful deployment is
under `fandirandi-uxs-projects/riri`. Existing Git integration already publishes
the dashboard. Do not create a duplicate Vercel project or replace that link.

## One-time host provisioning (requires existing authorized host access)

1. Inspect `systemctl cat riri-api`, the running process, its actual release,
   environment file, Python executable and persistent SQLite state. Back up
   that state consistently before moving it. Do not deploy over `/opt/riri`
   without confirming it is the active service.
2. Configure riri-api to use a stable `current` symlink for WorkingDirectory
   and `current/.venv/bin/uvicorn` for ExecStart, preserving the existing API
   environment. Set RIRI_STATE_DIR outside release directories and retain all
   journal, signal, cooldown and review databases. An empty directory would
   discard the safety history and is not a valid migration.
3. Install the reviewed backend-release.sh as a root-owned, non-writable
   `/usr/local/lib/riri/backend-release.sh`. Install a root-owned wrapper at
   `/usr/local/bin/riri-deploy` that exports RIRI_RELEASE_ROOT, RIRI_ACTIVE_LINK,
   RIRI_ENV_FILE, RIRI_STATE_DIR and RIRI_PUBLIC_ORIGIN, then execs the script.
   Verify the symlink is actually used by the service before enabling CI.
4. Grant the existing deployment user only the required release-directory
   writes and passwordless `systemctl restart riri-api`. Use a dedicated SSH
   key with no forwarding, no PTY and a restricted forced-command dispatcher
   accepting only `/usr/local/bin/riri-deploy <40-character hex SHA>`.
   Do not grant unrestricted root SSH. Store the private key only in the
   `riri-production` GitHub environment secret RIRI_SSH_KEY.
5. Set RIRI_SSH_HOST, RIRI_SSH_USER and independently verified
   RIRI_SSH_KNOWN_HOSTS in the same environment. Never disable host-key checks.
6. Compile and validate the matching executor on demo, preserve its settings,
   disable obsolete executors, validate the complete broker-confirmation flow,
   then set repository variable RIRI_BACKEND_DEPLOY_ENABLED=true.

After bootstrap, a successful main-branch CI run deploys the exact tested SHA.
Deployments serialize; failures restore the previous symlink and service.
The workflow does not turn on terminal AutoTrading or place orders. MQL5
source changes still require a separately connected Windows/MetaEditor host;
an Ubuntu API deployment cannot install a compiled EA into a Windows MT5.

Vercel remains driven by its existing GitHub integration. Team access must
include `fandirandi-uxs-projects` for direct project/settings changes. A successful
GitHub commit-status check confirms deployment, not backend/EA compatibility.
