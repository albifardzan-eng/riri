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

A successful response describes scoring and current pipeline outcomes. HTTP 200 does not mean a trade exists; inspect `qualified`, `decision`, `risk`, and `execution`.

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
`FILTERED` for directional confidence below 70, `ERROR` for provider/output
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
forbidden by the no-hedging/no-averaging rules.

Normal qualified calls are identity-scoped and limited by
`AI_MIN_CALL_INTERVAL_SECONDS` (default 60, durable across restart). A material
USD high-impact-news change may call AI early only after every deterministic
entry gate passes. Material means event identity, phase, or actual/forecast/
previous changed; countdown minutes alone do not trigger another call. The AI
receives only currently executable directions but execution repeats all rules;
there is no reuse of a prior AI decision or signal.

`ai_gate` in the market snapshot and journal provides `reason`, allowed
directions, directional block reasons, and whether a news change bypassed the
normal interval. Common values are `AI_CALLED_INITIAL_QUALIFIED`,
`AI_CALLED_INTERVAL_ELAPSED`, `AI_CALLED_NEWS_CHANGED`,
`AI_SKIPPED_SCORE_BELOW_70`, `AI_SKIPPED_SIGNAL_PENDING`,
`AI_SKIPPED_NO_EXECUTABLE_DIRECTION`, and `AI_SKIPPED_RATE_LIMIT`.

Common reasons: `AI_NO_TRADE`, `AI_DIRECTION_SELECTED`, `CONFIDENCE_BELOW_70`,
`AI_MAX_OUTPUT_TOKENS`, `AI_EMPTY_OUTPUT`, `AI_INVALID_OUTPUT`, `AI_REFUSAL`,
`AI_RESPONSE_NOT_COMPLETED`, `AI_TIMEOUT`, `AI_CONNECTION_ERROR`,
`AI_ACCESS_DENIED`, `AI_QUOTA_EXHAUSTED`, `AI_RATE_LIMITED`, `AI_API_ERROR`,
`AI_NOT_CONFIGURED`. Failures are not automatically retried.

Optional `latency_ms`, `input_tokens`, `output_tokens`, and `reasoning_tokens`
support diagnosis without exposing prompts or hidden reasoning. Output tokens
already include reasoning tokens; do not add the two to calculate output usage.
MT5 signal/ACK contracts and all trading thresholds are unchanged.

## `POST /execution/trade-event`

MT5 reports XAUUSD closing deals with broker deal/order/position IDs, side, filled lot, close price, profit, and event time. The journal de-duplicates closure events by account/instance/deal ID.
