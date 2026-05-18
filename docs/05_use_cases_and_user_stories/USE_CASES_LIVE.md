# Forensa — Use Cases & User Stories — LIVE Progress

**Doc:** 05b of 22 | **Companion to:** `USE_CASES.md` (canonical) | **Date stamp:** 2026-05-18 05:15 BST
**Status:** LIVE — updated after every dev commit before the next mini-sprint starts
**Last sweep:** 2026-05-18 05:15 BST after CP9.51 (`d7d9aaa`)
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

## 1. UC roll-up (HEAD CP9.51)

| UC | Subject | Stories | Status | Last commit |
|---|---|---|---|---|
| UC-01 | Regulator pack | US-F07, US-F17, US-F18, US-F19, US-F20 | `IMPLEMENTED+TESTED` (Compliance view UI PLANNED CP9.52) | `d7d9aaa` |
| UC-02 | Customer dispute | US-F03, US-F08, US-F17 | `IMPLEMENTED+TESTED` | (pre-CP9 baseline) |
| UC-03 | Multi-agent audit | US-F24 (deferred) | `PARTIAL` (single-agent works) | — |
| UC-04 | Policy drift | US-F11, US-F12 | `IMPLEMENTED+TESTED` | (Phase 9 narrative coverage) |
| UC-05 | Model deprecation | US-F01, US-F17 | `IMPLEMENTED+TESTED` in-process; AWS DEFERRED Phase 12 | `d7d9aaa` |
| UC-06 | DORA tabletop | US-F21, US-F22 | `IMPLEMENTED+TESTED` backend; UI `PLANNED` CP9.55 | `d7d9aaa` (CP9.29 anchor) |
| UC-07 | M&A diligence | US-F25 | `IMPLEMENTED+TESTED` backend; UI `PLANNED` CP9.56 | `d7d9aaa` (CP9.28 anchor) |
| UC-08 | Prompt injection | (rolled into narrative defence tests) | `IMPLEMENTED+TESTED` | `d7d9aaa` |
| **UC-09** | **Operator console journey** | **US-F28, US-F29, US-F30, US-F19** | **`PLANNED` CP9.52** | — |
| **UC-10** | **Multi-tenant auth** | **US-F32** | **`DEFERRED` Phase 10 CP10.1..CP10.4** | — |

**Roll-up:** 8 of 10 UCs `IMPLEMENTED+TESTED` at backend level; UC-09 PLANNED CP9.52; UC-10 DEFERRED Phase 10.

---

## 2. US-F roll-up (HEAD CP9.51)

| ID | Story | BR | SCR | Status | CP that closed it |
|---|---|---|---|---|---|
| US-F01 | Agent action ingested as signed Receipt | BR-01, BR-02 | — | ✅ `IMPLEMENTED+TESTED` | Phase 1 + CP9.18 |
| US-F02 | Retry-safe ingest | BR-01 / NFR-08 | — | ✅ `IMPLEMENTED+TESTED` | CP9.17 |
| US-F03 | Tenant signature verification | BR-02 | SCR-F03 | ✅ `IMPLEMENTED+TESTED` | Phase 2 |
| US-F04 | Agent identity signature | BR-02 | — | ✅ `IMPLEMENTED+TESTED` | CP9.18a/b/c |
| US-F05 | Reasoning capture in event | BR-03 | — | ✅ `IMPLEMENTED+TESTED` | Phase 1 |
| US-F06 | OTel GenAI envelope ingest | BR-01, BR-03 | — | ✅ `IMPLEMENTED+TESTED` (with named finding RC-F14 / IMP-F14) | Phase 1 |
| US-F07 | Receipt list view | BR-01 | SCR-F02 | 🟡 `PARTIAL` (table exists; full timeline CP9.52) | Phase 4 (basic) |
| US-F08 | Receipt detail with verification | BR-01, BR-06 | SCR-F03 | 🟡 `PARTIAL` (page exists; tabs CP9.52) | Phase 4 (basic) |
| US-F09 | Policy bundle snapshot at decision | BR-04 | — | ✅ `IMPLEMENTED+TESTED` | Phase 3 |
| US-F10 | Policy bundle approval workflow | BR-04 | — | ✅ `IMPLEMENTED+TESTED` | CP9.15 |
| US-F11 | Policy drift surfaced in narrative | BR-04, BR-10 | SCR-F08 | ✅ `IMPLEMENTED+TESTED` | CP9.1 |
| US-F12 | Policy replay never returns live state | BR-04 | — | ✅ `IMPLEMENTED+TESTED` | Phase 3 |
| US-F13 | Hash chain verifiable offline | BR-06 | — | ✅ `IMPLEMENTED+TESTED` | Phase 2 |
| US-F14 | Daily RFC 3161 anchor (FreeTSA) | BR-06 | SCR-F05 | ✅ `IMPLEMENTED+TESTED` | CP9.19 |
| US-F15 | Cert-chain verification of TSR | BR-06 | — | ✅ `IMPLEMENTED+TESTED` | **CP9.51** `d7d9aaa` |
| US-F16 | Raw TSR DER bytes downloadable | BR-06 | SCR-F05 | ✅ `IMPLEMENTED+TESTED` | CP9.27 |
| US-F17 | JSON-LD evidence pack | BR-05 | SCR-F04 | ✅ `IMPLEMENTED+TESTED` | Phase 6 |
| US-F18 | Regulator-grade PDF | BR-05 | SCR-F04 | ✅ `IMPLEMENTED+TESTED` | CP9.21a + CP9.21b |
| US-F19 | Evidence pack Compliance view | BR-05, BR-14 | SCR-F04 | 🔵 `PLANNED` | CP9.52d |
| US-F20 | Offline pack verification | BR-05, BR-06 | — | ✅ `IMPLEMENTED+TESTED` | Phase 6 |
| US-F21 | Tabletop drill via API | BR-12 | — | ✅ `IMPLEMENTED+TESTED` | CP9.29 |
| US-F22 | Tabletop replay window | BR-12 | — | ✅ `IMPLEMENTED+TESTED` | CP9.29 |
| US-F23 | Tabletop UI in Console | BR-12, BR-14 | SCR-F06 | 🔵 `PLANNED` CP9.55 | — |
| US-F24 | LangGraph multi-agent capture | BR-07 | — | ⏸ `DEFERRED` Phase 12 | — |
| US-F25 | M&A diligence export bundle | BR-13 | — | ✅ `IMPLEMENTED+TESTED` | CP9.28 |
| US-F26 | M&A diligence UI in Console | BR-13, BR-14 | SCR-F07 | 🔵 `PLANNED` CP9.56 | — |
| US-F27 | Free-text NL query in Console | BR-10 | — | ⏸ `DEFERRED` Phase 13 | — |
| US-F28 | Persona-aware landing | BR-14 | SCR-F01 | 🔵 `PLANNED` CP9.52e | — |
| US-F29 | Enterprise timeline (list-views-as-top-nav) | BR-14 | SCR-F02 | 🔵 `PLANNED` CP9.52a/b | — |
| US-F30 | Receipt detail tabbed view | BR-14 | SCR-F03 | 🔵 `PLANNED` CP9.52c | — |
| US-F31 | PWA installable to home screen | BR-14 | all | 🔵 `PLANNED` CP9.52f | — |
| US-F32 | Multi-tenant auth + tenant picker | BR-02, BR-14 | SCR-F09 | ⏸ `DEFERRED` Phase 10 CP10.1..CP10.4 | — |

**Roll-up:** 21/32 stories `IMPLEMENTED+TESTED`, 2 `PARTIAL` (US-F07, US-F08 — backend done, full UX in CP9.52), 6 `PLANNED` CP9.52..CP9.58, 3 `DEFERRED` (US-F24 Phase 12, US-F27 Phase 13, US-F32 Phase 10).

---

## 3. CP commit ledger (most recent first)

Per Rule A.11 each row names the IDs closed.

| Commit | Pushed | CP | IDs closed | What |
|---|---|---|---|---|
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

## 4. Forward queue (priority-ordered, CP9.52..Phase 10)

Per Rule A.11 each row names the IDs it will close.

| CP | IDs to close | Scope | Status |
|---|---|---|---|
| CP9.52a | US-F29 AC-1..AC-4, RT-F19 (advance) | `/receipts` list view: cursor pagination + filters + URL-query + sortable cols | 🔵 next |
| CP9.52b | US-F29 AC-5..AC-9, RT-F19 (close) | List view polish: chips, skeletons, empty/error, hash-collapsed | 🔵 |
| CP9.52c | US-F30 | Receipt detail Summary/Proof/Raw tabs | 🔵 |
| CP9.52d | US-F19 | `/evidence` Compliance view toggle | 🔵 |
| CP9.52e | US-F28 | Persona-aware landing on `/` | 🔵 |
| CP9.52f | US-F31, RT-F20 | PWA `manifest.json` + service worker + offline read shell | 🔵 |
| CP9.52g | TEST-F30..F35, RT-F19/RT-F20 closing tests | Playwright UI-driving E2E for SCR-F01..F04 | 🔵 |
| CP9.53 | SCR-F05 (anchors list view), US-F16 (UI access) | `/anchors` list | 🔵 |
| CP9.55 | US-F23, SCR-F06, RT-F21 (advance) | `/tabletop` page | 🔵 |
| CP9.56 | US-F26, SCR-F07 | `/diligence` workspace | 🔵 |
| CP9.57 | SCR-F08, RT-F21 (close) | `/narratives` page | 🔵 |
| CP9.58 | SCR-F10 | `/status` ops dashboard | 🔵 |
| CP10.1 | US-F32 (partial), RT-F22 (advance), DB-F08, API-F14, SCR-F09 | Auth surface: `POST /v1/auth/login` + `/login` page + sessions table | 🔵 |
| CP10.2 | US-F32 (close), RT-F22 (close), RC-F26 | Tenant picker + token-derived tenant | 🔵 |
| CP10.3 | NFR-10 (close at DB layer) | Postgres RLS policies | 🔵 |
| CP10.4 | UC-10 (close) | Full multi-tenant auth E2E | 🔵 |

---

## 5. Honest gaps tracking

See `TRACEABILITY_MATRIX_LIVE.md` §3 (Honest gaps tracking). Open gaps as of CP9.51:
- Gap 8 — Console-surface RT-F19..F22 Playwright UI-driving tests TEST-F30..F40 not yet green
- Gap 9 — EVAL-F01 gold set at N=50; pilot target N=250
- Gap 10 — EVAL-F02 prompt-injection corpus at N=30; pilot target N=500

---

## 6. Change log

| Date | Change |
|---|---|
| 2026-05-18 05:15 BST | LIVE doc reshaped against canonical `USE_CASES.md` v2.0 elaborated. UC-09 + UC-10 added. US-F01..F32 full enumeration with per-story status + closing CP. CP commit ledger added back to Phase 9 baseline. Forward queue updated for CP9.52..Phase 10 with Rule A.11 ID-closure named in every row. |
| 2026-05-17 22:30 BST | Prior LIVE companion sweep at end of CP9.50. |
