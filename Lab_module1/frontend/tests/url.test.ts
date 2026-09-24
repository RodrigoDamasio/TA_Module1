import { describe, expect, test } from "vitest";
import { normalizeUrl } from "@/lib/url";

describe("normalizeUrl", () => {
  test("L1: keeps a full URL unchanged", () => {
    expect(normalizeUrl("https://example.com/page")).toBe("https://example.com/page");
  });

  test("L2: adds https:// when the scheme is missing", () => {
    expect(normalizeUrl("example.com")).toBe("https://example.com");
  });

  test("L3: trims whitespace", () => {
    expect(normalizeUrl("  https://example.com  ")).toBe("https://example.com");
  });

  test("L4: accepts localhost", () => {
    expect(normalizeUrl("http://localhost:3000")).toBe("http://localhost:3000");
  });

  test.each(["", "   "])("L5: empty input %j → null", (input) => {
    expect(normalizeUrl(input)).toBeNull();
  });

  test.each(["ftp://example.com", "javascript:alert(1)"])(
    "L6: non-http scheme %j → null",
    (input) => {
      expect(normalizeUrl(input)).toBeNull();
    },
  );

  test.each(["not a url", "hello"])("L7: not a URL %j → null", (input) => {
    expect(normalizeUrl(input)).toBeNull();
  });
});
