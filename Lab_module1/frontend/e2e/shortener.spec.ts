import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

function uniqueUrl() {
  return `https://example.com/e2e/${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

async function shorten(page: Page, url: string) {
  await page.getByLabel("URL to shorten").fill(url);
  await page.getByRole("button", { name: "Shorten" }).click();
  const link = page.getByRole("link", { name: /^https?:\/\// });
  await expect(link).toBeVisible();
  return (await link.textContent())!;
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
});

test("E1: shortens a URL and the short URL redirects to it", async ({ page, request }) => {
  const original = uniqueUrl();
  const shortUrl = await shorten(page, original);

  expect(shortUrl).toMatch(/\/[A-Za-z0-9]{6}$/);
  const res = await request.get(shortUrl, { maxRedirects: 0 });
  expect(res.status()).toBe(307);
  expect(res.headers()["location"]).toBe(original);
});

test("E2: shortening the same URL twice gives the same short URL", async ({ page }) => {
  const original = uniqueUrl();
  const first = await shorten(page, original);
  await page.reload();
  const second = await shorten(page, original);
  expect(second).toBe(first);
});

test("E3: invalid input shows an error and no result", async ({ page }) => {
  await page.getByLabel("URL to shorten").fill("not a url");
  await page.getByRole("button", { name: "Shorten" }).click();

  await expect(page.getByRole("main").getByRole("alert")).toContainText("valid URL");
  await expect(page.getByRole("link", { name: /^https?:\/\// })).toHaveCount(0);
});

test("E4: backend down shows a friendly error", async ({ page }) => {
  await page.route("**/shorten", (route) => route.abort());
  await page.getByLabel("URL to shorten").fill(uniqueUrl());
  await page.getByRole("button", { name: "Shorten" }).click();

  await expect(page.getByRole("main").getByRole("alert")).toContainText("Can't reach the server");
});

test.describe("E5: mobile", () => {
  test.use({ viewport: { width: 375, height: 667 } });

  test("no horizontal scroll and controls usable", async ({ page }) => {
    const button = page.getByRole("button", { name: "Shorten" });
    await expect(page.getByLabel("URL to shorten")).toBeVisible();
    await expect(button).toBeVisible();

    await shorten(page, `${uniqueUrl()}/${"segment/".repeat(20)}`);
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible();

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

test("E6: no serious accessibility violations", async ({ page }) => {
  await shorten(page, uniqueUrl());
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(serious.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
});
