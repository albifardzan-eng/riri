# RIRI v1.3: entry policy and rollout

## Approved changes

| Entry type | Initial score | AI confidence | Other gates |
|---|---:|---:|---|
| First entry / profitable same-side scale-in | >=70 | >=60 | All apply |
| Same-side addition while any RIRI position on that side loses | >80 | >80 | All apply |
| Opposite-side entry / hedge | >80 | >80 | All apply |
| Mixed BUY/SELL RIRI portfolio | >80 | >80 | All apply |

Strict >80 means 81–100; score 80 or confidence 80 is not enough for an
exception. No martingale or loss-dependent lot escalation. Confidence 60–69
keeps 0.01 lot; >=70 keeps the equity formula. TP1000/SL3000, spread<=30,
ATR>=1, positive free margin, maximum 3 RIRI positions and gross RIRI volume
<=0.50 remain enforced. A hedge never cancels gross exposure for limit purposes.

Cooldown is 900 seconds from the newest **still-open RIRI** position. A new
RIRI entry restarts it; analysis, skips, price changes and foreign positions do
not. As before, closing all RIRI positions removes this open-position gate.
This is not a persisted cooldown since the most recent historical closed trade.

## Clock correction

The old EA sent POSITION_TIME (broker clock) while the backend subtracted it
from UTC. With a non-UTC broker this can extend/shorten the apparent cooldown.
The new EA sends server_time=TimeCurrent along with the unchanged open_time.
Both sides now compare timestamps from the same broker clock. Snapshot freshness
still uses TimeGMT/UTC. The backend conservatively uses age at snapshot time.
Unknown or future position times are blocked explicitly, with no guessed offset.

References: [TimeCurrent](https://www.mql5.com/en/docs/dateandtime/timecurrent),
[position properties](https://www.mql5.com/en/docs/constants/tradingconstants/positionproperties).
The user's actual broker offset still needs runtime verification; the code
defect does not by itself prove the cause of every historical skipped entry.

## Scope and AI cost

Only XAUUSD magic 20260701 affects RIRI position rules. Manual/EMERALD positions
remain visible in market/account context but do not reset cooldown or consume
RIRI's 3-position/0.50-lot limits. These are **not combined portfolio limits**;
running other EAs can increase total account exposure. Whole-account free margin
and broker OrderCheck still apply. Run one RIRI executor per account/magic;
multiple instances with the same magic share positions and must not race orders.

Normal AI interval stays 60 seconds. Material news, new closed candles, new
feasible directions or price movement >=0.25 ATR can trigger an earlier call
after at least 30 seconds. These defaults are configurable in .env. They never
override entry cooldown, initial score or risk gates. Identical ticks do not
trigger early calls and do not reset the interval. NONE remains a valid decision;
confidence is the model's estimate, not a verified probability guarantee.

## Safe coordinated rollout (not automatically performed)

1. Confirm current AutoTrading state, positions, active systemd WorkingDirectory
   and git SHA. Pause new automated entries. Do not close existing trades just
   to upgrade; if positions remain, explicitly plan their management first.
2. Back up service/drop-ins, private environment and durable state with a
   consistent SQLite backup or while the backend is stopped. Never copy live
   SQLite files without their WAL state. Do not delete/reinitialize the journal.
3. Prepare a separate v1.3 release at the reviewed commit; keep the old release
   and venv for rollback. Copy secrets privately, set APP_VERSION=1.3.0, retain
   RIRI_STATE_DIR=/var/lib/riri. No keys are rotated by this patch.
4. Run unit tests and compile checks offline. Run staging with a temporary
   RIRI_STATE_DIR and OPENAI_API_KEY empty; no production market POSTs or orders.
5. Compile all matching MT5 source files using MetaEditor. Native MT5 compilation
   and broker-order execution are not covered by the Python/static contract tests.
6. Switch the backend first and verify /health and authenticated /status. Replace
   the old EA with v1.3 while paused. An old EA against the new backend gets
   EXECUTOR_UPGRADE_REQUIRED and no new signals; a new EA rejects old signals.
7. Check [ENTRY_GATE]: own/foreign counts match MT5; entry age matches broker
   time; countdown reaches zero at 900s; low-score exceptions stay blocked.
   With AutoTrading paused, AI should be skipped as TRADING_NOT_ALLOWED.
8. Resume only after an explicit operator decision and verify in a demo account
   that >80/>80 exceptions, gross limits, cooldown and retained TP/SL work.

Rollback requires both backend and EA from the prior release. Pause entries
first; restoring only one side intentionally leaves entry blocked. The added
SQLite column is backward compatible; do not drop any history to roll back.

## Verification coverage

Offline regression tests cover 80/81 boundaries in risk and execution, timezone
offsets, exact 899/900/901-second cooldown boundaries, foreign-position isolation,
invalid clocks, unchanged gross caps/TP/SL/lot policy, paused/legacy/netting
fail-closed behavior, all-blocker diagnostics, pending signals, AI opportunity
throttle, restart/additive migration, and prompt/response directional thresholds.

MT5 source-contract tests verify parity of constants, metadata and guards.
They are not a substitute for MetaEditor compilation and demo order tests.
