# Frontend Plan — URL Shortener UI

Detailed plan for **Phase 2** of [PLAN.md](PLAN.md): how the Next.js frontend will be built, what the code looks like, and how its quality will be verified. It talks to the API described in [BACKEND_PLAN.md](BACKEND_PLAN.md).

## 1. Scope

| Requirement (from the lab) | How it is met |
|---|---|
| Single page with a URL input | One route (`/`) with a `<form>` and a labelled `<input type="text">` |
| Submit button that calls the API | `POST ${NEXT_PUBLIC_API_URL}/shorten` via `fetch` |
| Display the short URL with a copy button | Result card with a link + "Copy" button (Clipboard API) |
| Loading state during the call | Button disabled with "Shortening…" text, `aria-busy`, double-submit blocked |
| Handle errors gracefully | Every failure mapped to a friendly message in an `role="alert"` box |
| Responsive design | Mobile-first Tailwind layout: stacked on phones, side by side from 640px |

## 2. Stack

| Tool | Version | Why |
|---|---|---|
| Node.js | **24** (`nvm use 24`, already installed) | Next.js 16 needs ≥ 20.9; Vitest 5 needs ≥ 22.12 (installed 22.8 is too old) |
| Next.js | 16 (App Router) | Required by the lab; deploys natively on Vercel |
| TypeScript | strict mode | Required by the lab |
| Tailwind CSS | v4 (from `create-next-app`) | Fast responsive styling without writing CSS files |
| Vitest + React Testing Library | latest | Unit and component tests |
| Playwright | latest | End-to-end tests in a real browser |

Scaffolding command:

```bash
cd TA_Module1/Lab_module1
nvm use 24
npx create-next-app@latest frontend --ts --tailwind --eslint --app --no-src-dir --import-alias "@/*" --use-npm
```

## 3. Structure

```
frontend/
├── app/
│   ├── layout.tsx           # HTML shell, fonts, <title>
│   ├── page.tsx             # renders <Shortener />
│   └── globals.css          # Tailwind import
├── components/
│   └── Shortener.tsx        # the whole interactive UI (client component)
├── lib/
│   ├── api.ts               # shortenUrl(): fetch + error mapping
│   └── url.ts               # normalizeUrl(): client-side validation
├── tests/
│   ├── url.test.ts          # unit
│   ├── api.test.ts          # unit (fetch mocked)
│   └── Shortener.test.tsx   # component (API mocked)
├── e2e/
│   └── shortener.spec.ts    # Playwright, real backend
├── .env.local               # NEXT_PUBLIC_API_URL=http://localhost:8000 (not committed)
├── .env.example             # same keys, committed as documentation
├── vitest.config.ts
└── playwright.config.ts
```

Design principles:
- **UI separated from logic.** Network calls and URL validation live in `lib/`, so they can be unit-tested without rendering anything.
- **One client component.** `page.tsx` stays a server component; only `Shortener.tsx` runs in the browser (`"use client"`).
- **The backend is the source of truth.** Client-side validation only gives faster feedback; the backend still validates everything.

## 4. Configuration

| Variable | Local | On Vercel |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | `https://<railway-domain>` |

⚠️ `NEXT_PUBLIC_*` variables are **copied into the JavaScript at build time**. On Vercel, the variable must be set *before* the build; changing it later requires a redeploy.

## 5. Code

### URL normalization — `lib/url.ts`

Users often type `example.com` without `https://`. The frontend adds it, so the backend (which requires a scheme) accepts it.

```ts
const HAS_SCHEME = /^[a-z][a-z\d+.-]*:\/\//i;

/** Returns a full http(s) URL, or null if the input can't be one. */
export function normalizeUrl(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) return null;

  const candidate = HAS_SCHEME.test(trimmed) ? trimmed : `https://${trimmed}`;
  try {
    const url = new URL(candidate);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    if (!url.hostname.includes(".") && url.hostname !== "localhost") return null;
    return candidate;
  } catch {
    return null;
  }
}
```

### API client — `lib/api.ts`

Every possible failure becomes an `ApiError` with a message the UI can show directly.

```ts
export type ShortenResult = { short_code: string; short_url: string };
export type ApiErrorKind = "invalid_url" | "server" | "network" | "timeout";

export class ApiError extends Error {
  constructor(public kind: ApiErrorKind, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

const TIMEOUT_MS = 10_000;

export async function shortenUrl(url: string): Promise<ShortenResult> {
  const apiUrl = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

  let res: Response;
  try {
    res = await fetch(`${apiUrl}/shorten`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "TimeoutError") {
      throw new ApiError("timeout", "The server took too long to respond. Please try again.");
    }
    throw new ApiError("network", "Can't reach the server. Check your connection and try again.");
  }

  if (res.status === 422) {
    throw new ApiError("invalid_url", "That doesn't look like a valid URL. Try something like https://example.com.");
  }
  if (!res.ok) {
    throw new ApiError("server", "Something went wrong on our side. Please try again.");
  }
  return res.json();
}
```

Error mapping:

| Situation | Detected by | Message shown |
|---|---|---|
| Input can't be a URL | `normalizeUrl` returns `null` (no request sent) | "Please enter a valid URL, like https://example.com." |
| Backend rejects the URL | HTTP 422 | "That doesn't look like a valid URL…" |
| Backend error | HTTP 5xx / other non-2xx | "Something went wrong on our side…" |
| Backend down / offline / CORS blocked | `fetch` throws | "Can't reach the server…" |
| Backend too slow | 10s timeout | "The server took too long to respond…" |

### UI — `components/Shortener.tsx`

```tsx
"use client";

import { useState, type FormEvent } from "react";
import { ApiError, shortenUrl, type ShortenResult } from "@/lib/api";
import { normalizeUrl } from "@/lib/url";

type CopyState = "idle" | "copied" | "failed";

export default function Shortener() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ShortenResult | null>(null);
  const [copy, setCopy] = useState<CopyState>("idle");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (loading) return;

    setResult(null);
    setCopy("idle");
    const url = normalizeUrl(input);
    if (!url) {
      setError("Please enter a valid URL, like https://example.com.");
      return;
    }

    setError(null);
    setLoading(true);
    try {
      setResult(await shortenUrl(url));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unexpected error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCopy() {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.short_url);
      setCopy("copied");
    } catch {
      setCopy("failed");
    }
    setTimeout(() => setCopy("idle"), 2000);
  }

  return (
    <div className="w-full max-w-xl space-y-4">
      <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row" aria-busy={loading}>
        <label htmlFor="url" className="sr-only">URL to shorten</label>
        <input
          id="url"
          type="text"
          inputMode="url"
          placeholder="https://example.com/a/very/long/link"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="flex-1 rounded-lg border px-4 py-3"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-lg bg-blue-600 px-5 py-3 font-medium text-white disabled:opacity-50"
        >
          {loading ? "Shortening…" : "Shorten"}
        </button>
      </form>

      {error && (
        <p role="alert" className="rounded-lg bg-red-50 p-3 text-red-700">{error}</p>
      )}

      <div aria-live="polite">
        {result && (
          <div className="flex flex-col gap-2 rounded-lg border p-4 sm:flex-row sm:items-center">
            <a href={result.short_url} target="_blank" rel="noopener noreferrer"
               className="flex-1 break-all font-mono text-blue-700 underline">
              {result.short_url}
            </a>
            <button type="button" onClick={handleCopy} className="rounded-lg border px-4 py-2">
              {copy === "copied" ? "Copied!" : copy === "failed" ? "Copy failed" : "Copy"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
```

UX decisions:
- **`type="text"` with `inputMode="url"`** instead of `type="url"`: the browser's built-in URL check would reject `example.com`, which we want to accept and fix. Mobile keyboards still show the `.com`/`/` keys.
- **Button disabled while loading or empty**, and `if (loading) return` guards against double submits.
- **Input keeps its value after an error**, so the user can fix a typo instead of retyping.
- **`aria-live` / `role="alert"`**: screen readers announce the result and errors.
- **`break-all`** on the short URL so long domains never cause horizontal scrolling on phones.

## 6. Quality strategy

### Levels

| Level | Tool | What it covers | Backend needed? |
|---|---|---|---|
| Type check | `tsc --noEmit` | Type errors across the project | No |
| Lint | ESLint (Next.js config) | Bug patterns, React hooks rules, accessibility lint | No |
| Unit tests | Vitest | `normalizeUrl`, `shortenUrl` (with `fetch` mocked) | No |
| Component tests | Vitest + React Testing Library + user-event | `Shortener` behavior as a user sees it (with `lib/api` mocked) | No |
| Build | `next build` | Production build succeeds (catches server/client component mistakes) | No |
| End-to-end | Playwright (Chromium) | Real browser + real local backend, mobile viewport, accessibility scan | Yes |
| Manual | Browser + Lighthouse | Visual check on phone and desktop sizes; Lighthouse accessibility ≥ 90 | Yes |
| Production smoke | Playwright or manual | Same E2E flow against the Vercel URL after deploy | Deployed |

Coverage target: **≥ 80% of `lib/` and `components/`** (Vitest `--coverage`).

### Test cases

**Unit — `tests/url.test.ts`**

| ID | Input | Expected |
|---|---|---|
| L1 | `https://example.com/page` | unchanged |
| L2 | `example.com` | `https://example.com` (scheme added) |
| L3 | `  https://example.com  ` | trimmed |
| L4 | `http://localhost:3000` | accepted |
| L5 | `""`, `"   "` | `null` |
| L6 | `ftp://example.com`, `javascript:alert(1)` | `null` |
| L7 | `not a url`, `hello` (no dot in host) | `null` |

**Unit — `tests/api.test.ts`** (`fetch` replaced with `vi.fn()`)

| ID | Test | Expected |
|---|---|---|
| L8 | Request shape | `POST` to `${NEXT_PUBLIC_API_URL}/shorten`, JSON body `{"url": ...}`, `Content-Type: application/json` |
| L9 | Trailing slash in `NEXT_PUBLIC_API_URL` | No double slash in the request URL |
| L10 | 201 and 200 responses | Returns `{short_code, short_url}` |
| L11 | 422 | Throws `ApiError` kind `invalid_url` |
| L12 | 500 | Throws `ApiError` kind `server` |
| L13 | `fetch` rejects (network down) | Throws `ApiError` kind `network` |
| L14 | Timeout (`TimeoutError`) | Throws `ApiError` kind `timeout` |

**Component — `tests/Shortener.test.tsx`** (`@/lib/api` mocked with `vi.mock`)

| ID | Test | Expected |
|---|---|---|
| C1 | Initial render | Labelled input present; "Shorten" button disabled while empty |
| C2 | Submit | Typing `example.com` + click calls `shortenUrl("https://example.com")` |
| C3 | Enter key | Pressing Enter in the input submits the form |
| C4 | Loading state | While the promise is pending: button disabled, text "Shortening…"; clicking again does **not** call the API twice |
| C5 | Success | Short URL shown as a link with correct `href`, `target="_blank"`, `rel="noopener noreferrer"` |
| C6 | Copy | Click "Copy" → `navigator.clipboard.writeText` called with the short URL → label becomes "Copied!" → back to "Copy" after 2s (fake timers) |
| C7 | Copy failure | `writeText` rejects → "Copy failed" |
| C8 | Invalid input | `not a url` → error alert shown, API **not** called |
| C9 | API error | `ApiError` rejected → its message shown in `role="alert"`, input keeps its value |
| C10 | Unexpected error | Plain `Error` → generic message |
| C11 | Retry clears state | After an error, a successful submit removes the alert and shows the result |

**End-to-end — `e2e/shortener.spec.ts`** (backend running on `localhost:8000`, frontend on `localhost:3000`)

| ID | Test | Expected |
|---|---|---|
| E1 | Happy path | Enter URL → click Shorten → short URL appears; requesting it returns `307` with `Location` = original URL |
| E2 | Duplicate | Shortening the same URL twice shows the same short URL |
| E3 | Invalid URL | Error message visible, no result card |
| E4 | Backend down | Requests to the API blocked with `page.route(...).abort()` → "Can't reach the server" |
| E5 | Mobile (375×667) | No horizontal scroll; input and button visible and usable |
| E6 | Accessibility | `@axe-core/playwright` scan: no serious or critical violations |
| E7 | Production | E1 re-run with `BASE_URL=https://<vercel-domain>` after deploy |

Example of how the component tests read:

```tsx
// tests/Shortener.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import Shortener from "@/components/Shortener";
import { ApiError, shortenUrl } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  shortenUrl: vi.fn(),
}));
const mockShorten = vi.mocked(shortenUrl);

beforeEach(() => mockShorten.mockReset());

test("C2 + C5: submits the normalized URL and shows the result", async () => {
  mockShorten.mockResolvedValue({ short_code: "aB3xY9", short_url: "http://localhost:8000/aB3xY9" });
  render(<Shortener />);

  await userEvent.type(screen.getByLabelText(/url to shorten/i), "example.com");
  await userEvent.click(screen.getByRole("button", { name: "Shorten" }));

  expect(mockShorten).toHaveBeenCalledWith("https://example.com");
  const link = await screen.findByRole("link", { name: "http://localhost:8000/aB3xY9" });
  expect(link).toHaveAttribute("target", "_blank");
});

test("C9: shows the API error and keeps the input", async () => {
  mockShorten.mockRejectedValue(new ApiError("invalid_url", "That doesn't look like a valid URL."));
  render(<Shortener />);

  const input = screen.getByLabelText(/url to shorten/i);
  await userEvent.type(input, "https://example.com");
  await userEvent.click(screen.getByRole("button", { name: "Shorten" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("That doesn't look like a valid URL.");
  expect(input).toHaveValue("https://example.com");
});
```

### How to run

```bash
cd TA_Module1/Lab_module1/frontend
nvm use 24
npm install

npm run typecheck        # tsc --noEmit
npm run lint             # eslint
npm test                 # vitest run (unit + component)
npm run test:coverage    # vitest run --coverage
npm run build            # next build
npm run dev              # http://localhost:3000 (backend must run on :8000)
npm run test:e2e         # playwright test (starts the dev server itself)
```

### Known risk (resolved)

Playwright's bundled Chromium refuses to install on **Ubuntu 20.04**. Resolved by running Playwright against the **Google Chrome already installed** on the machine (`channel: "chrome"` in `playwright.config.ts`), so E1–E6 run automatically — no manual fallback needed.

### Definition of done

- [ ] `typecheck`, `lint`, `test` and `build` all pass
- [ ] Coverage ≥ 80% on `lib/` and `components/`
- [ ] E1–E6 pass (Playwright or manual checklist)
- [ ] Checked by hand at 375px (phone) and 1280px (desktop) widths
- [ ] `.env.local` not committed; `.env.example` committed

## 7. Out of scope (for now)

- History of previously shortened links
- Dark mode toggle (Tailwind follows the system setting only if added later)
- Extension challenges (analytics display, custom code input, expiration picker, QR code) — planned after the main deliverables
