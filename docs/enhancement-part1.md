# RIRI enhancement part 1 — implementation checkpoint

Reference: the user's two identically sized notes named `RIRI enhancement part 1.md`
and `RIRI_enhancement_part_1.md`, read on 23 September 2026. Baseline commit:
`cf7052fdb83de595c0c956270073d3ac2f150b48` (v1.3 / executor policy 2).

## Status

Prepared in a feature branch. No production rollout or actual order execution
has been performed. Backend validation: 95 offline tests pass, including an authenticated HTTP
market → signal → single-use permit → fill-confirmation flow. Tests use
temporary SQLite databases and mocked AI. Python compilation, shell syntax
and git whitespace checks pass.
MetaEditor compilation, tick replay and demo validation have not been performed.
The Windows MT5 host is not connected. Do not mix policy-2 and policy-3 executors.

| Requirement | Implementation | Activation / remaining verification |
|---|---|---|
| Global 15-minute cooldown | Durable account state, broker entry history, last fill survives flat positions and restarts; atomic account reservation and single-use broker submission permit | Backend + policy-3 executor must be deployed together; test real fills and lost ACKs |
| Small capital | Equity <=USD500 requires integer confidence 86–100; >500 retains prior tiers | Equity and equality at 500 are the note's proposed convention, explicitly selected for this implementation; no currency conversion, USD-only gate |
| Gross exposure | Positions + pending orders, BUY and SELL added; outstanding submission serializes account; nominal remaining loss to active SL plus candidate | 0.50 lot / 3 slots retained. Optional money cap remains UNSET, never assumed 5% or 10% |
| Trailing | Cost-adjusted break-even, ATR distance, only tightens, broker stop/freeze/tick-size checks, broker result verification | Disabled until activation/step/ATR multiplier are chosen and demo-tested. Exit commission is estimated equal to entry fees; actual slippage is not guaranteed |
| Pre-close | Broker session calendar; daily entry stop T-30/review T-30,T-10/deadline T-5; weekly entry stop T-60/review T-30/deadline T-15; daily HOLD requires fresh valid review and configured threshold | Trial schedule is disabled by default. Long breaks >=24h are conservatively treated as weekly. Broker holidays require validating the broker's session feed |
| Spread exception | Optional normal60 / hard150; above60 requires score>80 AND confidence>95; pre-AI accepts a possible exception, post-AI and EA enforce it | Disabled by default, baseline30 retained; all other gates still apply |
| Continuation vs pullback | Live MARKET/STATISTICS/FUNDAMENTAL/PATTERN retained; M5/M15/H1/H4 closed candles, EMA20/ATR14 distance, rejection context; structured scenario explanations, prompt hash/version, model and token metadata | Not evidence of improved profitability or calibrated confidence |
| 45-minute review | Separate authenticated lane per ticket; first review at2700s, proposed repeat900s; durable dedup/retry; CLOSE requires invalid thesis/high SL risk and cost comparison | Review enabled in shadow mode; actual closing disabled until demo validation. Invalid/failed review never auto-closes an aged position |

TP remains 1,000 and initial SL remains 3,000. No martingale is introduced.
The pre-existing averaging/hedging exception (>80 score and >80 confidence) is
retained; Part 1 does not introduce a new exception. Manual/EMERALD positions
are excluded using magic20260701. Account-wide margin still applies.

## Executor and independent protection

`RIRI_EXECUTOR.mq5` sends snapshots, requests position reviews, obtains a
single-use submission permit and executes orders. `RIRI_GUARDIAN.mq5` must be
attached to a separate XAUUSD chart in the same terminal for protection to
continue during synchronous HTTP/AI waits. Guardian's event handlers make no
HTTP calls. Both share an exclusive common-file broker lock; executor releases
it before network confirmation. Run matching protection settings on both.

The guardian does not protect a stopped terminal or disconnected broker. The
broker's installed TP/SL remains the final protection. Unknown broker outcomes
are held for reconciliation, never blindly resubmitted. Confirmed partial
closes are verified by reduced position volume; a remaining position is retried
on the next protection cycle. An ambiguous close with no subsequent deal must
be resolved against broker history before clearing its local pending marker.
No blanket retry or forced hedge is used.

Position reviews preserve the active ticket, lot, SL and TP. An executor rejects
a stale command or one whose position protection/volume changed during the AI
call. Pre-close supersedes age review via separate T-30/T-10 buckets. Sampled
min/max quote journeys explicitly start at first observation; they are not
claimed to be complete MFE/MAE since entry or tick-accurate replay.

## Access verified

- GitHub repository `albifardzan-eng/riri`: read and push permissions available;
  administration permission is absent.
- Vercel connection: `albi-s-agentic`, which does not provide direct access to
  RIRI. GitHub's latest main-commit status identifies the existing project as
  `fandirandi-uxs-projects/riri`; that page returns Not Found for the connected
  browser user. Existing Git deployment remains intact.
- SSH: no SSH key/known-hosts or gcloud credentials are present. Google Cloud
  console returns Site Unavailable in the available browser. No server changes
  or access grants have been made.
- CI-to-SSH workflow and rollback script are prepared, but no deployment secret
  or enable flag has been provisioned. See deployment-automation.md.

## Remaining release gates

1. Connect the existing host with authorized SSH access and the Vercel account
   that owns RIRI. Inspect actual systemd WorkingDirectory/ExecStart/env/state.
2. Compile BOTH EA sources in MetaEditor; preserve input settings and verify
   broker session times, symbol metadata, account currency, magic and actual
   attached EA versions.
3. Demo-test entry90s/899s/900s boundaries, close-last-position/restart,
   concurrent instance submission, partial/ambiguous broker results, pending
   orders, stale quotes, trailing stop/freeze levels and session close fallback.
4. Choose unsettled trailing numbers, portfolio money cap, HOLD threshold and
   whether to activate the trial spread/session schedule. Record choices rather
   than treating them as optimized values or historical user approvals.
5. Validate full tick Bid/Ask strategy replay and out-of-sample/demo outcomes
   before claiming improvement. The previous M1 SL replay is not validation.
6. Enable production CI only after coordinated backend/executor provisioning;
   the deploy script checks the served commit SHA and rolls back on failure.

## Official references used for implementation

- https://www.mql5.com/en/docs/marketinformation/symbolinfosessiontrade
- https://www.mql5.com/en/docs/trading/ordersend
- https://www.mql5.com/en/docs/globals/globalvariablesetoncondition

These APIs describe broker clocks, session boundaries and execution results;
source review is not a substitute for MetaEditor compilation or demo trading.
