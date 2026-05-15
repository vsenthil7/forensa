/**
 * Forensa end-to-end captioned demo - 4-scenario regulator flow.
 *
 * Ported from auditex/frontend/tests/demo/end-to-end-demo.spec.ts
 * (sibling hackathon project). Same captioned-BDD architecture:
 * title card on about:blank -> shutter -> per-scenario caption ->
 * action -> next caption. The only difference is Forensa has no
 * UI to drive (yet), so each "action" is a Playwright request.get()
 * against the FastAPI, with the response payload rendered inline
 * on a styled "regulator console" page so the viewer SEES the
 * evidence the API returned.
 *
 * Scenarios mirror tools/demo.sh's 4-step flow:
 *   1. GET evidence-pack (JSON-LD)        - the regulator's primary artifact
 *   2. GET evidence-pack (PDF wire form)  - the human-readable copy
 *   3. GET anchor (raw RFC 3161 TSR DER)  - the math the regulator runs offline
 *   4. Chain integrity sanity             - root_hash stability across requests
 *
 * Modes:
 *   DEMO=1 - slow-motion + visible cursor + captions + video on
 *   default - normal CI run, no captions, captures video only on failure
 *
 * Skip semantics: if FORENSA_TENANT_ID + FORENSA_TOKEN are missing
 * (no seed run yet), the entire scenario list is skipped with a clear
 * reason. The spec does NOT auto-seed - seeding TRUNCATES the demo
 * DB and we don't want playwright to wipe a dev's working state.
 */
import { test, expect } from '@playwright/test'
import {
  showCaption,
  hideCaption,
  showTitleCard,
  READ_SHORT,
  READ_LONG,
  ACTION_PAUSE,
} from './caption-overlay'

const API = process.env.FORENSA_API_URL ?? 'http://127.0.0.1:8000'
const TENANT_ID = process.env.FORENSA_TENANT_ID ?? ''
const TOKEN = process.env.FORENSA_TOKEN ?? ''
const SCOPE_START = process.env.FORENSA_SCOPE_START ?? '2026-05-13T00:00:00+00:00'
const SCOPE_END = process.env.FORENSA_SCOPE_END ?? '2026-05-14T23:59:59+00:00'
const IS_DEMO = process.env.DEMO === '1'

const seedAvailable = TENANT_ID.length > 0 && TOKEN.length > 0

interface Scenario {
  scene: string
  title: string
  given: string
  when: string
  then: string
  expected: string
  testData: string[]
  /** Executed inside the scenario. Returns a short payload string that
   *  the regulator console renders as the visible evidence on screen. */
  action: (
    request: import('@playwright/test').APIRequestContext,
    captured: Record<string, string>,
  ) => Promise<{ summary: string; details: string[] }>
}

const SCENARIOS: Scenario[] = [
  {
    scene: 'STEP 1 of 4',
    title: 'Fetch evidence pack (JSON-LD)',
    given: 'A regulator with a tenant_id and a bearer token',
    when: 'GET /v1/evidence-packs?tenant_id=...&scope_start=...&scope_end=...',
    then: 'Server returns JSON-LD: header + receipts + anchor + chain root_hash',
    expected: '200 OK with anchor.status=anchored and a 64-char-hex root_hash',
    testData: [
      `tenant_id: ${TENANT_ID.slice(0, 12)}...`,
      `scope: ${SCOPE_START.slice(0, 10)} -> ${SCOPE_END.slice(0, 10)}`,
      'Authorization: Bearer <HMAC-signed token>',
    ],
    action: async (request, captured) => {
      const url = `${API}/v1/evidence-packs?tenant_id=${TENANT_ID}&scope_start=${encodeURIComponent(SCOPE_START)}&scope_end=${encodeURIComponent(SCOPE_END)}`
      const response = await request.get(url, {
        headers: { Authorization: `Bearer ${TOKEN}` },
      })
      expect(response.status(), await response.text()).toBe(200)
      const body = await response.json()
      expect(body.root_hash).toMatch(/^[0-9a-f]{64}$/)
      expect(body.anchor.anchor_id).toMatch(/^[0-9a-f-]{36}$/)
      captured.root_hash = body.root_hash
      captured.anchor_id = body.anchor.anchor_id
      // Capture the chain of receipt_hashes for Step 4's stability check.
      // We store as comma-joined string because the captured object is
      // typed Record<string, string> (the captioned overlay only needs
      // primitives for inline rendering).
      const receiptHashes: string[] = body.receipts.map((r: { receipt_hash: string }) => r.receipt_hash)
      captured.receipt_hashes = receiptHashes.join(',')
      return {
        summary: `200 OK - ${body.header.receipt_count} receipts, anchor ${body.anchor.status}`,
        details: [
          `root_hash      ${body.root_hash}`,
          `anchor_id      ${body.anchor.anchor_id}`,
          `anchor_status  ${body.anchor.status}`,
          `receipt_count  ${body.header.receipt_count}`,
          `tenant_id      ${body.header.tenant_id}`,
        ],
      }
    },
  },
  {
    scene: 'STEP 2 of 4',
    title: 'Pull the PDF wire form',
    given: 'The JSON-LD body the regulator just received',
    when: 'GET the same URL with Accept: application/pdf',
    then: 'Server renders the pack as a human-readable PDF with the same root_hash',
    expected: 'application/pdf body starting with the %PDF magic header',
    testData: [
      'Accept: application/pdf',
      'Same tenant_id + scope as Step 1',
      'Magic bytes: 0x25 0x50 0x44 0x46 ("%PDF")',
    ],
    action: async (request) => {
      const url = `${API}/v1/evidence-packs?tenant_id=${TENANT_ID}&scope_start=${encodeURIComponent(SCOPE_START)}&scope_end=${encodeURIComponent(SCOPE_END)}`
      const response = await request.get(url, {
        headers: {
          Authorization: `Bearer ${TOKEN}`,
          Accept: 'application/pdf',
        },
      })
      expect(response.status()).toBe(200)
      expect(response.headers()['content-type']).toContain('application/pdf')
      const buffer = await response.body()
      expect(buffer.length).toBeGreaterThan(100)
      expect(buffer.subarray(0, 4).toString('ascii')).toBe('%PDF')
      const sizeKb = (buffer.length / 1024).toFixed(1)
      return {
        summary: `200 OK - ${sizeKb} KB PDF wire form`,
        details: [
          `content-type  application/pdf`,
          `body size     ${buffer.length} bytes (${sizeKb} KB)`,
          `magic bytes   ${Array.from(buffer.subarray(0, 8))
            .map((b) => '0x' + b.toString(16).padStart(2, '0'))
            .join(' ')}`,
          `magic ascii   "${buffer.subarray(0, 4).toString('ascii')}"`,
        ],
      }
    },
  },
  {
    scene: 'STEP 3 of 4',
    title: 'Fetch raw RFC 3161 TSR DER bytes',
    given: 'The anchor_id captured in Step 1',
    when: 'GET /v1/anchors/{anchor_id} with Accept: application/timestamp-reply',
    then: 'Server returns raw DER bytes (ASN.1 SEQUENCE, first byte = 0x30)',
    expected: 'Content-Type application/timestamp-reply + DER body + filename header',
    testData: [
      'Accept: application/timestamp-reply',
      'Content-Disposition: attachment; filename="anchor-<id>.tsr"',
      'X-Forensa-Anchor-Root-Hash: <same 64-hex root_hash from Step 1>',
    ],
    action: async (request, captured) => {
      const url = `${API}/v1/anchors/${captured.anchor_id}`
      const response = await request.get(url, {
        headers: {
          Authorization: `Bearer ${TOKEN}`,
          Accept: 'application/timestamp-reply',
        },
      })
      // Deferred anchors (no TSR bytes) -> 406. Mock TSAs may use a JSON
      // placeholder instead of true DER, which still surfaces as 200.
      expect([200, 406]).toContain(response.status())
      if (response.status() === 406) {
        return {
          summary: '406 Not Acceptable - anchor is deferred (no TSR bytes yet)',
          details: [
            `anchor_id      ${captured.anchor_id}`,
            'status         deferred',
            'reason         TSA did not return RFC 3161 bytes; pack still verifies via root_hash',
          ],
        }
      }
      expect(response.headers()['content-type']).toBe('application/timestamp-reply')
      const buffer = await response.body()
      expect(buffer.length).toBeGreaterThan(0)
      const headerRootHash = response.headers()['x-forensa-anchor-root-hash']
      expect(headerRootHash).toMatch(/^[0-9a-f]{64}$/)
      const dispo = response.headers()['content-disposition']
      expect(dispo).toContain(`filename="anchor-${captured.anchor_id}.tsr"`)
      // ASN.1 SEQUENCE tag is 0x30 for true RFC 3161 DER. Mock TSA returns
      // JSON, so we accept either: report what we got rather than failing.
      const firstByte = buffer[0]
      const isDer = firstByte === 0x30
      return {
        summary: `200 OK - ${buffer.length} bytes ${isDer ? 'RFC 3161 DER' : 'mock-TSA payload'}`,
        details: [
          `content-type      application/timestamp-reply`,
          `body size         ${buffer.length} bytes`,
          `first byte (hex)  0x${firstByte.toString(16).padStart(2, '0')} ${
            isDer ? '(ASN.1 SEQUENCE - real RFC 3161)' : '(mock-TSA JSON placeholder)'
          }`,
          `root-hash header  ${headerRootHash}`,
          `filename          anchor-${captured.anchor_id}.tsr`,
        ],
      }
    },
  },
  {
    scene: 'STEP 4 of 4',
    title: 'Chain integrity - receipts + anchor are stable',
    given: 'The receipt_hashes and anchor_id returned in Step 1',
    when: 'Re-fetch the evidence pack',
    then: 'Receipt chain + anchor_id are byte-for-byte identical',
    expected: 'Append-only ledger: same scope -> same receipt_hashes + same anchor, always',
    testData: [
      'Re-fetch with identical query params',
      'pack.root_hash includes a fresh generated_at -> intentionally differs per request',
      'The stable surface is receipts[].receipt_hash + anchor.anchor_id',
    ],
    action: async (request, captured) => {
      const url = `${API}/v1/evidence-packs?tenant_id=${TENANT_ID}&scope_start=${encodeURIComponent(SCOPE_START)}&scope_end=${encodeURIComponent(SCOPE_END)}`
      const response = await request.get(url, {
        headers: { Authorization: `Bearer ${TOKEN}` },
      })
      expect(response.status()).toBe(200)
      const body = await response.json()
      // The pack's root_hash is computed over the entire pack including a
      // fresh generated_at timestamp, so it intentionally differs across
      // requests (each pack is uniquely fingerprinted for replay-detection).
      // The stable integrity surface is the chain of receipt_hashes plus
      // the anchor_id. We assert those two are identical across requests.
      const stepOneReceipts: string[] = (captured.receipt_hashes ?? '').split(',').filter(Boolean)
      const stepFourReceipts: string[] = body.receipts.map((r: { receipt_hash: string }) => r.receipt_hash)
      expect(stepFourReceipts).toEqual(stepOneReceipts)
      expect(body.anchor.anchor_id).toBe(captured.anchor_id)
      return {
        summary: `200 OK - ${stepFourReceipts.length} receipts + anchor_id match Step 1 byte-for-byte`,
        details: [
          `step 1 receipts  ${stepOneReceipts.length} hashes`,
          `step 4 receipts  ${stepFourReceipts.length} hashes`,
          `chain match      ${JSON.stringify(stepFourReceipts) === JSON.stringify(stepOneReceipts)}`,
          `anchor_id match  ${body.anchor.anchor_id === captured.anchor_id}`,
          `interpretation   chain is append-only; receipts + anchor are stable across requests`,
        ],
      }
    },
  },
]

/**
 * Render the API response on the regulator console page so the recorded
 * video shows the evidence the API returned. Auditex had a real UI to
 * drive; Forensa is API-only, so we paint the evidence onto a styled
 * console-looking surface inside about:blank between captions.
 */
async function renderConsolePayload(
  page: import('@playwright/test').Page,
  scenario: Scenario,
  result: { summary: string; details: string[] },
): Promise<void> {
  await page.evaluate(({ title, summary, details }) => {
    const existing = document.getElementById('forensa-console')
    if (existing) existing.remove()
    const div = document.createElement('div')
    div.id = 'forensa-console'
    div.innerHTML = `
      <style>
        body { margin: 0; padding: 0; background: #0f172a; }
        #forensa-console {
          position: fixed; inset: 0; z-index: 2147483645;
          background: #0f172a; color: #e0e7ff;
          font-family: -apple-system, Segoe UI, Roboto, sans-serif;
          display: flex; flex-direction: column;
          padding: 60px 70px; box-sizing: border-box;
        }
        #forensa-console .brand { color: #a5b4fc; font-size: 14px; letter-spacing: 5px; text-transform: uppercase; font-weight: 700; margin-bottom: 10px; }
        #forensa-console .title { font-size: 38px; font-weight: 800; color: #fefce8; margin-bottom: 18px; }
        #forensa-console .summary { display: inline-block; padding: 10px 22px; background: #166534; color: #dcfce7; border-radius: 10px; font-size: 20px; font-weight: 700; margin-bottom: 26px; max-width: max-content; }
        #forensa-console pre { background: #1e1b4b; color: #fefce8; padding: 24px 28px; border-radius: 12px; font-family: "JetBrains Mono", Consolas, Menlo, monospace; font-size: 18px; line-height: 1.55; margin: 0; white-space: pre-wrap; word-break: break-all; flex: 1; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.4); }
        #forensa-console pre .k { color: #a5b4fc; }
        #forensa-console pre .v { color: #fefce8; }
        #forensa-console .footer { color: #6366f1; font-size: 14px; letter-spacing: 3px; text-transform: uppercase; margin-top: 18px; font-weight: 600; }
      </style>
      <div class="brand">Forensa &middot; Regulator Console</div>
      <div class="title">${title}</div>
      <div class="summary">${summary}</div>
      <pre>${details
        .map((line) => {
          const idx = line.indexOf('  ')
          if (idx > 0) {
            return `<span class="k">${line.slice(0, idx)}</span>${line.slice(idx)}`
          }
          return line
        })
        .join('\n')}</pre>
      <div class="footer">github.com/vsenthil7/forensa</div>
    `
    document.body.appendChild(div)
  }, { title: scenario.title, summary: result.summary, details: result.details })
}

test.describe('Forensa Captioned Demo - regulator verification flow', () => {
  test.skip(
    !seedAvailable,
    'FORENSA_TENANT_ID and FORENSA_TOKEN must be set; run scripts/seed_demo_data.py first',
  )

  test('4-step regulator flow: pack -> PDF -> TSR -> chain integrity', async ({ page, request }) => {
    test.setTimeout(30 * 60 * 1000) // 30 min - generous for slow-mo recording

    // Title card on about:blank BEFORE we go anywhere else. No app flash.
    // (Forensa has no app UI yet anyway - the whole demo runs on
    // about:blank surfaces - but this same pattern is what we'll use
    // when the console lands.)
    await page.goto('about:blank')
    await page.evaluate(() => {
      document.body.style.cssText = 'margin:0;padding:0;background:#0f172a;'
    })
    await showTitleCard(
      page,
      'Forensa',
      'Tamper-evident audit ledger for AI agents. ' +
        '4-step regulator verification flow: evidence pack -> PDF wire form -> RFC 3161 timestamp -> Merkle chain integrity. ' +
        'DoraHacks BUIDL Hack0018.',
      IS_DEMO ? 3500 : 600,
    )

    // Captured between scenarios so step 3 can reference step 1's anchor_id
    // and step 4 can reference step 1's root_hash.
    const captured: Record<string, string> = {}

    for (let i = 0; i < SCENARIOS.length; i++) {
      const sc = SCENARIOS[i]

      // Caption first (auditex pattern: caption -> action -> next caption).
      await showCaption(page, {
        scene: sc.scene,
        title: sc.title,
        given: sc.given,
        when: sc.when,
        then: sc.then,
        testData: sc.testData,
        expected: sc.expected,
        holdMs: IS_DEMO ? READ_LONG : 200,
      })
      await hideCaption(page)

      // Execute the actual API call.
      const result = await sc.action(request, captured)

      // Render the result on the "regulator console" surface so the
      // recorded video shows the evidence, not just black.
      await renderConsolePayload(page, sc, result)

      // Dwell so the viewer can read the response.
      await page.waitForTimeout(IS_DEMO ? READ_LONG : 100)

      // Smooth transition into the next scenario's caption.
      if (i < SCENARIOS.length - 1) {
        await page.waitForTimeout(IS_DEMO ? ACTION_PAUSE : 50)
      }
    }

    // End cap.
    await showTitleCard(
      page,
      'Forensa',
      'github.com/vsenthil7/forensa  |  Hack0018  |  ' +
        'Every receipt dual-signed, every day TSA-anchored, every pack regulator-verifiable offline.',
      IS_DEMO ? 3500 : 400,
    )
  })
})
