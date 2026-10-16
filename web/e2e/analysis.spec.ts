import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../docs/screenshots");

test.describe("Analysis page (demo mode)", () => {
  for (const theme of ["light", "dark"] as const) {
    test(`renders charts and table (${theme})`, async ({ page }, info) => {
      await page.goto("/?demo=1");
      await expect(page.getByRole("heading", { name: /Hello,/i })).toBeVisible({ timeout: 15_000 });
      await page.evaluate((t) => localStorage.setItem("labledger.theme", t), theme);
      await page.goto("/analysis");
      await expect(page.getByRole("heading", { name: "Analysis", exact: true })).toBeVisible({ timeout: 15_000 });
      for (const h of ["Status by category", "Status over time", "Furthest from range", "Biggest movers", "All markers"]) {
        await expect(page.getByRole("heading", { name: h })).toBeVisible();
      }
      await expect(page.locator("tbody tr").first()).toBeVisible();
      await page.waitForTimeout(700); // let entrance animations settle
      const kind = info.project.name === "mobile-chromium" ? "mobile" : "desktop";
      await page.screenshot({ path: path.join(DIR, `analysis-${kind}-${theme}.png`), fullPage: true });
    });
  }
});
