/**
 * Forensa Console — TopNav E2E spec (BR-14 AC-2).
 *
 * Asserts the list-views-as-top-nav contract:
 *   - Every active link is reachable on a cold page load.
 *   - Planned (future-CP) links are surfaced as disabled, not as
 *     dead clicks.
 *   - The active state follows pathname (parent route match for
 *     drill-down like /receipts/[id]).
 *
 * Runs on every project — desktop, iPhone, Pixel — so the
 * responsive layout doesn't silently break the chrome.
 */

import { test, expect, consoleUrl } from "./helpers";

test.describe("TopNav (BR-14 AC-2, SCR-F01)", () => {
  test("renders the logo + every primary link on the root page", async ({ page }) => {
    await page.goto(consoleUrl("/"));
    await expect(page.getByTestId("topnav")).toBeVisible();
    await expect(page.getByTestId("topnav-logo")).toBeVisible();
    await expect(page.getByTestId("topnav-link-home")).toBeVisible();
    await expect(page.getByTestId("topnav-link-receipts")).toBeVisible();
    await expect(page.getByTestId("topnav-link-evidence")).toBeVisible();
  });

  test("marks the home link active on / (data-active=true)", async ({ page }) => {
    await page.goto(consoleUrl("/"));
    await expect(page.getByTestId("topnav-link-home")).toHaveAttribute(
      "data-active",
      "true",
    );
  });

  test("marks the receipts link active on /receipts", async ({ page }) => {
    await page.goto(consoleUrl("/receipts"));
    await expect(page.getByTestId("topnav-link-receipts")).toHaveAttribute(
      "data-active",
      "true",
    );
  });

  test("marks the evidence link active on /evidence", async ({ page }) => {
    await page.goto(consoleUrl("/evidence"));
    await expect(page.getByTestId("topnav-link-evidence")).toHaveAttribute(
      "data-active",
      "true",
    );
  });

  test("after CP9.58, no DEFAULT_NAV_ITEMS are marked planned (every link is active)", async ({ page }) => {
    await page.goto(consoleUrl("/"));
    // CP9.52..CP9.58 promoted every screen; there are no more planned
    // entries in DEFAULT_NAV_ITEMS. The planned-rendering path still
    // exists in TopNav.tsx for future RT-F* items but is unit-tested
    // via a custom items prop in TopNav.test.tsx.
    const planned = page.locator('[data-planned="true"]');
    await expect(planned).toHaveCount(0);
  });

  test("/anchors, /diligence, /narratives, /tabletop, /status are active links (CP9.53..CP9.58)", async ({ page }) => {
    await page.goto(consoleUrl("/"));
    for (const id of [
      "topnav-link-anchors",
      "topnav-link-diligence",
      "topnav-link-narratives",
      "topnav-link-tabletop",
      "topnav-link-status",
    ]) {
      const el = page.getByTestId(id);
      await expect(el).toBeVisible();
      const tag = await el.evaluate((node) => node.tagName.toLowerCase());
      expect(tag).toBe("a");
    }
  });

  test("the tenant chip placeholder is rendered (Phase 10 tenant picker arrives at CP10.1)", async ({
    page,
  }) => {
    await page.goto(consoleUrl("/"));
    await expect(page.getByTestId("topnav-tenant-label")).toBeVisible();
  });

  test("logo click returns to the persona landing", async ({ page }) => {
    await page.goto(consoleUrl("/receipts"));
    await page.getByTestId("topnav-logo").click();
    await expect(page).toHaveURL(new RegExp("/$"));
    await expect(page.getByTestId("persona-landing")).toBeVisible();
  });
});
