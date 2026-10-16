import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.LABLEDGER_WEB_PORT || 5173);
const BASE = process.env.LABLEDGER_WEB_BASE || `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  timeout: 60_000,
  reporter: [["list"]],
  use: {
    baseURL: BASE,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile-chromium",
      use: { ...devices["Pixel 5"] },
    },
  ],
  webServer: process.env.LABLEDGER_NO_WEBSERVER
    ? undefined
    : {
        command: "npm run dev -- --host 127.0.0.1 --port 5173",
        url: BASE,
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
