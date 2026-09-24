# URL Shortener — Backend

FastAPI + SQLite. Design and test plan: [../BACKEND_PLAN.md](../BACKEND_PLAN.md). Architecture, error handling and security review: [../BACKEND_REVIEW_PLAN.md](../BACKEND_REVIEW_PLAN.md).

## Architecture

Layered, DDD-style — dependencies point inward (`api → application → domain ← infrastructure`), enforced by `tests/test_architecture.py`.

```
app/
├── domain/           # ShortCode, TargetUrl (value objects), ShortLink (aggregate), errors, ports
├── application/      # ShortenUrl, ResolveShortLink (use cases)
├── infrastructure/   # SQLite repository (the only SQL), random code generator, DB connection
├── api/              # routes, schemas, RFC 9457 problems, dependency wiring
├── config.py
└── main.py           # composition root (create_app)
```

**Errors** follow [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457): every error is `application/problem+json` with `type`, `title`, `status`, `detail`, `instance` (and `errors[]` with JSON Pointers for validation). Problem types are documented at `GET /problems/{slug}`.

**SQL injection:** all SQL is parameterized and lives in `app/infrastructure/`; Ruff's `S608` rule and `tests/test_sql_injection.py` guard against regressions.

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
