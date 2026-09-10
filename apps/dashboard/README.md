# RIRI Dashboard

Authenticated, server-rendered operational dashboard for RIRI.

Set these server-only variables:

```dotenv
RIRI_API_URL=https://api-riri.albiagent.com
RIRI_DASHBOARD_API_KEY=<same dashboard secret as brain>
```

Do not prefix the credential with `NEXT_PUBLIC_`; that would embed it in browser JavaScript.

## Vercel production

Set **Root Directory** to `apps/dashboard`, then configure both variables above
for Production, Preview, and Development as needed. Redeploy after saving them.
The dashboard is server-rendered; the API key never reaches the browser. Point
the `riri.albiagent.com` domain at that Vercel project after a successful build.

Production dashboard release: **v1.2.0**.

```bash
npm ci
npm run dev
npm run lint
npm run build
```
