# RIRI

RIRI is an account-scoped XAUUSD trading pipeline:

`MT5 executor → deterministic scoring → AI Trader → deterministic risk → leased execution signal → MT5 order → lifecycle journal`

## RIRI v1.3 entry policy

- Symbol: `XAUUSD` only
- Take profit: 1,000 points
- Stop loss: 3,000 points
- Maximum active RIRI XAUUSD positions (magic `20260701`): 3
- Maximum gross RIRI volume: 0.50 lot; BUY and SELL volumes are added, not netted
- No martingale. Averaging/hedging require initial score **>80 AND AI confidence >80**; exactly 80 is not sufficient
- Entry cooldown: 15 minutes from the newest still-open RIRI position, using the broker clock for both timestamps
- Other-EA/manual positions remain visible for context but do not reset RIRI cooldown or consume RIRI position limits. Account free margin still applies
- Confidence 60-69: a reduced fixed 0.01 lot; confidence 70+: 0.01 plus 0.01 for each complete USD 500 of equity, constrained by remaining exposure
- Score below 70: AI Trader is not called
- AI confidence below 60: no signal; confidence is the conservative probability that TP is reached before SL
- Maximum spread: 30 points; minimum ATR: 1.0

Policy version 2 requires the v1.3 executor and a hedging-mode account. New and
old executors must not run together on the same account/instance. AI keeps the
right to return NONE; a high self-reported confidence is not a calibrated
guarantee of success. See [upgrade and verification checklist](docs/entry-policy-v1.3.md).

## Repository

- `apps/brain`: FastAPI scoring, AI, risk, signal lifecycle, and SQLite journal
- `apps/dashboard`: authenticated server-rendered Next.js operations dashboard
- `mt5`: modular production Expert Advisor source
- `docs`: architecture and wire contracts

## Local startup

1. Copy environment templates and generate two different random secrets of at least 32 characters.
2. Set `OPENAI_API_KEY`, `RIRI_MT5_API_KEY`, and `RIRI_DASHBOARD_API_KEY`.
3. Run `docker compose up --build`.
4. In MT5, allow WebRequest for the HTTPS API origin, compile `mt5/RIRI_EXECUTOR.mq5`, and set the matching MT5 API key and a unique instance ID.

Never commit `.env`, compiled EA parameter files, archives, or credentials. See [architecture](docs/architecture.md) and [API contracts](docs/api-contracts.md).

## Production source of truth

The live backend is the path shown by `systemctl cat riri-api`, especially
`WorkingDirectory`, `EnvironmentFile`, and `ExecStart`. A checkout at
`/opt/riri` is not automatically the running release when systemd points to a
versioned directory such as `/opt/riri-releases/v1.1.0`. Diagnose and deploy
against the active release path, then verify both loopback and public
`/health` and `/ready` endpoints before resuming AutoTrading.

## Verification

```bash
cd apps/brain
python -m unittest discover -s tests -v
python -m compileall -q .

cd ../dashboard
npm ci
npm run lint
npm run build
npm audit --omit=dev
```
