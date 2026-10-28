# AI protection profile for small initial capital

This opt-in enhancement starts from production-reported revision
`ad986280b84e5a0a07a783bf8a10c1b566fa4a11` on
`fix/riri-enhancement-part1`. It does not activate trading or change live settings.

## Behavior

- One RIRI position or pending order at a time; no averaging/hedging or martingale.
- Pre-AI eligibility requires score >=85 by default, spread <=30 points, fresh
  market/history and broker sizing data. Structurally unaffordable minimum lot
  skips before spending tokens. Existing cooldown remains 15 minutes.
- AI chooses direction, TP/SL distance, trailing activation/distance/step,
  material movement review trigger, and falsifiable thesis in one JSON response.
- Confidence >=90 by default. This is **model judgment, not a measured win rate**.
  Historical and forward demo results are still required for calibration.
- SL must accommodate at least half ATR, broker stop distance plus spread,
  three spreads, and the cost buffer. AI cannot squeeze SL merely to fit capital.
- Net reward/risk >=1.5 after the configured buffer. Lot is rounded down to the
  broker step using nominal SL loss plus cost reserve, capped at 1% equity by
  default. If minimum lot exceeds the budget, skip. No forced 0.01-lot trade.
- Defaults are engineering starting points for demo evaluation, not proven
  optimal settings. At $100 many conventional XAUUSD contracts will be rejected.
- AI position reviews are independent of the entry score. They can CLOSE for
  thesis invalidation or early profit protection when closing is preferable
  after costs and confidence meets the threshold. Otherwise HOLD.
- AI cannot widen SL. MT5 executes the stored AI trailing plan locally, respects
  tick size/stops/freeze distance, includes observed fees/swap plus cost reserve,
  and only tightens the stop. Missing plan => retain server-side TP/SL.
- Terminal global variables persist trailing plans across restart. Backend
  confirmed execution persists the entry thesis for later AI reviews. Ambiguous
  confirmations use current evidence with an ATR trigger rather than a guessed
  entry rationale.

## Token control

Only 12 recent candles plus selected derived facts are sent; raw multi-timeframe
arrays and account IDs are excluded. Maximum prompt is 14,000 UTF-8 bytes.

Entry/review share persistent atomic quota: defaults 24 attempted calls/day,
120,000 conservative token units/day, and 1,536 maximum output tokens/call.
Reservation uses prompt/schema byte count plus output allowance and framing
buffer; actual input/output usage is logged. Failures retain their reservation.
These are ceilings, not expected spend or a currency billing guarantee.

One third of quota is reserved for position management. Minimum shared interval
is 120 seconds/account; stable price/news suppress repeat calls until 900 seconds.
A material price displacement or changed news facts triggers a new review subject
to the same floor and budget. News countdown alone is not a new event. MT5 polls
reviews at most once/minute without paying for an AI call on every poll.

If AI fails or budget is exhausted: no new AI entry/exit is issued. Broker TP/SL
and local trailing continue. There is no claim of AI control during an outage.

## Demo activation and verification

1. Keep new entries paused; reconcile pending/ambiguous executions and existing
   RIRI positions. Compile `RIRI_EXECUTOR.mq5` and `RIRI_GUARDIAN.mq5` with all
   sibling includes in MetaEditor. Require zero compile errors.
2. Deploy this exact backend revision. Enable `AI_CAPITAL_PROFILE=true` in its
   environment and `RIRI_AI_CAPITAL_PROFILE=true` on both EAs. Health reports
   `entry_policy_version:4` and `ai_capital_profile:true`. Old policy-3 executors
   cannot enter while the backend profile is enabled, and vice versa.
3. Match score/confidence/risk/reward-risk/cost settings on backend and executor.
   Use an isolated demo account near $100 equity and real broker contract specs.
   Choose the chart timeframe deliberately; existing H1/120 defaults are preserved.
4. Attach Guardian on a separate XAUUSD chart in the **same terminal**, with the
   capital profile enabled. This avoids network requests blocking its event queue.
   Both charts share the account lock and terminal plan state. The old fixed ATR
   trailing inputs do not control this profile.
5. Start with `POSITION_REVIEW_EXECUTE=false` and `RIRI_REVIEW_EXECUTE=false` to
   inspect review decisions. Enable both on demo to execute AI CLOSE decisions.
   Turning on only one cannot close a position. Entry testing needs demo AutoTrading
   enabled deliberately; no activation is performed by this code change.
6. Verify BUY and SELL initial stops, affordability rejects, broker min/step,
   stopped markets, partial fills, slippage, stale responses, token exhaustion,
   restart recovery, and strictly monotonic trailing. Compare broker logs with
   `CAPITAL_AI`, `POSITION_REVIEW`, and execution journal events.
7. Calibrate with held-out historical/forward data: net P/L after spread, commission,
   swap and AI spend; maximum drawdown; skips; confidence buckets; early-exit
   counterfactuals; and trailing effect. Do not select settings using only winners.

## Remaining limits / rollback

Backend unit tests use mocked AI and no broker. MetaEditor compilation, Strategy
Tester/forward demo, and empirical confidence calibration must be completed before
production activation. A broker can gap/slip beyond nominal SL; the percent cap
is a pre-trade nominal loss bound, not a guaranteed maximum realized loss.
The executor rechecks loss using `OrderCalcProfit` plus allowed slippage; it can
reject an otherwise backend-approved lot. Cost buffer must reflect the broker.

Keep Guardian and the profile settings in place while managing open AI-plan
positions. To roll back, pause entries, resolve/close positions and pending
submissions under operator control, then switch backend and both EAs back to
profile=false together. Never swap policy versions mid-flight.
