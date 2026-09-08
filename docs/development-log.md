# Development log

## 2026-09-08 — 1.1.3 billable-AI gate

- Retained ten-second MT5 snapshots while adding a durable 60-second,
  identity-scoped normal AI interval.
- Added deterministic two-direction preflight before AI: score, pending signal,
  cooldown, market quality, position/lot limits, no hedging, and no averaging.
  AI is not called when no direction could execute.
- Added material high-impact-news fingerprints. A new event, phase transition,
  or actual/forecast/previous revision can bypass the normal interval only when
  a new entry is otherwise legal.
- Passed currently executable directions into the existing strict AI prompt;
  backend and MT5 execution rechecks remain authoritative. No threshold, lot,
  TP/SL, hedging, averaging, or decision reuse rule changed.
- Added journal/dashboard diagnostics and regression coverage for rate limits,
  news changes, cooldown, loss-position blocking, and single legal direction.

## 2026-09-08 — 1.1.2 analysis observability

- Raised the default output-token ceiling to 2048; retained model, timeout,
  strict two-field schema, no retries, and every trading/risk threshold.
- Distinguished real NONE, low-confidence filtering, unavailable AI, quota,
  rate-limit, timeout, incomplete, refusal, empty and invalid responses.
- Added sanitized latency/token diagnostics, with no response bodies or secrets.
- Added durable cycle status and cycle-ID guards against stale snapshot writes.
  Unexpected/cancelled request handling records a terminal diagnostic.
- Dashboard displays current-cycle status and diagnostic reasons; journal
  prioritizes the actual spread rejection over generic RISK_REJECTED.
- Isolated all test state from production SQLite files and added offline
  regression coverage. No live OpenAI calls are needed to run these tests.
- Deployment is separate from publishing this branch. Existing `.env` values
  override defaults: explicitly set `APP_VERSION=1.1.2` and
  `OPENAI_MAX_OUTPUT_TOKENS=2048` in the **new** release before staging.
  A larger cap may increase cost/latency and does not guarantee completion.
  Keep the active release, shared state and rollback backup until verified.

## 2026-09-08 — AI response reliability

- Replaced prompt-only JSON with strict Responses API Structured Outputs.
- Raised the configurable output budget because it includes reasoning tokens,
  not only the visible two-field JSON object.
- Added explicit incomplete/empty/malformed response handling that fails closed
  to `NONE` without turning an expected model-output condition into a traceback.
- Disabled response persistence for one-shot market decisions.
- Added regression tests for the schema contract, all four live context inputs,
  token budget, privacy flag, and fail-closed edge cases.
- Isolated API tests from production `.env` so they cannot invoke or bill the
  live OpenAI model during deployment verification.
- Documented the systemd release path as production source of truth to prevent
  debugging the inactive `/opt/riri` checkout.

## 2026-09-02 — full audit remediation

- Replaced the stale monolithic EA with the supplied seven-file production source.
- Removed macro shadowing that silently changed H1/120 candles/magic configuration to M5/100/a different magic number.
- Switched analytical candles and ATR to closed bars while preserving live bid/ask and current tick volume.
- Added strict market metadata, UTC timestamps, identity binding, API authentication, and durable replay protection.
- Replaced the global one-shot signal with account-scoped SQLite expiry and delivery leases.
- Enforced confidence, spread, ATR, staleness, position count, exposure, hedging, and averaging rules in backend risk, signal creation, and MT5 preflight.
- Added broker `OrderCheck`, fill-mode selection, detailed execution/rejection ACKs, and idempotent close-event journaling.
- Fixed Pydantic fundamental payload loss and exposed provider availability to AI Trader.
- Restored RSI as the 15-point momentum input and removed the undeclared reversal boost from total score.
- Consolidated dashboard reads, kept credentials server-only, fixed lifecycle labels, and updated vulnerable production dependencies.
- Added reproducible Python pins, Docker deployment, automated rule tests, and CI.
- Removed `riri-source.zip` from the active tree because it contained a live-looking credential.

### Required operator action

Rotate/revoke the exposed OpenAI credential before deployment. Removing the ZIP in a new commit does not erase older Git history. Purging history and force-pushing is intentionally deferred because it rewrites shared history and must be coordinated explicitly.
