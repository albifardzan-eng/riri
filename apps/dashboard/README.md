# RIRI Dashboard

Authenticated, server-rendered operational dashboard for RIRI.

Set these server-only variables:

```dotenv
RIRI_API_URL=http://localhost:8000
RIRI_DASHBOARD_API_KEY=<same dashboard secret as brain>
```

Do not prefix the credential with `NEXT_PUBLIC_`; that would embed it in browser JavaScript.

```bash
npm ci
npm run dev
npm run lint
npm run build
```
