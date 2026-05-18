/**
 * Forensa Playwright E2E configuration (CP9.46 / IP #5).
 *
 * Boots the Forensa FastAPI on port 8000 before the test run. The
 * tests in ./tests-e2e/*.spec.ts hit the live API and assert the
 * demo flow (the same flow tools/demo.sh + tools/demo.ps1 walk
 * the regulator through).
 *
 * The webServer entry uses ``reuseExistingServer`` in non-CI mode
 * so local re-runs are fast (no spin-up cost when the API is
 * already running at the configured port).
 *
 * Cross-platform uvicorn invocation:
 *   The same config runs on a Windows dev box AND on Linux CI
 *   runners. process.platform branches between Windows
 *   poetry/Scripts/python and Linux/macOS poetry/bin/python.
 *   FORENSA_UVICORN_CMD env override wins over both -- used by
 *   GitHub Actions to point at the runner's installed Poetry venv
 *   path explicitly.
 *
 * Pattern inherited from the Verixa control-plane-ui playwright.config.ts
 * (sibling hackathon project, same author).
 */

import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, devices } from '@playwright/test';

const BACKEND_PORT = 8000;
const FRONTEND_PORT = 3000;

/**
 * Build the uvicorn command for the Forensa API.
 *
 * Precedence:
 *   1. FORENSA_UVICORN_CMD env var (CI sets this explicitly).
 *   2. process.platform === 'win32' -> poetry run uvicorn (Windows path)
 *   3. anything else                -> poetry run uvicorn (Linux/macOS)
 */
function buildUvicornCommand(): string {
  const override = process.env.FORENSA_UVICORN_CMD;
  if (override !== undefined && override.length > 0) {
    return (
      `${override} apps.api.main:app ` +
      `--host 127.0.0.1 --port ${BACKEND_PORT} --workers 1`
    );
  }
  // Both Windows and Linux work the same via Poetry; the venv path
  // differs but poetry resolves it. We invoke through poetry to keep
  // the dev experience consistent with `poetry run forensa-api`.
  return (
    `poetry run uvicorn apps.api.main:app ` +
    `--host 127.0.0.1 --port ${BACKEND_PORT} --workers 1`
  );
}

// Absolute path to the Forensa repo root (two parents up from
// apps/console/). uvicorn must boot from there so the Python
// import path resolves consistently. ESM-safe -- __dirname is
// not defined under `package.json: { type: "module" }`, so we
// derive it from import.meta.url.
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..', '..');

export default defineConfig({
  testDir: './tests-e2e',
  // FastAPI's first request after a cold start can be slow on Windows,
  // and ingestion + evidence-pack assembly add a few seconds each.
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  // Don't parallelise: tests share a single FastAPI instance + seeded
  // tenant state. Each spec assumes the seed is intact.
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',

  // DEMO=1 toggles slow-motion + video + larger viewport for the
  // captioned demo recording (auditex pattern). Default mode (CI) keeps
  // the viewport tight and only retains video on failure.
  use: {
    baseURL: process.env.FORENSA_API_URL ?? `http://127.0.0.1:${BACKEND_PORT}`,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    viewport:
      process.env.DEMO === '1'
        ? { width: 1440, height: 900 }
        : { width: 1280, height: 800 },
    video: process.env.DEMO === '1' ? 'on' : 'retain-on-failure',
    launchOptions: process.env.DEMO === '1' ? { slowMo: 400 } : {},
  },

  projects: [
    {
      name: 'chromium-desktop',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // US-F31 AC-3: installable on iOS Safari. We can't drive
      // the real Safari install prompt in Playwright, but the
      // webkit project exercises the manifest/SW fetches and
      // the responsive layout on a phone viewport.
      name: 'webkit-mobile',
      use: { ...devices['iPhone 15'] },
    },
    {
      // US-F31 AC-3: installable on Android Chrome. Pixel 7
      // gives a typical Android viewport + UA for the layout
      // assertions.
      name: 'chromium-android',
      use: { ...devices['Pixel 7'] },
    },
  ],

  // FastAPI boots before the first test runs. ``url`` is probed
  // until 2xx/3xx; once it reports up, tests start.
  //
  // The seed_demo_data.py step (which produces the FORENSA_TENANT_ID
  // + FORENSA_TOKEN that the demo spec needs) is the developer's
  // responsibility BEFORE running playwright -- the spec reads
  // those env vars and skips with a clear message if either is
  // missing. The spec does NOT auto-seed because seeding involves
  // a fresh database TRUNCATE and we don't want playwright to
  // wipe a dev's working state silently.
  //
  // The captioned demo spec drives the Next.js Console UI which
  // calls the FastAPI in the browser. So both servers must be up.
  // The Next.js dev server is the second entry; Playwright waits
  // on BOTH URLs before starting tests.
  webServer: [
    {
      command: buildUvicornCommand(),
      cwd: REPO_ROOT,
      url: `http://127.0.0.1:${BACKEND_PORT}/healthz`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      stdout: 'pipe',
      stderr: 'pipe',
    },
    {
      command: 'npm run dev',
      cwd: __dirname,
      url: `http://127.0.0.1:${FRONTEND_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      stdout: 'pipe',
      stderr: 'pipe',
    },
  ],
});
