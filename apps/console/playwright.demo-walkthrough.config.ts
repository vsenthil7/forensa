/**
 * Playwright config for the CP9.62 9-screen walkthrough demo.
 *
 * Differs from playwright.config.ts in one critical way: NO webServer block.
 * The compose stack is already serving the API on :8000 and the console on :3001.
 * Booting an additional uvicorn + next-dev would clash with port bindings.
 *
 * Other settings mirror the DEMO=1 path of the main config:
 *   slowMo=400, video=on, 1440x900 viewport, chromium-desktop only.
 */

import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests-e2e/demo',
  testMatch: 'walkthrough-9-screens.spec.ts',
  timeout: 600_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'line',
  use: {
    baseURL: process.env.FORENSA_API_URL ?? 'http://localhost:8000',
    trace: 'on',
    screenshot: 'only-on-failure',
    viewport: { width: 1440, height: 900 },
    video: 'on',
    launchOptions: { slowMo: 400 },
  },
  projects: [
    {
      name: 'chromium-desktop',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // INTENTIONALLY no webServer block - compose stack serves everything.
  outputDir: './test-results-walkthrough',
})
