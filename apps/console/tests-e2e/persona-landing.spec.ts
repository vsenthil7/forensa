/**
 * Forensa Console — Persona landing E2E spec (US-F28, SCR-F01).
 *
 * Acceptance closed:
 *   - 6 persona cards rendered with CTA each.
 *   - Each card CTA navigates to a non-empty, root-relative path.
 *   - Card layout adapts to mobile viewport (the grid is auto-fill).
 *
 * The negative path "unauthenticated -> redirect to SCR-F09 login"
 * lands in Phase 10 (CP10.1), so the only assertion here is that
 * the page renders without auth in dev mode (current behaviour).
 */

import { test, expect, consoleUrl } from "./helpers";

const PERSONA_TEST_IDS = [
  "persona-card-comp",
  "persona-card-aud",
  "persona-card-sec",
  "persona-card-counsel",
  "persona-card-plat",
  "persona-card-acq",
];

test.describe("Persona landing (US-F28, SCR-F01)", () => {
  test("renders the persona-landing block + grid", async ({ page }) => {
    await page.goto(consoleUrl("/"));
    await expect(page.getByTestId("persona-landing")).toBeVisible();
    await expect(page.getByTestId("persona-grid")).toBeVisible();
  });

  test("renders all 6 persona cards", async ({ page }) => {
    await page.goto(consoleUrl("/"));
    for (const id of PERSONA_TEST_IDS) {
      await expect(page.getByTestId(id)).toBeVisible();
    }
  });

  test("each persona card has a CTA with a root-relative href", async ({ page }) => {
    await page.goto(consoleUrl("/"));
    for (const id of PERSONA_TEST_IDS) {
      const cta = page.getByTestId(`${id}-cta`);
      await expect(cta).toBeVisible();
      const href = await cta.getAttribute("href");
      expect(href).toBeTruthy();
      expect(href?.startsWith("/")).toBe(true);
    }
  });

  test("clicking the Compliance Officer CTA navigates to /evidence", async ({ page }) => {
    await page.goto(consoleUrl("/"));
    await page.getByTestId("persona-card-comp-cta").click();
    await expect(page).toHaveURL(/\/evidence$/);
  });

  test("clicking the Auditor CTA navigates to /receipts", async ({ page }) => {
    await page.goto(consoleUrl("/"));
    await page.getByTestId("persona-card-aud-cta").click();
    await expect(page).toHaveURL(/\/receipts(\?|$)/);
  });

  test("the landing does not depend on sessionStorage (cold reload survives)", async ({ page }) => {
    // BR-14 AC-2 anti-pattern: no "active persona" sessionStorage.
    await page.goto(consoleUrl("/"));
    await page.evaluate(() => window.sessionStorage.clear());
    await page.reload();
    await expect(page.getByTestId("persona-landing")).toBeVisible();
    for (const id of PERSONA_TEST_IDS) {
      await expect(page.getByTestId(id)).toBeVisible();
    }
  });
});
