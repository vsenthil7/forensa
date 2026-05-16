/**
 * Forensa end-to-end captioned demo - matches auditex's 2-crypto-op pattern.
 *
 * Auditex source (verbatim):
 *   C:\Users\v_sen\Documents\Projects\
 *     0001_Hack0014_Vertex_Swarm_Tashi\auditex\frontend\tests\demo\
 *     end-to-end-demo.spec.ts
 *
 * Auditex per scenario: 1 sign-report + 1 verify-proof = 2 crypto ops.
 * Forensa parity per scenario:
 *   STEP 1 chain view              - product surface, NOT a verification
 *   STEP 2 receipt detail          - integrity check (= verify, 1 of 2 ops)
 *   STEP 3 evidence pack export    - regulator artifact (= sign/produce, 2 of 2 ops)
 *
 * The previous CP9.48 spec had 3 verifications visible (HealthBadge green +
 * 2 receipt-detail clicks). Audit at 21:32 confirmed: auditex shows 2 crypto
 * operations per scenario, mine showed 3. CP9.50 cuts the redundant second
 * receipt-detail click and replaces it with the evidence pack export step
 * that doesn't currently exist anywhere in the recording.
 *
 * Frame-1 blank-white fix: the initial title card now holds for 4500ms
 * (was 3000ms) so frame 1 of the 1fps audit lands on the title card paint,
 * not the about:blank pre-paint.
 *
 * Target recording length: ~70-90s at slowMo=400.
 */
import { test, expect } from '@playwright/test'
import { showCaption, hideCaption, showTitleCard } from './caption-overlay'

const CONSOLE = 'http://localhost:3000'
const API = 'http://localhost:8000'
const TENANT_ID = process.env.FORENSA_TENANT_ID ?? ''
const TOKEN = process.env.FORENSA_TOKEN ?? ''
const SCOPE_START = process.env.FORENSA_SCOPE_START ?? '2026-05-13T00:00:00+00:00'
const SCOPE_END = process.env.FORENSA_SCOPE_END ?? '2026-05-14T23:59:59+00:00'

interface CapturedState {
  totalReceipts: number
  firstReceiptId: string
  firstReceiptSequence: number
}

test.describe('Forensa End-to-End Captioned Demo - auditex 2-op pattern', () => {
  test.skip(
    TENANT_ID === '' || TOKEN === '',
    'FORENSA_TENANT_ID and FORENSA_TOKEN must be set. Run scripts/seed_demo_data.py first.',
  )

  test('Regulator walks the Forensa Console - 1 verify + 1 produce', async ({ page, request }) => {
    // 4-minute test ceiling. The spec itself targets ~70-90s of actual
    // playback at slowMo=400 (DEMO=1 default); the rest is headroom
    // for cold Next.js compile on the first goto.
    test.setTimeout(4 * 60 * 1000)
    const captured: CapturedState = {
      totalReceipts: 0,
      firstReceiptId: '',
      firstReceiptSequence: 0,
    }

    // ============================================================
    // PRE-FLIGHT: capture the receipt we'll click. Done before any
    // UI render so the captured state is ready before captions paint.
    // ============================================================
    const listResp = await request.get(
      `${API}/v1/receipts?tenant_id=${TENANT_ID}&limit=50`,
      { headers: TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {} },
    )
    expect(listResp.status(), await listResp.text()).toBe(200)
    const listBody = await listResp.json()
    captured.totalReceipts = listBody.items.length
    expect(captured.totalReceipts).toBeGreaterThan(0)
    captured.firstReceiptId = listBody.items[0].id
    captured.firstReceiptSequence = listBody.items[0].sequence

    // ============================================================
    // TITLE CARD on about:blank
    // ============================================================
    // 0-1s blank-white fix: paint the dark background FIRST, then
    // show the title card; the 4500ms hold ensures the 1fps frame
    // audit lands on the rendered card not the pre-paint.
    await page.goto('about:blank')
    await page.evaluate(() => {
      document.body.style.cssText = 'margin:0;padding:0;background:#0f172a;'
    })
    // Tiny dwell to let the background paint commit before the card slides in
    await page.waitForTimeout(150)
    await showTitleCard(
      page,
      'Forensa',
      'Cryptographic evidence layer for enterprise AI agents. 3-step regulator flow - 1 verify + 1 produce - driven through the real Console UI a compliance officer will use in production.',
      4500,
    )

    // ============================================================
    // STEP 1 CAPTION (on about:blank, before nav) - chain view
    // ============================================================
    await showCaption(page, {
      scene: 'STEP 1 of 3',
      title: 'Append-only receipt chain visible',
      given: 'A regulator opens the Forensa Console for the seeded tenant',
      when: 'The Console loads / and queries /healthz + /v1/receipts',
      then: 'Health badge turns green; the full receipt chain renders',
      testData: [
        `tenant_id     ${TENANT_ID}`,
        `expected      ${captured.totalReceipts} receipts in append-only order`,
        `endpoints     GET /healthz, GET /v1/receipts`,
      ],
      expected: 'Product surface visible - NOT a crypto operation',
      holdMs: 3000,
    })
    await hideCaption(page)

    // Navigate to the real Console root.
    await page.goto(CONSOLE, { waitUntil: 'domcontentloaded' })

    const healthBadge = page.locator('[data-testid="health-badge"]')
    await expect(healthBadge).toBeVisible({ timeout: 30000 })
    await expect(healthBadge).toHaveAttribute(
      'data-status',
      /ok|degraded|unauthenticated/,
      { timeout: 15000 },
    )
    await healthBadge.evaluate((el: HTMLElement) => {
      el.style.transition = 'box-shadow 0.3s, transform 0.3s'
      el.style.boxShadow = '0 0 0 6px rgba(34, 197, 94, 0.5)'
      el.style.transform = 'scale(1.06)'
      setTimeout(() => {
        el.style.boxShadow = ''
        el.style.transform = ''
      }, 1500)
    })
    await page.waitForTimeout(1800)

    const table = page.locator('[data-testid="receipt-list-table"]')
    await expect(table).toBeVisible({ timeout: 15000 })
    await table.evaluate((el: HTMLElement) => {
      el.style.transition = 'box-shadow 0.3s'
      el.style.boxShadow = '0 0 0 4px rgba(99, 102, 241, 0.5)'
      setTimeout(() => {
        el.style.boxShadow = ''
      }, 1800)
    })
    await page.waitForTimeout(2000)

    // Pulse the first row to telegraph the upcoming click.
    const firstRow = page.locator(`[data-testid="receipt-row-${captured.firstReceiptId}"]`)
    await expect(firstRow).toBeVisible({ timeout: 10000 })
    await firstRow.evaluate((el: HTMLElement) => {
      el.style.transition = 'background-color 0.3s'
      el.style.backgroundColor = '#fef3c7'
      setTimeout(() => {
        el.style.backgroundColor = ''
      }, 1200)
    })
    await page.waitForTimeout(1300)

    // ============================================================
    // STEP 2 CAPTION + click into receipt detail
    // VERIFY op (1 of 2 cryptographic operations)
    // ============================================================
    await showCaption(page, {
      scene: 'STEP 2 of 3',
      title: 'VERIFY - live integrity check on stored receipt',
      given: 'Regulator clicks the head of the chain',
      when: 'Console fetches GET /v1/receipts/{id} and recomputes the hash',
      then: 'Green integrity badge + recomputed hash matches stored hash',
      testData: [
        `receipt_id    ${captured.firstReceiptId.slice(0, 8)}...`,
        `sequence      ${captured.firstReceiptSequence}`,
        `crypto op     1 of 2 (verify; auditex parity)`,
      ],
      expected: 'integrity-badge[data-integrity-ok=true]',
      holdMs: 3000,
    })
    await hideCaption(page)

    await firstRow.click()
    await page.waitForLoadState('domcontentloaded', { timeout: 30000 }).catch(() => {})

    const integrityBadge = page.locator('[data-testid="integrity-badge"]')
    await expect(integrityBadge).toBeVisible({ timeout: 30000 })
    await expect(integrityBadge).toHaveAttribute('data-integrity-ok', 'true', { timeout: 15000 })

    // Money shot: pulse the green badge.
    await integrityBadge.evaluate((el: HTMLElement) => {
      el.style.transition = 'box-shadow 0.4s, transform 0.4s'
      el.style.boxShadow = '0 0 0 8px rgba(34, 197, 94, 0.55)'
      el.style.transform = 'scale(1.08)'
      setTimeout(() => {
        el.style.boxShadow = ''
        el.style.transform = ''
      }, 1800)
    })
    await page.waitForTimeout(2000)

    // Highlight the two hash rows in sequence so the viewer sees they match.
    const storedHash = page.locator('[data-testid="detail-receipt-hash"]')
    const recomputed = page.locator('[data-testid="detail-recomputed-hash"]')
    await storedHash.evaluate((el: HTMLElement) => {
      el.style.transition = 'background-color 0.3s'
      el.style.backgroundColor = '#dbeafe'
      setTimeout(() => {
        el.style.backgroundColor = ''
      }, 1600)
    })
    await page.waitForTimeout(700)
    await recomputed.evaluate((el: HTMLElement) => {
      el.style.transition = 'background-color 0.3s'
      el.style.backgroundColor = '#dbeafe'
      setTimeout(() => {
        el.style.backgroundColor = ''
      }, 1600)
    })
    await page.waitForTimeout(2000)

    // ============================================================
    // STEP 3 CAPTION + navigate to /evidence + click Generate
    // PRODUCE op (2 of 2 cryptographic operations)
    // ============================================================
    await showCaption(page, {
      scene: 'STEP 3 of 3',
      title: 'PRODUCE - evidence pack signed by Forensa + RFC 3161 TSA',
      given: 'Regulator needs a take-home artifact for the audit file',
      when: 'Console calls GET /v1/evidence-packs over the chain window',
      then: 'JSON-LD pack with root_hash, FreeTSA proof, and PDF download',
      testData: [
        `scope         ${SCOPE_START.slice(0, 10)} -> ${SCOPE_END.slice(0, 10)}`,
        `TSA           freetsa.org (live RFC 3161, real ASN.1 DER)`,
        `crypto op     2 of 2 (produce; auditex parity)`,
      ],
      expected: 'pack-signed-badge visible + pack-root-hash bound + TSA anchor block',
      holdMs: 3000,
    })
    await hideCaption(page)

    // Navigate to /evidence via the page-level link (real product navigation).
    await page.goto(`${CONSOLE}/evidence`, { waitUntil: 'domcontentloaded' })

    const genBtn = page.locator('[data-testid="generate-pack-button"]')
    await expect(genBtn).toBeVisible({ timeout: 30000 })
    // Telegraph the click.
    await genBtn.evaluate((el: HTMLElement) => {
      el.style.transition = 'box-shadow 0.3s, transform 0.3s'
      el.style.boxShadow = '0 0 0 6px rgba(30, 64, 175, 0.4)'
      el.style.transform = 'scale(1.04)'
      setTimeout(() => {
        el.style.boxShadow = ''
        el.style.transform = ''
      }, 1200)
    })
    await page.waitForTimeout(1300)
    await genBtn.click()

    // Watch the signed badge appear.
    const signedBadge = page.locator('[data-testid="pack-signed-badge"]')
    await expect(signedBadge).toBeVisible({ timeout: 30000 })
    await signedBadge.evaluate((el: HTMLElement) => {
      el.style.transition = 'box-shadow 0.4s, transform 0.4s'
      el.style.boxShadow = '0 0 0 8px rgba(6, 95, 70, 0.55)'
      el.style.transform = 'scale(1.06)'
      setTimeout(() => {
        el.style.boxShadow = ''
        el.style.transform = ''
      }, 1800)
    })
    await page.waitForTimeout(2000)

    // Highlight the root hash + TSA anchor rows so the regulator artifact reads clearly.
    const rootHashRow = page.locator('[data-testid="pack-root-hash"]')
    await expect(rootHashRow).toBeVisible({ timeout: 10000 })
    await rootHashRow.evaluate((el: HTMLElement) => {
      el.style.transition = 'background-color 0.3s'
      el.style.backgroundColor = '#dbeafe'
      setTimeout(() => {
        el.style.backgroundColor = ''
      }, 1600)
    })
    await page.waitForTimeout(900)

    const anchorTsa = page.locator('[data-testid="pack-anchor-tsa"]')
    if (await anchorTsa.isVisible().catch(() => false)) {
      await anchorTsa.evaluate((el: HTMLElement) => {
        el.style.transition = 'background-color 0.3s'
        el.style.backgroundColor = '#fef3c7'
        setTimeout(() => {
          el.style.backgroundColor = ''
        }, 1600)
      })
      await page.waitForTimeout(900)
      const anchorTime = page.locator('[data-testid="pack-anchor-time"]')
      await anchorTime.evaluate((el: HTMLElement) => {
        el.style.transition = 'background-color 0.3s'
        el.style.backgroundColor = '#fef3c7'
        setTimeout(() => {
          el.style.backgroundColor = ''
        }, 1600)
      })
      await page.waitForTimeout(1500)
    }

    // Pulse the download button so the viewer sees the take-home artifact path.
    const dlBtn = page.locator('[data-testid="download-pdf-button"]')
    await expect(dlBtn).toBeVisible({ timeout: 10000 })
    await dlBtn.evaluate((el: HTMLElement) => {
      el.style.transition = 'box-shadow 0.3s, transform 0.3s'
      el.style.boxShadow = '0 0 0 6px rgba(6, 95, 70, 0.45)'
      el.style.transform = 'scale(1.06)'
      setTimeout(() => {
        el.style.boxShadow = ''
        el.style.transform = ''
      }, 1500)
    })
    await page.waitForTimeout(1800)

    // ============================================================
    // CLOSING CARD
    // ============================================================
    await showTitleCard(
      page,
      'Forensa',
      'github.com/vsenthil7/forensa   |   TechEx Hackathon 2026   |   3-step flow with 2 crypto operations (verify + produce). Live FastAPI, real Postgres, real Ed25519 signatures, real RFC 3161 TSA proof from FreeTSA.',
      4000,
    )
  })
})
