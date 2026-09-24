# Backend Review Plan — SOLID, DDD, RFC 9457, SQL Injection

Review and refactoring plan for the deployed backend ([backend/](backend/)), building on [BACKEND_PLAN.md](BACKEND_PLAN.md).

> **Status: implemented.** Findings F1–F13 closed; 83 tests, 99% coverage, Ruff (incl. `S` rules) clean. Deployment results in section 8.

**Goals**
1. **SOLID**: each module has one reason to change, and business logic depends on abstractions, not on SQLite or FastAPI.
2. **DDD (proportionate)**: the code speaks the domain language and keeps the domain free of frameworks. This is a small domain, so only the building blocks that pay off are used.
3. **RFC 9457**: every error response is a Problem Details object (`application/problem+json`).
4. **SQL injection**: keep the code immune, and make that *verifiable* (tests + lint), not just true today.

**Non-goals**: no behavior change for clients except the error body format. Status codes, success bodies, and URLs stay the same, so the frontend keeps working.

---

## 1. Current state — review findings

Reviewed files: `app/main.py`, `app/shortener.py`, `app/db.py`, `app/config.py`, plus live responses from Railway.

| # | Area | Finding | Where | Severity |
|---|---|---|---|---|
| F1 | SOLID · SRP | `main.py` does 5 jobs: app creation, CORS wiring, request/response schemas, DB connection lifecycle, and route handlers. | `app/main.py:12-60` | Medium |
| F2 | SOLID · SRP | `shortener.py` mixes business rules (dedupe, collision retry), code generation, and raw SQL. | `app/shortener.py:18-45` | Medium |
| F3 | SOLID · DIP | Routes and business logic depend on the concrete `sqlite3.Connection`. Swapping storage (e.g. PostgreSQL) means editing business logic; unit tests need a real database. | `app/main.py:30-35,47,56`, `app/shortener.py:23,44` | Medium |
| F4 | SOLID · OCP | Code generation is a module function replaced in tests via monkeypatching, not an injectable strategy. Custom codes (extension challenge) would require editing the existing logic. | `app/shortener.py:10`, `tests/test_shortener.py` | Low |
| F5 | DDD | No domain model: short codes and URLs are plain `str`. The "6 alphanumerics" rule lives in a helper function; URL rules live only in the Pydantic request model (HTTP layer). | `app/shortener.py:14`, `app/main.py:21-22` | Medium |
| F6 | DDD | Domain failure uses a generic `RuntimeError`, which becomes an unstructured 500. | `app/shortener.py:41` | Medium |
| F7 | RFC 9457 | Errors are `application/json` with FastAPI's default `{"detail": ...}` shape; no `type`, `title`, `status`, `instance`. | Live: `GET /zzzzzz` → `{"detail":"Short URL not found"}` | High |
| F8 | RFC 9457 | Validation errors expose Pydantic internals (`loc`, `ctx`, `input` echoing the user's value). | Live: `POST /shorten {"url":"x"}` | Medium |
| F9 | RFC 9457 | Malformed JSON returns 422; it is a syntax problem and should be 400. | FastAPI default | Low |
| F10 | Errors · CORS | An unhandled exception returns a plain-text 500 **without CORS headers** (Starlette's error middleware sits outside `CORSMiddleware`), so the browser reports it as a network error instead of showing the message. | FastAPI/Starlette default | Medium |
| F11 | SQL injection | ✅ All 3 queries use `?` placeholders; no SQL is built with f-strings, `%` or `+`. The only `executescript` runs a constant schema. | `app/shortener.py:19,33,45`, `app/db.py:20` | OK (keep) |
| F12 | SQL injection | ⚠️ Nothing *prevents* a future regression: no lint rule and no tests with injection payloads. | project config, tests | Medium |
| F13 | Config | CORS origins are read once at import time while other settings are read per request; inconsistent and hard to test. | `app/main.py:15` | Low |

---

## 2. Target design

### 2.1 Ubiquitous language

| Term | Meaning |
|---|---|
| **Short link** | The pairing of a short code and a target URL. The aggregate. |
| **Short code** | 6 characters from `[A-Za-z0-9]`, unique. |
| **Target URL** | The original `http`/`https` URL a short link points to, normalized, max 2083 characters. |
| **Shorten** | Get the existing short link for a target URL, or create a new one. |
| **Resolve** | Find the target URL for a short code. |

These names replace today's `urls` / `url` / `code` wording in code (the table name stays `urls` to avoid a data migration).

### 2.2 Layers

```
app/
├── domain/                      # pure Python: no FastAPI, no sqlite3, no Pydantic
│   ├── model.py                 # ShortCode, TargetUrl (value objects), ShortLink (aggregate)
│   ├── errors.py                # DomainError, InvalidTargetUrl, InvalidShortCode,
│   │                            # ShortLinkNotFound, ShortCodeSpaceExhausted
│   └── ports.py                 # ShortLinkRepository, ShortCodeGenerator (Protocols)
├── application/
│   └── services.py              # ShortenUrl, ResolveShortLink (use cases)
├── infrastructure/
│   ├── sqlite_repository.py     # SqliteShortLinkRepository — the ONLY place with SQL
│   ├── code_generator.py        # RandomShortCodeGenerator (secrets)
│   └── database.py              # connection + schema
├── api/
│   ├── schemas.py               # Pydantic request/response models
│   ├── routes.py                # thin handlers: parse → call use case → map response
│   ├── problems.py              # RFC 9457 model + exception handlers
│   └── dependencies.py          # FastAPI Depends() wiring
├── config.py
└── main.py                      # composition root: create app, middleware, handlers, routes
```

**Dependency rule:** `api → application → domain ← infrastructure`. The domain imports nothing from the other layers. Enforced by a test (see T-A1).

### 2.3 How each SOLID principle is met

| Principle | Applied as |
|---|---|
| **S** — Single responsibility | One module per concern (table above). Routes only translate HTTP ↔ use cases; SQL lives only in the repository; error formatting lives only in `problems.py`. |
| **O** — Open/closed | New storage = new repository class; new code strategy (e.g. custom codes) = new `ShortCodeGenerator`. Use cases stay untouched. |
| **L** — Liskov substitution | `SqliteShortLinkRepository` and the test `InMemoryShortLinkRepository` both satisfy `ShortLinkRepository` and pass the **same contract test suite** (T-R1). |
| **I** — Interface segregation | Two small ports: the repository has 3 methods, the generator has 1. Use cases only receive what they use. |
| **D** — Dependency inversion | Use cases depend on the Protocols in `domain/ports.py`; concrete classes are chosen only in `api/dependencies.py`. |

### 2.4 DDD building blocks used (and not used)

| Used | Why |
|---|---|
| **Value objects** `ShortCode`, `TargetUrl` | Make invalid states unrepresentable: a `ShortCode` can't exist unless it is 6 alphanumerics. Validation moves from HTTP into the domain. |
| **Aggregate** `ShortLink` | The unit of consistency (code ↔ URL). Immutable. |
| **Repository** | Collection-like access to aggregates, hiding SQL. |
| **Application services** (use cases) | Orchestrate: dedupe, generate, retry on collision. |
| **Domain errors** | Named business failures, mapped to HTTP only at the edge. |

| Deliberately not used | Why |
|---|---|
| Domain events, factories, specifications, bounded-context mapping, CQRS | One small context with 2 operations — they would add code without benefit. Revisit if analytics/expiration grow into real features. |

### 2.5 Code sketches

**Value objects and aggregate** — `domain/model.py`

```python
import string
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from .errors import InvalidShortCode, InvalidTargetUrl

_ALPHABET = frozenset(string.ascii_letters + string.digits)


@dataclass(frozen=True, slots=True)
class ShortCode:
    value: str
    LENGTH = 6

    def __post_init__(self) -> None:
        if len(self.value) != self.LENGTH or not set(self.value) <= _ALPHABET:
            raise InvalidShortCode(self.value)


@dataclass(frozen=True, slots=True)
class TargetUrl:
    value: str
    MAX_LENGTH = 2083

    def __post_init__(self) -> None:
        parts = urlsplit(self.value)
        if (
            len(self.value) > self.MAX_LENGTH
            or parts.scheme not in ("http", "https")
            or not parts.hostname
        ):
            raise InvalidTargetUrl(self.value)


@dataclass(frozen=True, slots=True)
class ShortLink:
    code: ShortCode
    target: TargetUrl
    created_at: datetime | None = None
```

Pydantic `HttpUrl` stays at the API boundary for normalization and field-level messages; the domain re-checks its own invariants so it never depends on the caller doing so.

**Ports** — `domain/ports.py`

```python
from typing import Protocol

from .model import ShortCode, ShortLink, TargetUrl


class ShortLinkRepository(Protocol):
    def find_by_code(self, code: ShortCode) -> ShortLink | None: ...
    def find_by_target(self, target: TargetUrl) -> ShortLink | None: ...
    def add(self, link: ShortLink) -> None:
        """Raises CodeAlreadyTaken or TargetAlreadyStored on unique conflicts."""


class ShortCodeGenerator(Protocol):
    def generate(self) -> ShortCode: ...
```

**Use case** — `application/services.py`

```python
from dataclasses import dataclass

from app.domain.errors import CodeAlreadyTaken, ShortCodeSpaceExhausted, TargetAlreadyStored
from app.domain.model import ShortLink, TargetUrl
from app.domain.ports import ShortCodeGenerator, ShortLinkRepository


@dataclass(frozen=True)
class ShortenResult:
    link: ShortLink
    created: bool


class ShortenUrl:
    MAX_ATTEMPTS = 5

    def __init__(self, repo: ShortLinkRepository, generator: ShortCodeGenerator) -> None:
        self._repo = repo
        self._generator = generator

    def __call__(self, raw_url: str) -> ShortenResult:
        target = TargetUrl(raw_url)
        if existing := self._repo.find_by_target(target):
            return ShortenResult(existing, created=False)

        for _ in range(self.MAX_ATTEMPTS):
            link = ShortLink(self._generator.generate(), target)
            try:
                self._repo.add(link)
                return ShortenResult(link, created=True)
            except CodeAlreadyTaken:
                continue
            except TargetAlreadyStored:  # concurrent request stored it first
                return ShortenResult(self._repo.find_by_target(target), created=False)
        raise ShortCodeSpaceExhausted()
```

**Thin route** — `api/routes.py`

```python
@router.post("/shorten", response_model=ShortenResponse, status_code=201,
             responses={422: PROBLEM_RESPONSE, 503: PROBLEM_RESPONSE})
def shorten(body: ShortenRequest, response: Response,
            shorten_url: ShortenUrl = Depends(get_shorten_url),
            settings: Settings = Depends(get_settings)) -> ShortenResponse:
    result = shorten_url(str(body.url))
    if not result.created:
        response.status_code = 200
    return ShortenResponse.from_link(result.link, settings.base_url)
```

---

## 3. RFC 9457 — Problem Details

### 3.1 Rules applied

| RFC 9457 requirement | How the API complies |
|---|---|
| Media type `application/problem+json` | Every error response uses it (`JSONResponse(media_type=...)`). |
| `type` — URI identifying the problem type; absolute URIs recommended (§3.1.1) | `{BASE_URL}/problems/<slug>`, e.g. `https://backend-production-7f82d.up.railway.app/problems/short-link-not-found`. `GET /problems/<slug>` returns a short plain-text/JSON description (types SHOULD be documented when dereferenced). |
| `about:blank` when no extra semantics; its `title` SHOULD be the HTTP reason phrase (§4.2.1) | Used for generic framework errors: unknown route (404), method not allowed (405). |
| `title` — short, same for every occurrence of the type | Fixed per type in a catalog (below). |
| `status` — must match the HTTP status code | Set from the same value used for the response. |
| `detail` — human-readable, about *this* occurrence, no debugging info | E.g. `"No short link exists for code 'zzzzzz'."`. Never stack traces, SQL, or Pydantic internals. |
| `instance` — URI reference for this occurrence | The request path (`/zzzzzz`, `/shorten`). |
| Extension members allowed (§3.2) | `errors`: list of `{detail, pointer}` for validation failures, with **JSON Pointer** (RFC 6901) into the request body (`#/url`) — the same shape as the RFC's own example. |
| Don't leak sensitive data (§5) | The user's input is not echoed; 500s return a generic message and are logged server-side. |

### 3.2 Problem catalog

| Slug (`type` = `{BASE_URL}/problems/<slug>`) | Status | Title | Raised when |
|---|---|---|---|
| `validation-error` | 422 | Your request is not valid. | Body fails validation (bad URL, missing/wrong-type field) — with `errors[]` |
| `malformed-request` | 400 | The request body is not valid JSON. | Body can't be parsed |
| `short-link-not-found` | 404 | Short link not found. | Unknown code **or** malformed code (a visitor can't tell them apart) |
| `code-space-exhausted` | 503 | Could not generate a short code. | 5 collisions in a row; includes `Retry-After: 1` |
| `internal-error` | 500 | Internal server error. | Any unexpected exception |
| `about:blank` | 404 / 405 | `Not Found` / `Method Not Allowed` | Unknown route, wrong method |

### 3.3 Example responses

```http
HTTP/1.1 404 Not Found
Content-Type: application/problem+json

{
  "type": "https://backend-production-7f82d.up.railway.app/problems/short-link-not-found",
  "title": "Short link not found.",
  "status": 404,
  "detail": "No short link exists for code 'zzzzzz'.",
  "instance": "/zzzzzz"
}
```

```http
HTTP/1.1 422 Unprocessable Content
Content-Type: application/problem+json

{
  "type": "https://backend-production-7f82d.up.railway.app/problems/validation-error",
  "title": "Your request is not valid.",
  "status": 422,
  "detail": "The request body has 1 invalid field.",
  "instance": "/shorten",
  "errors": [
    { "detail": "Must be a valid http or https URL.", "pointer": "#/url" }
  ]
}
```

### 3.4 Implementation sketch — `api/problems.py`

```python
PROBLEM_JSON = "application/problem+json"


class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    errors: list[FieldError] | None = None   # extension member


def problem_response(request: Request, status: int, slug: str | None, title: str,
                     detail: str | None = None, **extensions) -> JSONResponse:
    type_ = f"{get_settings().base_url}/problems/{slug}" if slug else "about:blank"
    body = Problem(type=type_, title=title, status=status, detail=detail,
                   instance=request.url.path, **extensions)
    return JSONResponse(body.model_dump(exclude_none=True), status_code=status,
                        media_type=PROBLEM_JSON)


def register_problem_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ShortLinkNotFound, ...)        # → 404 short-link-not-found
    app.add_exception_handler(InvalidShortCode, ...)         # → 404 short-link-not-found
    app.add_exception_handler(InvalidTargetUrl, ...)         # → 422 validation-error
    app.add_exception_handler(ShortCodeSpaceExhausted, ...)  # → 503 + Retry-After
    app.add_exception_handler(RequestValidationError, ...)   # → 422, or 400 if json_invalid
    app.add_exception_handler(StarletteHTTPException, ...)   # → about:blank + reason phrase
```

**Unhandled exceptions (F10):** a small middleware registered *inside* `CORSMiddleware` catches `Exception`, logs it with the traceback, and returns the `internal-error` problem — so even 500s carry CORS headers and reach the frontend as readable JSON.

### 3.5 CORS changes

| # | Change | Why |
|---|---|---|
| C1 | **Register the error middleware *before* `CORSMiddleware` in `main.py`** | Starlette's `add_middleware` inserts each new middleware as the *outermost* one (`user_middleware.insert(0, …)`). Adding the error middleware first puts it *inside* CORS, so 500 problem responses get CORS headers (F10). Added in the wrong order, the fix silently does nothing. Covered by T-P7. |
| C2 | Add `expose_headers=["Retry-After"]` | Browsers only let JavaScript read "safelisted" response headers (`Content-Type`, `Cache-Control`, …). Without this, the frontend can't read `Retry-After` on a 503. `Content-Type: application/problem+json` is safelisted, so reading problem bodies needs nothing extra. |
| C3 | No change to `allow_headers` / `allow_methods` | `Accept` is already allowed by Starlette's CORS safelist, so the optional `Accept: application/problem+json` header works as-is; the frontend still only uses `POST /shorten`. |
| C4 | No change to `FRONTEND_ORIGIN` | A backend redeploy keeps the same Railway domain, and the Vercel production domain is unchanged. |

Not in scope, noted for later: Vercel *preview* deployments get unique URLs (`taller-url-shortener-<hash>-….vercel.app`) that are **not** in `FRONTEND_ORIGIN`, so previews can't call the API. Allowing them would need `allow_origin_regex` for this project's preview pattern.

### 3.6 Frontend impact

`lib/api.ts` decides by **status code only**, so it keeps working unchanged. Optional follow-up: show the server's `detail` for 422 instead of the fixed message, and send `Accept: application/problem+json, application/json`.

---

## 4. SQL injection

### 4.1 Current status

Safe today (F11). Every value reaches SQLite as a **bound parameter**, so the driver sends it as data, never as SQL text:

```python
conn.execute("SELECT url FROM urls WHERE short_code = ?", (code,))   # ✅ parameterized
conn.execute(f"SELECT url FROM urls WHERE short_code = '{code}'")    # ❌ never do this
```

### 4.2 Controls to keep it safe (defense in depth)

| # | Control | Type | How |
|---|---|---|---|
| S1 | **Parameterized queries only** | Rule | All SQL uses `?` placeholders; values are always passed in the parameters tuple. Table/column names are constants, never taken from input. |
| S2 | **SQL lives in one module** | Design | Only `infrastructure/sqlite_repository.py` and `database.py` import `sqlite3`. Enforced by test T-A2. |
| S3 | **Lint rule** | Static check | Enable Ruff's `S` (flake8-bandit) rules — **S608** flags SQL built with string formatting/concatenation. CI/`ruff check` fails on violation. |
| S4 | **Allowlist input validation** | Input validation | `ShortCode` accepts only `[A-Za-z0-9]{6}` and `TargetUrl` only valid http(s) URLs, *before* anything reaches the repository. A second barrier, not a replacement for S1. |
| S5 | **No dynamic `executescript`** | Rule | `executescript` (which runs multiple statements) only with the constant schema. |
| S6 | **Injection payload tests** | Tests | See T-S1…T-S4 below. |
| S7 | **Review checklist item** | Process | Every PR touching SQL is checked against S1/S2 (section 6). |

---

## 5. Test plan

The existing 38 tests are the **safety net**: they must stay green after each refactoring step. Only the error-body assertions change (F7).

### New and changed tests

| ID | Level | Test | Expected |
|---|---|---|---|
| **Domain** | | | |
| T-D1 | Unit | `ShortCode` accepts `aB3xY9`; rejects `abc`, `abcdefg`, `abc-12`, `abc 12`, `''`, `abc'--` | `InvalidShortCode` for invalid |
| T-D2 | Unit | `TargetUrl` accepts http/https; rejects `ftp://`, `javascript:`, no host, > 2083 chars | `InvalidTargetUrl` for invalid |
| T-D3 | Unit | Value objects are immutable and compare by value | `ShortCode("aB3xY9") == ShortCode("aB3xY9")`; assignment raises |
| **Application** (in-memory repo + fixed generator — no database) | | | |
| T-U1 | Unit | New URL → created; same URL → existing, not created | Replaces U4/U5 |
| T-U2 | Unit | Code collision → retries with next code | Replaces U6 without monkeypatching |
| T-U3 | Unit | 5 collisions → `ShortCodeSpaceExhausted` | Replaces U7 |
| T-U4 | Unit | Concurrent insert of same target → returns stored link | Replaces U9 |
| T-U5 | Unit | Resolve unknown code → `ShortLinkNotFound` | |
| **Repository contract** (runs against SQLite **and** in-memory) | | | |
| T-R1 | Integration | add / find_by_code / find_by_target / duplicate code / duplicate target | Same results for both implementations (Liskov) |
| **RFC 9457** | | | |
| T-P1 | API | `GET /zzzzzz` | 404, `Content-Type: application/problem+json`, `type` ends in `/problems/short-link-not-found`, `status == 404`, `instance == "/zzzzzz"` |
| T-P2 | API | `GET /abc-12` (malformed code) | Same as T-P1 |
| T-P3 | API | `POST /shorten {"url":"x"}` | 422 problem, `errors == [{"pointer": "#/url", ...}]`, body does **not** contain `"x"` echoed, no `loc`/`ctx` |
| T-P4 | API | Missing field / wrong type | 422 problem with pointer `#/url` |
| T-P5 | API | Body `not json` | **400** `malformed-request` |
| T-P6 | API | Generator always collides | 503 `code-space-exhausted`, `Retry-After` header |
| T-P7 | API | Use case raises unexpected `Exception` | 500 `internal-error`, generic `detail`, no traceback, **CORS header present** for allowed origin |
| T-P8 | API | `DELETE /shorten`, `GET /a/b/c` | 405 / 404 with `type: "about:blank"` and reason-phrase title |
| T-P9 | API | Every problem response | `status` in body == HTTP status; `title` identical across two occurrences of the same type |
| T-P10 | API | `GET /problems/short-link-not-found` | 200 with the type's description |
| **SQL injection** | | | |
| T-S1 | API | Shorten `https://example.com/?q=1' OR '1'='1` and `https://example.com/'; DROP TABLE urls; --` | 201; redirect `Location` equals the input exactly; table still exists with expected row count |
| T-S2 | API | `GET /'%20OR%20'1'='1` and `GET /1'--xx` as short codes | 404 problem; no other link returned |
| T-S3 | Unit | Repository `find_by_target("x' OR 1=1 --")` on a populated DB | `None` (no row matched) |
| T-S4 | Static | `ruff check` with `S608` enabled on a deliberately bad sample in a temp file | Violation reported (proves the rule is active) |
| **Architecture** | | | |
| T-A1 | Static test | Parse imports of `app/domain/**` | No imports of `fastapi`, `pydantic`, `sqlite3`, `starlette`, `app.api`, `app.infrastructure` |
| T-A2 | Static test | Search `app/**` for `import sqlite3` | Only in `app/infrastructure/` |

**Quality gates:** all tests green, coverage ≥ 90% (currently 100%), `ruff check` (now including `S` rules) clean, then the E2E suite (E1–E7) green locally and against production.

---

## 6. Review checklist (use on every backend PR)

**SOLID / DDD**
- [ ] Does the domain (`app/domain`) import only the standard library?
- [ ] Are routes thin (parse → use case → response), with no business rules or SQL?
- [ ] Are new dependencies injected through `api/dependencies.py`, not instantiated inside use cases?
- [ ] Do new business rules live in value objects or use cases, using the ubiquitous language?
- [ ] Are domain failures raised as named `DomainError` subclasses, not `RuntimeError`/`HTTPException`?

**RFC 9457 / CORS**
- [ ] Is any new middleware registered so that `CORSMiddleware` stays the outermost user middleware?
- [ ] Does every new failure mode have a catalog entry (slug, status, title) and a handler?
- [ ] Is `Content-Type: application/problem+json` on every error?
- [ ] Does `detail` avoid stack traces, SQL, internal names, and echoing raw user input?

**SQL injection**
- [ ] Are all SQL values passed as `?` parameters?
- [ ] Is SQL confined to `app/infrastructure/`?
- [ ] Does `ruff check` pass with `S608` enabled?

---

## 7. Execution order

Small steps; run the full test suite after each one.

| Step | Change | Findings closed |
|---|---|---|
| 1 | Enable Ruff `S` rules; add injection tests T-S1…T-S3 against the **current** code (they should pass immediately) | F12 |
| 2 | Add `domain/` (value objects, errors, ports) + tests T-D1…T-D3 | F5, F6 |
| 3 | Move SQL into `SqliteShortLinkRepository`; add in-memory repo + contract tests T-R1 | F2, F3 |
| 4 | Add `ShortenUrl` / `ResolveShortLink` use cases + T-U1…T-U5; delete `shortener.py` | F2, F4 |
| 5 | Split `main.py` into `api/` modules + composition root; settings via `Depends` | F1, F13 |
| 6 | Add `api/problems.py`, handlers, error middleware (registered before CORS — C1), `expose_headers` (C2), `/problems/{slug}`; update error assertions; add T-P1…T-P10 | F7, F8, F9, F10 |
| 7 | Add architecture tests T-A1, T-A2 | — |
| 8 | Update `BACKEND_PLAN.md` / README; run E2E locally; redeploy to Railway following section 8 | — |

---

## 8. Redeploy to Railway

The refactor changes code structure and error bodies only, so the redeploy is low-risk — but it touches production data and the live frontend, so it follows these steps. Full platform details: [backend/DEPLOY.md](backend/DEPLOY.md).

### 8.1 Compatibility check (before deploying)

| Concern | Status | Why |
|---|---|---|
| Start command | Unchanged | `main.py` stays the composition root, so `railpack.json` (`uvicorn app.main:app`) still works. |
| Dependencies | Unchanged | The domain uses only the standard library; `requirements.txt` stays `fastapi` + `uvicorn`. |
| Database / Volume | **Compatible, no migration** | The table name (`urls`) and columns stay the same; existing short links on `/data/urls.db` keep working. |
| Environment variables | Unchanged | `BASE_URL` (also used now for problem `type` URIs), `DATABASE_PATH`, `FRONTEND_ORIGIN`. |
| CORS | **Code change, no config change** | Middleware order (C1) and `expose_headers` (C2) change in `main.py`; the allowed origins stay the same (C4). |
| Health check | Unchanged | `GET /health` keeps the same path and response. |
| Frontend (Vercel) | **No redeploy needed** | It reads status codes only; success bodies and status codes are unchanged. |

### 8.2 Steps

```bash
cd TA_Module1/Lab_module1/backend

# 1. Gates — all must pass locally
pytest -q --cov=app && ruff check . && ruff format --check .
(cd ../frontend && nvm use 24 && npm run test:e2e)        # E2E against the local refactored backend

# 2. Record the currently live short link, to prove data survives the deploy
curl -s -o /dev/null -w '%{http_code} -> %{redirect_url}\n' \
     https://backend-production-7f82d.up.railway.app/kuqy03   # expect 307 -> github.com/fastapi/fastapi

# 3. Deploy
railway up --ci
```

### 8.3 Post-deploy verification

| # | Check | Expected |
|---|---|---|
| V1 | `GET /health` | 200 `{"status":"ok"}` |
| V2 | `GET /kuqy03` (link created **before** the refactor) | 307 → `https://github.com/fastapi/fastapi` — existing data intact |
| V3 | `GET /zzzzzz` | 404, `Content-Type: application/problem+json`, RFC 9457 body |
| V4 | `POST /shorten {"url":"x"}` | 422 problem with `errors[0].pointer == "#/url"` |
| V5 | `POST /shorten` with body `not json` | 400 `malformed-request` |
| V6 | `DELETE /shorten` | 405 `about:blank` |
| V7 | CORS preflight from `https://taller-url-shortener-gamma.vercel.app`; also a `GET /zzzzzz` with that `Origin` | `access-control-allow-origin` present on both — error responses carry CORS headers too |
| V8 | `BASE_URL=https://taller-url-shortener-gamma.vercel.app npx playwright test` (from `frontend/`) | E1–E6 pass against production |

### 8.4 Rollback

If any check V1–V8 fails:

1. Railway dashboard → service `backend` → **Deployments** → previous deployment → **Redeploy** (restores the last working version in ~1–2 min; the Volume and its data are not affected).
2. Or redeploy from the last good commit: `git checkout <good-commit> -- TA_Module1/Lab_module1/backend && railway up --ci`.
3. Re-run V1, V2 and V8 to confirm the rollback.

This is why the work should be **committed to git before starting** the refactor: it gives a known-good version to return to.

**Definition of done**
- [ ] All findings F1–F13 closed or explicitly accepted
- [ ] All tests (old + new) green, coverage ≥ 90%, `ruff check` clean with `S` rules
- [ ] Redeployed to Railway; post-deploy checks V1–V8 pass (section 8.3)
- [ ] Short links created before the refactor still redirect (V2)
- [ ] Every error response on production validates as RFC 9457 (V3–V6)
- [ ] Frontend E2E suite green against production (V8)
