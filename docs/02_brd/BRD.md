# Forensa - Business Requirements Document (BRD)

**Doc:** 02 of 22 | **Date:** 12 May 2026 | **Status:** v1, frozen | **Source:** Section A.2 of three-author master doc
**Status column added:** 14 May 2026 09:58 per EnterpriseGradeReview_Claude review fix #10 (close doc-claim-vs-code-reality gap)

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
| BR-02 | Multi-party identity binding | `PARTIAL` | Tenant-only signature today; agent signature deferred to Phase 10 CP10.4 (Service account + API key issuance) |
| BR-03 | Reasoning capture (Oracle AER pattern) | `IMPLEMENTED+TESTED` | - |
| BR-04 | Policy snapshot at decision time | `IMPLEMENTED+TESTED` | - |
| BR-05 | Regulator-grade export | `PARTIAL` | JSON-LD export DONE (Phase 6); PDF render in Phase 9 CP9.2 |
| BR-06 | Merkle-chained ledger with RFC 3161 TSA | `PARTIAL` | Hash chain DONE (Phase 1); RFC 3161 TSA anchor in Phase 11 CP11.5 |
| BR-07 | Multi-agent provenance graph (LangGraph) | `DEFERRED` | Phase 12 stretch |
| BR-08 | Omniverse physical-action replay | `DEFERRED` | Out of hackathon scope (was always stretch per "cut from v1 demo if Day 5 slips") |
| BR-09 | AWS-backed bulk historical backfill | `PARTIAL` | In-process throughput 6452 events/sec measured (Phase 8 CP8.2); full target (10K sustained + 100K peak across Kafka + S3) in Phase 12 CP12.4 |
| BR-10 | Investigator UI with natural-language query | `STUB` → `IMPLEMENTED` after CP9.1 | Mock client today (Phase 7); Live Gemini client lands in Phase 9 CP9.1; full Flash-driven NL query UX in Phase 13 stretch |
| BR-11 | Counterfactual narrative generation | `STUB` → `IMPLEMENTED` after CP9.1 | Mock client today; Live Gemini Pro client + 4-layer prompt-injection defence lands in Phase 9 CP9.1; semantic hallucination guard in Phase 12 NEW-P12.Y |
| BR-12 | Tabletop incident response mode | `DEFERRED` | Phase 10 stretch |
| BR-13 | M&A due diligence export | `DEFERRED` | Phase 13 stretch |

**Headline:** 4 of 13 BRs are `IMPLEMENTED+TESTED`. 4 are `PARTIAL`. 2 are `STUB` (becoming `IMPLEMENTED` after Phase 9 CP9.1). 3 are `DEFERRED`. This is the honest v1-on-Day-4-of-hackathon state.

## 13 Business Requirements (BR-01 through BR-13)

### BR-01 - Tamper-evident event recording
**Status:** `IMPLEMENTED+TESTED`
Every agent action (prompt, model response, tool call, policy verdict, human approval, business outcome) is captured as a structured event and appended to a cryptographically-chained ledger (Merkle-style hash chain; RFC 3161 TSA anchoring deferred — see BR-06).
**Architecture component:** packages/ingest, packages/ledger
**Test coverage:** unit + property-based on chain integrity (68 crypto tests + 53 ledger tests passing at 100% coverage)
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
**Status:** `PARTIAL`
JSON-LD + PROV-O evidence pack export is `IMPLEMENTED+TESTED` (Phase 6 CP6.1/6.2/6.4). PDF render (CP6.3) is deferred to Phase 9 CP9.2 — presentation-only over the same `root_hash`-bound JSON.
**Architecture component:** packages/export
**Test coverage:** integration on JSON-LD generation + `verify_evidence_pack` (25 export tests)
**Gap vs spec:** PDF format. No regulatory framework requires PDF specifically; JSON-LD is the canonical form.

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
**Status:** `DEFERRED`
`packages/policy/tabletop/` does not exist. Tracked for Phase 10 stretch.
**Architecture component:** packages/policy/tabletop (when built)
**Test coverage:** N/A — implementation pending

### BR-13 - M&A due diligence export
**Status:** `DEFERRED`
Inventory export endpoint is not in code. Tracked for Phase 13 stretch.
**Architecture component:** packages/export (when extended)
**Test coverage:** N/A — implementation pending

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
| 12 May 2026 | v1 BRD frozen with 13 BRs |
| 14 May 2026 09:58 | Status column added per EnterpriseGradeReview_Claude review fix #10. Headline: 4 IMPLEMENTED+TESTED / 4 PARTIAL / 2 STUB / 3 DEFERRED. Status of BR-10 and BR-11 will move to IMPLEMENTED after Phase 9 CP9.1 lands in this same session. |
