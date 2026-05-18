/**
 * Forensa 8-screen walkthrough demo — comprehensive captioned tour.
 *
 * CP9.62 — replaces the legacy 3-step demo (chain → verify → produce) with
 * a full 9-screen tour matching the MendoraCI walkthrough pattern.
 *
 * Two passes:
 *   PASS 1 — Empty state tour. Each screen shown with explanatory BDD caption
 *            (scene, title, Given/When/Then, Test Data, Expected Outcome) and
 *            then 2s on the empty screen so the viewer sees the surface
 *            structure without data noise.
 *   PASS 2 — Loaded state walkthrough. Same 9 screens, but with seeded
 *            data and short captions (~1500ms hold) for a fast tour.
 *
 * Screens (9 total):
 *   1. /             persona landing
 *   2. /receipts     timeline list
 *   3. /receipts/[id] receipt detail (Summary / Proof / Raw tabs)
 *   4. /evidence     evidence pack (produce regulator artifact)
 *   5. /anchors      RFC 3161 daily anchors
 *   6. /diligence    M&A diligence workspace
 *   7. /narratives   LLM narrative viewer
 *   8. /tabletop     scenario simulator
 *   9. /status       ops metrics dashboard
 *
 * Between PASS 1 and PASS 2 the spec calls the seed-trigger API endpoint
 * (or in standalone mode reads pre-seeded env vars; FORENSA_TENANT_ID and
 * FORENSA_TOKEN must already point at a seeded tenant by PASS 2).
 *
 * Spec reads:
 *   FORENSA_CONSOLE_URL    default http://localhost:3001 (compose stack)
 *   FORENSA_API_URL        default http://localhost:8000
 *   FORENSA_TENANT_ID      required for PASS 2 navigation
 *   FORENSA_TOKEN          required for PASS 2 navigation
 */

import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import { showCaption, hideCaption, showTitleCard } from './caption-overlay'

const CONSOLE = process.env.FORENSA_CONSOLE_URL ?? 'http://localhost:3001'
const API = process.env.FORENSA_API_URL ?? 'http://localhost:8000'
const TENANT_ID = process.env.FORENSA_TENANT_ID ?? ''
const TOKEN = process.env.FORENSA_TOKEN ?? ''
const SCOPE_START = process.env.FORENSA_SCOPE_START ?? '2026-05-13T00:00:00+00:00'
const SCOPE_END = process.env.FORENSA_SCOPE_END ?? '2026-05-14T23:59:59+00:00'
const SKIP_PASS_1 = process.env.FORENSA_SKIP_PASS_1 === '1'

// Pass 1 (empty) holds for ~3.5s per caption + 2s on the screen.
// Pass 2 (loaded) holds for ~1.6s per caption + 1.5s on the screen.
const HOLD_EMPTY_CAPTION = 3500
const HOLD_EMPTY_SCREEN = 2000
const HOLD_LOADED_CAPTION = 1600
const HOLD_LOADED_SCREEN = 1500

// Inject a small fade so transitions don't feel jarring.
async function fadeOutAll(page: Page) {
  await page.evaluate(() => {
    document.body.style.transition = 'opacity 0.25s'
    document.body.style.opacity = '1'
  })
}

// Pulse helper — give a visible orange-tinted glow + scale-up to telegraph
// where the viewer's eye should go.
async function pulse(page: Page, selector: string) {
  const el = page.locator(selector).first()
  if (!(await el.isVisible().catch(() => false))) return
  await el.evaluate((node: HTMLElement) => {
    node.style.transition = 'box-shadow 0.4s, transform 0.4s'
    node.style.boxShadow = '0 0 0 8px rgba(251, 191, 36, 0.55)'
    node.style.transform = 'scale(1.04)'
    setTimeout(() => {
      node.style.boxShadow = ''
      node.style.transform = ''
    }, 1500)
  })
  await page.waitForTimeout(1200)
}

test.describe('Forensa 9-Screen Walkthrough — empty-state tour + loaded-state fast pass', () => {
  test('regulator walks every Forensa Console surface, twice', async ({ page }) => {
    // 10-minute test ceiling - the spec produces ~3-4min of playback
    // at slowMo=400, plus seed + cold-compile headroom.
    test.setTimeout(10 * 60 * 1000)

    // ============================================================
    // OPENING TITLE CARD
    // ============================================================
    await page.goto('about:blank')
    await page.evaluate(() => {
      document.body.style.cssText = 'margin:0;padding:0;background:#0f172a;'
    })
    await page.waitForTimeout(200)
    await showTitleCard(
      page,
      'Forensa',
      'Cryptographic evidence layer for enterprise AI agents.  Comprehensive 9-screen Operator Console walkthrough — empty state first (showing each surface\'s purpose), then loaded with real data (showing the flow end-to-end).',
      5000,
    )

    // ============================================================
    // PASS 1 - EMPTY STATE TOUR (skippable via FORENSA_SKIP_PASS_1=1)
    // ============================================================
    if (!SKIP_PASS_1) {
    await page.goto('about:blank')
    await page.evaluate(() => {
      document.body.style.cssText = 'margin:0;padding:0;background:#0f172a;'
    })
    await page.waitForTimeout(150)
    await showTitleCard(
      page,
      'Test Case 1',
      'Empty State Tour — each screen shown with no data, explaining purpose, inputs, outputs, and where the user goes next.',
      4500,
    )

    // ----- 1. / persona landing -----
    await showCaption(page, {
      scene: 'PASS 1 · SCREEN 1 of 9',
      title: 'Persona Landing — entry point for 6 roles',
      given: 'A user opens the Forensa Console for the first time',
      when: 'The Console renders / with no auth-derived role yet',
      then: '6 persona-role cards visible; clicking a card routes to that role\'s primary surface',
      testData: [
        `route          GET /`,
        `surfaces       Compliance · Audit · Engineering · M&A · Security · Executive`,
        `data sources   none (static)`,
      ],
      expected: 'PersonaLanding component (SCR-F01) renders 6 cards',
      holdMs: HOLD_EMPTY_CAPTION,
    })
    await hideCaption(page)
    await page.goto(`${CONSOLE}/`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(HOLD_EMPTY_SCREEN)

    // ----- 2. /receipts timeline (empty) -----
    await showCaption(page, {
      scene: 'PASS 1 · SCREEN 2 of 9',
      title: 'Receipts Timeline — append-only signed-receipts ledger',
      given: 'No receipts have been ingested yet',
      when: 'Console queries GET /v1/receipts?tenant_id=… with no filters',
      then: 'Table renders with "No receipts yet" empty state + filter controls',
      testData: [
        `route          GET /receipts`,
        `api            GET /v1/receipts (paginated, cursor on sequence)`,
        `flow next      Click any row → /receipts/{id} detail`,
      ],
      expected: 'ReceiptsTimeline (SCR-F02) — empty list + filters · BR-14 AC-2 list-view top nav',
      holdMs: HOLD_EMPTY_CAPTION,
    })
    await hideCaption(page)
    await page.goto(`${CONSOLE}/receipts`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(HOLD_EMPTY_SCREEN)

    // ----- 3. /evidence pack (empty) -----
    await showCaption(page, {
      scene: 'PASS 1 · SCREEN 3 of 9',
      title: 'Evidence Pack — produce regulator artifact',
      given: 'Regulator needs a take-home audit artifact for a time window',
      when: 'User picks a scope window and clicks "Generate Pack"',
      then: 'JSON-LD pack with root_hash + RFC 3161 TSA proof + PDF download',
      testData: [
        `route          GET /evidence`,
        `api            GET /v1/evidence-packs?scope_start=…&scope_end=…`,
        `crypto         pack_root_hash + Ed25519 signature + FreeTSA RFC 3161 anchor`,
        `flow next      Download PDF → regulator audit file`,
      ],
      expected: 'EvidencePack (SCR-F04) — scope picker + Generate button (no pack yet)',
      holdMs: HOLD_EMPTY_CAPTION,
    })
    await hideCaption(page)
    await page.goto(`${CONSOLE}/evidence`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(HOLD_EMPTY_SCREEN)

    // ----- 4. /anchors -----
    await showCaption(page, {
      scene: 'PASS 1 · SCREEN 4 of 9',
      title: 'TSA Anchors — daily RFC 3161 timestamps',
      given: 'No daily anchors have been produced yet',
      when: 'Console queries GET /v1/anchors?tenant_id=…',
      then: 'Empty table with explanatory copy — anchors land overnight per BR-06',
      testData: [
        `route          GET /anchors`,
        `api            GET /v1/anchors`,
        `crypto         RFC 3161 DER TSR from FreeTSA, bound to daily Merkle root`,
        `flow next      Per-row "Download TSR" → offline openssl ts -verify`,
      ],
      expected: 'AnchorsList (SCR-F05) — empty list + Download-TSR primitives ready',
      holdMs: HOLD_EMPTY_CAPTION,
    })
    await hideCaption(page)
    await page.goto(`${CONSOLE}/anchors`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(HOLD_EMPTY_SCREEN)

    // ----- 5. /diligence -----
    await showCaption(page, {
      scene: 'PASS 1 · SCREEN 5 of 9',
      title: 'M&A Diligence — async export workspace',
      given: 'M&A counterparty requests an evidence bundle for due-diligence',
      when: 'User creates a job via POST /v1/exports/ma-diligence/jobs',
      then: 'Job appears in list with status pending → running → completed (auto-polls every 4s)',
      testData: [
        `route          GET /diligence`,
        `api            POST/GET /v1/exports/ma-diligence/jobs`,
        `crypto         ma_root_hash binds the exported window`,
        `flow next      Download bundle JSON → counterparty data room`,
      ],
      expected: 'DiligenceWorkspace (SCR-F07) — create + list + view + download',
      holdMs: HOLD_EMPTY_CAPTION,
    })
    await hideCaption(page)
    await page.goto(`${CONSOLE}/diligence`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(HOLD_EMPTY_SCREEN)

    // ----- 6. /narratives -----
    await showCaption(page, {
      scene: 'PASS 1 · SCREEN 6 of 9',
      title: 'Narratives — Gemini 2.5 Pro plain-English summaries',
      given: 'Compliance officer wants a natural-language readout of a window',
      when: 'User picks a window and clicks Generate Narrative',
      then: 'Plain text summary + provider model id + token counts + 4-layer injection defence',
      testData: [
        `route          GET /narratives`,
        `api            POST /v1/narratives?scope_start=…&scope_end=…`,
        `llm            Gemini 2.5 Pro (LiveNarrativeClient) or Mock fallback`,
        `defence        BR-10 four-layer prompt-injection defence; 422 → incident_id`,
      ],
      expected: 'NarrativeViewer (SCR-F08) — window picker + generate button',
      holdMs: HOLD_EMPTY_CAPTION,
    })
    await hideCaption(page)
    await page.goto(`${CONSOLE}/narratives`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(HOLD_EMPTY_SCREEN)

    // ----- 7. /tabletop -----
    await showCaption(page, {
      scene: 'PASS 1 · SCREEN 7 of 9',
      title: 'Tabletop Simulator — what-if scenario testing',
      given: 'Risk officer wants to test a hypothetical policy violation',
      when: 'User pastes a TabletopScenario JSON and clicks Run',
      then: 'Per-action verdicts (allow / deny / escalate / errored) + summary counts',
      testData: [
        `route          GET /tabletop`,
        `api            POST /v1/tabletop/simulate`,
        `engine         Lobster Trap policy verdict adapter`,
        `flow next      Replay against active bundle for impact analysis`,
      ],
      expected: 'TabletopSimulator (SCR-F06) — JSON input + Run + Load sample',
      holdMs: HOLD_EMPTY_CAPTION,
    })
    await hideCaption(page)
    await page.goto(`${CONSOLE}/tabletop`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(HOLD_EMPTY_SCREEN)

    // ----- 8. /status -----
    await showCaption(page, {
      scene: 'PASS 1 · SCREEN 8 of 9',
      title: 'Status Dashboard — live ops metrics',
      given: 'Engineer wants a real-time view of tenant ingest + signing health',
      when: 'Console queries GET /healthz (10s poll) + GET /v1/metrics',
      then: '5 cards: ingest rate · signing latency · chain head · anchors · M&A jobs',
      testData: [
        `route          GET /status`,
        `api            GET /healthz · GET /v1/metrics?window_hours=24`,
        `cards          ingest · signing · chain head · anchors · M&A`,
        `polling        10s auto-refresh; warn flags on deferred/failed`,
      ],
      expected: 'StatusDashboard (SCR-F10) — health badge + 5 metric panels (API-F15 wired)',
      holdMs: HOLD_EMPTY_CAPTION,
    })
    await hideCaption(page)
    await page.goto(`${CONSOLE}/status`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(HOLD_EMPTY_SCREEN)

    // ----- 9. /receipts/[id] detail (placeholder — empty list means we can't open one, so show route description card) -----
    await showCaption(page, {
      scene: 'PASS 1 · SCREEN 9 of 9',
      title: 'Receipt Detail — Summary · Proof · Raw tabs (shown in PASS 2)',
      given: 'A receipt exists and the user clicks its row',
      when: 'Console fetches GET /v1/receipts/{id} and re-computes the hash',
      then: 'Three tabs — Summary (claim · agent · scope) · Proof (chain · TSA) · Raw JSON',
      testData: [
        `route          GET /receipts/{id}`,
        `api            GET /v1/receipts/{id}`,
        `crypto op      VERIFY — re-hash payload, compare to stored receipt_hash`,
        `flow next      "Copy as JSON" for evidence chains`,
      ],
      expected: 'ReceiptDetailTabs (SCR-F03) — hash-routed deep links; SHOWN IN PASS 2',
      holdMs: HOLD_EMPTY_CAPTION,
    })
    await hideCaption(page)

    } // end if (!SKIP_PASS_1)

    // ============================================================
    // TRANSITION — between passes
    // ============================================================
    await page.goto('about:blank')
    await page.evaluate(() => {
      document.body.style.cssText = 'margin:0;padding:0;background:#0f172a;'
    })
    await page.waitForTimeout(150)
    await showTitleCard(
      page,
      'Test Case 2',
      'Loaded State Walkthrough — same 9 screens, now with real seeded data. 1 tenant · 1 agent · 1 policy bundle · 5 chained receipts · 1 RFC 3161 anchor from FreeTSA. Fast pass — see the data flow end-to-end.',
      5000,
    )

    if (TENANT_ID === '' || TOKEN === '') {
      // Pass 2 cannot run without auth env. Skip with a clearly-labelled
      // closing card so the recording still terminates cleanly.
      await showTitleCard(
        page,
        'PASS 2 skipped',
        'FORENSA_TENANT_ID + FORENSA_TOKEN env vars not set — re-run with scripts/seed_demo_data.py output in the env.',
        4000,
      )
      return
    }

    // Set tokens on the page via localStorage so the Console's apiFetch
    // can find them (matches the convention in apps/console/src/lib/apiFetch.ts).
    await page.goto(`${CONSOLE}/`, { waitUntil: 'domcontentloaded' })
    await page.evaluate(({ token, tenant }) => {
      try {
        localStorage.setItem('forensa.token', token)
        localStorage.setItem('forensa.tenant_id', tenant)
      } catch {}
    }, { token: TOKEN, tenant: TENANT_ID })

    // ============================================================
    // PASS 2 - LOADED STATE WALKTHROUGH (FAST)
    // ============================================================

    // ----- 1. / persona landing (loaded) -----
    await showCaption(page, {
      scene: 'PASS 2 · SCREEN 1 of 9',
      title: 'Persona Landing — user picks Compliance role',
      given: 'Tenant is now seeded with 5 receipts + 1 anchor',
      when: 'User clicks the Compliance card',
      then: 'Routes to /receipts with this tenant\'s data',
      holdMs: HOLD_LOADED_CAPTION,
    })
    await hideCaption(page)
    await page.goto(`${CONSOLE}/`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(HOLD_LOADED_SCREEN)

    // ----- 2. /receipts timeline (loaded) -----
    await showCaption(page, {
      scene: 'PASS 2 · SCREEN 2 of 9',
      title: 'Receipts Timeline — 5 receipts visible in append-only order',
      given: 'Tenant has 3 day-1 receipts + 2 day-2 receipts',
      when: 'Console fetches GET /v1/receipts',
      then: 'Table populated with sequence numbers, claim ids, signed_at timestamps',
      holdMs: HOLD_LOADED_CAPTION,
    })
    await hideCaption(page)
    await page.goto(`${CONSOLE}/receipts?tenant_id=${TENANT_ID}`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(HOLD_LOADED_SCREEN)
    await pulse(page, '[data-testid="receipt-list-table"]')

    // ----- 3. receipt detail (loaded) -----
    // Pull the first receipt id via API so we can deep-link.
    let firstReceiptId = ''
    try {
      const r = await page.request.get(
        `${API}/v1/receipts?tenant_id=${TENANT_ID}&limit=1`,
        { headers: { Authorization: `Bearer ${TOKEN}` } },
      )
      const body = await r.json()
      firstReceiptId = body?.items?.[0]?.id ?? ''
    } catch {}

    await showCaption(page, {
      scene: 'PASS 2 · SCREEN 3 of 9',
      title: 'Receipt Detail — VERIFY crypto op',
      given: 'User clicks the head of the chain',
      when: 'Console fetches GET /v1/receipts/{id} and recomputes the hash',
      then: 'Green integrity badge — stored hash equals re-computed hash',
      holdMs: HOLD_LOADED_CAPTION,
    })
    await hideCaption(page)
    if (firstReceiptId) {
      await page.goto(`${CONSOLE}/receipts/${firstReceiptId}?tenant_id=${TENANT_ID}`, { waitUntil: 'domcontentloaded' })
      await page.waitForTimeout(HOLD_LOADED_SCREEN)
      await pulse(page, '[data-testid="integrity-badge"]')
    } else {
      await page.waitForTimeout(HOLD_LOADED_SCREEN)
    }

    // ----- 4. /evidence (loaded — generate pack) -----
    await showCaption(page, {
      scene: 'PASS 2 · SCREEN 4 of 9',
      title: 'Evidence Pack — PRODUCE crypto op',
      given: 'Scope window covers the 2 seeded days',
      when: 'User clicks Generate Pack',
      then: 'JSON-LD pack with root_hash, Ed25519 signature, FreeTSA TSA anchor, PDF',
      holdMs: HOLD_LOADED_CAPTION,
    })
    await hideCaption(page)
    await page.goto(`${CONSOLE}/evidence?tenant_id=${TENANT_ID}&scope_start=${encodeURIComponent(SCOPE_START)}&scope_end=${encodeURIComponent(SCOPE_END)}`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(HOLD_LOADED_SCREEN)
    const genBtn = page.locator('[data-testid="generate-pack-button"]')
    if (await genBtn.isVisible().catch(() => false)) {
      await pulse(page, '[data-testid="generate-pack-button"]')
      await genBtn.click()
      await page.waitForTimeout(2000)
      await pulse(page, '[data-testid="pack-signed-badge"]')
    }

    // ----- 5. /anchors (loaded) -----
    await showCaption(page, {
      scene: 'PASS 2 · SCREEN 5 of 9',
      title: 'TSA Anchors — 1 anchored day visible',
      given: 'Day 1 (2026-05-13) has been anchored via FreeTSA',
      when: 'Console fetches GET /v1/anchors',
      then: 'Row shows date · TSA · status: anchored · Download TSR button',
      holdMs: HOLD_LOADED_CAPTION,
    })
    await hideCaption(page)
    await page.goto(`${CONSOLE}/anchors?tenant_id=${TENANT_ID}`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(HOLD_LOADED_SCREEN)
    await pulse(page, '[data-testid="anchors-list"]')

    // ----- 6. /diligence (loaded) -----
    await showCaption(page, {
      scene: 'PASS 2 · SCREEN 6 of 9',
      title: 'M&A Diligence — async job pattern',
      given: 'User creates a new export job',
      when: 'POST /v1/exports/ma-diligence/jobs returns 202 with job_id',
      then: 'Job appears in list with pending status; auto-polls until completed',
      holdMs: HOLD_LOADED_CAPTION,
    })
    await hideCaption(page)
    await page.goto(`${CONSOLE}/diligence?tenant_id=${TENANT_ID}`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(HOLD_LOADED_SCREEN)

    // ----- 7. /narratives (loaded) -----
    await showCaption(page, {
      scene: 'PASS 2 · SCREEN 7 of 9',
      title: 'Narratives — Gemini summary of the seeded window',
      given: 'Scope window has 5 receipts to narrate',
      when: 'User clicks Generate Narrative',
      then: 'Plain-English summary with model id + token counts + content hash',
      holdMs: HOLD_LOADED_CAPTION,
    })
    await hideCaption(page)
    await page.goto(`${CONSOLE}/narratives?tenant_id=${TENANT_ID}&scope_start=${encodeURIComponent(SCOPE_START)}&scope_end=${encodeURIComponent(SCOPE_END)}`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(HOLD_LOADED_SCREEN)

    // ----- 8. /tabletop (loaded with sample) -----
    await showCaption(page, {
      scene: 'PASS 2 · SCREEN 8 of 9',
      title: 'Tabletop Simulator — sample scenario',
      given: 'User loads the bundled sample scenario',
      when: 'Click Run Simulation',
      then: 'Per-action verdicts with allow/deny/escalate pills + summary counts',
      holdMs: HOLD_LOADED_CAPTION,
    })
    await hideCaption(page)
    await page.goto(`${CONSOLE}/tabletop?tenant_id=${TENANT_ID}`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(HOLD_LOADED_SCREEN)

    // ----- 9. /status (loaded) -----
    await showCaption(page, {
      scene: 'PASS 2 · SCREEN 9 of 9',
      title: 'Status Dashboard — 5 live cards',
      given: 'Tenant has 5 signed receipts + 1 anchor today',
      when: 'Console fetches GET /v1/metrics?window_hours=24',
      then: 'Cards: ingest=5 · receipts=5 · chain head=4 · anchors=1 · M&A=0',
      holdMs: HOLD_LOADED_CAPTION,
    })
    await hideCaption(page)
    await page.goto(`${CONSOLE}/status?tenant_id=${TENANT_ID}`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(HOLD_LOADED_SCREEN)
    await pulse(page, '[data-testid="metrics-panel"]')

    // ============================================================
    // CLOSING CARD
    // ============================================================
    await showTitleCard(
      page,
      'Forensa',
      '9 screens · 2 cryptographic operations (verify + produce) · Real Ed25519 signatures · Real RFC 3161 TSA proof from FreeTSA · github.com/vsenthil7/forensa · TechEx Hackathon 2026',
      5000,
    )
  })
})
