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

## `POST /execution/trade-event`

MT5 reports XAUUSD closing deals with broker deal/order/position IDs, side, filled lot, close price, profit, and event time. The journal de-duplicates closure events by account/instance/deal ID.
