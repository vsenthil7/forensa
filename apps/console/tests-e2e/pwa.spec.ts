/**
 * Forensa Console — PWA E2E spec (US-F31, RT-F20).
 *
 * Acceptance closed:
 *   AC-1 manifest.json declares icon, theme color, display=standalone, scope
 *   AC-2 service worker caches read-only shell
 *   AC-3 installable on iOS Safari, Android Chrome, desktop Chrome/Edge
 *        (we assert the install-prerequisite signals; the real install
 *        prompt is a browser-mediated event we can't fire from Playwright)
 *
 * Mobile viewport projects (webkit-mobile, chromium-android) inherit
 * these tests automatically and verify the manifest is reachable
 * from the mobile UA too — the "mobile playwright coverage" piece
 * of the BR-14 acceptance.
 */

import { test, expect, consoleUrl, UI_BASE_URL } from "./helpers";

test.describe("PWA shell (US-F31, RT-F20)", () => {
  test("manifest.webmanifest is reachable and declares standalone display + scope", async ({
    request,
  }) => {
    const res = await request.get(`${UI_BASE_URL}/manifest.webmanifest`);
    expect(res.status()).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.name).toBe("Forensa Console");
    expect(body.short_name).toBe("Forensa");
    expect(body.display).toBe("standalone");
    expect(body.scope).toBe("/");
    expect(body.start_url).toBe("/");
    expect(body.theme_color).toBe("#1e40af");
    expect(Array.isArray(body.icons)).toBe(true);
    const icons = body.icons as Array<{ src: string; sizes: string }>;
    expect(icons.length).toBeGreaterThanOrEqual(2);
  });

  test("sw.js is served at /sw.js (200 with JS content)", async ({ request }) => {
    const res = await request.get(`${UI_BASE_URL}/sw.js`);
    expect(res.status()).toBe(200);
    const ct = res.headers()["content-type"] ?? "";
    expect(ct.includes("javascript") || ct.includes("application/")).toBeTruthy();
    const body = await res.text();
    // Spot-check that the cache + fetch handlers are present (US-F31 AC-2).
    expect(body).toContain("install");
    expect(body).toContain("fetch");
    expect(body).toContain("activate");
  });

  test("icons (192 + 512) are reachable", async ({ request }) => {
    for (const path of ["/icon-192.svg", "/icon-512.svg"]) {
      const res = await request.get(`${UI_BASE_URL}${path}`);
      expect(res.status()).toBe(200);
    }
  });

  test("the root page links the manifest + theme color in <head>", async ({ page }) => {
    await page.goto(consoleUrl("/"));
    const manifestHref = await page.locator('link[rel="manifest"]').getAttribute("href");
    expect(manifestHref).toBe("/manifest.webmanifest");
    const themeColor = await page
      .locator('meta[name="theme-color"]')
      .getAttribute("content");
    expect(themeColor).toBe("#1e40af");
  });

  test("read-only views render without crashing under a faked offline event (US-F31 AC-5 affordance)", async ({
    page,
    context,
  }) => {
    await page.goto(consoleUrl("/"));
    await expect(page.getByTestId("persona-landing")).toBeVisible();
    // Simulate going offline at the browser level. The page should
    // still be visible (cached shell) and the OfflineBanner should
    // appear with data-online=false.
    await context.setOffline(true);
    await page.evaluate(() => window.dispatchEvent(new Event("offline")));
    await expect(page.getByTestId("offline-banner")).toBeVisible();
    await expect(page.getByTestId("offline-banner")).toHaveAttribute(
      "data-online",
      "false",
    );
    // Restore so subsequent specs aren't affected.
    await context.setOffline(false);
  });
});
