# Backend Deployment — Railway

The exact steps used to deploy this FastAPI backend to Railway, in the order they were run.

**Result:** https://backend-production-7f82d.up.railway.app

| Item | Value |
|---|---|
| Railway project | `taller-url-shortener` |
| Service | `backend` |
| Environment | `production` |
| Volume | `backend-volume`, mounted at `/data` |
| Builder | Railpack (auto-detected Python 3.12, pip) |

## Prerequisites

1. A Railway account (railway.com).
2. The Railway CLI, installed once:
   ```bash
   npm i -g @railway/cli
   ```
3. Log in (opens the browser — done by the account owner):
   ```bash
   railway login
   railway whoami          # confirm
   ```

## Files that configure the deploy

| File | Purpose |
|---|---|
| `requirements.txt` | Runtime dependencies (`fastapi`, `uvicorn`) — tells Railpack this is a pip project |
| `.python-version` | `3.12` — Python version for the build |
| `railpack.json` | Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| `railway.json` | Health check: `GET /health` must answer before traffic is switched to a new deploy |

## Steps

All commands run from this folder:

```bash
cd TA_Module1/Lab_module1/backend
```

### 1. Create the project and link this folder

```bash
railway whoami --json                      # shows the workspace ID
railway init --name taller-url-shortener --workspace <workspace-id>
```

### 2. Create the service with the database path

Created *before* the first deploy, so the first run already writes to the volume.

```bash
railway add --service backend --variables "DATABASE_PATH=/data/urls.db"
railway service link backend
```

### 3. Add a persistent volume for SQLite

Without it, `urls.db` lives inside the container and is erased on every redeploy.

```bash
railway volume add --mount-path /data
```

### 4. Generate the public domain and set `BASE_URL`

`BASE_URL` is used to build the `short_url` returned by `POST /shorten`.

```bash
railway domain --json                       # → https://backend-production-7f82d.up.railway.app
railway variables --set "BASE_URL=https://backend-production-7f82d.up.railway.app" --skip-deploys
```

### 5. Deploy

```bash
railway up --ci
```

`railway up` uploads this folder, Railpack builds it, and Railway starts it once `/health` answers.

### 6. Allow the frontend (CORS) — after the frontend is on Vercel

Setting a variable triggers an automatic redeploy (~1–2 min).

```bash
railway variables --set "FRONTEND_ORIGIN=http://localhost:3000,https://taller-url-shortener-gamma.vercel.app"
```

`localhost:3000` is kept so local frontend development can still call the deployed backend.

## Final environment variables

| Variable | Value |
|---|---|
| `DATABASE_PATH` | `/data/urls.db` |
| `BASE_URL` | `https://backend-production-7f82d.up.railway.app` |
| `FRONTEND_ORIGIN` | `http://localhost:3000,https://taller-url-shortener-gamma.vercel.app` |
| `PORT` | set by Railway automatically |

## Verification (smoke test)

```bash
API=https://backend-production-7f82d.up.railway.app

curl -s $API/health                                   # {"status":"ok"}
curl -s -X POST $API/shorten -H 'Content-Type: application/json' \
     -d '{"url":"https://github.com/fastapi/fastapi"}'  # 201, then 200 on repeat
curl -s -o /dev/null -w '%{http_code} -> %{redirect_url}\n' $API/<short_code>   # 307 -> original URL
curl -s $API/zzzzzz                                   # 404

# CORS: must return the Vercel origin
curl -s -o /dev/null -D - -X OPTIONS $API/shorten \
     -H "Origin: https://taller-url-shortener-gamma.vercel.app" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" | grep -i access-control-allow-origin
```

## Problems hit and how they were fixed

| Problem | Cause | Fix |
|---|---|---|
| First deploy failed: *"No start command detected"* | Railpack only auto-detects FastAPI when `main.py` is at the project root; ours is `app/main.py`. The `startCommand` in `railway.json` is applied at deploy time, after Railpack already failed at build time. | Added `railpack.json` with `deploy.startCommand`; `railway.json` keeps only the health check. |
| CLI warning: *"Config as Code (railway.json) is deprecated"* | Railway is moving to a new config format. | Nothing needed now — existing files keep working until **2026-12-01**. Run `railway config migrate` before then if the service is still in use. |

## Redeploying after code changes

```bash
cd TA_Module1/Lab_module1/backend
pytest -q && ruff check .      # make sure it's green first
railway up --ci
```

Useful commands: `railway status`, `railway logs`, `railway variables --kv`, `railway open` (dashboard).
