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
