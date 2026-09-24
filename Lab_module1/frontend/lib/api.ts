export type ShortenResult = { short_code: string; short_url: string };
export type ApiErrorKind = "invalid_url" | "server" | "network" | "timeout";

export class ApiError extends Error {
  constructor(
    public kind: ApiErrorKind,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const TIMEOUT_MS = 10_000;

export async function shortenUrl(url: string): Promise<ShortenResult> {
  // Referenced directly so Next.js can inline the value at build time.
  const apiUrl = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

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
    throw new ApiError(
      "invalid_url",
      "That doesn't look like a valid URL. Try something like https://example.com.",
    );
  }
  if (!res.ok) {
    throw new ApiError("server", "Something went wrong on our side. Please try again.");
  }
  return res.json();
}
