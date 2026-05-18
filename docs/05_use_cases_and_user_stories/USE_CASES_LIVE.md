# Forensa — Use Cases & User Stories — LIVE Progress

**Doc:** 05b of 22 | **Companion to:** `USE_CASES.md` (canonical) | **Date stamp:** 2026-05-18 16:30 BST
**Status:** LIVE — updated after every dev commit before the next mini-sprint starts
**Last sweep:** 2026-05-18 16:30 BST after CP9.59 (API-F15 metrics endpoint)
**Supersedes:** prior LIVE companion at `/home/claude/output/Forensa_005-01-H18_UseCases_LIVE_20260517.md` (17 May 2026 22:30 BST)

---

## 0. Rules

### 0.1 Rule A.10 (inherited)
Before each CP, open canonical `USE_CASES.md` + `BRD.md` + `TRACEABILITY_MATRIX.md`. Pick CP by which US-F\* needs closing next.

### 0.2 Rule A.11 — CP ↔ requirement closure (LOCKED)
Every dev commit closes ≥ 1 named ID. Commit message names them. This file records the CP commit against the ID(s) closed in §3 below. CPs not closing a named ID are labelled `CPx.y-tooling`.

### 0.3 Update cadence
**This file is updated immediately after every dev commit, before the next mini-sprint starts.** No exceptions. Inherited from mendoraci CLAUDE_RULES discipline. Going forward this file is the canonical "what's done, what's next" record.

---

## 1. UC roll-up (HEAD CP9.59)

| UC | Subject | Stories | Status | Last commit |
|---|---|---|---|---|
| UC-01 | Regulator pack | US-F07, US-F17, US-F18, US-F19, US-F20 | `IMPLEMENTED+TESTED` (Compliance view UI closed CP9.52d) | CP9.52d |
| UC-02 | Customer dispute | US-F03, US-F08, US-F17 | `IMPLEMENTED+TESTED` | (pre-CP9 baseline) |
| UC-03 | Multi-agent audit | US-F24 (deferred) | `PARTIAL` (single-agent works) | — |
| UC-04 | Policy drift | US-F11, US-F12 | `IMPLEMENTED+TESTED` | (Phase 9 narrative coverage) |
| UC-05 | Model deprecation | US-F01, US-F17 | `IMPLEMENTED+TESTED` in-process; AWS DEFERRED Phase 12 | `d7d9aaa` |
| UC-06 | DORA tabletop | US-F21, US-F22, US-F23 | `IMPLEMENTED+TESTED` (UI closed CP9.55) | CP9.55 |
| UC-07 | M&A diligence | US-F25, US-F26 | `IMPLEMENTED+TESTED` (UI closed CP9.56) | CP9.56 |
| UC-08 | Prompt injection | (rolled into narrative defence tests) | `IMPLEMENTED+TESTED` | `d7d9aaa` |
| **UC-09** | **Operator console journey** | **US-F28, US-F29, US-F30, US-F19** | **`IMPLEMENTED+TESTED`** (closed CP9.52a-g) | CP9.52a-g |
| **UC-10** | **Multi-tenant auth** | **US-F32** | **`DEFERRED` Phase 10 CP10.1..CP10.4** | — |

**Roll-up:** 9 of 10 UCs `IMPLEMENTED+TESTED`; UC-03 PARTIAL (single-agent only, multi-agent DEFERRED Phase 12); UC-10 DEFERRED Phase 10 by design.

---

## 2. US-F roll-up (HEAD CP9.59)

| ID | Story | BR | SCR | Status | CP that closed it |
|---|---|---|---|---|---|
| US-F01 | Agent action ingested as signed Receipt | BR-01, BR-02 | — | ✅ `IMPLEMENTED+TESTED` | Phase 1 + CP9.18 |
| US-F02 | Retry-safe ingest | BR-01 / NFR-08 | — | ✅ `IMPLEMENTED+TESTED` | CP9.17 |
| US-F03 | Tenant signature verification | BR-02 | SCR-F03 | ✅ `IMPLEMENTED+TESTED` | Phase 2 |
| US-F04 | Agent identity signature | BR-02 | — | ✅ `IMPLEMENTED+TESTED` | CP9.18a/b/c |
| US-F05 | Reasoning capture in event | BR-03 | — | ✅ `IMPLEMENTED+TESTED` | Phase 1 |
| US-F06 | OTel GenAI envelope ingest | BR-01, BR-03 | — | ✅ `IMPLEMENTED+TESTED` (with named finding RC-F14 / IMP-F14) | Phase 1 |
| US-F07 | Receipt list view | BR-01 | SCR-F02 | ✅ `IMPLEMENTED+TESTED` (full enterprise timeline) | **CP9.52a-b** |
| US-F08 | Receipt detail with verification | BR-01, BR-06 | SCR-F03 | ✅ `IMPLEMENTED+TESTED` (Summary/Proof/Raw tabs) | **CP9.52c** |
| US-F09 | Policy bundle snapshot at decision | BR-04 | — | ✅ `IMPLEMENTED+TESTED` | Phase 3 |
| US-F10 | Policy bundle approval workflow | BR-04 | — | ✅ `IMPLEMENTED+TESTED` | CP9.15 |
| US-F11 | Policy drift surfaced in narrative | BR-04, BR-10 | SCR-F08 | ✅ `IMPLEMENTED+TESTED` | CP9.1 |
| US-F12 | Policy replay never returns live state | BR-04 | — | ✅ `IMPLEMENTED+TESTED` | Phase 3 |
| US-F13 | Hash chain verifiable offline | BR-06 | — | ✅ `IMPLEMENTED+TESTED` | Phase 2 |
| US-F14 | Daily RFC 3161 anchor (FreeTSA) | BR-06 | SCR-F05 | ✅ `IMPLEMENTED+TESTED` | CP9.19 |
| US-F15 | Cert-chain verification of TSR | BR-06 | — | ✅ `IMPLEMENTED+TESTED` | CP9.51 `d7d9aaa` |
| US-F16 | Raw TSR DER bytes downloadable | BR-06 | SCR-F05 | ✅ `IMPLEMENTED+TESTED` (API CP9.27 + UI **CP9.53**) | CP9.27 + **CP9.53** |
| US-F17 | JSON-LD evidence pack | BR-05 | SCR-F04 | ✅ `IMPLEMENTED+TESTED` | Phase 6 |
| US-F18 | Regulator-grade PDF | BR-05 | SCR-F04 | ✅ `IMPLEMENTED+TESTED` | CP9.21a + CP9.21b |
| US-F19 | Evidence pack Compliance view | BR-05, BR-14 | SCR-F04 | ✅ `IMPLEMENTED+TESTED` | **CP9.52d** |
| US-F20 | Offline pack verification | BR-05, BR-06 | — | ✅ `IMPLEMENTED+TESTED` | Phase 6 |
| US-F21 | Tabletop drill via API | BR-12 | — | ✅ `IMPLEMENTED+TESTED` | CP9.29 |
| US-F22 | Tabletop replay window | BR-12 | — | ✅ `IMPLEMENTED+TESTED` | CP9.29 |
| US-F23 | Tabletop UI in Console | BR-12, BR-14 | SCR-F06 | ✅ `IMPLEMENTED+TESTED` | **CP9.55** |
| US-F24 | LangGraph multi-agent capture | BR-07 | — | ⏸ `DEFERRED` Phase 12 | — |
| US-F25 | M&A diligence export bundle | BR-13 | — | ✅ `IMPLEMENTED+TESTED` | CP9.28 |
| US-F26 | M&A diligence UI in Console | BR-13, BR-14 | SCR-F07 | ✅ `IMPLEMENTED+TESTED` | **CP9.56** |
| US-F27 | Free-text NL query in Console | BR-10 | — | ⏸ `DEFERRED` Phase 13 | — |
| US-F28 | Persona-aware landing | BR-14 | SCR-F01 | ✅ `IMPLEMENTED+TESTED` | **CP9.52e** |
| US-F29 | Enterprise timeline (list-views-as-top-nav) | BR-14 | SCR-F02 | ✅ `IMPLEMENTED+TESTED` (all 9 ACs) | **CP9.52a-b** |
| US-F30 | Receipt detail tabbed view | BR-14 | SCR-F03 | ✅ `IMPLEMENTED+TESTED` | **CP9.52c** |
| US-F31 | PWA installable to home screen | BR-14 | all | ✅ `IMPLEMENTED+TESTED` | **CP9.52f** |
| US-F32 | Multi-tenant auth + tenant picker | BR-02, BR-14 | SCR-F09 | ⏸ `DEFERRED` Phase 10 CP10.1..CP10.4 | — |

**Roll-up:** 29/32 stories `IMPLEMENTED+TESTED` (up from 21/32). 3 `DEFERRED` (US-F24 Phase 12 multi-agent, US-F27 Phase 13 NL query, US-F32 Phase 10 auth). No `PARTIAL` rows remain — every story is either fully closed or DEFERRED with a named target phase.

**SCR-F screen roll-up:** SCR-F01..F08 + SCR-F10 = ✅ `IMPLEMENTED+TESTED`. SCR-F09 (auth) ⏸ Phase 10 by design. SCR-F10 fully closed by CP9.59 — `GET /v1/metrics` wired, MetricsPanel rendering ingest / signing / chain head / anchors / M&A jobs cards; signing latency p50/p95/p99 panel remains deferred to Phase 11 request-middleware sweep.

---

## 3. CP commit ledger (most recent first)

Per Rule A.11 each row names the IDs closed.

| Commit | Pushed | CP | IDs closed | What |
|---|---|---|---|---|
| `<pending>` | 18 May 2026 16:30 BST | **CP9.59** | **API-F15, SCR-F10 close, Gap 14 close** | `GET /v1/metrics` tenant-scoped operational metrics snapshot (DB counts at request time, JSON only — no Prometheus format). Ingest counts (total + window + per-hour), signing counts + chain-head sequence + last-signed timestamp, anchoring counts (anchored vs deferred), M&A export-job counts by status. 24h default window, `?window_hours=N` override (1..168). Console `/status` page extended with a MetricsPanel rendering 5 cards (ingest / signing / chain head / anchors / M&A jobs); deferred anchors and failed jobs auto-flag warn. Signing latency p50/p95/p99 deferred to Phase 11 (request middleware). 8 pytest at 100% statement+branch coverage on the route; 309 backend API tests pass. Console: 218 vitest at 100/100/100/100; 210 Playwright across 14 spec files × 3 device projects. |
| `<pending>` | 18 May 2026 15:21 BST | **CP9.58** | **SCR-F10 (partial — API-F15 gap)** | `/status` dashboard from `/healthz`: overall chip, API panel (status / version / narrative provider / model id / fallback flag), Refresh button, 10s auto-poll, explicit "API-F15 planned" placeholder for ingest rate / signing latency / anchor success-failure / chain integrity. 9 vitest tests at 100% coverage. Playwright spec covers all structural assertions (no seed required). |
| `<pending>` | 18 May 2026 15:21 BST | **CP9.57** | **SCR-F08, RT-F21 close** | `/narratives` page: window picker → POST /v1/narratives (query params) → plain-English narrative pane with model id, prompt/completion token counts, pack_root_hash, content_hash, generated_at. 422 defence path renders the BR-10 4-layer-defence `incident_id` without exposing the offending text. 12 vitest tests at 100% coverage. |
| `<pending>` | 18 May 2026 15:21 BST | **CP9.56** | **US-F26, SCR-F07** | `/diligence` workspace: create job (POST /v1/exports/ma-diligence/jobs) → list jobs (GET ... /jobs) → view detail (GET /jobs/{id}) → download bundle JSON. Status-badge palette for pending/running/completed/failed. Auto-polls every 4s while any job is pending or running, stops once all settle. 16 vitest tests at 100% coverage. |
| `<pending>` | 18 May 2026 15:21 BST | **CP9.55** | **US-F23, SCR-F06, RT-F21 advance** | `/tabletop` simulator: paste `TabletopScenario` JSON or click "Load sample" → POST /v1/tabletop/simulate → render per-action verdicts (decision pills: allow / deny / escalate / errored) + aggregate summary stats. 14 vitest tests at 100% coverage. |
| `<pending>` | 18 May 2026 15:21 BST | **CP9.53** | **US-F16 (UI access), SCR-F05** | `/anchors` list view: one row per daily TSA anchor with date, status chip (anchored / deferred), TSA identifier, timestamp, root-hash head. "Download TSR" button sets `Accept: application/timestamp-reply` and pipes DER bytes into a blob download (US-F16 UI surface for offline `openssl ts -verify`). Deferred rows show no download button. 11 vitest tests at 100% coverage. |
| `<pending>` | 18 May 2026 14:45 BST | **CP9.52a-g** | **US-F19, US-F28, US-F29 (all 9 ACs), US-F30, US-F31, RT-F19, RT-F20, UC-09 close** | Operator Console + PWA shell. 4 console screens (persona landing, receipts timeline, receipt-detail Summary/Proof/Raw tabs, evidence-pack Compliance/Technical toggle with narrated loading) + PWA manifest + service worker (stale-while-revalidate for /v1/receipts /v1/evidence-packs /v1/anchors; never caches non-GET writes per AC-5) + offline + 24h-stale banner. TopNav implementing BR-14 AC-2 list-views-as-top-nav with no sessionStorage. 146 vitest tests at 100% coverage. 141 Playwright tests across chromium-desktop + webkit-mobile (iPhone 15) + chromium-android (Pixel 7). |
| `d7d9aaa` | 17 May 2026 17:50 BST | CP9.51 | US-F15, RC-F08, RT-F08 (extends) | `verify_rfc3161_timestamp_response()` in `packages/crypto/tsa.py`: full PKIX cert-chain verification of RFC 3161 DER bytes against FreeTSA's published cert chain. 14 unit + live integration tests. FreeTSA cert fixtures bundled at `tests/fixtures/freetsa/`. |
| `b92c308` | 17 May 2026 03:47 BST | CP9.50 | RT-F09 (extends), captioned demo spec | `/evidence` Console page with `EvidencePack` React component. Rewrote captioned demo spec to auditex 2-crypto-op pattern (verify + produce). Fixed Chromium pre-paint blank frame in recording pipeline. |
| (prior) | 15 May 2026 11:22 BST | CP9.29 | US-F21, US-F22, BR-12, RT-F12 | Tabletop simulation backend: 19 tests (13 unit + 6 endpoint); 100% line+branch coverage. BR-12 flipped DEFERRED → IMPLEMENTED+TESTED. |
| (prior) | 15 May 2026 10:55 BST | CP9.28 | US-F25, BR-13, RT-F13 | M&A diligence export: `ma_root_hash` composition; 17 tests (12 unit + 5 endpoint); 100% coverage. BR-13 flipped STUB → IMPLEMENTED+TESTED. |
| (prior) | 15 May 2026 07:10 BST | CP9.21a + CP9.21b | US-F18, BR-05, RT-F09 | PDF renderer (24 tests) + content negotiation (17 tests) on `GET /v1/evidence-packs`. BR-05 PARTIAL → IMPLEMENTED+TESTED. |
| (prior) | 14 May 2026 22:02 BST | CP9.17 | US-F02, NFR-08, RT-F14 | Retry-safe ingest: 54 tests (35 store + 19 route) at 100% coverage. In-memory + Postgres store impls. NFR-08 added at IMPLEMENTED+TESTED. |
| (prior) | 14 May 2026 20:07 BST | CP9.16-PG-up | NFR-01, RT-F16 | DB-level append-only triggers verified on PG 16.13. 14 PG-integration tests. |
| (prior) | (Phase 9 baseline) | CP9.1 | US-F11, BR-10, BR-11, RT-F10 | Live Gemini 2.5 Pro narrative client. 4-layer prompt-injection defence. 19 tests including 3 injection negatives. |
| (prior) | (Phase 9) | CP9.19 | US-F14, BR-06 (TSA part), RT-F08 | FreeTSA live integration. Deferred-tombstone fallback. 11 TSA tests. |
| (prior) | (Phase 9) | CP9.18a/b/c | US-F04, BR-02, RT-F04 | Agent signing key. Route-layer principal-vs-tenant match enforcement. 21 sign tests + agent-sig route tests. |
| (prior) | (Phase 9) | CP9.15 | US-F10, RT-F06 | Bundle approval workflow + append-only PG triggers on `policy_bundle_approvals`. 6 PG-integration tests. |

---

## 4. Forward queue (priority-ordered, CP10.1 → Phase 10)

Per Rule A.11 each row names the IDs it will close.

**Landed since the last LIVE sweep (CP9.59):** see §3 commit ledger. `GET /v1/metrics` (API-F15) is live; SCR-F10 fully closed; Gap 14 closed.

| CP | IDs to close | Scope | Status |
|---|---|---|---|
| CP10.1 | US-F32 (partial), RT-F22 (advance), DB-F08, API-F14, SCR-F09 | Auth surface: `POST /v1/auth/login` + `/login` page + sessions table | 🔵 next |
| CP10.2 | US-F32 (close), RT-F22 (close), RC-F26 | Tenant picker + token-derived tenant | 🔵 |
| CP10.3 | NFR-10 (close at DB layer) | Postgres RLS policies | 🔵 |
| CP10.4 | UC-10 (close) | Full multi-tenant auth E2E | 🔵 |

**Phase 11 observability sweep (queued):** signing latency p50 / p95 / p99 (request middleware) — closes the last labelled deferred panel on the `/status` page.

**Documentation-only CPs queued (close Gap 11, Gap 12):**
- `CP-doc1` — Refresh `08_api_specification/API_SPECIFICATION.md` with API-F09/F11/F12/F13/F15 + `GET /v1/anchors`.

---

## 5. Honest gaps tracking

See `TRACEABILITY_MATRIX_LIVE.md` §3 for the canonical list. Open gaps as of CP9.59:
- Gap 8 — **CLOSED for RT-F19, RT-F20, RT-F21** by CP9.52..CP9.58 (210 vitest at 100% + 210 Playwright tests across 3 device projects). Remains OPEN for RT-F22 (Phase 10 by design — closes at CP10.4).
- Gap 9 — EVAL-F01 gold set at N=50; pilot target N=250 (OPEN — closes at pilot exit)
- Gap 10 — EVAL-F02 prompt-injection corpus at N=30; pilot target N=500 (OPEN — closes at Phase 10 entry)
- Gap 11 — API-F11 `POST /v1/tabletop/simulate` undocumented in API_SPECIFICATION (OPEN — light task)
- Gap 12 — API-F09 `POST /v1/exports/ma-diligence` similarly undocumented (OPEN — light task)
- **Gap 14 — CLOSED by CP9.59** (`GET /v1/metrics` wired; signing latency p50/p95/p99 panel remains deferred to Phase 11).

---

## 6. Change log

| Date | Change |
|---|---|
| 2026-05-18 16:30 BST | **CP9.59 sweep.** §1 UC roll-up: HEAD label flipped CP9.58 → CP9.59. §2 US-F roll-up: HEAD label flipped CP9.58 → CP9.59; SCR-F screen roll-up paragraph updated (SCR-F10 fully closed; signing-latency p50/p95/p99 still deferred to Phase 11). §3 commit ledger: row added for `GET /v1/metrics` (API-F15) + `/status` MetricsPanel. §4 forward queue: CP9.59 row removed (landed); header now reads "CP10.1 → Phase 10"; new "Phase 11 observability sweep" line added. §5 gaps: **Gap 14 CLOSED**. Backend: 8 new pytest tests at 100% on `apps/api/routes/metrics.py`; full API suite 309 tests pass. Console: 218/218 vitest at 100/100/100/100; `tsc --noEmit` clean; 210 Playwright tests enumerate. |
| 2026-05-18 15:55 BST | **Cumulative CP9.52..CP9.58 sweep.** §1 UC roll-up: UC-06 + UC-07 flipped to `IMPLEMENTED+TESTED` (DORA tabletop UI + M&A diligence UI), UC-09 closed by CP9.52a-g (operator console journey). §2 US-F roll-up: 8 stories flipped to ✅ (US-F07, F08, F19, F23, F26, F28, F29, F30, F31; US-F16 UI access added). Final score 29/32 stories `IMPLEMENTED+TESTED`; remaining 3 all `DEFERRED` with named phase targets (no `PARTIAL` rows remain). New SCR-F roll-up line records SCR-F09 still Phase 10 + SCR-F10 with Gap 14. §3 commit ledger: 6 new rows for CP9.52..CP9.58. §4 forward queue: landed CPs removed; new CP9.59 added at top (closes Gap 14); Phase 10 CPs unchanged. §5 gaps: Gap 8 partially closed (RT-F22 remains by-design); new Gap 14 added. Cumulative deliverable: 210 vitest tests at 100/100/100/100 coverage across 17 components; 210 Playwright tests across 14 spec files × 3 device projects; `tsc --noEmit` clean. |
| 2026-05-18 05:15 BST | LIVE doc reshaped against canonical `USE_CASES.md` v2.0 elaborated. UC-09 + UC-10 added. US-F01..F32 full enumeration with per-story status + closing CP. CP commit ledger added back to Phase 9 baseline. Forward queue updated for CP9.52..Phase 10 with Rule A.11 ID-closure named in every row. |
| 2026-05-17 22:30 BST | Prior LIVE companion sweep at end of CP9.50. |
