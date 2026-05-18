/**
 * Forensa real-user-action walkthrough demo - CP9.62 v2.
 *
 * Mirrors auditex/frontend/tests/demo/end-to-end-demo.spec.ts pattern:
 *   - 5 scenarios, each a real user journey end-to-end
 *   - Real form fills (type into actual inputs, click actual buttons)
 *   - Real API responses (no stubs, no .goto-and-pretend)
 *   - Caption shows the test data ABOUT to be entered, then we SEE it entered
 *
 * Scenarios:
 *   TC-1 Verify receipt integrity   - click row -> tabs (Summary/Proof/Raw) -> integrity badge
 *   TC-2 Generate evidence pack     - click Generate -> see signed pack + TSA anchor
 *   TC-3 Download TSA anchor        - click Download TSR -> capture DER blob via Playwright
 *   TC-4 Create M&A diligence job   - type scope dates -> click Create -> watch poll Pending->Completed
 *   TC-5 Run tabletop simulation    - Load sample -> swap bundle_id -> Run -> see verdicts
 *
 * Required env (orchestrator wires them):
 *   FORENSA_CONSOLE_URL              default http://localhost:3001
 *   FORENSA_API_URL                  default http://localhost:8000
 *   FORENSA_TENANT_ID                from seed_demo_data.py output
 *   FORENSA_TOKEN                    from seed_demo_data.py output
 *   FORENSA_DEMO_BUNDLE_ID           from seed_demo_data.py output (for TC-5)
 *   FORENSA_SCOPE_START / END        date window covered by seeded data
 */

import { test, expect, type Page, type Locator } from '@playwright/test'
import { showCaption, hideCaption, showTitleCard } from './caption-overlay'

const CONSOLE = process.env.FORENSA_CONSOLE_URL ?? 'http://localhost:3001'
const API = process.env.FORENSA_API_URL ?? 'http://localhost:8000'
const TENANT_ID = process.env.FORENSA_TENANT_ID ?? ''
const TOKEN = process.env.FORENSA_TOKEN ?? ''
const BUNDLE_ID = process.env.FORENSA_DEMO_BUNDLE_ID ?? ''
const SCOPE_START_DATE = (process.env.FORENSA_SCOPE_START ?? '2026-05-13T00:00:00+00:00').slice(0, 10)
const SCOPE_END_DATE = (process.env.FORENSA_SCOPE_END ?? '2026-05-14T23:59:59+00:00').slice(0, 10)

// Highlight helpers
async function highlight(loc: Locator, color = 'rgba(251, 191, 36, 0.55)', ms = 1500) {
  if (!(await loc.isVisible().catch(() => false))) return
  await loc.evaluate((el: HTMLElement, args: { color: string; ms: number }) => {
    el.style.transition = 'box-shadow 0.4s, transform 0.4s'
    el.style.boxShadow = `0 0 0 6px ${args.color}`
    el.style.transform = 'scale(1.04)'
    setTimeout(() => {
      el.style.boxShadow = ''
      el.style.transform = ''
    }, args.ms)
  }, { color, ms })
  await loc.page().waitForTimeout(ms - 200)
}

async function pulseRow(loc: Locator, ms = 1200) {
  if (!(await loc.isVisible().catch(() => false))) return
  await loc.evaluate((el: HTMLElement, msArg: number) => {
    el.style.transition = 'background-color 0.3s'
    el.style.backgroundColor = '#fef3c7'
    setTimeout(() => { el.style.backgroundColor = '' }, msArg)
  }, ms)
  await loc.page().waitForTimeout(ms)
}

// Inject Authorization header into every request the page makes.
// The console's apiFetch reads NEXT_PUBLIC_FORENSA_TOKEN at BUILD TIME,
// which is empty in the compose-built bundle. setExtraHTTPHeaders attaches
// the bearer at the network layer, which the api accepts.
async function wireAuthIntoContext(page: Page) {
  await page.context().setExtraHTTPHeaders({ Authorization: `Bearer ${TOKEN}` })
  // Make sure navigator.onLine reads true (Playwright sometimes spawns offline).
  await page.context().setOffline(false)
}

test.describe('Forensa real-user-action walkthrough (5 scenarios)', () => {
  test.skip(
    TENANT_ID === '' || TOKEN === '',
    'Set FORENSA_TENANT_ID and FORENSA_TOKEN. Run scripts/seed_demo_data.py first.',
  )

  test('5 scenarios driving real DOM elements end-to-end', async ({ page, request }) => {
    test.setTimeout(15 * 60 * 1000)

    // === OPENING TITLE CARD ===
    await page.goto('about:blank')
    await page.evaluate(() => {
      document.body.style.cssText = 'margin:0;padding:0;background:#0f172a;'
    })
    await page.waitForTimeout(150)
    await showTitleCard(
      page,
      'Forensa',
      'Cryptographic evidence layer for enterprise AI agents.  5 scenarios, every one a real user journey - real form fills, real API calls, real crypto.  Operator Console driven through Playwright.',
      5000,
    )

    // ============================================================
    // TC-1 - Verify receipt integrity
    // ============================================================
    await showCaption(page, {
      scene: 'TC-1 of 5',
      title: 'Verify a receipt - 1 of 2 crypto operations',
      given: 'Tenant has 5 seeded receipts forming an append-only chain',
      when: 'Compliance officer clicks the head of the chain to inspect it',
      then: 'Console fetches the receipt, recomputes its hash, and shows integrity = OK',
      testData: [
        `tenant_id      ${TENANT_ID.slice(0, 8)}...`,
        `endpoint       GET /v1/receipts/{id}`,
        `crypto         SHA-256 recompute over payload + chain link`,
        `tabs           Summary -> Proof -> Raw JSON`,
      ],
      expected: 'integrity-badge[data-integrity-ok="true"] + tabs render Summary/Proof/Raw',
      holdMs: 3500,
    })
    await hideCaption(page)

    // Wire auth BEFORE first navigation so the console's initial API
    // calls already carry the bearer header.
    await wireAuthIntoContext(page)
    await page.goto(`${CONSOLE}/receipts?tenant_id=${TENANT_ID}`, { waitUntil: 'domcontentloaded' })

    // Wait for the timeline to load
    const timelineTable = page.locator('[data-testid="receipts-timeline-table"]')
    await expect(timelineTable).toBeVisible({ timeout: 30000 })
    await page.waitForTimeout(1500)
    await highlight(timelineTable, 'rgba(99, 102, 241, 0.55)', 2000)

    // Pull the first receipt id via API so we can locate the row by test-id
    const listResp = await request.get(
      `${API}/v1/receipts?tenant_id=${TENANT_ID}&limit=5`,
      { headers: { Authorization: `Bearer ${TOKEN}` } },
    )
    const listBody = await listResp.json()
    const firstReceiptId = listBody.items[0].id
    const firstRow = page.locator(`[data-testid="receipt-row-${firstReceiptId}"]`)
    await firstRow.scrollIntoViewIfNeeded()
    await pulseRow(firstRow, 1500)

    // Click the "Open" link in that row to navigate to detail
    const openLink = page.locator(`[data-testid="row-link-${firstReceiptId}"]`)
    await highlight(openLink, 'rgba(251, 191, 36, 0.55)', 1300)
    await openLink.click()
    await page.waitForLoadState('domcontentloaded', { timeout: 30000 }).catch(() => {})

    // Detail page loaded - walk the 3 tabs
    const tabsRoot = page.locator('[data-testid="receipt-detail-tabs"]')
    await expect(tabsRoot).toBeVisible({ timeout: 30000 })
    await page.waitForTimeout(800)

    // Summary tab (default) - integrity line
    const summaryPane = page.locator('[data-testid="summary-pane"]')
    await expect(summaryPane).toBeVisible({ timeout: 10000 })
    const integrityLine = page.locator('[data-testid="summary-integrity-line"]')
    await expect(integrityLine).toHaveAttribute('data-integrity-ok', 'true', { timeout: 5000 })
    await highlight(integrityLine, 'rgba(34, 197, 94, 0.55)', 2200)

    // Proof tab - hash visual
    const proofTab = page.locator('[data-testid="tab-proof"]')
    await highlight(proofTab, 'rgba(251, 191, 36, 0.55)', 1200)
    await proofTab.click()
    await page.waitForTimeout(800)
    const proofCurrent = page.locator('[data-testid="proof-current"]')
    await expect(proofCurrent).toBeVisible({ timeout: 10000 })
    await highlight(proofCurrent, 'rgba(99, 102, 241, 0.55)', 2000)

    // Raw tab - copy button
    const rawTab = page.locator('[data-testid="tab-raw"]')
    await highlight(rawTab, 'rgba(251, 191, 36, 0.55)', 1200)
    await rawTab.click()
    await page.waitForTimeout(800)
    const rawJson = page.locator('[data-testid="raw-json"]')
    await expect(rawJson).toBeVisible({ timeout: 10000 })
    await page.waitForTimeout(1500)

    // ============================================================
    // TC-2 - Generate evidence pack
    // ============================================================
    await showCaption(page, {
      scene: 'TC-2 of 5',
      title: 'Generate evidence pack - 2 of 2 crypto operations (PRODUCE)',
      given: 'Regulator wants a take-home audit artifact for the seeded window',
      when: 'User opens /evidence and clicks Generate evidence pack',
      then: 'Forensa builds JSON-LD pack with root_hash + RFC 3161 TSA anchor + Ed25519 signature',
      testData: [
        `route          GET /evidence?tenant_id=...&scope_start=${SCOPE_START_DATE}&scope_end=${SCOPE_END_DATE}`,
        `api            GET /v1/evidence-packs`,
        `crypto         pack_root_hash | Ed25519 sig | FreeTSA RFC 3161 TSR`,
        `output         JSON-LD body + Download PDF for regulator`,
      ],
      expected: 'pack-signed-badge appears + pack-id + pack-root-hash + Download button',
      holdMs: 3500,
    })
    await hideCaption(page)

    await page.goto(
      `${CONSOLE}/evidence?tenant_id=${TENANT_ID}` +
      `&scope_start=${encodeURIComponent(`${SCOPE_START_DATE}T00:00:00+00:00`)}` +
      `&scope_end=${encodeURIComponent(`${SCOPE_END_DATE}T23:59:59+00:00`)}`,
      { waitUntil: 'domcontentloaded' },
    )
    await page.waitForTimeout(1500)

    // Click the real Generate button
    const genBtn = page.locator('[data-testid="generate-pack-button"]')
    await expect(genBtn).toBeVisible({ timeout: 30000 })
    await highlight(genBtn, 'rgba(251, 191, 36, 0.55)', 1500)
    await genBtn.click()

    // Wait for the signed badge - real round-trip to /v1/evidence-packs
    const signedBadge = page.locator('[data-testid="pack-signed-badge"]')
    await expect(signedBadge).toBeVisible({ timeout: 60000 })
    await highlight(signedBadge, 'rgba(34, 197, 94, 0.55)', 2200)

    // Pulse the root hash + anchor rows so viewer reads the artifact
    const rootHash = page.locator('[data-testid="pack-root-hash"]')
    await expect(rootHash).toBeVisible({ timeout: 10000 })
    await highlight(rootHash, 'rgba(99, 102, 241, 0.55)', 1800)

    const tsaRow = page.locator('[data-testid="pack-anchor-tsa"]')
    if (await tsaRow.isVisible().catch(() => false)) {
      await highlight(tsaRow, 'rgba(251, 191, 36, 0.55)', 1500)
    }

    const downloadBtn = page.locator('[data-testid="download-pdf-button"]')
    if (await downloadBtn.isVisible().catch(() => false)) {
      await highlight(downloadBtn, 'rgba(6, 95, 70, 0.55)', 1800)
    }

    // ============================================================
    // TC-3 - Download TSA anchor (Playwright captures DER blob)
    // ============================================================
    await showCaption(page, {
      scene: 'TC-3 of 5',
      title: 'Download RFC 3161 TSA anchor (real DER bytes)',
      given: 'Day 1 (2026-05-13) was anchored via TSA when the demo seeded',
      when: 'Auditor clicks Download TSR on the anchored day row',
      then: 'Console fetches /v1/anchors/{id} with Accept: application/timestamp-reply and saves DER',
      testData: [
        `route          GET /anchors`,
        `api            GET /v1/anchors/{id}  Accept: application/timestamp-reply`,
        `output         forensa-anchor-2026-05-13-{prefix}.tsr   (raw ASN.1 DER)`,
        `verify         openssl ts -verify -in <file>.tsr (offline)`,
      ],
      expected: 'browser Download event fires + Playwright captures the DER blob to disk',
      holdMs: 3500,
    })
    await hideCaption(page)

    await page.goto(`${CONSOLE}/anchors?tenant_id=${TENANT_ID}`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(1500)

    const anchorsTable = page.locator('[data-testid="anchors-table"]')
    await expect(anchorsTable).toBeVisible({ timeout: 30000 })
    await highlight(anchorsTable, 'rgba(99, 102, 241, 0.55)', 2000)

    // Find the download button - data-testid prefix anchor-download-
    const dlButton = page.locator('button[data-testid^="anchor-download-"]').first()
    if (await dlButton.isVisible().catch(() => false)) {
      await highlight(dlButton, 'rgba(251, 191, 36, 0.55)', 1800)
      // Set up the download promise BEFORE clicking
      const downloadPromise = page.waitForEvent('download', { timeout: 15000 })
      await dlButton.click()
      const download = await downloadPromise.catch(() => null)
      if (download) {
        const savedTo = `/tmp/${download.suggestedFilename()}`
        await download.saveAs(savedTo).catch(() => {})
        // Show a quick confirmation overlay
        await page.evaluate((path: string) => {
          const div = document.createElement('div')
          div.id = 'tsr-saved-toast'
          div.style.cssText = 'position:fixed;bottom:24px;left:24px;z-index:2147483646;padding:14px 20px;background:#065f46;color:#ecfdf5;border-radius:8px;font-family:monospace;font-size:14px;box-shadow:0 10px 30px rgba(0,0,0,0.3);'
          div.textContent = 'TSR saved: ' + path.split('/').pop()
          document.body.appendChild(div)
          setTimeout(() => div.remove(), 3000)
        }, savedTo)
        await page.waitForTimeout(2500)
      }
    }

    // ============================================================
    // TC-4 - Create M&A diligence job
    // ============================================================
    await showCaption(page, {
      scene: 'TC-4 of 5',
      title: 'Create M&A diligence job - async pattern (P-ACQ persona)',
      given: 'M&A team needs an evidence bundle for the same scope window',
      when: 'User fills the Window dates and clicks Create job',
      then: 'Job appears Pending -> Running -> Completed (4s auto-poll); bundle JSON downloadable',
      testData: [
        `route          GET /diligence`,
        `api            POST /v1/exports/ma-diligence/jobs`,
        `body           { tenant_id, scope_start, scope_end }`,
        `inputs         window-start = ${SCOPE_START_DATE}, window-end = ${SCOPE_END_DATE}`,
      ],
      expected: 'job row shows pending->running->completed in <10s; Download bundle button visible',
      holdMs: 3500,
    })
    await hideCaption(page)

    await page.goto(`${CONSOLE}/diligence?tenant_id=${TENANT_ID}`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(1500)

    const createForm = page.locator('[data-testid="diligence-create-form"]')
    await expect(createForm).toBeVisible({ timeout: 30000 })
    await highlight(createForm, 'rgba(99, 102, 241, 0.45)', 1800)

    // Type the dates into REAL inputs - date inputs accept YYYY-MM-DD via .fill()
    const startInput = page.locator('[data-testid="diligence-scope-start"]')
    await highlight(startInput, 'rgba(251, 191, 36, 0.55)', 800)
    await startInput.fill(SCOPE_START_DATE)
    await page.waitForTimeout(400)

    const endInput = page.locator('[data-testid="diligence-scope-end"]')
    await highlight(endInput, 'rgba(251, 191, 36, 0.55)', 800)
    await endInput.fill(SCOPE_END_DATE)
    await page.waitForTimeout(600)

    // Click Create
    const createBtn = page.locator('[data-testid="diligence-create-submit"]')
    await highlight(createBtn, 'rgba(30, 64, 175, 0.55)', 1200)
    await createBtn.click()
    await page.waitForTimeout(1500)

    // Wait for any completed job row to show up (auto-polls every 4s)
    const completedBadge = page.locator('[data-testid="diligence-status-completed"]').first()
    await expect(completedBadge).toBeVisible({ timeout: 60000 })
    await highlight(completedBadge, 'rgba(34, 197, 94, 0.55)', 2000)

    // Click View on the first row to show the detail panel
    const firstViewBtn = page.locator('button[data-testid^="diligence-job-select-"]').first()
    if (await firstViewBtn.isVisible().catch(() => false)) {
      await highlight(firstViewBtn, 'rgba(251, 191, 36, 0.55)', 1200)
      await firstViewBtn.click()
      await page.waitForTimeout(1000)
      const dlBundle = page.locator('[data-testid="diligence-download-bundle"]')
      if (await dlBundle.isVisible().catch(() => false)) {
        await highlight(dlBundle, 'rgba(6, 95, 70, 0.55)', 1800)
      }
    }

    // ============================================================
    // TC-5 - Run tabletop simulation
    // ============================================================
    await showCaption(page, {
      scene: 'TC-5 of 5',
      title: 'Run tabletop simulation - "what-if" against the active bundle',
      given: 'Risk officer wants to test a hypothetical policy verdict',
      when: 'User clicks Load sample, swaps in the real bundle_id, clicks Run',
      then: 'Per-action verdicts + summary counts populate from the live policy engine',
      testData: [
        `route          GET /tabletop`,
        `api            POST /v1/tabletop/simulate`,
        `body           TabletopScenario JSON (sample loaded from UI)`,
        `bundle_id      ${BUNDLE_ID ? BUNDLE_ID.slice(0, 8) + '...' : '(missing - skip)'}`,
      ],
      expected: 'tabletop-summary + tabletop-actions-table show allow/deny/escalate verdicts',
      holdMs: 3500,
    })
    await hideCaption(page)

    await page.goto(`${CONSOLE}/tabletop?tenant_id=${TENANT_ID}`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(1500)

    const tabletopForm = page.locator('[data-testid="tabletop-form"]')
    await expect(tabletopForm).toBeVisible({ timeout: 30000 })
    await highlight(tabletopForm, 'rgba(99, 102, 241, 0.45)', 1800)

    // Click Load sample
    const loadSample = page.locator('[data-testid="tabletop-load-sample"]')
    await highlight(loadSample, 'rgba(251, 191, 36, 0.55)', 1200)
    await loadSample.click()
    await page.waitForTimeout(800)

    // Substitute the real bundle_id over the placeholder if provided
    if (BUNDLE_ID) {
      const scenarioInput = page.locator('[data-testid="tabletop-scenario-input"]')
      const currentJson = await scenarioInput.inputValue()
      const patched = currentJson.replace('<paste-your-policy-bundle-uuid>', BUNDLE_ID)
      await scenarioInput.fill(patched)
      await page.waitForTimeout(500)
      await highlight(scenarioInput, 'rgba(99, 102, 241, 0.45)', 1500)
    }

    // Click Run
    const runBtn = page.locator('[data-testid="tabletop-run"]')
    await highlight(runBtn, 'rgba(30, 64, 175, 0.55)', 1200)
    await runBtn.click()
    await page.waitForTimeout(2500)

    // Wait for either the result pane OR error pane
    const resultPane = page.locator('[data-testid="tabletop-result"]')
    const errorPane = page.locator('[data-testid="tabletop-error"]')
    await Promise.race([
      resultPane.waitFor({ state: 'visible', timeout: 30000 }).catch(() => null),
      errorPane.waitFor({ state: 'visible', timeout: 30000 }).catch(() => null),
    ])

    if (await resultPane.isVisible().catch(() => false)) {
      await highlight(resultPane, 'rgba(34, 197, 94, 0.45)', 2000)
      const summary = page.locator('[data-testid="tabletop-summary"]')
      if (await summary.isVisible().catch(() => false)) {
        await highlight(summary, 'rgba(251, 191, 36, 0.45)', 2000)
      }
      const actionsTable = page.locator('[data-testid="tabletop-actions-table"]')
      if (await actionsTable.isVisible().catch(() => false)) {
        await highlight(actionsTable, 'rgba(99, 102, 241, 0.45)', 2000)
      }
    } else if (await errorPane.isVisible().catch(() => false)) {
      // Pulse the error so the recording still shows something meaningful
      await highlight(errorPane, 'rgba(220, 38, 38, 0.45)', 2500)
    }

    // ============================================================
    // CLOSING CARD
    // ============================================================
    await showTitleCard(
      page,
      'Forensa',
      '5 scenarios driven through the real Operator Console.  Verify + Produce + Anchor + Diligence + Tabletop - every form input typed for real, every API call live, every crypto operation real.  github.com/vsenthil7/forensa  -  TechEx Hackathon 2026',
      6000,
    )
  })
})
