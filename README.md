# TA_Module1

Lab Module 1 — **URL Shortener**, built with an AI-assisted ("vibe coding") workflow.

**Live:** [frontend](https://taller-url-shortener-gamma.vercel.app) · [backend API docs](https://backend-production-7f82d.up.railway.app/docs)

| Part | Stack | Deployed on |
|---|---|---|
| [Backend](Lab_module1/backend/) | Python 3.12 · FastAPI · SQLite | Railway |
| [Frontend](Lab_module1/frontend/) | Next.js 16 · TypeScript · Tailwind | Vercel |

## Contents

| Document | What it covers |
|---|---|
| [Lab1_URL_Shortener.md](Lab_module1/Lab1_URL_Shortener.md) | The lab assignment and deliverables |
| [PLAN.md](Lab_module1/PLAN.md) | Implementation plan and end-to-end architecture diagram |
| [BACKEND_PLAN.md](Lab_module1/BACKEND_PLAN.md) | Backend design and test strategy |
| [FRONTEND_PLAN.md](Lab_module1/FRONTEND_PLAN.md) | Frontend design and test strategy |
| [BACKEND_REVIEW_PLAN.md](Lab_module1/BACKEND_REVIEW_PLAN.md) | SOLID/DDD refactor, RFC 9457 errors, SQL-injection controls |
| [backend/DEPLOY.md](Lab_module1/backend/DEPLOY.md) · [frontend/DEPLOY.md](Lab_module1/frontend/DEPLOY.md) | Exact deployment steps for Railway and Vercel |

## Quick start

```bash
# Backend (http://localhost:8000/docs)
cd Lab_module1/backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest && uvicorn app.main:app --reload

# Frontend (http://localhost:3000) — Node 24
cd Lab_module1/frontend
npm install && npm run dev
```
