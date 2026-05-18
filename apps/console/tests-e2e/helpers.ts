/**
 * Forensa Console — shared Playwright helpers.
 *
 * Why these exist
 * ---------------
 * The captioned-demo spec (demo_script.spec.ts) talks to the API
 * directly on port 8000. The new UI specs drive the Next.js
 * Console on port 3000 and assert what the user sees. Same
 * `playwright.config.ts` covers both: we use absolute URLs in
 * the UI specs so the API-targeted `baseURL` doesn't collide.
 *
 * The auth seed is shared with the demo spec: scripts/seed_demo_data.py
 * prints FORENSA_TENANT_ID + FORENSA_TOKEN. The UI specs also need
 * NEXT_PUBLIC_FORENSA_TOKEN baked into the Next build (or set as
 * an env var on `npm run dev`) so the Console's apiFetch helper
 * forwards the bearer. When the seed isn't available, specs that
 * need data skip with a clear message.
 *
 * Pattern inherited from the Verixa control-plane-ui Playwright
 * specs (sibling hackathon project, same author).
 */

import { test as base } from "@playwright/test";

export const UI_BASE_URL =
  process.env.FORENSA_CONSOLE_URL ?? "http://127.0.0.1:3000";

export const TENANT_ID = process.env.FORENSA_TENANT_ID ?? "";
export const TOKEN = process.env.FORENSA_TOKEN ?? "";

export const seedAvailable = TENANT_ID.length > 0 && TOKEN.length > 0;

/**
 * Test fixture that fails fast when the seed env vars are absent.
 * Used by specs that need live API data (receipts list, evidence pack);
 * structural specs (PWA manifest, TopNav render, persona landing)
 * don't need the seed and use the default `test`.
 */
export const test = base.extend<NonNullable<unknown>>({});
export { expect } from "@playwright/test";

export function skipIfNoSeed(reason: string) {
  return {
    skip: !seedAvailable,
    reason,
  };
}

/** Build a Console URL from a path. */
export function consoleUrl(path: string): string {
  const sep = path.startsWith("/") ? "" : "/";
  return `${UI_BASE_URL}${sep}${path}`;
}
