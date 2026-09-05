# Development log

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
