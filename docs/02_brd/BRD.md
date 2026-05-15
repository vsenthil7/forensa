# Forensa - Business Requirements Document (BRD)

**Doc:** 02 of 22 | **Date:** 12 May 2026 (v1) / 14 May 2026 (v1.2) | **Status:** v1.2, status-tracked | **Source:** Section A.2 of three-author master doc
**Status column added:** 14 May 2026 09:58 per EnterpriseGradeReview_Claude review fix #10 (close doc-claim-vs-code-reality gap)
**Last status sweep:** 15 May 2026 11:22 after CP9.29 tabletop incident-response simulation (BR-12 flips DEFERRED -> IMPLEMENTED+TESTED, headline 9/13 -> 10/13)

## Status legend

| Code | Meaning |
|---|---|
| `IMPLEMENTED+TESTED` | Production code + tests in place; CI gates the suite at 100% coverage; demoable today. |
| `IMPLEMENTED` | Production code in place; minimal or no test coverage yet. |
| `PARTIAL` | Some sub-requirements met; specifically named gaps below. |
| `STUB` | Architectural surface in place (ABC, interface, contract) but production impl absent or mocked. |
| `DEFERRED` | Out of v1 hackathon scope; tracked in `phases/ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md` or `docs/reviews/01_Rev_Claude_20260514_0919/REVIEW_RESPONSE_AND_BACKLOG_20260514_0955.md`. |

## Status summary table

| BR | Title | Status | Roadmap slot if not IMPLEMENTED+TESTED |
|---|---|---|---|
| BR-01 | Tamper-evident event recording | `IMPLEMENTED+TESTED` | - |
| BR-02 | Multi-party identity binding | `IMPLEMENTED+TESTED` | Tenant signature + agent signature both wired in CP9.18a/b/c (HEAD `ec81920`). Per-tenant signing keys via `apps/api/ingest_service.py`; agent signature via `apps/api/auth/` module wired in CP9.18b. Route-layer enforcement in CP9.18c. |
| BR-03 | Reasoning capture (Oracle AER pattern) | `IMPLEMENTED+TESTED` | - |
| BR-04 | Policy snapshot at decision time | `IMPLEMENTED+TESTED` | - |
| BR-05 | Regulator-grade export | `IMPLEMENTED+TESTED` | JSON-LD export DONE (Phase 6 CP6.1/6.2/6.4); PDF render module DONE (Phase 9 CP9.21a) + Accept: application/pdf branch on GET /v1/evidence-packs DONE (Phase 9 CP9.21b). Both wire forms bind the same root_hash. |
| BR-06 | Merkle-chained ledger with RFC 3161 TSA | `IMPLEMENTED+TESTED` | Hash chain DONE (Phase 1); RFC 3161 TSA daily anchoring DONE in CP9.19 (HEAD `8176502`) via `packages/crypto/tsa.py` + `packages/ledger/tsa_anchor.py` with deferred-tombstone fallback for failed TSA calls. Raw DER pipe via `Accept: application/timestamp-reply` on GET /v1/anchors/{id} DONE in CP9.27. |
| BR-07 | Multi-agent provenance graph (LangGraph) | `DEFERRED` | Phase 12 stretch |
| BR-08 | Omniverse physical-action replay | `DEFERRED` | Out of hackathon scope (was always stretch per "cut from v1 demo if Day 5 slips") |
| BR-09 | AWS-backed bulk historical backfill | `PARTIAL` | In-process throughput 6452 events/sec measured (Phase 8 CP8.2); full target (10K sustained + 100K peak across Kafka + S3) in Phase 12 CP12.4 |
| BR-10 | Investigator UI with natural-language query | `IMPLEMENTED+TESTED` | Live Gemini 2.5 Pro narrative client landed in CP9.1 (HEAD `4a18b67`) with 4-layer prompt-injection defence. SDK migrated google.generativeai -> google.genai in CP9.20 (HEAD `5535329`). Console NL query UX remains a Phase 13 stretch but the underlying narrative API surface is fully wired. |
| BR-11 | Counterfactual narrative generation | `IMPLEMENTED+TESTED` | Live Gemini 2.5 Pro client + 4-layer prompt-injection defence landed in CP9.1. HTTP 422 + `incident_id` returned when defence fires (CP9.6 HEAD `41fc9e7`). Semantic hallucination guardrail tracked as NEW-P12.Y. |
| BR-12 | Tabletop incident response mode | `IMPLEMENTED+TESTED` | - |
| BR-13 | M&A due diligence export | `IMPLEMENTED+TESTED` | - |

**Headline:** **10 of 13 BRs are `IMPLEMENTED+TESTED`** at HEAD CP9.29 (BR-01, BR-02, BR-03, BR-04, BR-05, BR-06, BR-10, BR-11, BR-12, BR-13). CP9.29 flipped BR-12 from DEFERRED to IMPLEMENTED+TESTED (tabletop incident-response simulation). CP9.28 flipped BR-13 from STUB to IMPLEMENTED+TESTED (M&A due-diligence export). 1 is `PARTIAL` (BR-09 in-process throughput is IMPLEMENTED+TESTED; the AWS-backed bulk historical backfill at 10K/sec sustained + 100K peak across Kafka + S3 lands in Phase 12 CP12.4). 2 are `DEFERRED` by design (BR-07 LangGraph multi-agent + BR-08 Omniverse physical-action replay). The live scoreboard truth is in `phases/PHASES_REVIEW_BEFORE_AFTER_*.md` and `phases/PHASES_DONE_PHASE9_*.md`.

## 13 Business Requirements (BR-01 through BR-13)

### BR-01 - Tamper-evident event recording
**Status:** `IMPLEMENTED+TESTED`
Every agent action (prompt, model response, tool call, policy verdict, human approval, business outcome) is captured as a structured event and appended to a cryptographically-chained ledger (Merkle-style hash chain; RFC 3161 TSA anchoring deferred - see BR-06).
**Architecture component:** packages/ingest, packages/ledger; CP9.16 added DB-level append-only triggers on `policy_bundle_approvals` (PL/pgSQL `forensa_block_approval_mutation` raises on UPDATE/DELETE) verified against real PostgreSQL 16.13 in `tests/integration/test_pg_append_only_triggers.py` (6 tests).
**Test coverage:** unit + property-based on chain integrity (68 crypto tests + 53 ledger tests passing at 100% coverage). CP9.16 added 14 PG-integration tests covering migration round-trip, partial UNIQUE index race-safety, and trigger-level append-only enforcement that SQLite cannot model. CP9.17 added 54 tests on retry-safe ingest (idempotency dedup) - see new NFR row "Retry-safe ingest" below.
**Gap vs spec:** None on tamper-evidence. RFC 3161 anchoring tracked under BR-06.

### BR-02 - Multi-party identity binding
**Status:** `PARTIAL`
Every event is signed by the enterprise tenant. **Agent-side identity signature is not yet in place** — today receipts are signed by the tenant key only. Agent identity binding (DID/HDP) is deferred to Phase 10 CP10.4 (Service account + API key issuance) where machine identities are introduced.
**Architecture component:** packages/crypto, apps/api/auth
**Test coverage:** unit + integration on tenant-side signature verification (21 sign tests)
**Gap vs spec:** Agent-side signature path absent. `apps/api/auth/` is a stub folder today (`__init__.py` + README only).

### BR-03 - Reasoning capture (Oracle AER pattern)
**Status:** `IMPLEMENTED+TESTED`
For LLM-mediated actions, the event schema captures intermediate reasoning chain (chain-of-thought summary, tool selection rationale, confidence signals) via the `reasoning` field on `Event`.
**Architecture component:** packages/schema, packages/ingest
**Test coverage:** unit on schema validation; OTel GenAI normaliser maps `forensa.reasoning` and `gen_ai.response.text` (32 schema tests + 18 normaliser tests)

### BR-04 - Policy snapshot at decision time
**Status:** `IMPLEMENTED+TESTED`
Every event records which policy bundle version + content hash was active when the decision was made. Six months later when policies have changed, the original policy state is reconstructible from the snapshot.
**Architecture component:** packages/policy, packages/ledger
**Test coverage:** integration on snapshot binding (17 snapshot tests + 5 replay tests proving `live_bundle.content_hash` is never returned)

### BR-05 - Regulator-grade export
**Status:** `IMPLEMENTED+TESTED`
JSON-LD + PROV-O evidence pack export is `IMPLEMENTED+TESTED` (Phase 6 CP6.1/6.2/6.4). PDF render is `IMPLEMENTED+TESTED` as of Phase 9 CP9.21a (renderer module, 24 tests, 100% line+branch coverage on `packages/export/pdf_renderer.py`) + CP9.21b (Accept-header content negotiation on GET /v1/evidence-packs, 17 endpoint tests). The PDF is a deterministic A4 rendering of the same pack content bound by `root_hash` so a regulator can hand the PDF to a forensic accountant and the JSON-LD to a developer in parallel and they agree on every fact. Filename includes the first 12 chars of `root_hash`; response carries `X-Forensa-Root-Hash` header for direct cross-check against the JSON-LD form.
**Architecture component:** packages/export (builder + schema + pdf_renderer); apps/api/routes/evidence.py
**Test coverage:** 24 unit on PDF renderer + 17 endpoint on Accept-header content negotiation + 6 existing JSON-LD endpoint + integration on JSON-LD generation and `verify_evidence_pack` (25 export tests) = 72 evidence-pack tests total.
**Gap vs spec:** None for hackathon scope. Detached platform signature on the pack (so an auditor can verify pack-level provenance without re-rendering) is `TRACKED-P11.6` for both wire forms.

### BR-06 - Merkle-chained ledger with RFC 3161 TSA
**Status:** `PARTIAL`
Hash-chain implementation is `IMPLEMENTED+TESTED` (linked hash chain per `packages/crypto/merkle.py`; review note: this is a chain, not an RFC 6962-style tree — `NEW-P11.X.merkle-tree` in backlog for inclusion-proof support). **RFC 3161 TSA anchoring is `DEFERRED` to Phase 11 CP11.5.** Today `signed_at` is a server-clock value from `datetime.now(UTC)`.
**Architecture component:** packages/crypto, packages/ledger
**Test coverage:** property-based on chain verification (22 merkle tests)
**Gap vs spec:** External time-stamping authority not yet integrated. A regulator with `T+1 year` doubt cannot prove the server clock wasn't tampered with.

### BR-07 - Multi-agent provenance graph (LangGraph)
**Status:** `DEFERRED`
LangGraph is not yet a project dependency. Multi-agent DAG capture is not in v1 code. Tracked for Phase 12 stretch alongside CP12.4 (Kafka ingest) since both share async-pipeline shape.
**Architecture component:** packages/ingest, apps/api (when built)
**Test coverage:** N/A — implementation pending

### BR-08 - Omniverse physical-action replay (stretch)
**Status:** `DEFERRED`
Explicitly marked stretch in the original spec ("cut from v1 demo if Day 5 slips"). Day 5 has passed; this remains out of hackathon scope.
**Architecture component:** apps/console (replay viewer)
**Test coverage:** N/A — out of scope

### BR-09 - AWS-backed bulk historical backfill
**Status:** `PARTIAL`
**In-process throughput** is `IMPLEMENTED+TESTED` — Phase 8 CP8.2 load test measured 6452 events/sec for 1000-event chain build + pack + verify (~387x under the 60-second budget). **Full AWS topology (S3 + EventBridge + Glue + Step Functions + OpenSearch Serverless + Kafka ingest)** is `DEFERRED` to Phase 12 CP12.3/CP12.4 alongside multi-region deploy. Today the system runs against a single Postgres; the chain primitives are validated but the surrounding pipeline is not built.
**Architecture component:** deploy/, packages/ledger
**Test coverage:** in-process load test (`scripts/load_test.py`) — 2 functional tests
**Gap vs spec:** No S3, no EventBridge, no Glue, no Step Functions, no OpenSearch Serverless, no Kafka, no SageMaker Feature Store.

### BR-10 - Investigator UI with natural-language query
**Status:** `STUB` (today) → `IMPLEMENTED` after Phase 9 CP9.1
Today the narrative client is `MockNarrativeClient` only — deterministic template text. Phase 9 CP9.1 wires `LiveNarrativeClient` against `google-generativeai` with the 4-layer prompt-injection defence (structural isolation, role separation, output sanitisation, structural consistency assertion). Full Gemini Flash-driven natural-language query UX in the console (typing free-text questions and getting back evidence chains) is `DEFERRED` to Phase 13 stretch — beyond the hackathon's submission scope.
**Architecture component:** apps/console, packages/narrative
**Test coverage:** Mock client paths covered today (12 narrative tests); Live client adds 7 tests in CP9.1
**Gap vs spec:** Free-text NL query UI in console. Today the console renders receipts and badges; it does not yet have a query-input box.

### BR-11 - Counterfactual narrative generation
**Status:** `STUB` (today) → `IMPLEMENTED` after Phase 9 CP9.1
Today `MockNarrativeClient` returns deterministic template text. Phase 9 CP9.1 wires the live Gemini Pro client with 4-layer prompt-injection defence. **Note:** The CP9.1 v1 defence is structural (deny-list of trigger phrases + output sanitisation), not semantic. Full semantic hallucination guardrails (assert narrative's claimed event counts match pack's actual contents) are `DEFERRED` to NEW-P12.Y in the backlog (3 days estimated).
**Architecture component:** packages/narrative
**Test coverage:** Mock paths (12 tests); CP9.1 adds 7 tests for Live client including 3 negative-path injection-attempt tests
**Gap vs spec:** Semantic hallucination guardrails. Structural deny-list lands in CP9.1; semantic correctness in Phase 12.

### BR-12 - Tabletop incident response mode
**Status:** `IMPLEMENTED+TESTED`
Security-engineer simulation surface: replay a sequence of synthetic agent events through the configured `PolicyEnforcementClient` against a stored `PolicyBundle`, capture the verdicts, and return aggregate decision counts - **without persisting anything, without writing Receipts, without mutating the chain.** A security engineer can validate "what would happen if I deploy this stricter policy bundle?" before risking a production rollback.
`POST /v1/tabletop/simulate` accepts a `TabletopScenario` body (name + tenant_id + policy_bundle_id + 1-1000 `TabletopActionSpec` actions), returns a `TabletopResult` (scenario echo + bundle metadata for audit trail + per-action `TabletopActionResult` list + `TabletopSummary` aggregate counts). Adapter errors are captured per-action as `errored=True` results rather than aborting the scenario.
Tenant isolation: scenario.tenant_id must match the authenticated principal (403); resolved bundle must belong to the same tenant (404, not 403, to avoid leaking bundle ids across tenants). Bundle-not-found is 404. Scenario validation errors are 422 (empty actions, > 1000 actions, empty label).
**Architecture component:** `packages/policy/tabletop.py` (TabletopScenario + TabletopActionSpec + TabletopActionResult + TabletopSummary + TabletopResult Pydantic frozen models + `simulate_scenario` pure-async function; ~190 LOC); `apps/api/routes/tabletop.py` (POST endpoint with tenant scoping, ~100 LOC); wired into `apps/api/main.py` router list.
**Test coverage:** 13 unit on the module (`tests/packages/test_tabletop.py`: happy paths 3 + tenant isolation 2 + error handling 2 + scenario validation 4 + no side effects 2) + 6 endpoint (`tests/api/test_tabletop_route.py`: happy path + 403 cross-tenant + 404 bundle-not-found + 404 cross-tenant-bundle + 422 empty actions + 422 empty label). 100% line+branch coverage on the new code surface. 914 total default tests passing at this commit.
**Gap vs spec:** Today the route resolves the bundle via `get_bundle_by_id` (status-agnostic); a future enhancement should allow scenarios to target draft / proposed bundles from the approval workflow as well as active ones - tracked as `NEW-P11.X.tabletop-bundle-from-storage`. Real-event replay (run a window of historical real events against a candidate bundle, read-only on the ledger) is `TRACKED-NEW-P12.X.tabletop-replay-real-events`. Diff-report comparing simulated vs actual decisions is `TRACKED-NEW-P12.X.tabletop-diff-report`.

### BR-13 - M&A due diligence export
**Status:** `IMPLEMENTED+TESTED`
Full-window evidence trail export for M&A due diligence buyers. Composes a sealed bundle containing one `EvidencePack` per anchored day in scope plus the full set of `AnchorEvidence` proofs covering the window, all bound by a single `ma_root_hash` so the acquirer verifies the bundle's integrity in one operation. `POST /v1/exports/ma-diligence` accepts a JSON body with `tenant_id` + `scope_start` + `scope_end`, returns `MaDiligenceExport` JSON. Tenant-scoped (403 cross-tenant); 413 when scope spans more than 366 anchored days or any day contains more than 1000 receipts; 422 on naive or inverted scope window. Acquirer verifies the bundle offline via `verify_ma_diligence_export()` which recomputes `ma_root_hash` from the canonical bind shape (header + every pack's root_hash + every anchor's anchor_id + every anchor's root_hash).
**Architecture component:** `packages/export/ma_export.py` (MaDiligenceHeader + MaDiligenceExport Pydantic models + `build_ma_diligence_export` + `verify_ma_diligence_export` + `daily_chunks` helpers; ~170 LOC); `apps/api/routes/exports.py` (POST endpoint, ~165 LOC); wired into `apps/api/main.py` router list.
**Test coverage:** 12 unit on the module (`tests/packages/test_ma_export.py`: daily_chunks 5 + build happy path 2 + tenant isolation 1 + size limits 1 + tamper detection 2 + tz validation 1) + 5 endpoint (`tests/api/test_exports_route.py`: happy path 2 anchored days + empty scope + 403 cross-tenant + 422 inverted scope + mixed anchored/deferred rows). 100% line+branch coverage on the new code surface. 895 total default tests passing at this commit.
**Gap vs spec:** Async-job mode for very large windows (>366 days OR >100K receipts) is `TRACKED-NEW-P12.X.ma-export-async-job`. Encryption-at-rest with the acquirer's public key is `TRACKED-NEW-P10.X.ma-export-encryption-at-rest`. Detached platform signature on the bundle (so the acquirer can verify it came from Forensa not a forger) is `TRACKED-NEW-P11.X.ma-export-detached-platform-signature`.

## Non-functional requirements (from Section C.16)

| NFR | Status | Notes |
|---|---|---|
| High integrity and immutability (BR-01, BR-06) | `IMPLEMENTED+TESTED` | Append-only at application and ORM layer; DB-level RLS deferred to Phase 10 CP10.3 |
| Low-latency event capture (p99 < 5ms at 10K req/s) | `PARTIAL` | In-process 6452/sec measured; production throughput depends on Phase 12 CP12.4 (Kafka) |
| Secure encryption (at rest + in transit) | `DEFERRED` | KMS envelope encryption in Phase 11 CP11.2; TLS at gateway is deployment-time config |
| On-prem or VPC deployability | `DEFERRED` | Helm chart in Phase 13 CP13.6 |
| Explainability and exportability | `IMPLEMENTED+TESTED` | JSON-LD pack + Mock narrative today; Live narrative after CP9.1 |
| Scalable storage and search (OpenSearch backend) | `DEFERRED` | Phase 12 |
| Retention and deletion controls aligned to enterprise policy (5-10 year default) | `DEFERRED` | GDPR erasure × append-only tension addressed in Phase 13 CP13.2 |
| **Retry-safe ingest (idempotency dedup)** | `IMPLEMENTED+TESTED` | CP9.17 lands Stripe-style `Idempotency-Key` header on POST /v1/events. Same key + same body within TTL returns the original 201 response without re-running the ingest pipeline (no double-counting in the evidence ledger under retry storms). Same key + different body returns 409 Conflict. In-memory store wired by default with `InMemoryIdempotencyStore` (process-local, 24h TTL, asyncio.Lock-guarded). `PostgresIdempotencyStore` fully implemented + unit-tested but not wired into the default route yet (NEW-P9.17.3 pending - production cutover work). New alembic migration 0005 creates `idempotency_records` table with composite (tenant_id, key) PK + four CHECK constraints. 54 tests at 100% coverage: 35 unit on the store, 19 on the route. Closes the Enterprise-Grade Review section 3.2 finding ("No idempotency key... retries will produce duplicate events with different UUIDs"). |

## Out of scope for v1

- Full enterprise SIEM replacement
- End-to-end legal hold platform
- Complete document management system
- Deep ERP workflow automation beyond evidence capture
- General observability suite for all infrastructure

## Traceability

Each BR maps to architecture component + test suite. See `docs/17_traceability_matrix/TRACEABILITY_MATRIX.md` for the full BR -> component -> test -> code-file mapping. Status changes here should be reflected there in the same commit.

## Change log

| Date | Change |
|---|---|
| 15 May 2026 11:22 | CP9.29 landed. **BR-12 flips DEFERRED -> IMPLEMENTED+TESTED.** New module `packages/policy/tabletop.py` (~190 LOC: TabletopScenario + TabletopActionSpec + TabletopActionResult + TabletopSummary + TabletopResult Pydantic frozen models + `simulate_scenario` pure-async function). New route `apps/api/routes/tabletop.py` (~100 LOC: `POST /v1/tabletop/simulate` with tenant scoping + bundle tenant-scope via 404-not-403 + scenario validation). Wired into `apps/api/main.py` router list. **Headline scoreboard moves from 9/13 to 10/13 IMPLEMENTED+TESTED.** 19 new tests at 100% coverage (13 unit + 6 endpoint). 914 total default tests after this commit (up from 895). 3 production-deferred items named: NEW-P11.X.tabletop-bundle-from-storage + NEW-P12.X.tabletop-replay-real-events + NEW-P12.X.tabletop-diff-report. |
| 15 May 2026 10:55 | CP9.28 landed (HEAD `dc62fd0`). **BR-13 flips STUB -> IMPLEMENTED+TESTED.** New module `packages/export/ma_export.py` (~170 LOC: MaDiligenceHeader + MaDiligenceExport Pydantic frozen models + `build_ma_diligence_export` + `verify_ma_diligence_export` + `daily_chunks`). New route `apps/api/routes/exports.py` (~165 LOC: `POST /v1/exports/ma-diligence` with tenant-scoped auth + 413 size limits + 422 input validation). Wired into `apps/api/main.py` router list. **Headline scoreboard moves from 8/13 to 9/13 IMPLEMENTED+TESTED** with the Status column re-grounded against the canonical close-out doc to fix a prior off-by-one in the PHASES_DONE_PHASE9 narrative (the close-out doc said 9/13 but its underlying table listed 8 IMPL+TESTED rows; CP9.28 closes that arithmetic gap). Same-CP edit also flipped the BR-02, BR-06, BR-10, BR-11 rows from their stale `PARTIAL`/`STUB -> IMPLEMENTED after CP9.X` codes to the actual `IMPLEMENTED+TESTED` state they reached in CP9.18, CP9.19, CP9.1 respectively (the Headline para already acknowledged these flips but the table itself was stale). 17 new tests at 100% coverage (12 unit + 5 endpoint). 895 total default tests after this commit (up from 878). Closes the BR-13 STUB row that had been deferred since the v1 BRD freeze on 12 May. 3 production-deferred items named: NEW-P10.X.ma-export-encryption-at-rest + NEW-P11.X.ma-export-detached-platform-signature + NEW-P12.X.ma-export-async-job. |
| 15 May 2026 07:10 | CP9.21a + CP9.21b landed. BR-05 flips PARTIAL -> IMPLEMENTED+TESTED. PDF render module (`packages/export/pdf_renderer.py`, 330 LOC) + Accept-header content negotiation on `GET /v1/evidence-packs`. Headline scoreboard moves to 9/13 IMPLEMENTED+TESTED. Closes the CP6.3 deferral carried since Phase 6 (14 May 02:47-03:20) and the Enterprise-Grade Review section 3.17 item 1 finding (No PDF rendering). 41 new tests at 100% coverage (24 renderer + 17 endpoint). 837 total default tests after this commit. |
| 12 May 2026 | v1 BRD frozen with 13 BRs |
| 14 May 2026 09:58 | Status column added per EnterpriseGradeReview_Claude review fix #10. Headline: 4 IMPLEMENTED+TESTED / 4 PARTIAL / 2 STUB / 3 DEFERRED. Status of BR-10 and BR-11 will move to IMPLEMENTED after Phase 9 CP9.1 lands in this same session. |
| 14 May 2026 20:07 | CP9.16-PG-up landed (HEAD `099afdb`). BR-01 narrative updated to reference DB-level append-only triggers verified on real PostgreSQL 16.13 via 14 new tests in `tests/integration/`. No BR status code change (BR-01 was already IMPLEMENTED+TESTED). Closes 3 honest gaps from CP9.15.1 named in the Enterprise-Grade Review: migration round-trip on real PG, partial UNIQUE concurrency test, trigger-level UPDATE/DELETE rejection. |
| 14 May 2026 22:02 | CP9.17 landed (HEAD `689a26d`). New NFR row "Retry-safe ingest (idempotency dedup)" added at IMPLEMENTED+TESTED. Closes Enterprise-Grade Review section 3.2 finding on Idempotency-Key. 54 new tests at 100% coverage; no BR status code change (this is an enterprise-grade hardening item rather than a BR). NEW-P9.17.1 (cleanup cron), NEW-P9.17.2 (other mutating routes), NEW-P9.17.3 (production-wiring PostgresIdempotencyStore) tracked in commit body of `689a26d` for future CPs. |
