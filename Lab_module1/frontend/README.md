# URL Shortener — Frontend

Next.js 16 + TypeScript + Tailwind. Design and test plan: [../FRONTEND_PLAN.md](../FRONTEND_PLAN.md).

## Run locally

Requires **Node 24** (`nvm use 24`).

```bash
cd TA_Module1/Lab_module1/frontend
nvm use 24
npm install
npm run dev          # http://localhost:3000
```

The API address comes from `.env.local` (`NEXT_PUBLIC_API_URL=http://localhost:8000`), so start the backend first — or point it at the deployed backend:

```bash
NEXT_PUBLIC_API_URL=https://backend-production-7f82d.up.railway.app npm run dev
```

## Quality checks

```bash
npm run typecheck        # tsc --noEmit
npm run lint             # eslint
npm test                 # unit + component tests (Vitest)
npm run test:coverage    # same, with coverage (thresholds: 80%)
npm run build            # production build
npm run test:e2e         # Playwright; starts the backend (port 8000) and frontend (3000) itself
```

End-to-end tests use the **Google Chrome installed on the machine** (`channel: "chrome"`), because Playwright's bundled Chromium doesn't support Ubuntu 20.04.

To run the E2E suite against the deployed site (E7):

```bash
BASE_URL=https://<vercel-domain> npm run test:e2e
```

## Deploy to Vercel

Full step-by-step record of how it was deployed, including problems hit: [DEPLOY.md](DEPLOY.md).

**Deployed:** https://taller-url-shortener-gamma.vercel.app (project `taller-url-shortener`).

`NEXT_PUBLIC_API_URL` is **inlined at build time**, so it must be set before the build.

```bash
npm i -g vercel          # once
vercel login             # opens the browser
cd TA_Module1/Lab_module1/frontend
vercel link              # create/link the project
vercel env add NEXT_PUBLIC_API_URL production   # value: https://backend-production-7f82d.up.railway.app
vercel --prod
```

Then allow the Vercel domain on the backend (CORS), from `../backend`:

```bash
railway variables --set "FRONTEND_ORIGIN=http://localhost:3000,https://<vercel-domain>"
```
