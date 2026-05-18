/**
 * Forensa Console — Receipt detail tabs E2E spec (US-F30, SCR-F03).
 *
 * Closes acceptance criteria:
 *   AC-1 Summary tab default with plain English
 *   AC-2 Proof tab with prev -> current hash visual
 *   AC-3 Raw tab with copy-to-clipboard
 *
 * Strategy: navigate from the receipts list to the first row's
 * detail page so we have a real receipt id; if the list is empty
 * the spec skips with a clear reason.
 *
 * Hash-based tab routing is also asserted (deep link to #proof
 * lands directly on the Proof tab on cold load, per BR-14 AC-2
 * "no sessionStorage for deep-link recovery").
 */

import { test, expect, consoleUrl, seedAvailable } from "./helpers";

test.describe("Receipt detail tabs (US-F30, SCR-F03)", () => {
  test.skip(
    !seedAvailable,
    "FORENSA_TENANT_ID and FORENSA_TOKEN must be set; run scripts/seed_demo_data.py first",
  );

  /** Returns the first receipt id from the list, or null if empty. */
  async function getFirstReceiptId(page: import("@playwright/test").Page) {
    await page.goto(consoleUrl("/receipts"));
    const settled = page
      .getByTestId("receipts-timeline-table")
      .or(page.getByTestId("receipts-timeline-empty"));
    await expect(settled).toBeVisible();
    const link = page.locator('[data-testid^="row-link-"]').first();
    const exists = await link.count();
    if (exists === 0) return null;
    const href = await link.getAttribute("href");
    if (!href) return null;
    const m = /\/receipts\/([^?#]+)/.exec(href);
    return m ? m[1] : null;
  }

  test("AC-1 Summary tab is the default on a cold detail page load", async ({ page }) => {
    const id = await getFirstReceiptId(page);
    test.skip(!id, "no receipts in seed");
    await page.goto(consoleUrl(`/receipts/${id}`));
    await expect(page.getByTestId("receipt-detail-tabs")).toBeVisible();
    await expect(page.getByTestId("tab-summary")).toHaveAttribute(
      "data-active",
      "true",
    );
    await expect(page.getByTestId("summary-pane")).toBeVisible();
  });

  test("AC-2 Proof tab renders prev -> current hash visual", async ({ page }) => {
    const id = await getFirstReceiptId(page);
    test.skip(!id, "no receipts in seed");
    await page.goto(consoleUrl(`/receipts/${id}`));
    await page.getByTestId("tab-proof").click();
    await expect(page.getByTestId("proof-pane")).toBeVisible();
    await expect(page.getByTestId("proof-prev")).toBeVisible();
    await expect(page.getByTestId("proof-current")).toBeVisible();
  });

  test("AC-3 Raw tab exposes copy-to-clipboard and JSON payload", async ({ page, context, browserName }) => {
    const id = await getFirstReceiptId(page);
    test.skip(!id, "no receipts in seed");
    test.skip(
      browserName !== "chromium",
      "clipboard-read permission is Chromium-only in Playwright",
    );
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.goto(consoleUrl(`/receipts/${id}`));
    await page.getByTestId("tab-raw").click();
    await expect(page.getByTestId("raw-pane")).toBeVisible();
    await expect(page.getByTestId("raw-json")).toBeVisible();
    await page.getByTestId("raw-copy").click();
    await expect(page.getByTestId("raw-copy")).toContainText("Copied");
  });

  test("deep-link #proof lands directly on Proof tab without sessionStorage", async ({ page }) => {
    const id = await getFirstReceiptId(page);
    test.skip(!id, "no receipts in seed");
    await page.evaluate(() => window.sessionStorage.clear());
    await page.goto(consoleUrl(`/receipts/${id}#proof`));
    await expect(page.getByTestId("proof-pane")).toBeVisible();
    await expect(page.getByTestId("tab-proof")).toHaveAttribute(
      "data-active",
      "true",
    );
  });

  test("Back-to-receipts link is reachable from the detail page", async ({ page }) => {
    const id = await getFirstReceiptId(page);
    test.skip(!id, "no receipts in seed");
    await page.goto(consoleUrl(`/receipts/${id}`));
    await expect(page.getByTestId("receipt-detail-back-link")).toBeVisible();
    await page.getByTestId("receipt-detail-back-link").click();
    await expect(page).toHaveURL(/\/receipts(\?|$)/);
  });
});
