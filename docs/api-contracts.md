# API contracts

## Authentication

MT5 endpoints require these headers:

| Header | Meaning |
|---|---|
| `X-RIRI-API-Key` | Secret of at least 32 characters |
| `X-RIRI-Account-ID` | MT5 login ID |
| `X-RIRI-Terminal-ID` | Broker/server identity |
| `X-RIRI-Instance-ID` | Unique EA instance label |

Dashboard endpoints require `Authorization: Bearer <RIRI_DASHBOARD_API_KEY>`. `GET /health` is public liveness. `GET /ready` is public readiness and returns HTTP 503 plus missing configuration names—never values—when required secrets are absent or weak.

## `POST /mt5/market`

Strict snapshot fields include identity, `XAUUSD`, timeframe, UTC market timestamp, bid/ask/spread, point/digits/tick metadata, account balances, closed candles, all visible XAUUSD positions (including magic number), and fundamental availability/event data. Unknown fields are rejected. Header and body identity must match.

A successful response describes scoring and current pipeline outcomes. HTTP 200 does not mean a trade exists; inspect `qualified`, `decision`, `risk`, and `execution`. It also includes flat MT5-safe telemetry (`ai_called`, `ai_gate_reason`, `ai_decision`, `ai_confidence`, `ai_status`, `ai_reason`, `risk_approved`, `risk_reason`, `execution_reason`, `signal_lot`) for the EA Expert log.

Since 1.1.2, responses and analysis journal records also carry `pipeline`
(`cycle_id`, `status`, `stage`, `reason`). A superseded analysis returns HTTP 409
and cannot write its stages over the newer cycle; unexpected processing errors
return HTTP 503 with a sanitized message. AI-provider failures still produce a
successful snapshot response, but `pipeline.status=ERROR` and decision `NONE/0`.

## `GET /execution/pending`

Returns `{"signal": null}` or an identity-bound signal containing direction, lot, immutable TP/SL points, confidence, source market time, and expiry epochs. Delivery is leased; an unacknowledged signal may be delivered again after the lease.

## `POST /execution/confirm`

Required payload:

```json
{
  "signal_id": "uuid",
  "status": "EXECUTED",
  "action": "BUY",
  "order_id": 123,
  "deal_id": 456,
  "requested_lot": 0.03,
  "filled_lot": 0.03,
  "executed_price": 2300.1,
  "retcode": 10009,
  "reason": "filled"
}
```

`status` is `EXECUTED` or `REJECTED`. Wrong identity, signal ID, or action returns HTTP 409. The signal is removed only after a matching ACK.

## Dashboard endpoints

`GET /dashboard/latest` returns one coherent latest pipeline snapshot. `GET /journal/history` returns up to 100 ordered lifecycle records. Legacy per-stage reads remain available but carry the same dashboard authentication.

The latest snapshot is **in progress**, not necessarily the last completed
analysis. Starting a cycle clears its predecessor's stages. Inspect `pipeline`:

| Status | Meaning |
|---|---|
| `PROCESSING` | Research, AI, risk or execution stage is running; later stages may be absent |
| `COMPLETED` | Analysis finished, including normal NONE, filtered confidence or risk rejection; not proof of an order |
| `SKIPPED` | Analysis gated by score/cooldown, or an older request superseded |
| `ERROR` | AI unavailable/failed, or processing failed/interrupted |

Snapshot pipeline metadata includes `started_at`, `updated_at`, `completed_at`
and source `market_time`. The dashboard is server-rendered: refresh to fetch a
new snapshot. Old records have no diagnostics; treat them as `UNKNOWN`, not as
confirmed normal NONE. A hard process kill cannot write an interruption marker;
check timestamps and service health if a PROCESSING row stops updating.

`decision.status` is backend-generated: `COMPLETED` for valid model output,
`FILTERED` for directional confidence below 60, `ERROR` for provider/output
failure, `UNAVAILABLE` when not configured, and `UNKNOWN` for legacy data.
Every failure/filter returns `decision=NONE, confidence=0`. `reason` is a
deterministic diagnostic code, **not** an AI-generated strategy explanation.
The provider's strict JSON schema remains only `decision` and `confidence`.

## AI call gate

MT5 still posts a fresh snapshot every ten seconds. That data-only request is
not an OpenAI request. Before calling AI, the backend deterministically checks
the score and whether either direction could create a new order. It skips AI
for score below 70, pending signals, entry cooldown, exhausted position/lot
limits, invalid margin/spread/ATR/staleness, and when both directions are
blocked by the conditional hedging/averaging rules (v1.3: both score and
confidence must exceed 80). Eligibility checks score before calling AI; risk,
execution and MT5 verify confidence after the response.

Normal qualified calls are identity-scoped and limited by
`AI_MIN_CALL_INTERVAL_SECONDS` (default 60, durable across restart). A material
USD high-impact-news or material opportunity change may call AI early only
after every deterministic entry gate passes and the event interval elapses
(default 30 seconds). Material news means event identity, phase, or actual/forecast/
previous changed; countdown minutes alone do not trigger another call. The AI
receives only currently executable directions but execution repeats all rules;
there is no reuse of a prior AI decision or signal.

`ai_gate` in the market snapshot and journal provides `reason`, allowed
directions, directional block reasons, and whether a news change bypassed the
normal interval. Common values are `AI_CALLED_INITIAL_QUALIFIED`,
`AI_CALLED_INTERVAL_ELAPSED`, `AI_CALLED_NEWS_CHANGED`,
`AI_SKIPPED_SCORE_BELOW_70`, `AI_SKIPPED_SIGNAL_PENDING`,
`AI_SKIPPED_NO_EXECUTABLE_DIRECTION`, and `AI_SKIPPED_RATE_LIMIT`.

Confidence is a conservative estimate that the fixed 1,000-point TP is reached
before the fixed 3,000-point SL from the current price. Confidence 60-69 can
create only a fixed 0.01-lot signal; confidence 70+ retains normal equity-based
lot sizing. Below 60 no signal is created.

Common reasons: `AI_NO_TRADE`, `AI_DIRECTION_SELECTED`,
`AI_DIRECTION_SELECTED_REDUCED_RISK`, `CONFIDENCE_BELOW_60`,
`AI_MAX_OUTPUT_TOKENS`, `AI_EMPTY_OUTPUT`, `AI_INVALID_OUTPUT`, `AI_REFUSAL`,
`AI_RESPONSE_NOT_COMPLETED`, `AI_TIMEOUT`, `AI_CONNECTION_ERROR`,
`AI_ACCESS_DENIED`, `AI_QUOTA_EXHAUSTED`, `AI_RATE_LIMITED`, `AI_API_ERROR`,
`AI_NOT_CONFIGURED`. Failures are not automatically retried.

Optional `latency_ms`, `input_tokens`, `output_tokens`, and `reasoning_tokens`
support diagnosis without exposing prompts or hidden reasoning. Output tokens
already include reasoning tokens; do not add the two to calculate output usage.
The v1.3 signal contract additionally requires initial score, policy version,
and RIRI magic number; see the versioned contract below. ACK fields are unchanged.

## v1.3 entry-policy contract (version 2)

New market fields: `server_time` (same clock as position `open_time`),
`executor_policy_version=2`, `trade_allowed` (terminal, EA and account permissions),
and `hedging_account`. `market_time` remains UTC for transport freshness.
Never compare position `open_time` directly to UTC. Defaults for legacy payloads
are fail-closed: data can be stored, but AI and entry are blocked until upgrade.
Strict legacy backends reject v1.3's extra fields; upgrade backend before EA.

Positions remain visible in the snapshot, but cooldown, direction policy, count
and gross-lot limits use only magic `20260701`. The cap is not an account-wide
portfolio cap. Free margin and broker order checks still use the whole account.
Netting accounts cannot provide reliable EA isolation and are rejected.

Signals carry `initial_score`, `entry_policy_version=2` and `magic_number`.
The executor rejects missing/mismatched versions before sending any order.
The new signal score is calculated by the backend, not supplied by the model.

`ai_gate` includes `required_confidence` per direction and `diagnostics` with
all common/directional blockers, RIRI/foreign position counts, gross lots,
profit, most recent broker entry time, its age, and remaining cooldown.
Invalid times produce `POSITION_TIME_INVALID`, not an indefinite timer.
Flat MT5 telemetry exposes the same cooldown, per-direction blockers/minimum
confidence and AI retry interval. Unknown ages/countdowns are null (MT5: -1).

`AI_SKIPPED_ENTRY_COOLDOWN` identifies a timer block; `AI_SKIPPED_TRADING_NOT_ALLOWED`,
`AI_SKIPPED_POSITION_POLICY_BLOCKED` and other specific reasons replace the old
umbrella label. For mixed blockers inspect both `buy_blockers` and `sell_blockers`.

The 60-second normal AI interval remains. A new closed candle, newly feasible
direction/lower directional confidence requirement, or a mid-price movement
of at least `AI_PRICE_CHANGE_ATR` (default 0.25) times the ATR at the last AI call
can trigger `AI_CALLED_OPPORTUNITY_CHANGED` after the event minimum (30 seconds).
Identical snapshots and tiny ticks do not bypass throttling. Skipped calls do
not reset the clock; only actual call reservations do. All state is durable and
the schema migration is additive. No prior decision is reused as a new signal.

## `POST /execution/trade-event`

MT5 reports XAUUSD closing deals with broker deal/order/position IDs, side, filled lot, close price, profit, and event time. The journal de-duplicates closure events by account/instance/deal ID.
