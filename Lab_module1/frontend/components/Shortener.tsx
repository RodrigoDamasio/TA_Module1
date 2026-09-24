"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, shortenUrl, type ShortenResult } from "@/lib/api";
import { normalizeUrl } from "@/lib/url";

type CopyState = "idle" | "copied" | "failed";

const COPY_RESET_MS = 2000;

export default function Shortener() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ShortenResult | null>(null);
  const [copy, setCopy] = useState<CopyState>("idle");
  const copyTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => clearTimeout(copyTimer.current), []);

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
    clearTimeout(copyTimer.current);
    copyTimer.current = setTimeout(() => setCopy("idle"), COPY_RESET_MS);
  }

  return (
    <div className="w-full max-w-xl space-y-4">
      <form
        onSubmit={handleSubmit}
        aria-busy={loading}
        className="flex flex-col gap-2 sm:flex-row"
      >
        <label htmlFor="url" className="sr-only">
          URL to shorten
        </label>
        <input
          id="url"
          type="text"
          inputMode="url"
          autoComplete="url"
          placeholder="https://example.com/a/very/long/link"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="min-w-0 flex-1 rounded-lg border border-zinc-300 bg-white px-4 py-3 text-zinc-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/30 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-lg bg-blue-600 px-5 py-3 font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Shortening…" : "Shorten"}
        </button>
      </form>

      {error && (
        <p
          role="alert"
          className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950/50 dark:text-red-300"
        >
          {error}
        </p>
      )}

      <div aria-live="polite">
        {result && (
          <div className="flex flex-col gap-3 rounded-lg border border-zinc-200 bg-white p-4 sm:flex-row sm:items-center dark:border-zinc-800 dark:bg-zinc-900">
            <a
              href={result.short_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 font-mono break-all text-blue-700 underline dark:text-blue-400"
            >
              {result.short_url}
            </a>
            <button
              type="button"
              onClick={handleCopy}
              className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium transition hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
            >
              {copy === "copied" ? "Copied!" : copy === "failed" ? "Copy failed" : "Copy"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
