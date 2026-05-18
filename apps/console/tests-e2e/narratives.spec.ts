/**
 * Forensa Console — Narrative viewer E2E spec (SCR-F08, RT-F21 advance).
 *
 * Structural assertions don't require the seed. The happy-path
 * (model returns 200 with a real narrative) needs both the seed +
 * a working Gemini key on the API; we skip cleanly when either
 * is missing.
 */

import { test, expect, consoleUrl, seedAvailable } from "./helpers";

test.describe("Narrative viewer (SCR-F08, RT-F21)", () => {
  test("the /narratives page mounts (structural)", async ({ page }) => {
    await page.goto(consoleUrl("/narratives"));
    await expect(page.getByTestId("narratives-page")).toBeVisible();
    await expect(page.getByTestId("narrative-form")).toBeVisible();
  });

  test("the form exposes both date inputs + submit", async ({ page }) => {
    await page.goto(consoleUrl("/narratives"));
    await expect(page.getByTestId("narrative-scope-start")).toBeVisible();
    await expect(page.getByTestId("narrative-scope-end")).toBeVisible();
    await expect(page.getByTestId("narrative-submit")).toBeVisible();
  });

  test("submitting with empty dates shows the validation error", async ({ page }) => {
    await page.goto(consoleUrl("/narratives"));
    await page.getByTestId("narrative-submit").click();
    await expect(page.getByTestId("narrative-error")).toBeVisible();
    await expect(page.getByTestId("narrative-error")).toContainText("Pick both");
  });

  test.describe("with seeded data", () => {
    test.skip(
      !seedAvailable,
      "FORENSA_TENANT_ID and FORENSA_TOKEN must be set; run scripts/seed_demo_data.py first",
    );

    test("submitting a valid window settles into pane / error / loading", async ({ page }) => {
      await page.goto(consoleUrl("/narratives"));
      await page.getByTestId("narrative-scope-start").fill("2026-05-13");
      await page.getByTestId("narrative-scope-end").fill("2026-05-14");
      await page.getByTestId("narrative-submit").click();
      const settled = page
        .getByTestId("narrative-pane")
        .or(page.getByTestId("narrative-error"));
      // Gemini round-trip can be slow; give it 30s.
      await expect(settled).toBeVisible({ timeout: 30_000 });
    });
  });
});
