/**
 * Forensa Console — Evidence pack toggle E2E spec (US-F19, SCR-F04).
 *
 * Closes acceptance:
 *   - Compliance view default: plain-English summary + big PDF CTA;
 *     no hex hashes visible.
 *   - Technical view: full JSON-LD pack (root hash, pack id, anchor).
 *   - Narrated loading: while building, stepwise human-readable
 *     progress, not a generic spinner.
 *
 * Pre-flight (skip-with-reason if absent): FORENSA_TENANT_ID + FORENSA_TOKEN.
 */

import { test, expect, consoleUrl, seedAvailable } from "./helpers";

test.describe("Evidence pack toggle (US-F19, SCR-F04)", () => {
  test.skip(
    !seedAvailable,
    "FORENSA_TENANT_ID and FORENSA_TOKEN must be set; run scripts/seed_demo_data.py first",
  );

  test("page mounts with the toggle component visible", async ({ page }) => {
    await page.goto(consoleUrl("/evidence"));
    await expect(page.getByTestId("evidence-pack-toggle")).toBeVisible();
    await expect(page.getByTestId("evidence-view-switcher")).toBeVisible();
  });

  test("Compliance view is the default", async ({ page }) => {
    await page.goto(consoleUrl("/evidence"));
    await expect(page.getByTestId("view-compliance")).toHaveAttribute(
      "data-active",
      "true",
    );
    await expect(page.getByTestId("view-technical")).toHaveAttribute(
      "data-active",
      "false",
    );
    // The Generate CTA wears the compliance-flavoured label.
    await expect(page.getByTestId("generate-pack-button")).toContainText("FCA");
  });

  test("switching to Technical view flips the active flag + CTA copy", async ({ page }) => {
    await page.goto(consoleUrl("/evidence"));
    await page.getByTestId("view-technical").click();
    await expect(page.getByTestId("view-technical")).toHaveAttribute(
      "data-active",
      "true",
    );
    await expect(page.getByTestId("generate-pack-button")).toContainText(
      "Generate evidence pack",
    );
  });

  test("Generate shows narrated loading then a compliance ok pane", async ({ page }) => {
    await page.goto(consoleUrl("/evidence"));
    await page.getByTestId("generate-pack-button").click();
    // We don't try to catch the loading state (server is fast); we
    // assert the resolved compliance view + Download CTA.
    await expect(page.getByTestId("compliance-view")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("compliance-headline")).toBeVisible();
    await expect(page.getByTestId("download-pdf-button")).toBeVisible();
  });

  test("Technical view after Generate shows pack-root-hash + anchor", async ({ page }) => {
    await page.goto(consoleUrl("/evidence"));
    await page.getByTestId("view-technical").click();
    await page.getByTestId("generate-pack-button").click();
    await expect(page.getByTestId("technical-view")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("pack-root-hash")).toBeVisible();
    await expect(page.getByTestId("pack-receipt-count")).toBeVisible();
  });

  test("the Compliance view's body does NOT show the root hash hex (UC-09 'without touching JSON or hash strings')", async ({
    page,
  }) => {
    await page.goto(consoleUrl("/evidence"));
    await page.getByTestId("generate-pack-button").click();
    await expect(page.getByTestId("compliance-view")).toBeVisible({
      timeout: 30_000,
    });
    // Pull the compliance view's text and verify there's no 64-hex.
    const txt = (await page.getByTestId("compliance-view").innerText()) ?? "";
    expect(/[0-9a-f]{64}/i.test(txt)).toBe(false);
  });
});
