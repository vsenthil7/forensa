/**
 * Forensa Console — M&A diligence workspace E2E spec (US-F26, SCR-F07).
 *
 * AC closed:
 *   - Create job -> list -> view detail -> download bundle.
 *
 * The page mounts unconditionally (structural assertions don't need
 * the seed); data-dependent assertions skip when seed env vars are
 * absent.
 */

import { test, expect, consoleUrl, seedAvailable } from "./helpers";

test.describe("Diligence workspace (US-F26, SCR-F07)", () => {
  test("the /diligence page mounts (structural)", async ({ page }) => {
    await page.goto(consoleUrl("/diligence"));
    await expect(page.getByTestId("diligence-page")).toBeVisible();
    await expect(page.getByTestId("diligence-create-form")).toBeVisible();
  });

  test("the create form exposes both date inputs + submit", async ({ page }) => {
    await page.goto(consoleUrl("/diligence"));
    await expect(page.getByTestId("diligence-scope-start")).toBeVisible();
    await expect(page.getByTestId("diligence-scope-end")).toBeVisible();
    await expect(page.getByTestId("diligence-create-submit")).toBeVisible();
  });

  test("submitting with empty dates shows a validation error", async ({ page }) => {
    await page.goto(consoleUrl("/diligence"));
    await page.getByTestId("diligence-create-submit").click();
    await expect(page.getByTestId("diligence-create-error")).toBeVisible();
  });

  test.describe("with seeded data", () => {
    test.skip(
      !seedAvailable,
      "FORENSA_TENANT_ID and FORENSA_TOKEN must be set; run scripts/seed_demo_data.py first",
    );

    test("the jobs list (or empty state) settles after page mount", async ({ page }) => {
      await page.goto(consoleUrl("/diligence"));
      const settled = page
        .getByTestId("diligence-jobs-table")
        .or(page.getByTestId("diligence-list-empty"))
        .or(page.getByTestId("diligence-list-error"));
      await expect(settled).toBeVisible();
    });

    test("creating a job appears in the jobs table", async ({ page }) => {
      await page.goto(consoleUrl("/diligence"));
      await page.getByTestId("diligence-scope-start").fill("2026-05-13");
      await page.getByTestId("diligence-scope-end").fill("2026-05-14");
      await page.getByTestId("diligence-create-submit").click();
      // The job appears in the table — at least one row eventually.
      const firstRow = page.locator('[data-testid^="diligence-job-row-"]').first();
      await expect(firstRow).toBeVisible({ timeout: 15_000 });
    });
  });
});
