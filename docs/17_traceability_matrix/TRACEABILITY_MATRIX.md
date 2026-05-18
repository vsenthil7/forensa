# Forensa — Traceability Matrix

**Doc:** 17 of 22 | **Version:** v2.0 ELABORATED — 2026-05-18 05:15 BST
**Status:** authoritative against HEAD CP9.51
**Last status sweep:** 2026-05-18 05:15 BST after CP9.51 (`d7d9aaa` RFC 3161 cert-chain verification)
**Supersedes:** `_archive/TRACEABILITY_MATRIX_v1_20260514_22h02.md` — preserved verbatim
**Companion:** `TRACEABILITY_MATRIX_LIVE.md` — live commit ledger, mini-sprint status, forward queue

Every row cross-references BG / BR / US / SCR / API / DB / TEST / EVID / RC / IMP / EVAL identifiers per `BRD_IDENTIFIER_MAP.md`.

---

## 0. Rules — read this before editing

### 0.1 Rule A.10 (inherited)
Open this file + BRD.md + USE_CASES.md before each CP. CP selection driven by which RT-F\* / BR / US-F\* need closing.

### 0.2 Rule A.11 — CP ↔ requirement closure
Every CP commit must close (or advance) at least one named requirement ID. The CP commit message names the IDs. **This file (or `TRACEABILITY_MATRIX_LIVE.md`) records the CP commit against those IDs.** A CP that does not close any named ID is engineering-convenience-labelled (`CPx.y-tooling: ...`) and does NOT advance the requirement scoreboard here.

### 0.3 Update cadence
The LIVE companion is updated **immediately after every dev commit**, before the next mini-sprint starts. This canonical doc is re-swept at every CP that flips a status code (e.g. PARTIAL → IMPLEMENTED+TESTED) and at every Phase boundary. Both docs share Section 1 RT index row format; LIVE adds commit / test-passing / pushed columns.

---

## 1. Traceability Index — RT-F01..RT-F22 (12 columns, mendoraci shape)

| RT | Subject | BG | BR | UC | SCR | API | DB | TEST | EVID | RC | IMP | EVAL | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RT-F01 | Event ingest pipeline | BG-F01, BG-F02 | BR-01 | UC-01, UC-02, UC-05, UC-08 | (cross — backend) | API-F01 | DB-F01, DB-F02 | TEST-F01..F04 | EVID-F01 Receipt | RC-F01 idempotency missing → CP9.17 | IMP-F01 payload-size limit; IMP-F02 OTel traceparent | — | `IMPLEMENTED+TESTED` |
| RT-F02 | In-process throughput | BG-F02 | BR-01, BR-09 | UC-05 | — | API-F01 | DB-F01 | TEST-F05 load test 6452/sec | (rolls EVID-F01) | RC-F02 AWS topology absent | IMP-F09 Kafka + S3 pipeline | — | `IMPLEMENTED+TESTED` (in-process); AWS topology `DEFERRED` Phase 12 |
| RT-F03 | Reasoning capture (AER) | BG-F03 | BR-03 | UC-01, UC-08 | SCR-F03 | API-F01 | DB-F02 (event.reasoning) | TEST-F06 32 schema + 18 normaliser | (rolls EVID-F01) | RC-F14 normaliser conflates `forensa.reasoning` and `gen_ai.response.text` | IMP-F14 separate fields | — | `IMPLEMENTED+TESTED` with named finding |
| RT-F04 | Multi-party identity (tenant + agent sig) | BG-F02 | BR-02 | UC-02 | SCR-F03 (proof tab) | API-F01 | (event payload) | TEST-F07 21 sign + agent-sig tests | EVID-F01 Receipt | RC-F03 agent sig stub closed CP9.18 | IMP-F15 KMS-rooted DEK | — | `IMPLEMENTED+TESTED` (CP9.18a/b/c) |
| RT-F05 | Policy snapshot binding | BG-F03 | BR-04 | UC-01, UC-04, UC-08 | SCR-F03 (proof tab) | API-F01 | DB-F03 policy_bundle_approvals (append-only triggers) | TEST-F08 17 snapshot + 5 replay | (rolls EVID-F01) | RC-F04 live state leak risk closed by 5 tests | IMP-F16 OPA integration | — | `IMPLEMENTED+TESTED` |
| RT-F06 | Bundle approval workflow | BG-F03 | BR-04 | UC-04 | (admin SCR planned Phase 11) | (admin API planned Phase 11) | DB-F03 | TEST-F09 6 PG-integration | (cross EVID) | RC-F05 PG triggers verified on real PG 16.13 | IMP-F17 admin UI | — | `IMPLEMENTED+TESTED` (CP9.15) |
| RT-F07 | Hash chain primitive | BG-F02 | BR-06 (chain part) | UC-01 | SCR-F03 (proof tab) | (internal) | DB-F02 | TEST-F10 22 merkle property-based | EVID-F01 | RC-F06 chain not tree | IMP-F03 merkle tree (RFC 6962) for inclusion proofs | — | `IMPLEMENTED+TESTED` |
| RT-F08 | RFC 3161 TSA anchoring | BG-F02 | BR-06 (TSA part) | UC-01 | SCR-F05 | API-F08 `GET /v1/anchors`, `GET /v1/anchors/{id}` | DB-F04 timestamp_anchors | TEST-F11 11 TSA tests + 14 cert-chain tests (CP9.51) | EVID-F03 AnchorEvidence | RC-F07 TSA fail mode → deferred-tombstone; RC-F08 cert chain verification (CP9.51) | IMP-F12 second TSA fallback (Phase 11) | — | `IMPLEMENTED+TESTED` (CP9.19 + CP9.51) |
| RT-F09 | Regulator-grade export (JSON-LD + PDF) | BG-F01 | BR-05 | UC-01, UC-02, UC-07 | SCR-F04 | API-F07 `GET /v1/evidence-packs` (Accept: json-ld OR application/pdf) | DB-F02 (read), DB-F04 (read) | TEST-F12 72 evidence-pack tests (24 PDF renderer + 17 content-neg + 6 JSON-LD + 25 export) | EVID-F02 EvidencePack | RC-F09 PDF deterministic; RC-F10 X-Forensa-Root-Hash header for cross-check | IMP-F04 detached platform signature (Phase 11) | — | `IMPLEMENTED+TESTED` (CP9.21a/b) |
| RT-F10 | Live narrative + injection defence | BG-F06 | BR-10, BR-11 | UC-01, UC-04, UC-08 | SCR-F08 (planned CP9.57) | API-F13 `POST /v1/narratives` | (no persist) | TEST-F13 19 narrative tests (incl 3 injection negatives) | EVID-F06 Narrative | RC-F11 4-layer defence structural + RC-F12 SDK migration | IMP-F11 semantic hallucination guardrail (Phase 12) | EVAL-F01, EVAL-F02 | `IMPLEMENTED+TESTED` (CP9.1 + CP9.20) |
| RT-F11 | Receipt list pagination | BG-F04 | BR-01 | UC-01 | SCR-F02 | API-F05 `GET /v1/receipts` | DB-F02 (read) | TEST-F14 cursor pagination integration | (rolls EVID-F01) | RC-F13 cursor encoding (base64url) | IMP-F18 OpenSearch backend (Phase 12) | — | `IMPLEMENTED+TESTED` (cursor); OpenSearch backend `DEFERRED` |
| RT-F12 | Tabletop simulation | BG-F03 | BR-12 | UC-06 | SCR-F06 (planned CP9.55) | API-F11 `POST /v1/tabletop/simulate`, API-F12 `POST /v1/tabletop/replay-window` | (no persist) | TEST-F15 19 tests (13 unit + 6 endpoint) | EVID-F05 TabletopResult | RC-F15 tabletop diff report deferred | IMP-F19 tabletop diff (Phase 12) | — | `IMPLEMENTED+TESTED` (CP9.29) |
| RT-F13 | M&A diligence export | BG-F05 | BR-13 | UC-07 | SCR-F07 (planned CP9.56) | API-F09 `POST /v1/exports/ma-diligence`, API-F10 jobs endpoints | DB-F05 ma_export_jobs | TEST-F16 17 tests (12 unit + 5 endpoint) | EVID-F04 MaDiligenceExport | RC-F16 async-job mode deferred | IMP-F05 ma-export-detached-platform-signature; IMP-F06 ma-export-encryption-at-rest; IMP-F20 ma-export-async-job | — | `IMPLEMENTED+TESTED` (CP9.28) |
| RT-F14 | Retry-safe ingest (idempotency) | BG-F02 | BR-01 / NFR-08 | UC-01, UC-05 | (cross — backend) | API-F01 | DB-F06 idempotency_records | TEST-F17 54 tests (35 store + 19 route) | (cross EVID) | RC-F17 in-memory default; Postgres store wired (CP9.17) | IMP-F23 cleanup cron; IMP-F24 production-wiring PostgresIdempotencyStore | — | `IMPLEMENTED+TESTED` (CP9.17) |
| RT-F15 | Multi-tenant isolation | BG-F02 | NFR-10 | all | all SCR-F\* | all API-F\* | tenant_id RLS on all tables | TEST-F18 cross-tenant 403/404 tests per route | (cross EVID) | RC-F18 404-not-403 to avoid bundle-id leak | IMP-F25 row-level security DB enforcement Phase 11 | — | `IMPLEMENTED+TESTED` |
| RT-F16 | PG triggers + partial UNIQUE | BG-F02 | BR-01 / NFR-01 | UC-01 | — | (internal) | DB-F03, DB-F07 (migrations) | TEST-F19 14 PG-integration tests | (rolls EVID-F01) | RC-F19 PG 16.13 verified | — | — | `IMPLEMENTED+TESTED` (CP9.16) |
| RT-F17 | LangGraph multi-agent provenance | BG-F06 | BR-07 | UC-03, UC-08 | (future SCR) | (future API) | (future DB) | (future) | (future EVID) | — | IMP-F07 LangGraph adapter Phase 12 | — | `DEFERRED` Phase 12 |
| RT-F18 | Omniverse physical replay | BG-F06 | BR-08 | (out) | (future) | (future) | — | — | — | — | IMP-F08 Phase 13 stretch | — | `DEFERRED` Phase 13 |
| **RT-F19** | **Operator Console — enterprise list views (NEW v2.0)** | **BG-F04** | **BR-14** | **UC-09** | **SCR-F01, SCR-F02 (full), SCR-F03 (tabs), SCR-F04 (Compliance view), SCR-F05, SCR-F08, SCR-F10** | **API-F05, API-F06, API-F07, API-F08, API-F13** | **(read-side only)** | **TEST-F30..F35 Playwright UI-driving E2E (planned)** | **(presents EVID-F01..F06)** | **RC-F20 list-views-as-top-nav pattern (mendoraci CP-9 inspired); RC-F21 no sessionStorage shortcuts** | **IMP-F26 timeline status chips; IMP-F27 receipt-detail tabs; IMP-F28 Compliance view toggle** | **—** | **`PLANNED` CP9.52** |
| **RT-F20** | **PWA installable shell (NEW v2.0)** | **BG-F04** | **BR-14** | **UC-09** | **all SCR-F\* with offline-aware affordances** | **(client-side service worker)** | **(client cache)** | **TEST-F36..F38 PWA install + offline-shell tests** | **—** | **RC-F22 service-worker scope; RC-F23 offline read-only mode** | **IMP-F29 install prompt UX; IMP-F30 24h-stale-warning** | **—** | **`PLANNED` CP9.52 (alongside RT-F19)** |
| **RT-F21** | **Tabletop / M&A / Narrative Console UI (NEW v2.0)** | **BG-F04** | **BR-12, BR-13, BR-10, BR-14** | **UC-06, UC-07, UC-04** | **SCR-F06, SCR-F07, SCR-F08** | **API-F11, API-F12, API-F09, API-F10, API-F13** | **DB-F05** | **TEST-F39 Playwright per-screen E2E (planned)** | **EVID-F04, EVID-F05, EVID-F06** | **RC-F24 list-views convention applies to tabletop runs, M&A jobs, narratives** | **IMP-F31 tabletop drill UI; IMP-F32 M&A workspace; IMP-F33 narrative viewer** | **EVAL-F01** | **`PLANNED` CP9.55..CP9.57** |
| **RT-F22** | **Multi-tenant auth surface (NEW v2.0)** | **BG-F02, BG-F04** | **BR-02, BR-14** | **UC-10** | **SCR-F09, tenant picker in SCR-F01** | **API-F14 `POST /v1/auth/login`** | **DB-F08 sessions (planned)** | **TEST-F40 auth integration + login E2E** | **—** | **RC-F25 SSO + bearer-token fallback; RC-F26 tenant-id-from-token replaces env-var** | **IMP-F34 SCIM; IMP-F35 SAML; IMP-F36 tenant picker UX** | **—** | **`DEFERRED` Phase 10 CP10.1..CP10.4** |

**Roll-up (HEAD CP9.51):**
- 16 of 22 RT rows `IMPLEMENTED+TESTED`
- 2 of 22 `DEFERRED` by design (RT-F17 LangGraph Phase 12, RT-F18 Omniverse Phase 13)
- 4 of 22 `PLANNED` for CP9.52+ (RT-F19 Console list-views, RT-F20 PWA, RT-F21 Console UI for tabletop/M&A/narrative, RT-F22 multi-tenant auth)
- 0 `PARTIAL` at RT-level (RT-F02 records the BR-09 PARTIAL state — in-process throughput proven, AWS topology Phase 12)

---

## 2. BG → BR Contribution

See `BRD.md` §6.2 for the full BG → BR weighted contribution matrix.

---

## 3. BR → US → SCR → API Mapping (mendoraci shape)

| BR | Representative US | SCR | API | Acceptance anchor | Edge case | Negative path | Exit gate |
|---|---|---|---|---|---|---|---|
| BR-01 | US-F01, US-F02 | SCR-F02 | API-F01 | 201 with integrity_ok=true | Concurrent sequence races | Idempotency violation → 409 | TEST-F01..F04 |
| BR-02 | US-F03, US-F04 | SCR-F03 | API-F01 (sig fields) | Tenant + agent sig verifiable | Key rotation mid-window | Cross-tenant sig → 403 | TEST-F07 21 sign tests |
| BR-03 | US-F05, US-F06 | SCR-F03 | API-F01 (Event schema) | reasoning structured | Non-LLM events with null reasoning | Malformed reasoning → 422 | TEST-F06 32 schema + 18 normaliser |
| BR-04 | US-F09, US-F10, US-F12 | SCR-F03 | API-F01 + (admin SCR planned) | policy_snapshot_id binds | Live-state leak | Live state returned in replay → test fail | TEST-F08 17 snapshot + 5 replay |
| BR-05 | US-F17, US-F18, US-F19, US-F20 | SCR-F04 | API-F07 | JSON-LD + PDF same root_hash | Empty scope window | Naive tz / inverted scope → 422 | TEST-F12 72 evidence-pack |
| BR-06 | US-F13, US-F14, US-F15, US-F16 | SCR-F05 | API-F08 | TSA anchor daily + cert chain verifiable | TSA outage | Forged TSR → cert verify reject | TEST-F10 22 + TEST-F11 25 |
| BR-07 | US-F24 (deferred) | (future) | (future) | LangGraph capture | — | — | DEFERRED |
| BR-08 | (deferred) | (future) | — | Omniverse replay | — | — | DEFERRED |
| BR-09 | (covered by US-F01 in-process) | — | API-F01 | 6452/sec measured | — | — | TEST-F05 load test + AWS topology DEFERRED |
| BR-10 | US-F11, US-F27 (deferred) | SCR-F08 (planned) | API-F13 | Plain-English narrative + 4-layer defence | Long window | Injection attempt → 422 + incident_id | TEST-F13 19 narrative |
| BR-11 | (rolled into BR-10 stories) | SCR-F08 | API-F13 | Counterfactual narrative | Hallucination | Semantic guardrail fires (deferred IMP-F11) | TEST-F13 |
| BR-12 | US-F21, US-F22, US-F23 | SCR-F06 (planned) | API-F11, API-F12 | Scenario echo + verdicts + summary | Empty actions | Empty actions list → 422 | TEST-F15 19 tabletop |
| BR-13 | US-F25, US-F26 | SCR-F07 (planned) | API-F09, API-F10 | ma_root_hash binds all packs | >366 day scope | Scope >366 days → 413 | TEST-F16 17 ma-export |
| **BR-14** | **US-F28, US-F29, US-F30, US-F31, US-F32** | **SCR-F01..F10** | **API-F05, F06, F07, F08, F13, F11, F12, F09, F10, F14 (cross)** | **List-views-as-top-nav; PWA installable; auth gate** | **Offline stale cache; PWA install dismissal** | **Cross-tenant deep link → 404** | **TEST-F30..F40 (planned CP9.52..CP10.4)** |

---

## 4. API → DB → Evidence Mapping (mendoraci shape)

| API | Verb / path | Request schema | Response | DB writes | Evidence emitted | Idempotency | Timeout / SLO |
|---|---|---|---|---|---|---|---|
| API-F01 | `POST /v1/events` | Event | EventCreatedResponse | DB-F02 receipts (atomic with DB-F01 event, DB-F03 policy_snapshot ref), DB-F06 idempotency_records | EVID-F01 Receipt | `Idempotency-Key` header REQUIRED; dedupe 24h (in-memory) or configurable (Postgres) | 5s soft, 15s hard |
| API-F05 | `GET /v1/receipts` | query params (tenant_id, limit, offset, before, after) | ReceiptListResponse (cursor) | (read DB-F02) | (rolls EVID-F01) | n/a (read) | 2s |
| API-F06 | `GET /v1/receipts/{id}` | path id | ReceiptDetail | (read DB-F02) | (rolls EVID-F01) | n/a (read) | 2s |
| API-F07 | `GET /v1/evidence-packs` | query (tenant_id, scope_start, scope_end) | JSON-LD pack OR application/pdf | (read DB-F02, DB-F04) | EVID-F02 EvidencePack | n/a (deterministic over input) | 30s; 8s p95 |
| API-F08 | `GET /v1/anchors`, `GET /v1/anchors/{id}` | query / path | AnchorList / AnchorEvidence (Accept: application/json or application/timestamp-reply) | (read DB-F04) | EVID-F03 AnchorEvidence | n/a | 5s |
| API-F09 | `POST /v1/exports/ma-diligence` | MaDiligenceRequest | MaDiligenceExport | DB-F05 ma_export_jobs (optional, async mode planned) | EVID-F04 MaDiligenceExport | unique per (tenant_id, scope_start, scope_end) | 60s; async mode planned IMP-F20 |
| API-F10 | `POST /v1/exports/ma-diligence/jobs`, `GET .../jobs/{id}`, `GET .../jobs` | per spec | per spec | DB-F05 | EVID-F04 | n/a | 5s |
| API-F11 | `POST /v1/tabletop/simulate` | TabletopScenario | TabletopResult | (no persist) | EVID-F05 TabletopResult | unique per scenario.name+tenant_id+bundle_id within request | 30s |
| API-F12 | `POST /v1/tabletop/replay-window` | ReplayRequest | ReplayResult | (read-only on ledger; no persist) | EVID-F05 | unique per window+bundle | 30s |
| API-F13 | `POST /v1/narratives` | NarrativeRequest | NarrativeResponse | (no persist; live Gemini 2.5 Pro client) | EVID-F06 Narrative | unique per window+bundle | 60s (LLM-bound) |
| **API-F14** | **`POST /v1/auth/login` (planned Phase 10)** | LoginRequest | LoginResponse + cookie | DB-F08 sessions (planned) | — | unique per (tenant_id, principal) | 5s |
| **API-F15** | **`GET /v1/metrics` (planned)** | — | metrics | (read) | — | n/a | 2s |

---

## 5. DB Schema → Migration → Test Mapping

| DB-F | Entity | Migration(s) | Tested in | Notes |
|---|---|---|---|---|
| DB-F01 | events | initial Phase 1 + 20260514_1744 bundle_approval_workflow | TEST-F01..F04 | parent of Receipt |
| DB-F02 | receipts | initial Phase 1 + PG triggers (CP9.16-PG-up) | TEST-F01..F04, TEST-F19 | append-only at app + PG layer |
| DB-F03 | policy_bundle_approvals | 20260514_1744 + append-only triggers | TEST-F09 6 PG-integration | UPDATE/DELETE blocked at DB |
| DB-F04 | timestamp_anchors | 20260515_0018 | TEST-F11 25 anchor tests | per-day RFC 3161 anchor |
| DB-F05 | ma_export_jobs | 20260515_1500 | TEST-F16 17 ma-export | optional async (sync mode default) |
| DB-F06 | idempotency_records | 20260514_2120 | TEST-F17 54 idempotency | composite (tenant_id, key) PK + 4 CHECK constraints |
| DB-F07 | agent_signatures | 20260514_2120_agent_signature (rolled into 20260514_2120) | TEST-F07 21 sign | CP9.18b |
| DB-F08 | sessions (planned Phase 10) | (future migration) | (future TEST-F40) | RT-F22 multi-tenant auth |

---

## 6. Test Coverage Map (TEST-F01..F40)

| TEST-F | Family | Test count | Layer | Status |
|---|---|---|---|---|
| TEST-F01..F04 | Ingest happy/422/401/idempotency | varies | pytest unit + integration | ✅ |
| TEST-F05 | Load test 6452/sec | 2 functional | scripts/load_test.py | ✅ |
| TEST-F06 | Schema + OTel normaliser | 50 (32+18) | pytest unit | ✅ |
| TEST-F07 | Signature + agent-sig | 21 | pytest unit + integration | ✅ |
| TEST-F08 | Snapshot + replay | 22 (17+5) | pytest integration | ✅ |
| TEST-F09 | Bundle approval triggers | 6 | tests/integration PG | ✅ |
| TEST-F10 | Merkle chain property tests | 22 | pytest property-based (hypothesis) | ✅ |
| TEST-F11 | RFC 3161 TSA tests | 25 (11 base + 14 cert-chain CP9.51) | pytest unit + live integration | ✅ |
| TEST-F12 | Evidence pack (JSON-LD + PDF) | 72 (24 PDF + 17 content-neg + 6 JSON-LD endpoint + 25 export) | pytest unit + integration | ✅ |
| TEST-F13 | Narrative + injection defence | 19 (16 + 3 negative) | pytest unit + integration | ✅ |
| TEST-F14 | Receipt list cursor pagination | varies | pytest integration | ✅ |
| TEST-F15 | Tabletop | 19 (13 unit + 6 endpoint) | pytest unit + integration | ✅ |
| TEST-F16 | M&A export | 17 (12 unit + 5 endpoint) | pytest unit + integration | ✅ |
| TEST-F17 | Idempotency | 54 (35 store + 19 route) | pytest unit + integration | ✅ |
| TEST-F18 | Cross-tenant 403/404 | per-route | pytest integration | ✅ |
| TEST-F19 | PG triggers + partial UNIQUE | 14 | tests/integration PG | ✅ |
| TEST-F20..F29 | (Reserved for future BR-07/BR-08/BR-09-AWS) | — | — | DEFERRED |
| **TEST-F30..F35** | **Console list-views-as-top-nav E2E** | **planned ~30 cases** | **Playwright UI-driving** | **`PLANNED` CP9.52** |
| **TEST-F36..F38** | **PWA install + offline shell** | **planned ~15 cases** | **Playwright + manual cross-browser** | **`PLANNED` CP9.52** |
| **TEST-F39** | **Tabletop/M&A/Narrative Console E2E** | **planned ~24 cases** | **Playwright** | **`PLANNED` CP9.55..CP9.57** |
| **TEST-F40** | **Auth + login + tenant picker E2E** | **planned ~10 cases** | **Playwright + auth integration** | **`PLANNED` Phase 10 CP10.1..CP10.4** |

**Existing test count at HEAD CP9.51:** 914+ default tests (per BRD change log). New planned tests for CP9.52+: ~79 additional Playwright cases.

---

## 7. Evidence Artefact Index (EVID-F01..F06)

| EVID-F | Artefact | Bound by | Produced by API | Verifiable offline? |
|---|---|---|---|---|
| EVID-F01 | Receipt | receipt_hash + signature_b64 | API-F01 | Yes — `verify_chain()` |
| EVID-F02 | EvidencePack | root_hash | API-F07 | Yes — `verify_evidence_pack()` |
| EVID-F03 | AnchorEvidence | TSR DER bytes + cert chain | API-F08 | Yes — `openssl ts -verify` or `verify_rfc3161_timestamp_response()` |
| EVID-F04 | MaDiligenceExport | ma_root_hash | API-F09 | Yes — `verify_ma_diligence_export()` |
| EVID-F05 | TabletopResult | (not persisted; one-shot) | API-F11, API-F12 | Returned to caller; no chain mutation |
| EVID-F06 | Narrative | (not persisted; LLM output) | API-F13 | Caller can replay deterministically given same prompt + model version |

Full spec for EVID-F02 at `12_evidence_pack_spec/EVIDENCE_PACK_SPEC.md`.

---

## 8. Persona → RT Mapping

| Persona | RTs they exercise |
|---|---|
| P-COMP Compliance Officer | RT-F01, RT-F05, RT-F09, RT-F10, RT-F19, RT-F20, RT-F21 |
| P-AUD Internal Auditor | RT-F03, RT-F04, RT-F05, RT-F07, RT-F08, RT-F11, RT-F19 |
| P-SEC Security Engineer | RT-F03, RT-F04, RT-F10, RT-F12, RT-F17 (deferred), RT-F21 |
| P-COUNSEL General Counsel | RT-F09, RT-F13, RT-F19 |
| P-PLAT AI Platform Owner | RT-F01, RT-F02, RT-F14, RT-F15, RT-F16, RT-F20, RT-F22 |
| P-ACQ M&A Acquirer | RT-F13, RT-F21 |
| P-REG Regulator / external auditor | (consumer; verifies EVID-F02, EVID-F03, EVID-F04 offline) |

---

## 9. Sponsor → BR Mapping

| Sponsor | BRs primarily served | RT IDs |
|---|---|---|
| Veea Lobster Trap | BR-01, BR-04, BR-07 | RT-F01, RT-F05, RT-F17 (deferred) |
| Gemini 3 Pro (long context) | BR-11 | RT-F10 |
| Gemini 3 Pro (multimodal) | BR-03 (PDF binding) | RT-F03, RT-F09 |
| Gemini 3 Flash | BR-10 | RT-F10 |
| Google AI Studio | BR-05 (custom templates) | RT-F09 |
| AWS data pipeline | BR-09 (Phase 12) | RT-F02 (deferred for AWS topology) |
| LangGraph | BR-07 (deferred) | RT-F17 |
| MCP | BR-05 (auditor portal) | RT-F09 |
| OpenTelemetry GenAI | BR-01 (wire format) | RT-F01, RT-F03 |
| NVIDIA Omniverse + Isaac Sim | BR-08 (stretch, deferred) | RT-F18 |
| NVIDIA GR00T VLA | BR-03 (VLA reasoning eval) | RT-F03 |
| DT Consortium / XMPro | BR-08 (semantics) | RT-F18 |

---

## 10. Regulator → BR Mapping

| Framework | BRs | RT IDs |
|---|---|---|
| EU AI Act Article 12 | BR-01, BR-03, BR-04, BR-05, BR-06 | RT-F01, RT-F03, RT-F05, RT-F09, RT-F08 |
| EU AI Act Article 14 (human oversight) | BR-01, BR-04 | RT-F01, RT-F06 |
| EU AI Act Article 18 (10-year retention) | BR-01, BR-05 | RT-F01, RT-F09 |
| DORA Article 30 | BR-05, BR-12 | RT-F09, RT-F12 |
| NIST AI RMF | BR-01, BR-04, BR-05 | RT-F01, RT-F05, RT-F09 |
| ISO 42001 | BR-01, BR-04, BR-05 | RT-F01, RT-F05, RT-F09 |
| SOC 2 Type II | BR-01, BR-02, BR-06 | RT-F01, RT-F04, RT-F08 |
| HIPAA | BR-01, BR-05, BR-09 | RT-F01, RT-F09, RT-F02 |
| MAR / Reg FD | BR-01, BR-04, BR-05 | RT-F01, RT-F05, RT-F09 |
| GDPR Article 32 | BR-02, security arch | RT-F04 |
| GDPR Article 17 | (retention controls — cryptographic shredding DEFERRED Phase 13) | (future RT) |

---

## 11. NFR Coverage

| NFR | Status | BR linkage | Test layer | RT |
|---|---|---|---|---|
| NFR-01 Integrity/immutability | `IMPLEMENTED+TESTED` | BR-01, BR-06 | property-based + PG-integration (14 tests) | RT-F07, RT-F16 |
| NFR-02 Low-latency capture (p99 <5ms @10K/sec) | `PARTIAL` (in-process 6452/sec; AWS topology DEFERRED) | BR-01, BR-09 | scripts/load_test.py | RT-F02 |
| NFR-03 Encryption at rest + in transit | `DEFERRED` Phase 11 CP11.2 | (security arch) | integration | (cross) |
| NFR-04 On-prem / VPC | `DEFERRED` Phase 13 CP13.6 | (deploy) | Helm smoke | (cross) |
| NFR-05 Explainability | `IMPLEMENTED+TESTED` | BR-11 | integration | RT-F10 |
| NFR-06 Scalable search | `IMPLEMENTED+TESTED` (cursor); OpenSearch DEFERRED | BR-10 | pytest + Playwright | RT-F11 |
| NFR-07 Retention controls | `DEFERRED` (GDPR×append-only addressed Phase 13 CP13.2) | (data protection) | integration | (cross) |
| NFR-08 Retry-safe ingest | `IMPLEMENTED+TESTED` (CP9.17) | BR-01 | 54 tests at 100% coverage | RT-F14 |
| **NFR-09 Console accessibility (WCAG 2.1 AA)** | **`DEFERRED` Phase 11** | **BR-14** | **Axe + manual** | **RT-F19** |
| **NFR-10 Multi-tenant isolation** | **`IMPLEMENTED+TESTED`** | **BR-02 + cross** | **cross-tenant tests per route** | **RT-F15** |

---

## 12. Coverage Requirement

Every BR must have:
- At least one source file (code)
- At least one test (covering happy + failure paths)
- At least one CI run that passes
- At least one mention in evidence pack / demo
- **At least one US-F\* story (NEW in v2.0)**
- **At least one RT-F\* bundle (NEW in v2.0)**

At HEAD CP9.51: **every BR and every RT meets these gates** except BR-07 / BR-08 (DEFERRED, by design), BR-09 (PARTIAL, AWS topology Phase 12), and BR-14 (PARTIAL — three screens shipped at MVP level, CP9.52 closes the gap). The gaps are named, not hidden.

---

## 13. Forward Queue — IMP-F\* enhancements per RT

| RT | IMP-F items in queue | Phase |
|---|---|---|
| RT-F01 | IMP-F01 payload-size limit; IMP-F02 OTel traceparent | 12 |
| RT-F02 | IMP-F09 Kafka + S3 pipeline (full BR-09) | 12 |
| RT-F03 | IMP-F14 separate `forensa.reasoning` from `gen_ai.response.text` | 11 |
| RT-F04 | IMP-F15 KMS-rooted DEK | 11 |
| RT-F05 | IMP-F16 OPA integration for richer policy expressions | 12 |
| RT-F06 | IMP-F17 admin UI for bundle approval workflow | 11 |
| RT-F07 | IMP-F03 merkle tree (RFC 6962) for inclusion proofs | 12 |
| RT-F08 | IMP-F12 second TSA fallback | 11 |
| RT-F09 | IMP-F04 detached platform signature on pack | 11 |
| RT-F10 | IMP-F11 semantic hallucination guardrail | 12 |
| RT-F11 | IMP-F18 OpenSearch backend | 12 |
| RT-F12 | IMP-F19 tabletop diff report (sim vs actual) | 12 |
| RT-F13 | IMP-F05, IMP-F06, IMP-F20 (ma-export sig + at-rest enc + async-job) | 11/12 |
| RT-F14 | IMP-F23 cleanup cron; IMP-F24 production-wiring PostgresIdempotencyStore | 11 |
| RT-F15 | IMP-F25 row-level security DB enforcement | 11 |
| **RT-F19** | **IMP-F26 timeline status chips; IMP-F27 receipt-detail tabs; IMP-F28 Compliance view toggle** | **9.52** |
| **RT-F20** | **IMP-F29 install prompt UX; IMP-F30 24h-stale-warning** | **9.52** |
| **RT-F21** | **IMP-F31 tabletop drill UI; IMP-F32 M&A workspace; IMP-F33 narrative viewer** | **9.55..9.57** |
| **RT-F22** | **IMP-F34 SCIM; IMP-F35 SAML; IMP-F36 tenant picker UX** | **10** |

---

## 14. Honest gaps (named, not hidden)

| Gap | Description | Status |
|---|---|---|
| Gap 1 (closed) | Canonical traceability matrix stale at 14 May 22:02 | **CLOSED** — v2.0 swept to CP9.51 |
| Gap 2 (closed) | "Day 5/6" calendar narrative drift | **CLOSED** — replaced by CP-anchored phase plan in BRD §10 |
| Gap 3 (closed) | Canonical USE_CASES had 8 UCs but no numbered stories | **CLOSED** — US-F01..F32 added |
| Gap 4 (closed) | RT-IDs did not previously exist | **CLOSED** — RT-F01..F22 added |
| Gap 5 (closed) | BR-09 PARTIAL status not exposed in canonical | **CLOSED** — RT-F02 records the PARTIAL state explicitly |
| Gap 6 (closed) | Two RT-eligible streams had no parent BR | **CLOSED** — pagination rolled into RT-F11/BR-10; PG triggers rolled into RT-F16/BR-01 |
| Gap 7 (closed) | FreeTSA test fixture partially-documented | **CLOSED** — `tests/fixtures/freetsa/` bundled at CP9.51 with cert provenance |
| **Gap 8 (new, named for v2.0)** | Console-surface RTs (RT-F19..F22) introduced today; Playwright UI-driving E2E tests TEST-F30..F40 are planned, not green | **OPEN** — closes when CP9.52..Phase 10 commits land |
| **Gap 9 (new, named for v2.0)** | EVAL-F01 narrative quality gold set at N=50 today; pilot target N=250 | **OPEN** — closes by pilot exit |
| **Gap 10 (new, named for v2.0)** | EVAL-F02 prompt-injection defence corpus at N=30 today; pilot target N=500 | **OPEN** — closes by Phase 10 entry |

---

## 15. Change log

| Date | Change |
|---|---|
| 2026-05-18 05:15 BST | **v2.0 ELABORATED.** Extended RT index to 22 rows (RT-F19..F22 new for Console list-views / PWA / Console UI for tabletop+M&A+narrative / multi-tenant auth). Added 12-column index per mendoraci shape. Added API → DB → Evidence map (§4). Added DB schema → migration → test map (§5). Added Test coverage map TEST-F01..F40 (§6). Added Evidence Artefact Index EVID-F01..F06 (§7). Added Persona → RT (§8), Sponsor → BR + RT (§9), Regulator → BR + RT (§10), NFR coverage with RT cross-ref (§11). Added IMP-F\* forward queue per RT (§13). Closed 7 historical gaps; named 3 new for v2.0 (§14). Locked Rule A.11. v1 preserved at `_archive/TRACEABILITY_MATRIX_v1_20260514_22h02.md`. |
| 2026-05-14 22:02 | v1 last status sweep (CP9.16-PG-up + CP9.17). |
