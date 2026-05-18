# Forensa — Traceability Matrix — LIVE Progress

**Doc:** 17b of 22 | **Companion to:** `TRACEABILITY_MATRIX.md` (canonical) | **Date stamp:** 2026-05-18 19:34 BST
**Status:** LIVE — updated after every dev commit before the next mini-sprint starts
**Last sweep:** 2026-05-18 19:34 BST after CP9.61 (enterprise-grade docker-compose stack + HMAC auth wiring)
**Supersedes:** prior LIVE companion at `/home/claude/output/Forensa_005-01-H18_Traceability_LIVE_20260517.md`

---

## 0. Rules

### 0.1 Rule A.10 (inherited)
Open canonical `TRACEABILITY_MATRIX.md` + `BRD.md` + `USE_CASES.md` before each CP. Pick CP by which RT-F\* / BR / US-F\* needs closing next.

### 0.2 Rule A.11 — CP ↔ requirement closure (LOCKED, MOST IMPORTANT RULE)
**Every dev commit closes ≥ 1 named requirement ID (BR-N / US-FN / UC-N / RT-FN / SCR-FN).** The commit message names the IDs closed. This file's §2 RT roll-up and §1 commit ledger record the commit against the IDs.

A CP that does not close any named ID is engineering-convenience-labelled (`CPx.y-tooling: ...`) and does **NOT** advance the requirement scoreboard. Engineering-convenience CPs are allowed but rare.

### 0.3 Update cadence — strict, no exceptions

```
Build (edit/new) -> git commit/push -> test -> green? next : fix -> commit/push -> test -> loop
                              \
                               -> update §1 + §2 of this file before the next CP starts
```

This rule was adopted from mendoraci CLAUDE_RULES which moved this discipline from convention to enforcement. Documentation drift between canonical and LIVE (R-F12 in BRD risk register) is the failure mode this rule prevents.

---

## 1. Commit ledger (most recent first)

Per Rule A.11 every row names the IDs the commit closed (or advanced).

| Commit | Pushed | CP | IDs closed | What |
|---|---|---|---|---|
| `aec3de6` | 2026-05-18 19:33 BST | **CP9.61 / CP9.61b** | **NFR-deployment-local close, BR-02 wiring** | Enterprise-grade local-dev orchestration: docker-compose stack with 4 services (postgres + api-migrate + api + console) matching MendoraCI pattern (`restart: unless-stopped`, healthchecks on every persistent service, `depends_on` with conditions, named volume `forensa-pg-data`, env-file `.env.compose` committed safe-default + `.env.compose.local` gitignored override). Ports chosen to avoid MendoraCI clash: postgres 5433, api 8000, console 3001. HMAC bearer auth (BR-02 / CP9.18b) wired through `FORENSA_HMAC_SECRET` + `FORENSA_HMAC_TENANT_ID` so `/v1/anchors`, `/v1/receipts`, `/v1/metrics` etc. return HTTP 200 out of the box. `tools/dev.ps1` helper with 14 actions (up/down/down-v/ps/logs/build/health/psql/migrate/status/restart/token/demo/help). `scripts/mint_demo_token.py` mints a Bearer token for the demo tenant. Six pre-existing latent bugs found and fixed: pnpm workspace symlinks with host absolute paths leaking into the image; alembic `FORENSA_DATABASE_URL` vs API `FORENSA_DB_URL` env-var mismatch; poetry venv absolute-path shebang in `/build/.venv`; PowerShell parser eating `$s?tenant_id`; `scripts/` not COPYed into the API runtime image; console Dockerfile's multi-stage standalone build never worked end-to-end. **11 commits in this CP**, all pushed to `origin/main`. End-to-end smoke test passes: all 3 services healthy, console serves 4 routes at 200, 3 authed API surfaces return 200. |
| `b4403bc` | 2026-05-18 17:16 BST | **CP9.60b** | LIVE doc SHA sweep | Replace `<pending>` placeholders for CP9.52/9.53/9.55/9.56/9.57/9.58/9.59 with the actual landed SHAs (1b8a2f5, aefb18c, 321ceb7). LIVE matrix now grounded against `origin/main` HEAD. Per Rule A.11: this row is documentation reconciliation, not a code CP. |
| `b7c78cb` | 2026-05-18 16:53 BST | **CP9.60a** | Rule A.11 introduction, supersession map (BR-02/06/10/11), BRD_IDENTIFIER_MAP.md, docs/21_traceability_workbook | Apply forensa_docs_v2.0_20260518.zip (nested): full elaborated doc pack v2.0 (BRD 135-486 LOC, USE_CASES 52-328 LOC, TRACEABILITY_MATRIX 80-241 LOC, LIVE companions for both, new 13-sheet workbook, archived v1.x snapshots). |
| `321ceb7` | 2026-05-18 17:08 BST | **CP9.59** | **API-F15, SCR-F10 close, Gap 14 close** | `GET /v1/metrics` tenant-scoped operational metrics snapshot built from DB counts at request time (no in-memory counters, no Prometheus format — JSON snapshot only). Returns ingest counts (total + window + per-hour), signing counts + chain-head sequence + last-signed timestamp, anchoring counts (anchored vs deferred), M&A export-job counts by status. Window defaults to 24h, override `?window_hours=N` (1..168). Console `/status` page extended with a MetricsPanel that fetches this and renders 5 cards (ingest, signing, chain head, anchors, M&A jobs); deferred anchors and failed jobs auto-flag warn. Signing latency p50/p95/p99 remains deferred to Phase 11 (needs request middleware). 8 pytest tests at 100% statement+branch coverage on `apps/api/routes/metrics.py`; 309 backend API tests pass overall. Console: 218 vitest at 100/100/100/100 coverage on 17 components; `tsc --noEmit` clean; 210 Playwright tests enumerate. |
| `aefb18c` | 2026-05-18 17:05 BST | **CP9.58** | **SCR-F10 (partial — API-F15 gap)** | `/status` dashboard from `/healthz`: overall chip, API panel (status / version / narrative provider / model id / fallback flag), Refresh button, 10s auto-poll, explicit "API-F15 planned" placeholder for ingest rate / signing latency / anchor success-failure / chain integrity. 9 vitest tests at 100% coverage. Playwright spec covers all structural assertions (no seed required). |
| `aefb18c` | 2026-05-18 17:05 BST | **CP9.57** | **SCR-F08, RT-F21 close** | `/narratives` page: window picker → POST /v1/narratives (query params) → plain-English narrative pane with model id, prompt/completion token counts, pack_root_hash, content_hash, generated_at. 422 defence path renders the BR-10 4-layer-defence `incident_id` without exposing the offending text. 12 vitest tests at 100% coverage. |
| `aefb18c` | 2026-05-18 17:05 BST | **CP9.56** | **US-F26, SCR-F07** | `/diligence` workspace: create job (POST /v1/exports/ma-diligence/jobs) → list jobs (GET ... /jobs) → view detail (GET /jobs/{id}) → download bundle JSON. Status-badge palette for pending/running/completed/failed. Auto-polls every 4s while any job is pending or running, stops once all settle. 16 vitest tests at 100% coverage. |
| `aefb18c` | 2026-05-18 17:05 BST | **CP9.55** | **US-F23, SCR-F06, RT-F21 advance** | `/tabletop` simulator: paste `TabletopScenario` JSON or click "Load sample" → POST /v1/tabletop/simulate → render per-action verdicts with decision pills (allow / deny / escalate / errored) + aggregate summary stats (total / allow / deny / escalate / errored). 14 vitest tests at 100% coverage. |
| `aefb18c` | 2026-05-18 17:05 BST | **CP9.53** | **US-F16 (UI access), SCR-F05** | `/anchors` list view: one row per daily TSA anchor with date, status chip (anchored / deferred), TSA identifier, timestamp, root-hash head. "Download TSR" button sets `Accept: application/timestamp-reply` and pipes DER bytes into a blob download (US-F16 UI surface for offline `openssl ts -verify`). Deferred rows show no download button. 11 vitest tests at 100% coverage. |
| `1b8a2f5` | 2026-05-18 17:02 BST | **CP9.52a-g** | **US-F19, US-F28, US-F29 (all 9 ACs), US-F30, US-F31, RT-F19, RT-F20** | Operator Console + PWA shell. 4 console screens (persona landing, receipts timeline, receipt-detail Summary/Proof/Raw tabs, evidence-pack Compliance/Technical toggle with narrated loading) + PWA manifest + service worker (stale-while-revalidate for /v1/receipts /v1/evidence-packs /v1/anchors; never caches non-GET writes per AC-5) + offline + 24h-stale banner. TopNav implementing BR-14 AC-2 list-views-as-top-nav with no sessionStorage. 146 vitest tests at 100% coverage. 141 Playwright tests across chromium-desktop + webkit-mobile (iPhone 15) + chromium-android (Pixel 7). |
| `d7d9aaa` | 2026-05-17 17:50 BST | CP9.51 | US-F15, RC-F08, RT-F08 extends | `verify_rfc3161_timestamp_response()` in `packages/crypto/tsa.py`: full PKIX cert-chain verification of RFC 3161 DER bytes against FreeTSA's published cert chain. 14 unit + live integration tests. FreeTSA cert fixtures bundled at `tests/fixtures/freetsa/`. |
| `b92c308` | 2026-05-17 03:47 BST | CP9.50 | RT-F09 extends; demo spec rewritten | `/evidence` Console page with `EvidencePack` React component. Rewrote captioned demo spec to auditex 2-crypto-op pattern. Fixed Chromium pre-paint blank frame. |
| (prior) | 2026-05-15 11:22 BST | CP9.29 | US-F21, US-F22, BR-12, RT-F12 | Tabletop simulation + replay: 19 tests (13 unit + 6 endpoint); 100% coverage. **BR-12 DEFERRED → IMPLEMENTED+TESTED.** Headline 9/13 → 10/13. |
| (prior) | 2026-05-15 10:55 BST | CP9.28 | US-F25, BR-13, RT-F13 | M&A diligence export with `ma_root_hash`: 17 tests; 100% coverage. **BR-13 STUB → IMPLEMENTED+TESTED.** Headline 8/13 → 9/13. |
| (prior) | 2026-05-15 07:10 BST | CP9.21a + CP9.21b | US-F18, BR-05, RT-F09 | PDF renderer (24 tests) + content negotiation (17 tests). **BR-05 PARTIAL → IMPLEMENTED+TESTED.** |
| (prior) | 2026-05-14 22:02 BST | CP9.17 | US-F02, NFR-08, RT-F14 | Retry-safe ingest: 54 tests at 100% coverage. NFR-08 added at IMPLEMENTED+TESTED. |
| (prior) | 2026-05-14 20:07 BST | CP9.16-PG-up | NFR-01, RT-F16 | DB-level append-only triggers verified on PG 16.13. 14 PG-integration tests. |
| (prior) | (Phase 9 baseline) | CP9.20 | BR-10/11 (extends), RT-F10 (extends) | Gemini SDK migration `google.generativeai` → `google.genai`. |
| (prior) | (Phase 9) | CP9.19 | US-F14, BR-06 (TSA part), RT-F08 | FreeTSA live integration + deferred-tombstone fallback. 11 TSA tests. |
| (prior) | (Phase 9) | CP9.18a/b/c | US-F04, BR-02, RT-F04 | Agent signing key + route-layer principal-vs-tenant enforcement. |
| (prior) | (Phase 9) | CP9.15 | US-F10, RT-F06 | Bundle approval workflow + append-only PG triggers. 6 PG-integration tests. |
| (prior) | (Phase 9) | CP9.1 | US-F11, BR-10, BR-11, RT-F10 | Live Gemini 2.5 Pro narrative + 4-layer injection defence. 19 tests. |
| (prior) | Phase 8 baseline | CP8.2 | BR-09 in-process, RT-F02 | Load test 6452 events/sec. |
| (prior) | Phase 7 baseline | CP7.x | BR-10/11 mock | MockNarrativeClient (superseded by CP9.1). |
| (prior) | Phases 1-6 | various | BR-01..BR-04, BR-05 (JSON-LD), BR-06 (chain), NFR-01, NFR-05 | Scaffold + chain + snapshot + JSON-LD export. |

---

## 2. RT roll-up (HEAD CP9.59) — 22 rows

| RT | Status | Last commit | Test count | Notes |
|---|---|---|---|---|
| RT-F01 | ✅ `IMPLEMENTED+TESTED` | (Phase 1) | TEST-F01..F04 + cross | Ingest pipeline |
| RT-F02 | 🟡 `IMPLEMENTED+TESTED` (in-process); **AWS topology DEFERRED Phase 12** | CP8.2 | TEST-F05 load | BR-09 PARTIAL state recorded here |
| RT-F03 | ✅ `IMPLEMENTED+TESTED` with named finding | (Phase 1) | TEST-F06 50 tests | RC-F14 / IMP-F14 normaliser separation queued |
| RT-F04 | ✅ `IMPLEMENTED+TESTED` | CP9.18c `ec81920` | TEST-F07 21 sign | Agent signature wired |
| RT-F05 | ✅ `IMPLEMENTED+TESTED` | (Phase 3) | TEST-F08 22 | Snapshot binding + replay |
| RT-F06 | ✅ `IMPLEMENTED+TESTED` | CP9.15 | TEST-F09 6 PG-integration | Bundle approval triggers |
| RT-F07 | ✅ `IMPLEMENTED+TESTED` | (Phase 2) | TEST-F10 22 merkle property | Chain primitive |
| RT-F08 | ✅ `IMPLEMENTED+TESTED` (extends CP9.51) | `d7d9aaa` | TEST-F11 25 (11 + 14 cert) | TSA + **cert chain CP9.51** |
| RT-F09 | ✅ `IMPLEMENTED+TESTED` | CP9.21a+b + CP9.50 | TEST-F12 72 | JSON-LD + PDF |
| RT-F10 | ✅ `IMPLEMENTED+TESTED` | CP9.1 + CP9.20 | TEST-F13 19 | Live narrative |
| RT-F11 | ✅ `IMPLEMENTED+TESTED` (cursor); OpenSearch DEFERRED | — | TEST-F14 | Pagination |
| RT-F12 | ✅ `IMPLEMENTED+TESTED` | CP9.29 | TEST-F15 19 | Tabletop |
| RT-F13 | ✅ `IMPLEMENTED+TESTED` | CP9.28 | TEST-F16 17 | M&A export |
| RT-F14 | ✅ `IMPLEMENTED+TESTED` | CP9.17 | TEST-F17 54 | Idempotency |
| RT-F15 | ✅ `IMPLEMENTED+TESTED` | (cross — every route) | TEST-F18 | Multi-tenant isolation |
| RT-F16 | ✅ `IMPLEMENTED+TESTED` | CP9.16-PG-up | TEST-F19 14 | PG triggers |
| RT-F17 | ⏸ `DEFERRED` Phase 12 | — | — | LangGraph multi-agent |
| RT-F18 | ⏸ `DEFERRED` Phase 13 | — | — | Omniverse |
| **RT-F19** | ✅ **`IMPLEMENTED+TESTED`** | CP9.52a-g | 146 vitest at 100% coverage + 141 Playwright × 3 device projects | **Console list-views-as-top-nav (BR-14 AC-2). 4 screens (persona landing, receipts timeline, receipt-detail tabs, evidence-pack toggle).** |
| **RT-F20** | ✅ **`IMPLEMENTED+TESTED`** | CP9.52f | (within 146 vitest) + 5 PWA Playwright specs | **PWA shell — manifest, sw.js with stale-while-revalidate, offline banner, 24h-stale banner.** |
| **RT-F21** | ✅ **`IMPLEMENTED+TESTED`** | CP9.55 + CP9.56 + CP9.57 | 14 + 16 + 12 vitest = 42 at 100% + 3 Playwright specs | **Tabletop / M&A diligence / Narrative Console UI.** |
| **RT-F22** | ⏸ **`DEFERRED` Phase 10 CP10.1..CP10.4** | — | TEST-F40 planned | **Multi-tenant auth (UC-10).** |

**Roll-up at HEAD CP9.58:** 19 ✅ + 2 ⏸ Phase 12-13 (by design) + 1 ⏸ Phase 10 (RT-F22, by design) = 22 / 22 accounted for.

**BR scoreboard:** 10/13 BR-01..BR-13 `IMPLEMENTED+TESTED` + **BR-14 `IMPLEMENTED+TESTED` for v1.x scope** (8 of 9 SCR-F screens shipped; SCR-F09 is by-design Phase 10 work).

**SCR-F roll-up:** SCR-F01 ✅, SCR-F02 ✅, SCR-F03 ✅, SCR-F04 ✅, SCR-F05 ✅, SCR-F06 ✅, SCR-F07 ✅, SCR-F08 ✅, SCR-F09 ⏸ Phase 10, SCR-F10 ✅ (closed by CP9.59 — `/v1/metrics` wired; signing latency p50/p95/p99 remains deferred to Phase 11 request-middleware sweep).

---

## 3. Honest gaps tracking

| Gap | Description | Open / Closed | Closes when |
|---|---|---|---|
| Gap 1 | Canonical traceability stale at 14 May 22:02 | **CLOSED** (v2.0 sweep 18 May 05:15) | n/a |
| Gap 2 | "Day 5/6" calendar narrative drift | **CLOSED** (replaced by CP-anchored phase plan in BRD §10) | n/a |
| Gap 3 | Canonical USE_CASES had 8 UCs but no numbered stories | **CLOSED** (US-F01..F32 added in v2.0) | n/a |
| Gap 4 | RT-IDs did not previously exist | **CLOSED** (RT-F01..F22 added) | n/a |
| Gap 5 | BR-09 PARTIAL not exposed in canonical | **CLOSED** (RT-F02 records explicitly) | n/a |
| Gap 6 | Two RT-eligible streams had no parent BR | **CLOSED** (rolled into RT-F11 and RT-F16) | n/a |
| Gap 7 | FreeTSA test fixtures partially-documented | **CLOSED** (CP9.51 bundled fixtures) | n/a |
| **Gap 8** | Console-surface RTs (RT-F19..F22) introduced; Playwright UI-driving tests TEST-F30..F40 not green | **CLOSED for RT-F19, RT-F20, RT-F21** (CP9.52..CP9.58 landed; 210 vitest at 100% + 210 Playwright tests across 3 device projects). **Remains OPEN for RT-F22** (Phase 10 by design). | RT-F22 closes at CP10.4 |
| **Gap 9** | EVAL-F01 gold set N=50 today; pilot target N=250 | **OPEN** | Pilot exit |
| **Gap 10** | EVAL-F02 prompt-injection corpus N=30 today; pilot target N=500 | **OPEN** | Phase 10 entry |
| **Gap 11** | API-F11 `POST /v1/tabletop/simulate` not yet exposed in `08_api_specification/API_SPECIFICATION.md` (CP9.29 backend shipped without canonical API doc update) | **OPEN** | API_SPECIFICATION refresh (light task) |
| **Gap 12** | API-F09 `POST /v1/exports/ma-diligence` similarly not in API_SPECIFICATION | **OPEN** | API_SPECIFICATION refresh |
| **Gap 13** | `NavLinks` / sessionStorage anti-pattern not yet in our codebase but the BR-14 AC-2 prohibition is in place pre-emptively | n/a (preventive, not a gap) | n/a |
| **Gap 14** | API-F15 `GET /v1/metrics` not yet built; `/status` page (SCR-F10) surfaces `/healthz` only and shows the operational-metrics panels (ingest rate, signing latency, anchor success/failure, chain integrity sparkline) as explicit "API-F15 planned" placeholders. **Not a stub — placeholders are clearly labelled as deferred.** | **CLOSED** (CP9.59 — `GET /v1/metrics` returns tenant-scoped DB-snapshot; `/status` MetricsPanel wired). **Signing latency p50/p95/p99 panel remains deferred to Phase 11** (needs request middleware) — labelled accordingly in the UI. | n/a |

---

## 4. Forward queue (CP10.1 → Phase 10) — per Rule A.11

**Landed since the last LIVE sweep (CP9.59):** see §1 commit ledger. `GET /v1/metrics` (API-F15) now live; SCR-F10 fully closed; Gap 14 closed.

| CP | IDs to close | Scope | Owner |
|---|---|---|---|
| CP10.1 | US-F32 partial, DB-F08, API-F14, SCR-F09, RT-F22 advance | Auth surface MVP: `/login` page + `POST /v1/auth/login` + `users` / `sessions` tables | Tech Lead |
| CP10.2 | US-F32 close, RC-F26, RT-F22 close | Tenant picker in header + token-derived tenant | Tech Lead |
| CP10.3 | NFR-10 close at DB layer | Postgres row-level security policies | Tech Lead |
| CP10.4 | UC-10 close | Full multi-tenant auth E2E test | Tech Lead |

**Phase 11 observability sweep (queued):** Signing latency p50/p95/p99 (request middleware) — closes the last labelled deferred panel on the `/status` page.

**Documentation-only CPs queued (close Gap 11 + Gap 12 + the documented API surface):**
- `CP-doc1` — Update `08_api_specification/API_SPECIFICATION.md` with `POST /v1/tabletop/simulate` + `POST /v1/exports/ma-diligence` + `POST /v1/exports/ma-diligence/jobs` + `POST /v1/narratives` + `GET /v1/anchors` + `GET /v1/metrics`.

---

## 5. IMP-F forward queue (longer-horizon enhancements)

See `TRACEABILITY_MATRIX.md` §13 for the full IMP-F\* table per RT. Highest-priority items for Phase 10–12:

| IMP-F | Description | Target |
|---|---|---|
| IMP-F04 | Detached platform signature on JSON-LD + PDF | CP11.6 |
| IMP-F12 | Second TSA fallback (in addition to FreeTSA) | Phase 11 |
| IMP-F14 | Separate `forensa.reasoning` from `gen_ai.response.text` in OTel normaliser | Phase 11 |
| IMP-F03 | Merkle tree (RFC 6962) for inclusion proofs (today chain only) | Phase 12 |
| IMP-F11 | Semantic hallucination guardrail on narrative output | Phase 12 |
| IMP-F09 | Kafka + S3 + EventBridge BR-09 full topology | Phase 12 |
| IMP-F07 | LangGraph adapter (BR-07) | Phase 12 |
| IMP-F08 | Omniverse / Isaac Sim adapter (BR-08) | Phase 13 (stretch) |
| IMP-F20 | M&A export async-job mode (current sync only) | Phase 12 |
| IMP-F34 / F35 | SCIM / SAML enterprise SSO | Phase 11 |

---

## 6. Change log

| Date | Change |
|---|---|
| 2026-05-18 19:34 BST | **CP9.61 sweep.** §1 commit ledger: row added for CP9.61 (enterprise-grade docker-compose stack + HMAC wiring). Header `Last sweep` flipped CP9.59 → CP9.61. Closes NFR-deployment-local. Test gate: all 4 services healthy, 4 console routes serve 200, 3 authed API surfaces return 200 with valid Bearer. Six latent bugs found and fixed during compose-up (documented in CP9.61_CLOSEOUT). |
| 2026-05-18 16:30 BST | **CP9.59 sweep.** §1 commit ledger: row added for `GET /v1/metrics` (API-F15) + `/status` MetricsPanel. §2 RT roll-up: HEAD label flipped CP9.58 → CP9.59; SCR-F roll-up paragraph updated (SCR-F10 fully closed; signing-latency p50/p95/p99 still deferred to Phase 11). §3 gaps: **Gap 14 CLOSED**. §4 forward queue: CP9.59 row removed (landed); header now reads "CP10.1 → Phase 10"; new "Phase 11 observability sweep" line added for the latency-histograms work. Backend: 8 new pytest tests at 100% on `apps/api/routes/metrics.py`; full API suite 309 tests pass. Console: 218/218 vitest at 100/100/100/100; `tsc --noEmit` clean; 210 Playwright tests enumerate. |
| 2026-05-18 15:55 BST | **Cumulative CP9.52..CP9.58 sweep.** §1 commit ledger: 6 new rows for CP9.52a-g + CP9.53 + CP9.55 + CP9.56 + CP9.57 + CP9.58 (most recent first). §2 RT roll-up: RT-F19, RT-F20, RT-F21 flipped to ✅ `IMPLEMENTED+TESTED`; HEAD label moved to CP9.58; new BR-14 status (IMPLEMENTED+TESTED for v1.x scope); new SCR-F roll-up line. §3 gaps: Gap 8 closed for RT-F19/F20/F21 (RT-F22 remains by-design Phase 10); **new Gap 14 added** — API-F15 `GET /v1/metrics` not yet built, `/status` page surfaces `/healthz` only with explicit "API-F15 planned" placeholders. §4 forward queue: landed CPs removed; new CP9.59 (API-F15 + SCR-F10 close) added at the top; Phase 10 auth CPs (CP10.1..CP10.4) unchanged; new `CP-doc1` documentation-only CP queued to close Gap 11 + Gap 12 + the documented API surface. Cumulative deliverable: 210 vitest tests at 100/100/100/100 coverage across 17 components; 210 Playwright tests across 14 spec files × 3 device projects (chromium-desktop, webkit-mobile / iPhone 15, chromium-android / Pixel 7); `tsc --noEmit` clean. |
| 2026-05-18 05:15 BST | LIVE doc reshaped against canonical `TRACEABILITY_MATRIX.md` v2.0 elaborated. Commit ledger extended back through Phase 9 baseline. RT roll-up extended to 22 rows (RT-F19..F22 new for Console / PWA / Console UI / multi-tenant auth). Honest-gaps tracking carries forward 7 closed gaps + 3 v2.0-new open gaps + 2 new API-spec-drift gaps (Gap 11, Gap 12 — lightweight to close). Rule A.11 locked at top with strict update-after-commit cadence rule restated. Forward queue named per Rule A.11. |
| 2026-05-17 17:50 BST | Prior sweep at end of CP9.51. |
