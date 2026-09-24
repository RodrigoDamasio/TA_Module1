# Backend Plan — URL Shortener API

Detailed plan for **Phase 1** of [PLAN.md](PLAN.md): how the FastAPI backend will be built, what the code looks like, and how its quality will be verified.

## 1. Scope

| Requirement (from the lab) | How it is met |
|---|---|
| `POST /shorten` accepts `{"url"}`, returns `{"short_code", "short_url"}` | FastAPI route with Pydantic request/response models |
| `GET /{short_code}` redirects to the original URL | `RedirectResponse` with status 307 |
| SQLite storage | Python's built-in `sqlite3`, one file (`urls.db`) |
| 6-character alphanumeric codes | `secrets.choice` over `[A-Za-z0-9]` → 62⁶ ≈ 56.8 billion combinations |
| URL validation | Pydantic `HttpUrl`: only `http`/`https`, must have a host, max 2083 chars |
| Duplicate URLs return the existing code | `UNIQUE` constraint on `url` + lookup before insert |

Plus, needed for deploy: `GET /health`, CORS for the frontend, configuration through environment variables.

## 2. Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── config.py        # settings read from environment variables
│   ├── db.py            # SQLite connection + schema
│   ├── shortener.py     # code generation + create/lookup logic
│   └── main.py          # FastAPI app, routes, CORS
├── tests/
│   ├── conftest.py      # fixtures: temporary DB, test client
│   ├── test_shortener.py  # unit tests (logic only)
│   └── test_api.py        # API tests (HTTP level)
├── requirements.txt       # runtime: fastapi, uvicorn
├── requirements-dev.txt   # tests: pytest, httpx, pytest-cov, ruff
├── pyproject.toml         # pytest + ruff settings
├── .python-version        # 3.12, read by Railway
└── railway.json           # Railway start command + health check
```

Design principles:
- **Logic separated from HTTP.** `shortener.py` knows nothing about FastAPI, so it can be unit-tested directly.
- **No hardcoded environment details.** Database path, public URL and allowed frontend origin come from environment variables with local defaults.
- **No ORM.** Only one table, so plain `sqlite3` keeps it simple and dependency-free.

## 3. Configuration

| Variable | Local default | On Railway |
|---|---|---|
| `DATABASE_PATH` | `urls.db` | `/data/urls.db` (Volume) |
| `BASE_URL` | `http://localhost:8000` | `https://<railway-domain>` |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | `https://<vercel-domain>` |
| `PORT` | 8000 | set by Railway |

```python
# app/config.py
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_path: str
    base_url: str
    frontend_origins: list[str]


def get_settings() -> Settings:
    return Settings(
        database_path=os.getenv("DATABASE_PATH", "urls.db"),
        base_url=os.getenv("BASE_URL", "http://localhost:8000").rstrip("/"),
        frontend_origins=os.getenv("FRONTEND_ORIGIN", "http://localhost:3000").split(","),
    )
```

## 4. Database

One table. Both columns that must be unique are enforced by the database itself, not just by code.

```python
# app/db.py
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    short_code  TEXT NOT NULL UNIQUE,
    url         TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
```

## 5. Core logic

```python
# app/shortener.py
import secrets
import sqlite3
import string

ALPHABET = string.ascii_letters + string.digits  # 62 characters
CODE_LENGTH = 6
MAX_ATTEMPTS = 5


def generate_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def is_valid_code(code: str) -> bool:
    return len(code) == CODE_LENGTH and all(c in ALPHABET for c in code)


def get_or_create(conn: sqlite3.Connection, url: str) -> tuple[str, bool]:
    """Return (short_code, created). Reuses the code if the URL already exists."""
    row = conn.execute("SELECT short_code FROM urls WHERE url = ?", (url,)).fetchone()
    if row:
        return row["short_code"], False

    for _ in range(MAX_ATTEMPTS):
        code = generate_code()
        try:
            with conn:
                conn.execute("INSERT INTO urls (short_code, url) VALUES (?, ?)", (code, url))
            return code, True
        except sqlite3.IntegrityError:
            # Either the code collided (retry) or another request inserted
            # the same URL in the meantime (return that one).
            row = conn.execute("SELECT short_code FROM urls WHERE url = ?", (url,)).fetchone()
            if row:
                return row["short_code"], False
    raise RuntimeError("Could not generate a unique short code")


def resolve(conn: sqlite3.Connection, code: str) -> str | None:
    row = conn.execute("SELECT url FROM urls WHERE short_code = ?", (code,)).fetchone()
    return row["url"] if row else None
```

Why `secrets` and not `random`: codes from `random` are predictable, so someone could guess other people's links. `secrets` uses a cryptographically secure source.

## 6. API

```python
# app/main.py
from collections.abc import Iterator

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl

from . import db, shortener
from .config import get_settings

settings = get_settings()
app = FastAPI(title="URL Shortener")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ShortenRequest(BaseModel):
    url: HttpUrl


class ShortenResponse(BaseModel):
    short_code: str
    short_url: str


def get_conn() -> Iterator:
    conn = db.connect(get_settings().database_path)
    try:
        yield conn
    finally:
        conn.close()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/shorten", response_model=ShortenResponse, status_code=status.HTTP_201_CREATED)
def shorten(body: ShortenRequest, response: Response, conn=Depends(get_conn)):
    code, created = shortener.get_or_create(conn, str(body.url))
    if not created:
        response.status_code = status.HTTP_200_OK
    return ShortenResponse(short_code=code, short_url=f"{get_settings().base_url}/{code}")


@app.get("/{short_code}")
def redirect(short_code: str, conn=Depends(get_conn)):
    url = shortener.resolve(conn, short_code) if shortener.is_valid_code(short_code) else None
    if url is None:
        raise HTTPException(status_code=404, detail="Short URL not found")
    return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
```

API contract:

| Request | Response |
|---|---|
| `POST /shorten {"url": "https://example.com/page"}` (new) | `201 {"short_code": "aB3xY9", "short_url": "http://localhost:8000/aB3xY9"}` |
| same request again | `200` with the same body |
| `POST /shorten {"url": "not a url"}` | `422` with validation details |
| `GET /aB3xY9` | `307`, header `Location: https://example.com/page` |
| `GET /zzzzzz` (unknown) | `404 {"detail": "Short URL not found"}` |

Decisions worth noting:
- **307 (temporary) instead of 301 (permanent).** Browsers cache 301s forever and stop calling the backend, which would break click analytics (extension challenge) and make changes impossible.
- **201 vs 200.** 201 = a new link was created; 200 = an existing one was returned. The frontend treats both as success.
- **Invalid code format → 404, not 422.** For a visitor, a malformed link and an unknown link are the same thing: "not found".
- **`/health` is declared before `/{short_code}`**, so it is never treated as a short code.
- **URL normalization:** `HttpUrl` normalizes URLs (e.g. `https://Example.com` → `https://example.com/`), so trivially different spellings of the same URL share one code.

## 7. Quality strategy

### Levels

| Level | Tool | What it covers |
|---|---|---|
| Unit tests | `pytest` | `shortener.py` logic in isolation (code format, randomness, collisions, duplicates) |
| API tests | `pytest` + FastAPI `TestClient` | Every endpoint over HTTP: status codes, bodies, headers, validation, CORS |
| Coverage | `pytest-cov` | Target **≥ 90%** line coverage of `app/` |
| Lint / style | `ruff` | Unused imports, bugs patterns, formatting |
| Manual smoke test | `curl` / Swagger UI at `/docs` | Real server running locally |
| Deploy smoke test | `curl` against Railway | Same checks against the production URL |

### Test isolation

Each test gets its **own temporary SQLite file** (pytest's `tmp_path`), so tests never share data and never touch the real `urls.db`.

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("BASE_URL", "http://test.local")
    from app.main import app
    return TestClient(app)
```

### Test cases

**Unit — `test_shortener.py`**

| ID | Test | Expected |
|---|---|---|
| U1 | `generate_code()` format | Always 6 characters, all in `[A-Za-z0-9]` (checked over 1,000 codes) |
| U2 | Codes are random | 1,000 generated codes are all distinct |
| U3 | `is_valid_code` | Accepts `aB3xY9`; rejects `abc`, `abcdefg`, `abc-12`, `abc 12`, empty string |
| U4 | New URL | `get_or_create` returns `(code, True)` and the row exists |
| U5 | Duplicate URL | Second call returns `(same code, False)`; table still has 1 row |
| U6 | Collision retry | `generate_code` patched to return an existing code first, then a new one → succeeds with the new code |
| U7 | Collision exhaustion | `generate_code` always returns an existing code → `RuntimeError` after 5 attempts |
| U8 | `resolve` | Known code → original URL; unknown code → `None` |
| U9 | Concurrent insert of the same URL | Insert fails on the `url` UNIQUE constraint → the code saved by the other request is returned |

**API — `test_api.py`**

| ID | Test | Expected |
|---|---|---|
| A1 | Shorten a valid URL | `201`, `short_code` matches `^[A-Za-z0-9]{6}$`, `short_url == "http://test.local/" + short_code` |
| A2 | Shorten the same URL twice | Second response `200` with the **same** `short_code` |
| A3 | Shorten two different URLs | Different codes |
| A4 | Invalid URLs *(parametrized)*: `"not-a-url"`, `"example.com"` (no scheme), `"ftp://example.com"`, `"javascript:alert(1)"`, `"http://"`, `""` | `422` for each |
| A5 | URL longer than 2083 chars | `422` |
| A6 | Missing `url` field / body not JSON / `url` not a string | `422` |
| A7 | Redirect | `GET /{code}` with `follow_redirects=False` → `307`, `Location` = original URL |
| A8 | Query string and fragment preserved | `https://example.com/search?q=a+b&page=2#top` redirects to exactly that URL |
| A9 | Unknown code | `GET /zzzzzz` → `404` |
| A10 | Malformed code *(parametrized)*: `abc`, `abcdefgh`, `abc-12` | `404` |
| A11 | Health check | `GET /health` → `200 {"status": "ok"}` |
| A12 | CORS allowed origin | Preflight `OPTIONS /shorten` with `Origin: http://localhost:3000` → `Access-Control-Allow-Origin` header present |
| A13 | CORS other origin | Same with `Origin: https://evil.example` → header absent |
| A14 | Persistence | Shorten a URL, create a **new** client on the same DB file → redirect still works |
| A15 | End-to-end flow | Shorten → request the path of the returned `short_url` → `Location` is the original URL (the real browser hop is checked in the smoke test) |

Example of how the tests read:

```python
# tests/test_api.py
import re

import pytest

CODE_RE = re.compile(r"^[A-Za-z0-9]{6}$")


def test_shorten_valid_url(client):
    r = client.post("/shorten", json={"url": "https://example.com/page"})
    assert r.status_code == 201
    body = r.json()
    assert CODE_RE.match(body["short_code"])
    assert body["short_url"] == f"http://test.local/{body['short_code']}"


def test_duplicate_url_returns_same_code(client):
    first = client.post("/shorten", json={"url": "https://example.com"}).json()
    r = client.post("/shorten", json={"url": "https://example.com"})
    assert r.status_code == 200
    assert r.json()["short_code"] == first["short_code"]


@pytest.mark.parametrize("bad", ["not-a-url", "example.com", "ftp://example.com",
                                 "javascript:alert(1)", "http://", ""])
def test_invalid_urls_rejected(client, bad):
    assert client.post("/shorten", json={"url": bad}).status_code == 422


def test_redirect(client):
    code = client.post("/shorten", json={"url": "https://example.com/page"}).json()["short_code"]
    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "https://example.com/page"
```

### How to run

```bash
cd TA_Module1/Lab_module1/backend
source ../../../.venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

pytest -v --cov=app --cov-report=term-missing   # all tests + coverage
ruff check .                                     # lint
uvicorn app.main:app --reload                    # run locally → http://localhost:8000/docs
```

### Manual smoke test (local, then again on Railway)

```bash
API=http://localhost:8000          # later: https://<railway-domain>
curl -s $API/health
curl -s -X POST $API/shorten -H 'Content-Type: application/json' -d '{"url":"https://example.com"}'
curl -si $API/<short_code> | grep -i location
```

### Definition of done

- [ ] All unit and API tests pass
- [ ] Coverage ≥ 90% on `app/`
- [ ] `ruff check` reports no issues
- [ ] Manual smoke test passes locally
- [ ] `urls.db` is in `.gitignore`

## 8. Out of scope (for now)

- Rate limiting and abuse protection (spam links)
- Blocking links to known malicious domains
- Authentication / user accounts
- Extension challenges (analytics, custom codes, expiration, QR) — planned after the main deliverables
