import { beforeEach, describe, expect, test, vi } from "vitest";
import { ApiError, shortenUrl } from "@/lib/api";

const RESULT = { short_code: "aB3xY9", short_url: "http://api.test/aB3xY9" };

function mockFetch(impl: () => Promise<Response>) {
  const fetchMock = vi.fn<typeof fetch>(impl);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function jsonResponse(status: number, body: unknown = {}) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

async function expectApiError(kind: string) {
  const err = await shortenUrl("https://example.com").catch((e: unknown) => e);
  expect(err).toBeInstanceOf(ApiError);
  expect((err as ApiError).kind).toBe(kind);
  expect((err as ApiError).message).not.toBe("");
}

describe("shortenUrl", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
  });

  test("L8: sends a JSON POST to /shorten", async () => {
    const fetchMock = mockFetch(() => jsonResponse(201, RESULT));
    await shortenUrl("https://example.com");

    const [url, init = {}] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/shorten");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body as string)).toEqual({ url: "https://example.com" });
  });

  test("L9: trailing slash in the API URL does not produce a double slash", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test/");
    const fetchMock = mockFetch(() => jsonResponse(201, RESULT));
    await shortenUrl("https://example.com");
    expect(fetchMock.mock.calls[0][0]).toBe("http://api.test/shorten");
  });

  test.each([201, 200])("L10: returns the result on %i", async (status) => {
    mockFetch(() => jsonResponse(status, RESULT));
    await expect(shortenUrl("https://example.com")).resolves.toEqual(RESULT);
  });

  test("L11: 422 → invalid_url", async () => {
    mockFetch(() => jsonResponse(422, { detail: [] }));
    await expectApiError("invalid_url");
  });

  test("L12: 500 → server", async () => {
    mockFetch(() => jsonResponse(500));
    await expectApiError("server");
  });

  test("L13: network failure → network", async () => {
    mockFetch(() => Promise.reject(new TypeError("Failed to fetch")));
    await expectApiError("network");
  });

  test("L14: timeout → timeout", async () => {
    mockFetch(() => Promise.reject(new DOMException("signal timed out", "TimeoutError")));
    await expectApiError("timeout");
  });
});
