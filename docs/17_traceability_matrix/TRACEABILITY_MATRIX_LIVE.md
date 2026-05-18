# Forensa — Traceability Matrix — LIVE Progress

**Doc:** 17b of 22 | **Companion to:** `TRACEABILITY_MATRIX.md` (canonical) | **Date stamp:** 2026-05-18 05:15 BST
**Status:** LIVE — updated after every dev commit before the next mini-sprint starts
**Last sweep:** 2026-05-18 05:15 BST after CP9.51 (`d7d9aaa`)
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
| `d7d9aaa` | 2026-05-17 17:50 BST | **CP9.51** | **US-F15, RC-F08, RT-F08 extends** | `verify_rfc3161_timestamp_response()` in `packages/crypto/tsa.py`: full PKIX cert-chain verification of RFC 3161 DER bytes against FreeTSA's published cert chain. 14 unit + live integration tests. FreeTSA cert fixtures bundled at `tests/fixtures/freetsa/`. |
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

## 2. RT roll-up (HEAD CP9.51) — 22 rows

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
| **RT-F19** | 🔵 **`PLANNED` CP9.52** | — | TEST-F30..F35 planned | **Console list-views-as-top-nav** |
| **RT-F20** | 🔵 **`PLANNED` CP9.52** | — | TEST-F36..F38 planned | **PWA shell** |
| **RT-F21** | 🔵 **`PLANNED` CP9.55..CP9.57** | — | TEST-F39 planned | **Tabletop / M&A / Narrative Console UI** |
| **RT-F22** | ⏸ **`DEFERRED` Phase 10 CP10.1..CP10.4** | — | TEST-F40 planned | **Multi-tenant auth** |

**Roll-up at HEAD CP9.51:** 16 ✅ + 2 ⏸ (by design) + 4 🔵 (CP9.52..Phase 10) = 22 / 22 accounted for.

**BR scoreboard:** 10/13 BR-01..BR-13 `IMPLEMENTED+TESTED`. BR-14 PARTIAL (3 console screens at MVP; CP9.52 closes for v1.x).

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
| **Gap 8** | Console-surface RTs (RT-F19..F22) introduced; Playwright UI-driving tests TEST-F30..F40 not green | **OPEN** | CP9.52..Phase 10 commits land |
| **Gap 9** | EVAL-F01 gold set N=50 today; pilot target N=250 | **OPEN** | Pilot exit |
| **Gap 10** | EVAL-F02 prompt-injection corpus N=30 today; pilot target N=500 | **OPEN** | Phase 10 entry |
| **Gap 11** | API-F11 `POST /v1/tabletop/simulate` not yet exposed in `08_api_specification/API_SPECIFICATION.md` (CP9.29 backend shipped without canonical API doc update) | **OPEN** | API_SPECIFICATION refresh (light task) |
| **Gap 12** | API-F09 `POST /v1/exports/ma-diligence` similarly not in API_SPECIFICATION | **OPEN** | API_SPECIFICATION refresh |
| **Gap 13** | `NavLinks` / sessionStorage anti-pattern not yet in our codebase but the BR-14 AC-2 prohibition is in place pre-emptively | n/a (preventive, not a gap) | n/a |

---

## 4. Forward queue (CP9.52 → Phase 10) — per Rule A.11

| CP | IDs to close | Scope | Owner |
|---|---|---|---|
| **CP9.52a** | US-F29 AC-1..AC-4, RT-F19 advance | `/receipts` enterprise timeline: cursor pagination + filters + URL-query persistence + sortable columns | Tech Lead |
| **CP9.52b** | US-F29 AC-5..AC-9, RT-F19 close | List view polish: status chips, loading skeletons, empty/error, hash-collapsed | Tech Lead |
| **CP9.52c** | US-F30 | Receipt-detail Summary/Proof/Raw tabs | Tech Lead |
| **CP9.52d** | US-F19 | `/evidence` Compliance view toggle + narrated loading | Tech Lead |
| **CP9.52e** | US-F28 | Persona-aware landing on `/` | Tech Lead |
| **CP9.52f** | US-F31, RT-F20 | PWA manifest + service worker + offline read shell + 24h-stale banner | Tech Lead |
| **CP9.52g** | TEST-F30..F35 + TEST-F36..F38 | Playwright UI-driving + PWA tests | Tech Lead |
| CP9.53 | SCR-F05, US-F16 (UI access) | `/anchors` list view | Tech Lead |
| CP9.55 | US-F23, SCR-F06, RT-F21 advance | `/tabletop` page | Tech Lead |
| CP9.56 | US-F26, SCR-F07 | `/diligence` workspace | Tech Lead |
| CP9.57 | SCR-F08, RT-F21 close | `/narratives` page | Tech Lead |
| CP9.58 | SCR-F10 | `/status` dashboard | Tech Lead |
| CP10.1 | US-F32 partial, DB-F08, API-F14, SCR-F09, RT-F22 advance | Auth surface MVP | Tech Lead |
| CP10.2 | US-F32 close, RC-F26, RT-F22 close | Tenant picker + token-derived tenant | Tech Lead |
| CP10.3 | NFR-10 close at DB layer | Postgres RLS policies | Tech Lead |
| CP10.4 | UC-10 close | Full multi-tenant auth E2E | Tech Lead |

**Engineering-convenience CPs (will be named, do not advance scoreboard):**
- `CP9.52-tooling` — Vite/Next build config tweaks if needed for PWA
- `CP9.53-tooling` — CI runner config

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
| 2026-05-18 05:15 BST | LIVE doc reshaped against canonical `TRACEABILITY_MATRIX.md` v2.0 elaborated. Commit ledger extended back through Phase 9 baseline. RT roll-up extended to 22 rows (RT-F19..F22 new for Console / PWA / Console UI / multi-tenant auth). Honest-gaps tracking carries forward 7 closed gaps + 3 v2.0-new open gaps + 2 new API-spec-drift gaps (Gap 11, Gap 12 — lightweight to close). Rule A.11 locked at top with strict update-after-commit cadence rule restated. Forward queue named per Rule A.11. |
| 2026-05-17 17:50 BST | Prior sweep at end of CP9.51. |
