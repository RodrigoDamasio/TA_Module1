# Frontend Deployment — Vercel

The exact steps used to deploy this Next.js frontend to Vercel, in the order they were run.

**Result:** https://taller-url-shortener-gamma.vercel.app

| Item | Value |
|---|---|
| Vercel account / scope | `rodrigodamasiojulio-9268` (Hobby plan, free) |
| Project | `taller-url-shortener` |
| Framework | Next.js 16 (auto-detected) |
| Backend it calls | https://backend-production-7f82d.up.railway.app (see [../backend/DEPLOY.md](../backend/DEPLOY.md)) |

## Prerequisites

1. A Vercel account (vercel.com).
2. The backend already deployed — the frontend needs its URL at build time.
3. The Vercel CLI, installed once:
   ```bash
   npm i -g vercel
   ```
4. Log in (opens the browser — done by the account owner):
   ```bash
   vercel login
   vercel whoami          # confirm
   ```

## Steps

All commands run from this folder:

```bash
cd TA_Module1/Lab_module1/frontend
```

### 1. Create and link the project

```bash
vercel link --yes --project taller-url-shortener
```

This creates `.vercel/project.json` (git-ignored) and adds a `VERCEL_OIDC_TOKEN` line to `.env.local`. The existing `NEXT_PUBLIC_API_URL` in `.env.local` is kept.

### 2. Set the backend URL — before building

`NEXT_PUBLIC_*` variables are **copied into the JavaScript at build time**, so this must exist before the first production build.

```bash
printf 'https://backend-production-7f82d.up.railway.app' | vercel env add NEXT_PUBLIC_API_URL production
vercel env ls                   # confirm it is listed for Production
```

(`printf` is used instead of `echo` so no trailing newline ends up in the value.)

### 3. Deploy to production

```bash
vercel --prod --yes
```

Vercel builds the app remotely and assigns the production domain:
- `https://taller-url-shortener-gamma.vercel.app` (main)
- `https://taller-url-shortener-rodrigodamasiojulio-9268.vercel.app` (alias)

Check the deployment:

```bash
vercel inspect <deployment-url>     # status must be "● Ready"
```

### 4. Allow the Vercel domain on the backend (CORS)

Done on Railway, from `../backend`:

```bash
railway variables --set "FRONTEND_ORIGIN=http://localhost:3000,https://taller-url-shortener-gamma.vercel.app"
```

Railway redeploys automatically; it took ~100 seconds until the backend accepted requests from the Vercel domain. Until then, the page loads but every "Shorten" shows *"Can't reach the server"* (the browser blocks the call).

## Verification

```bash
FE=https://taller-url-shortener-gamma.vercel.app

# 1. Page is public
curl -s -o /dev/null -w '%{http_code}\n' $FE/          # 200

# 2. The build contains the backend URL
for js in $(curl -s $FE/ | grep -oE '/_next/static/[^"]+\.js' | sort -u); do
  curl -s $FE$js | grep -q backend-production-7f82d.up.railway.app && echo "found in $js"
done

# 3. Full end-to-end suite against production (E7) — 6/6 passed
nvm use 24
BASE_URL=$FE npx playwright test
```

## Things to remember

- **Changing the backend URL** requires a new build: update the variable (`vercel env rm` / `vercel env add`), then `vercel --prod` again.
- **A new frontend domain** (e.g. a custom domain) must also be added to `FRONTEND_ORIGIN` on Railway, or the browser will block API calls.
- The E2E run against production stores a few `https://example.com/e2e/...` test links in the live database.

## Redeploying after code changes

```bash
cd TA_Module1/Lab_module1/frontend
nvm use 24
npm run typecheck && npm run lint && npm test && npm run build   # make sure it's green first
vercel --prod
BASE_URL=https://taller-url-shortener-gamma.vercel.app npx playwright test
```

Useful commands: `vercel ls` (deployments), `vercel logs <deployment-url>`, `vercel env ls`, `vercel rollback` (back to the previous production deployment).
