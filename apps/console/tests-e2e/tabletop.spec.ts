/**
 * Forensa Console — Tabletop simulator E2E spec (US-F23, SCR-F06).
 *
 * Structural assertions don't need the seed; the run-simulation
 * happy path needs a real policy_bundle_id from the seed AND a
 * valid scenario, so it skips by default.
 */

import { test, expect, consoleUrl, seedAvailable } from "./helpers";

test.describe("Tabletop simulator (US-F23, SCR-F06)", () => {
  test("the /tabletop page mounts (structural)", async ({ page }) => {
    await page.goto(consoleUrl("/tabletop"));
    await expect(page.getByTestId("tabletop-page")).toBeVisible();
    await expect(page.getByTestId("tabletop-simulator")).toBeVisible();
  });

  test("Load sample populates the textarea with a starting skeleton", async ({ page }) => {
    await page.goto(consoleUrl("/tabletop"));
    await page.getByTestId("tabletop-load-sample").click();
    const ta = page.getByTestId("tabletop-scenario-input");
    await expect(ta).not.toHaveValue("");
  });

  test("running with empty input surfaces the validation error", async ({ page }) => {
    await page.goto(consoleUrl("/tabletop"));
    await page.getByTestId("tabletop-run").click();
    await expect(page.getByTestId("tabletop-error")).toBeVisible();
    await expect(page.getByTestId("tabletop-error")).toContainText("Paste");
  });

  test("running with malformed JSON surfaces the parse error", async ({ page }) => {
    await page.goto(consoleUrl("/tabletop"));
    await page.getByTestId("tabletop-scenario-input").fill("{not valid");
    await page.getByTestId("tabletop-run").click();
    await expect(page.getByTestId("tabletop-error")).toContainText(
      "Invalid JSON",
    );
  });

  test.describe("with seeded data", () => {
    test.skip(
      !seedAvailable,
      "FORENSA_TENANT_ID and FORENSA_TOKEN must be set; run scripts/seed_demo_data.py first",
    );

    test("running the sample scenario settles into a result or an HTTP error", async ({ page }) => {
      await page.goto(consoleUrl("/tabletop"));
      await page.getByTestId("tabletop-load-sample").click();
      await page.getByTestId("tabletop-run").click();
      // The sample template has a placeholder policy_bundle_id; the
      // API will 422 it. Either way we leave the loading state.
      const settled = page
        .getByTestId("tabletop-result")
        .or(page.getByTestId("tabletop-error"));
      await expect(settled).toBeVisible({ timeout: 20_000 });
    });
  });
});
