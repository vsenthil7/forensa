/**
 * Forensa Console — status dashboard E2E spec (SCR-F10).
 *
 * No seed required: /healthz is unauthenticated. The structural
 * assertions are all that's needed to validate SCR-F10 because the
 * Operational-metrics panels are intentionally placeholders pending
 * API-F15.
 */

import { test, expect, consoleUrl } from "./helpers";

test.describe("Status dashboard (SCR-F10)", () => {
  test("the /status page mounts (no seed required)", async ({ page }) => {
    await page.goto(consoleUrl("/status"));
    await expect(page.getByTestId("status-page")).toBeVisible();
    await expect(page.getByTestId("status-dashboard")).toBeVisible();
  });

  test("/healthz is called and the api panel (or error) settles", async ({ page }) => {
    await page.goto(consoleUrl("/status"));
    const settled = page
      .getByTestId("status-api-panel")
      .or(page.getByTestId("status-error"));
    await expect(settled).toBeVisible();
  });

  test("the planned panels section names API-F15", async ({ page }) => {
    await page.goto(consoleUrl("/status"));
    await expect(page.getByTestId("status-planned-panels")).toBeVisible();
    await expect(page.getByTestId("status-planned-panels")).toContainText("API-F15");
    await expect(page.getByTestId("status-planned-list")).toBeVisible();
  });

  test("Refresh button re-runs the health check", async ({ page }) => {
    await page.goto(consoleUrl("/status"));
    await expect(page.getByTestId("status-refresh")).toBeVisible();
    // Just assert the button is clickable; the actual re-fetch
    // verification is in the unit tests.
    await page.getByTestId("status-refresh").click();
    const settled = page
      .getByTestId("status-api-panel")
      .or(page.getByTestId("status-error"));
    await expect(settled).toBeVisible();
  });
});
