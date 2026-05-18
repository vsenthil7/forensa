/**
 * Playwright config for the CP9.62 v2 real-user-action walkthrough.
 *
 * No webServer block - the docker-compose stack already serves
 * the API on :8000 and the console on :3001.
 */

import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests-e2e/demo',
  testMatch: 'walkthrough-real.spec.ts',
  timeout: 900_000,
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
    launchOptions: { slowMo: 350 },
    // Allow downloads (TC-3 captures the TSR blob via page.waitForEvent('download'))
    acceptDownloads: true,
  },
  projects: [
    {
      name: 'chromium-desktop',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  outputDir: './test-results-walkthrough-real',
})
