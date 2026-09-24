import { defineConfig, devices } from "@playwright/test";

// Set BASE_URL to run the suite against a deployed frontend (E7) instead of local servers.
const deployedUrl = process.env.BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  reporter: [["list"]],
  use: {
    baseURL: deployedUrl ?? "http://localhost:3000",
    // Playwright's bundled Chromium is not supported on Ubuntu 20.04, so we drive the
    // Google Chrome installed on the machine instead.
    channel: "chrome",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], channel: "chrome" } },
  ],
  webServer: deployedUrl
    ? undefined
    : [
        {
          command: "../../../.venv/bin/uvicorn app.main:app --port 8000",
          cwd: "../backend",
          url: "http://localhost:8000/health",
          env: { DATABASE_PATH: "e2e.db", FRONTEND_ORIGIN: "http://localhost:3000" },
          reuseExistingServer: true,
        },
        {
          command: "npm run dev",
          url: "http://localhost:3000",
          env: { NEXT_PUBLIC_API_URL: "http://localhost:8000" },
          reuseExistingServer: true,
        },
      ],
});
