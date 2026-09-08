# RIRI

RIRI is an account-scoped XAUUSD trading pipeline:

`MT5 executor → deterministic scoring → AI Trader → deterministic risk → leased execution signal → MT5 order → lifecycle journal`

## RIRI v1 immutable rules

- Symbol: `XAUUSD` only
- Take profit: 1,000 points
- Stop loss: 3,000 points
- Maximum active XAUUSD positions visible to the EA: 3
- Maximum combined XAUUSD volume visible to the EA: 0.50 lot
- No hedging, martingale, or averaging into a losing position
- Lot: 0.01 plus 0.01 for each complete USD 500 of equity, constrained by remaining exposure
- Score below 70: AI Trader is not called
- AI confidence below 70: no signal
- Maximum spread: 30 points; minimum ATR: 1.0

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
