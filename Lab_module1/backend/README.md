# URL Shortener — Backend

FastAPI + SQLite. Design and test plan: [../BACKEND_PLAN.md](../BACKEND_PLAN.md).

## Run locally

```bash
cd TA_Module1/Lab_module1/backend
source ../../../.venv/bin/activate
pip install -r requirements-dev.txt

uvicorn app.main:app --reload      # http://localhost:8000/docs
```

## Quality checks

```bash
pytest -v --cov=app --cov-report=term-missing
ruff check . && ruff format --check .
```

## Environment variables

| Variable | Default | Railway value |
|---|---|---|
| `DATABASE_PATH` | `urls.db` | `/data/urls.db` |
| `BASE_URL` | `http://localhost:8000` | `https://<railway-domain>` |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | `https://<vercel-domain>` (comma-separated for several) |
| `PORT` | — | set by Railway automatically |

## Deploy to Railway

Full step-by-step record of how it was deployed, including problems hit: [DEPLOY.md](DEPLOY.md).

`railpack.json` sets the start command (Railpack only auto-detects FastAPI when `main.py` is at the top level; ours is `app/main.py`), `railway.json` sets the `/health` health check, and `requirements.txt` + `.python-version` tell Railway to build a Python 3.12 app.

**Deployed:** https://backend-production-7f82d.up.railway.app (project `taller-url-shortener`, service `backend`, volume at `/data`).

```bash
npm i -g @railway/cli          # once
railway login                  # opens the browser
cd TA_Module1/Lab_module1/backend
railway init                   # create a new project
railway up                     # build and deploy this folder
```

Then, in the Railway dashboard for the service:

1. **Volume**: add a volume with mount path `/data` (keeps SQLite between deploys).
2. **Variables**: `DATABASE_PATH=/data/urls.db`
3. **Networking**: *Generate Domain* → copy it, then set `BASE_URL=https://<that-domain>`
4. After the frontend is on Vercel: `FRONTEND_ORIGIN=https://<vercel-domain>`

Changing variables triggers a redeploy. Verify with:

```bash
API=https://<railway-domain>
curl -s $API/health
curl -s -X POST $API/shorten -H 'Content-Type: application/json' -d '{"url":"https://example.com"}'
```
