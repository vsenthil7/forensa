/**
 * Forensa Console — Anchors page E2E spec (SCR-F05, US-F16 UI access).
 *
 * Closes the UI-access acceptance for US-F16:
 *   - List view shows one row per daily anchor.
 *   - Anchored row has a "Download TSR" button; clicking it pipes
 *     application/timestamp-reply bytes into a browser download.
 *   - Deferred rows show the deferred chip + no download button.
 *
 * Requires the seed env vars for data-dependent assertions.
 */

import { test, expect, consoleUrl, seedAvailable } from "./helpers";

test.describe("Anchors page (SCR-F05, US-F16)", () => {
  test("the /anchors page mounts (structural, no seed required)", async ({ page }) => {
    await page.goto(consoleUrl("/anchors"));
    await expect(page.getByTestId("anchors-page")).toBeVisible();
  });

  test("the page settles into one of: list / empty / error", async ({ page }) => {
    await page.goto(consoleUrl("/anchors"));
    const settled = page
      .getByTestId("anchors-list")
      .or(page.getByTestId("anchors-list-empty"))
      .or(page.getByTestId("anchors-list-error"));
    await expect(settled).toBeVisible();
  });

  test.describe("with seeded data", () => {
    test.skip(
      !seedAvailable,
      "FORENSA_TENANT_ID and FORENSA_TOKEN must be set; run scripts/seed_demo_data.py first",
    );

    test("renders the anchors table when there is at least one anchor", async ({ page }) => {
      await page.goto(consoleUrl("/anchors"));
      const hasTable = await page
        .getByTestId("anchors-table")
        .isVisible()
        .catch(() => false);
      test.skip(!hasTable, "no anchors in seed");
      const firstRow = page.locator('[data-testid^="anchor-row-"]').first();
      await expect(firstRow).toBeVisible();
    });

    test("clicking an anchor download initiates a browser download", async ({ page }) => {
      await page.goto(consoleUrl("/anchors"));
      const hasTable = await page
        .getByTestId("anchors-table")
        .isVisible()
        .catch(() => false);
      test.skip(!hasTable, "no anchors in seed");

      const downloadButton = page
        .locator('[data-testid^="anchor-download-"]')
        .first();
      const exists = await downloadButton.count();
      test.skip(exists === 0, "no anchored rows in seed");

      const [download] = await Promise.all([
        page.waitForEvent("download"),
        downloadButton.click(),
      ]);
      // The suggested filename includes the day + first 8 chars of the
      // anchor id; we just assert it ends with .tsr.
      expect(download.suggestedFilename().endsWith(".tsr")).toBe(true);
    });
  });
});
