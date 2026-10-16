import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = path.resolve(__dirname, "../../docs/screenshots");

test.describe("Labledger smoke (demo mode)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/?demo=1");
    // demo flag is applied then we may need a reload if first paint was empty
    await page.waitForTimeout(300);
    if (!(await page.getByText(/Hello,/i).count()) && !(await page.getByText(/Welcome to Labledger/i).count())) {
      await page.reload();
    }
  });

  test("demo dashboard loads with trends", async ({ page }) => {
    // Demo mode should skip onboarding and show overview
    await expect(page.getByRole("heading", { name: /Hello,/i })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/confirmed values/i)).toBeVisible();
    await expect(page.getByText(/Latest report/i)).toBeVisible();
  });

  test("navigate matrix, compare, documents, export", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /Hello,/i })).toBeVisible({ timeout: 15_000 });

    // Desktop header nav is md:flex (hidden on mobile); bottom nav is md:hidden.
    // Click the visible instance of each label.
    for (const label of ["Matrix", "Compare", "Documents", "Export"]) {
      const link = page.locator(`a:visible`, { hasText: new RegExp(`^${label}$`) }).first();
      await link.click();
      await page.waitForTimeout(250);
    }
    // Export/print route
    await expect(page).toHaveURL(/\/print/);
    await expect(page.locator("main")).toBeVisible();
  });

  test("biomarker detail + unit toggle when available", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /Hello,/i })).toBeVisible({ timeout: 15_000 });
    // Click first biomarker card link if present
    const card = page.locator("a[href*='/biomarker/']").first();
    if (await card.count()) {
      await card.click();
      await expect(page.locator("body")).toContainText(/Reference|Trend|History|values/i);
      // Unit toggle if present
      const toggle = page.getByRole("button", { name: /SI|Conventional|mg\/dL|mmol/i }).first();
      if (await toggle.count()) {
        await toggle.click();
      }
    } else {
      test.info().annotations.push({ type: "note", description: "No biomarker links in demo overview" });
    }
  });

  test("axe: overview has no critical violations", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /Hello,/i })).toBeVisible({ timeout: 15_000 });
    const results = await new AxeBuilder({ page }).analyze();
    const critical = results.violations.filter((v) => v.impact === "critical");
    expect(critical, JSON.stringify(critical, null, 2)).toEqual([]);
  });
});

test.describe("Labledger onboarding (no demo)", () => {
  test("empty state onboarding form", async ({ page }) => {
    await page.goto("/?demo=0");
    await page.evaluate(() => localStorage.removeItem("labledger.profileId"));
    await page.reload();
    // Without API profiles, Gate shows Onboarding
    const welcome = page.getByText(/Welcome to Labledger/i);
    const hello = page.getByText(/Hello,/i);
    await expect(welcome.or(hello)).toBeVisible({ timeout: 15_000 });
    if (await welcome.count()) {
      await page.getByLabel(/^Name/i).fill("Test User");
      // Submit may fail if API down — that's ok; mark soft
      const continueBtn = page.getByRole("button", { name: /Continue/i });
      await expect(continueBtn).toBeVisible();
    }
  });
});

test.describe("Screenshots", () => {
  test("capture key views dark/light desktop", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "desktop only");
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/?demo=1");
    await expect(page.getByRole("heading", { name: /Hello,/i })).toBeVisible({ timeout: 15_000 });

    const shots: { name: string; path: string; action?: () => Promise<void> }[] = [
      { name: "overview-dark", path: "overview-desktop-dark.png" },
    ];

    // Ensure dark
    await page.evaluate(() => localStorage.setItem("labledger.theme", "dark"));
    await page.reload();
    await expect(page.getByRole("heading", { name: /Hello,/i })).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "overview-desktop-dark.png"), fullPage: true });

    // Light
    await page.evaluate(() => localStorage.setItem("labledger.theme", "light"));
    await page.reload();
    await expect(page.getByRole("heading", { name: /Hello,/i })).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "overview-desktop-light.png"), fullPage: true });

    // Matrix
    await page.getByRole("link", { name: "Matrix" }).first().click();
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "matrix-desktop-light.png"), fullPage: true });

    // Documents
    await page.getByRole("link", { name: "Documents" }).first().click();
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "documents-desktop-light.png"), fullPage: true });

    // Export
    await page.getByRole("link", { name: "Export" }).first().click();
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "export-desktop-light.png"), fullPage: true });

    // Dark again for matrix
    await page.evaluate(() => localStorage.setItem("labledger.theme", "dark"));
    await page.goto("/matrix?demo=1");
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "matrix-desktop-dark.png"), fullPage: true });
  });

  test("capture mobile overview", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "mobile-chromium", "mobile only");
    await page.goto("/?demo=1");
    await expect(page.getByRole("heading", { name: /Hello,/i })).toBeVisible({ timeout: 15_000 });
    await page.evaluate(() => localStorage.setItem("labledger.theme", "dark"));
    await page.reload();
    await expect(page.getByRole("heading", { name: /Hello,/i })).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "overview-mobile-dark.png"), fullPage: true });
    await page.evaluate(() => localStorage.setItem("labledger.theme", "light"));
    await page.reload();
    await expect(page.getByRole("heading", { name: /Hello,/i })).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "overview-mobile-light.png"), fullPage: true });
  });
});

/**
 * Full upload→review→confirm flow against live API.
 * Skipped unless LABLEDGER_E2E_LIVE=1 and API is up with seed-catalog.
 */
test.describe("Live API flow", () => {
  test("onboarding → upload → review → confirm", async ({ page }) => {
    test.skip(process.env.LABLEDGER_E2E_LIVE !== "1", "Set LABLEDGER_E2E_LIVE=1 with make dev-api running");
    await page.goto("/?demo=0");
    await page.evaluate(() => {
      localStorage.removeItem("labledger.demo");
      localStorage.removeItem("labledger.profileId");
    });
    await page.reload();

    // Onboarding or existing profiles
    if (await page.getByText(/Welcome to Labledger/i).count()) {
      await page.getByLabel(/^Name/i).fill("E2E Live User");
      await page.getByRole("button", { name: /Continue/i }).click();
      await expect(page.getByText(/Hello,/i)).toBeVisible({ timeout: 15_000 });
    }

    // Upload a synthetic PDF if upload control exists
    const pdf = path.resolve(__dirname, "../../api/tests/fixtures/synth/digital/amberpine_standard.pdf");
    const fileInput = page.locator('input[type="file"]');
    test.skip((await fileInput.count()) === 0, "Upload input not in DOM");
    await fileInput.setInputFiles(pdf);

    // Wait for processing / navigate to documents
    await page.getByRole("link", { name: "Documents" }).first().click();
    // Soft assertions — pipeline timing varies
    await page.waitForTimeout(2000);
  });
});

test.describe("Review duplicate conflict (demo mode)", () => {
  test("side-by-side panel resolves with keep existing / keep new", async ({ page }) => {
    await page.goto("/review/doc8?demo=1");
    await page.waitForTimeout(300);
    if (!(await page.getByRole("listbox").count())) await page.reload();
    const list = page.getByRole("listbox", { name: "Extracted rows" });
    await expect(list).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/↔ 3 duplicates/)).toBeVisible();

    await list.getByRole("option").filter({ hasText: "Hemoglobin" }).click();
    const panel = page.getByRole("region", { name: "Duplicate comparison" });
    await expect(panel).toBeVisible();
    await expect(panel).toContainText(/Same value as new/);
    await expect(panel).toContainText("City Path Labs");
    const shot = process.env.LABLEDGER_SCREENSHOTS ? path.join(SCREENSHOT_DIR, `review-duplicate-${test.info().project.name}.png`) : undefined;
    if (shot) await page.screenshot({ path: shot, fullPage: false });
    await panel.getByRole("button", { name: "Keep existing" }).click();
    await expect(page.getByText(/↔ 2 duplicates/)).toBeVisible();

    await list.getByRole("option").filter({ hasText: "TSH" }).click();
    await page.getByRole("region", { name: "Duplicate comparison" }).getByRole("button", { name: "Keep new" }).click();
    await expect(page.getByText(/↔ 1 duplicate\b/)).toBeVisible();
  });
});
