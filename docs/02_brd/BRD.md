# Forensa — Business Requirements Document (BRD)

**Doc:** 02 of 22 | **Version:** v2.0 ELABORATED — 2026-05-18 05:15 BST
**Status:** Tier 1, status-tracked against HEAD CP9.51
**Supersedes (in part):** `_archive/BRD_v1.2_20260515_CP9.29.md` — see §0.3 for the supersession map
**Companion docs:** `BRD_IDENTIFIER_MAP.md`, `USE_CASES.md`, `TRACEABILITY_MATRIX.md`, and their LIVE counterparts
**Editorial principle:** v1.2 body is preserved verbatim in `_archive/`. v2.0 is a structural elaboration to enterprise BRD shape (mendoraci pattern). Where v1.2 narrative drifts from HEAD, §0.3 names the supersession; the v1.2 wording is not edited in archive.

---

## 0. Rules — read this before editing or extending

### 0.1 Rule A.10 (inherited) — requirement-traceability discipline
Before each Checkpoint (CP), open this BRD + `USE_CASES.md` + `TRACEABILITY_MATRIX.md`. CP selection is driven by which named requirement IDs need closing, not by engineering convenience.

### 0.2 Rule A.11 — CP ↔ requirement closure (NEW in v2.0)
**Every mini-sprint Checkpoint (CP) commit must close (or advance) at least one named requirement ID drawn from `BRD_IDENTIFIER_MAP.md`.** The CP commit message names the ID(s) closed. The LIVE traceability document records the CP commit against those IDs.

A CP that does not close any named ID is not a tracked CP — it is engineering convenience. Engineering-convenience CPs are allowed but must be labelled (`CP9.52-tooling: ...`) and do not advance the requirement scoreboard.

This rule prevents the documented failure mode (memory: 14 accumulated failure modes) of "optimising for next CP that ships clean rather than closing actual requirement gaps."

### 0.3 Supersession map — where v2.0 corrects v1.2 narrative drift

| v1.2 row | v1.2 said (in narrative body) | HEAD reality | v2.0 status |
|---|---|---|---|
| BR-02 narrative | `PARTIAL` — agent-side identity signature not in place (line 47) | Agent signature wired in CP9.18a/b/c (HEAD `ec81920`); route-layer enforcement in CP9.18c | **`IMPLEMENTED+TESTED`** (matches v1.2 summary table line 22) |
| BR-06 narrative | `PARTIAL` — RFC 3161 TSA anchoring DEFERRED to Phase 11 CP11.5 (line 74) | CP9.19 landed live FreeTSA (HEAD `8176502`); CP9.51 added cert-chain verification (`d7d9aaa`) | **`IMPLEMENTED+TESTED`** (matches v1.2 summary table line 26) |
| BR-10 narrative | `STUB` (today) → `IMPLEMENTED` after CP9.1 (line 99) | CP9.1 landed (HEAD `4a18b67`); CP9.20 migrated to `google.genai` SDK | **`IMPLEMENTED+TESTED`** for narrative API; NL query UX in console remains `DEFERRED` Phase 13 |
| BR-11 narrative | `STUB` (today) → `IMPLEMENTED` after CP9.1 (line 106) | CP9.1 landed live Gemini 2.5 Pro client + 4-layer prompt-injection defence | **`IMPLEMENTED+TESTED`** |
| "Day 1..Day 6" status legend in archived TRACEABILITY_MATRIX | calendar-anchored timeline ending "Day 6 submission" | CP-anchored timeline through CP9.51 | superseded by §10 below (CP-anchored phase plan) |

### 0.4 Reading order
Buyer/exec: §1 → §3.4 → §11 → §12 → §13. Implementer: §7 → §10 → NFRs §9. Auditor/regulator: §7 → §14.5 → §16. AI lead: §7 (BR-10/11) → §14.1 → §14.2 → §14.4 → EVAL-F01, EVAL-F02. Compliance officer: §1 → §14.5 → §16.

---

## 1. Executive Summary

Forensa is an **enterprise-grade cryptographic evidence layer for AI agents**. It sits beside (not inside) the agent runtime — ingesting every agent action (prompt, model response, tool call, policy verdict, human approval, business outcome) as a structured event, signing each as an immutable receipt, hash-chaining receipts into a Merkle-style ledger, and anchoring each day to a public RFC 3161 Time-Stamping Authority (FreeTSA) so a regulator with `T+1 year` doubt cannot dispute server-clock tampering.

The product produces (a) per-event signed Receipts, (b) per-window cryptographic Evidence Packs (JSON-LD + regulator-grade PDF, both bound by a single `root_hash`), (c) RFC 3161 Anchor proofs verifiable offline, (d) M&A diligence exports composing 1..N anchored days under a single `ma_root_hash`, and (e) tabletop incident-response simulations that replay synthetic events against stored policy bundles without mutating the chain.

**Quantified value (per 500-AI-action-per-day enterprise, year 1):**

| Dimension | Baseline | Target | Annualised value (USD) |
|---|---|---|---|
| Regulator-inquiry response time (mortgage / fintech case) | 6 weeks | ≤ 3 days (−93%) | $480K avoided cost |
| Internal-audit sample preparation | 12 hr / sample | ≤ 45 min (−94%) | $230K |
| AI-incident mean-time-to-investigate | 4 days | ≤ 90 min (−97%) | $310K avoided escalation |
| Evidence completeness (vs ad-hoc Slack/JIRA) | 32% | 100% | $180K audit-cycle savings |
| Legal hold export turnaround | 5 business days | ≤ 4 hours | $90K outside-counsel offload |
| EU AI Act Article 12 compliance gap closure | open finding | closed with cryptographic evidence | regulatory penalty avoidance, range $50K–$15M |
| **Total annualised recapture (typical 500-agent-action/day enterprise)** | | | **~$1.3M baseline + 10–100× penalty avoidance** |

**Commercial framing.** TAM ~$8.2B (2026 enterprise AI governance market intersected with cryptographic evidence platforms). SAM ~$1.1B (regulated-sector AI deployments in EU + UK financial services, healthcare, govtech). ACV tiers — see §13. Currency USD.

**Why now.** EU AI Act Article 12 high-risk logging obligations bind 2 August 2026; Article 18 ten-year technical-documentation retention bind same date. DORA Article 30 ICT-third-party tabletop obligations are live since 17 January 2025. SOC 2, ISO 42001:2023, and NIST AI RMF all require auditable AI decision lineage — none of the major AI agent platforms ship this natively. Forensa is the gap-filler.

---

## 2. Identifier Map

The full identifier map lives in `BRD_IDENTIFIER_MAP.md`. Summary:

| Prefix | Meaning | Range | Forensa-specific note |
|---|---|---|---|
| BG | Business Goal | BG-F01..F06 | New in v2.0 |
| BR | Business Requirement | BR-01..BR-14 | BR-14 (Operator Console) new in v2.0 |
| UC | Use Case | UC-01..UC-10 | UC-09, UC-10 new in v2.0 |
| US-F | User Story | US-F01..US-F32 | New (numbered) in v1 (17 May); extended in v2.0 (18 May) |
| SCR-F | Console Screen | SCR-F01..SCR-F10 | New in v2.0 |
| API-F | Backend API | API-F01..API-F13 | API-F11..F13 planned (auth, metrics, login) |
| DB-F | DB entity | DB-F01..DB-F12 | Derived from alembic migrations |
| TEST-F | Test case | TEST-F01..TEST-F40+ | Pre-existing + extended for Console |
| EVID-F | Evidence artefact | EVID-F01..EVID-F06 | Receipt, EvidencePack, AnchorEvidence, MaDiligenceExport, TabletopResult, Narrative |
| RT-F | Trace Row | RT-F01..RT-F22 | RT-F19..F22 new for Console/Web/PWA/Auth |
| IMP-F | Enhancement | IMP-F01..IMP-F25+ | Forward queue |
| EVAL-F | AI evaluation gate | EVAL-F01, EVAL-F02 | Narrative quality + injection defence |
| OPT-F | Competitor option | OPT-F01..OPT-F08 | See §12 |
| R-F | Risk | R-F01..R-F12 | See §15 |

---

## 3. Problem, Current State, Target State, Success Metrics

### 3.1 Problem definition

Enterprises deploying AI agents face four converging pressures that no existing tool satisfies in combination:

1. **EU AI Act Article 12 binding August 2026.** High-risk AI systems must produce automatic, lifetime, traceable logs of inputs, outputs, and operator decisions. Current observability stacks (Datadog, Splunk) capture infrastructure telemetry, not policy-bound decision lineage.
2. **DORA Article 30 binding January 2025.** ICT third-party tabletop exercises must be evidenced. AI agents are ICT third-party. Today the evidence is a Slack thread.
3. **AI agents are non-deterministic.** A model decision six months ago cannot be reproduced exactly; only its evidence trail (prompt, snapshot of policy bundle, model version, tool calls, verdict) can support a forensic reconstruction.
4. **Evidence quality is correlated with regulator outcome.** UK FCA, EU EBA, US SEC have all signalled in 2024–2026 that algorithmic-decisioning inquiries close faster when the firm produces cryptographically signed evidence at inquiry-open vs producing reconstructed evidence three weeks later.

### 3.2 Current state baseline (10-day discovery probe)

| Metric | Source | Sample frame | Statistical treatment |
|---|---|---|---|
| Inquiry response time | Customer compliance team logs | All FCA/EBA inquiries 12-month window | Median + p75; outlier trim 1% |
| Evidence-pack completeness | Manual inventory per inquiry: presence of {prompt template hash, model version, policy bundle hash, decision verdict, chain integrity proof} | Random N=30 inquiries | Score 0–5; ≥ 4 = complete |
| Mean-time-to-investigate AI incident | Security ops ticket from first-alert to root-cause-doc | All AI-touching incidents 90-day rolling | Median + p90 |
| Approval-to-evidence latency | Time from policy verdict to written evidence pack | All high-stakes (>£10K impact) AI decisions | Median |
| Chain integrity verifiability | Can a regulator hand the pack to a forensic accountant and reconstruct the chain offline? | Per-pack manual test | Binary pass/fail |

### 3.3 Target state (day 90 post-pilot)

Every agent action ingested as an Event; every Event evaluated against a snapshot-bound Policy Bundle; every decision sealed as a hash-chained Receipt; every day's chain anchored to FreeTSA RFC 3161; every regulator-window producible as a JSON-LD + PDF Evidence Pack with offline verification; every M&A diligence ask producible as a sealed multi-day bundle; every tabletop drill replayable without mutating production state; all of the above accessible to non-technical personas via the **Operator Console (BR-14)** — a Next.js web app installable as PWA, with native iOS/Android deferred to Phase 14+.

### 3.4 Success metrics and exit gates

| KPI | MVP exit | Pilot exit (90 days) | Promotion (12 months) |
|---|---|---|---|
| Chain-integrity verification on regulator pack | 100% demo | 100% pilot | 100% all tenants |
| RFC 3161 TSA anchor coverage | Daily anchor on demo tenant | Daily anchor + deferred-tombstone fallback all tenants | 99.9% anchor success rate |
| Inquiry response time | n/a | ≤ 3 days median | ≤ 1 day median |
| Evidence completeness score | 5/5 demo path | 5/5 pilot pipelines | 5/5 all production tenants |
| Operator Console usable by non-technical persona (Compliance Officer) | Demo persona task complete | Task complete with no engineer assistance | All personas (P-COMP, P-AUD, P-COUNSEL, P-PLAT, P-SEC, P-ACQ) complete primary task without engineer |
| EVAL-F01 narrative quality | ≥ 0.80 vs human ground truth on N=50 | ≥ 0.85 | ≥ 0.90 |
| EVAL-F02 prompt-injection defence | 0 leaks on N=100 attack corpus | 0 leaks on N=500 | 0 leaks production red-team continuous |

---

## 4. Stakeholders and Personas

| Persona | Code | Role | Pain | KPI focus |
|---|---|---|---|---|
| Compliance Officer | P-COMP | Owns regulatory exposure | "FCA asked about an AI mortgage decline 6 months ago — I have 3 days to respond and we have Slack threads" | Inquiry response time, evidence completeness |
| Internal Auditor | P-AUD | Audits AI deployments quarterly | "I sample 30 AI decisions and 12 of them have no policy lineage" | Sample-pull time, chain integrity verifiability |
| Security Engineer | P-SEC | Investigates AI misuse | "Tabletop drill required by DORA — I have no replay surface" | MTTI on AI incidents, tabletop turnaround |
| General Counsel | P-COUNSEL | Defends in disputes; manages legal hold | "Plaintiff's discovery request — I need legally-admissible evidence in 4 hours, not 4 days" | Legal hold export turnaround, chain-of-custody integrity |
| AI Platform Owner | P-PLAT | Operates AI infrastructure | "Agents ship every week and my evidence story is a quarterly fire drill" | Ingest reliability, chain integrity, operator console adoption |
| M&A Acquirer (target-side data room admin) | P-ACQ | Provides AI governance evidence in M&A diligence | "Acquirer asked for 90-day AI decision sample with proof of governance — I exported 47 spreadsheets and it took 11 weeks" | Diligence export turnaround, governance signal completeness |
| Regulator / external auditor (consumer of artefacts) | P-REG | Reviews exported evidence | "Firms send me PDFs I can't verify" | Offline verifiability, chain integrity proof |

**Note on persona changes from v1.2:** v1.2 listed 5 personas in USE_CASES.md table (lines 57–63). v2.0 promotes P-ACQ (M&A Acquirer) from implicit (in UC-07) to named persona, and adds P-REG (external consumer) because the offline-verification property is a first-class regulator-facing requirement.

---

## 5. Scope (In / Out)

### 5.1 In scope for v1.x (Phase 1–11)
- BR-01..BR-06, BR-10..BR-14 IMPLEMENTED+TESTED on demo tenant
- Five core APIs (events ingest, receipts list/detail, evidence-packs, anchors, narratives) + four diligence/tabletop APIs
- Operator Console (BR-14) Web tier: Next.js 16 SSR with five primary screens (SCR-F01..F05) and three planned screens (SCR-F06..F08) backed by enterprise list-views pattern (no sessionStorage shortcuts — see §7 BR-14 acceptance criteria for why)
- **PWA tier (BR-14):** manifest + service worker, installable to phone / desktop home screen, offline shell for read-only views
- Multi-tenant authentication (UC-10): per-tenant signing keys, agent identity signatures, route-layer enforcement of principal-vs-tenant matching
- Live RFC 3161 TSA integration (FreeTSA) with cert-chain verification
- M&A diligence export (BR-13) with daily-chunk size limits and offline `ma_root_hash` verification
- Tabletop simulation (BR-12) without persistence

### 5.2 Out of scope for v1.x (deferred to named future Phases)
- **Native iOS / native Android Operator Console clients** — deferred Phase 14+. PWA is v1.x scope. Native is a separate engineering investment (separate auth flow, separate test matrix, app-store submission process); committing to native in v1.x would crowd out enterprise hardening. The architectural commitment to native as a future surface is on record here so the API surface (already client-agnostic per `apps/api/`) does not regress into Console-specific coupling.
- **LangGraph multi-agent provenance graph** (BR-07) — Phase 12 stretch
- **NVIDIA Omniverse / Isaac Sim physical-action replay** (BR-08) — Phase 13 stretch (was always "cut from v1 if Day 5 slips" per original spec)
- **AWS bulk-historical-backfill production topology** (BR-09 remainder) — Phase 12 CP12.3/CP12.4 — in-process throughput proven, AWS Kafka + S3 + EventBridge + Glue + Step Functions + OpenSearch deferred
- **Free-text NL query UX in Console** (BR-10 remainder; US-F24) — Phase 13. Narrative API backend is live; the typing-question-getting-evidence-chain console surface is deferred
- **On-prem / VPC Helm chart deploy** — Phase 13 CP13.6
- **KMS envelope encryption at rest** — Phase 11 CP11.2 (TLS at gateway is deployment-time config, not a Forensa code path)
- **GDPR Article 17 cryptographic shredding** — Phase 13 CP13.2
- **OpenSearch backend for scalable search** — Phase 12 (cursor pagination is `IMPLEMENTED+TESTED` and meets v1.x scale)
- **SOC 2 Type II audit** — Phase 14 (the controls are mapped; the audit cycle requires 6-month evidence window)

---

## 6. Business Goals and BG → BR Weighted Contribution

### 6.1 Business goals

| ID | Goal | Quantification | Owner | Linked BRs |
|---|---|---|---|---|
| BG-F01 | Reduce regulator-inquiry response time | −90% vs baseline | Compliance Officer (P-COMP) | BR-01, BR-04, BR-05, BR-10, BR-11 |
| BG-F02 | Achieve cryptographic chain integrity verifiable offline | 100% pack verifiability | AI Platform Owner (P-PLAT) | BR-01, BR-02, BR-06 |
| BG-F03 | Close EU AI Act Article 12 / DORA Article 30 evidence gaps | Article 12 logging + Article 18 retention compliant | General Counsel (P-COUNSEL) | BR-01, BR-04, BR-05, BR-12 |
| BG-F04 | Enable non-technical operator workflows | All 6 named personas complete primary task without engineer | Product Owner | BR-14 (Operator Console — Web + PWA) |
| BG-F05 | Support M&A diligence + legal hold export | Diligence turnaround ≤ 4 hours | M&A Acquirer (P-ACQ) + General Counsel | BR-05, BR-13 |
| BG-F06 | Demonstrate AI safety surface (prompt injection, hallucination defence) | EVAL-F02 ≥ 0 leaks on N=500 | AI Lead | BR-10, BR-11 |

### 6.2 BG → BR contribution matrix (cols sum to 100% per BG)

| BR ↓ / BG → | BG-F01 | BG-F02 | BG-F03 | BG-F04 | BG-F05 | BG-F06 |
|---|---|---|---|---|---|---|
| BR-01 Tamper-evident recording | 25% | 30% | 25% | 5% | 10% | 5% |
| BR-02 Multi-party identity binding | 5% | 25% | 10% | 5% | 5% | 5% |
| BR-03 Reasoning capture (AER) | 10% | 5% | 10% | 5% | 5% | 15% |
| BR-04 Policy snapshot binding | 15% | 5% | 20% | 5% | 5% | 5% |
| BR-05 Regulator-grade export | 25% | 10% | 25% | 10% | 25% | 5% |
| BR-06 Merkle ledger + RFC 3161 TSA | 5% | 20% | 5% | 5% | 5% | 5% |
| BR-07 Multi-agent provenance | — | — | — | — | — | 5% (deferred) |
| BR-08 Omniverse replay (stretch) | — | — | — | — | — | — |
| BR-09 AWS bulk backfill | 5% | — | 5% | — | 5% | — |
| BR-10 Investigator narrative | 5% | — | — | 5% | 10% | 25% |
| BR-11 Counterfactual narrative | 5% | — | — | — | 10% | 25% |
| BR-12 Tabletop simulation | — | — | 5% | 5% | — | 5% |
| BR-13 M&A diligence export | — | — | — | 5% | 25% | — |
| **BR-14 Operator Console (Web + PWA, native deferred)** | — | 5% | — | 50% | — | — |

---

## 7. Functional Requirements — BR-01..BR-14

**v2.0 editorial note:** the v1.2 BR narratives (BR-01..BR-13) are preserved verbatim in `_archive/BRD_v1.2_20260515_CP9.29.md`. The v2.0 form below restates each BR in mendoraci shape (statement, acceptance criteria as AC-N, edge cases, negative paths, exit gate) and **supersedes v1.2 narratives where v1.2 has drifted from HEAD** (see §0.3). BR-14 is new in v2.0.

### BR-01 — Tamper-evident event recording
**Status:** `IMPLEMENTED+TESTED`
**Statement:** Every agent action (prompt, model response, tool call, policy verdict, human approval, business outcome) is captured as a structured `Event` and appended to a cryptographically-chained ledger. The ledger uses a linked Merkle-style hash chain (note: per-BR-06 narrative, this is a chain, not an RFC 6962-style tree); each appended receipt binds `prev_receipt_hash` + `payload_hash` + `signature_b64`.
**Acceptance criteria:**
- AC-1 Every accepted `POST /v1/events` produces a persisted Receipt with `integrity_ok=True`
- AC-2 Receipt sequence is strictly monotonic per tenant (DB-level partial UNIQUE index `(tenant_id, sequence)` enforced)
- AC-3 DB-level append-only triggers on `policy_bundle_approvals` raise on `UPDATE` / `DELETE` (PL/pgSQL `forensa_block_approval_mutation`)
- AC-4 100% line+branch test coverage on `packages/ingest/` + `packages/ledger/` + chain integrity property tests
- AC-5 Retry-safe ingest: same `Idempotency-Key` + same body within TTL returns original 201 response without re-running ingest pipeline (CP9.17)
**Edge cases:** concurrent ingests at same `sequence` (PG partial UNIQUE race); truncated event payloads; oversized payloads.
**Negative paths:** unsigned event → 401; same `Idempotency-Key` + different body → 409; payload schema invalid → 422; tenant mismatch in principal-vs-body → 403.
**Exit gate:** TEST-F01..TEST-F06 (68 crypto + 53 ledger + 14 PG-integration + 54 idempotency) all green at 100% coverage.

### BR-02 — Multi-party identity binding
**Status (v2.0 supersedes v1.2 narrative):** `IMPLEMENTED+TESTED`
**Statement:** Every event is signed by both the enterprise tenant key and (where present) the agent identity key. Tenant signature via `packages/crypto/sign.py`; agent signature via `apps/api/auth/` module wired in CP9.18b; route-layer enforcement of principal-vs-tenant match in CP9.18c (HEAD `ec81920`).
**Acceptance criteria:**
- AC-1 Receipt includes both `tenant_signature_b64` and `agent_signature_b64` when agent identity is provided
- AC-2 Cross-tenant signature mismatch → 403
- AC-3 Agent signing key rotation does not invalidate historical receipts (signature verification uses key version at signing time)
**Edge cases:** agent without DID (degrades to tenant-only signing with explicit `agent_signature_b64=null`); key rotation mid-window.
**Negative paths:** signature verification failure → 422 with structured error.
**Exit gate:** 21 sign tests + agent-signature-route tests green.
**v1.2 supersession:** v1.2 narrative (`_archive/BRD_v1.2_20260515_CP9.29.md` line 47) said "Agent-side identity signature is not yet in place." CP9.18a/b/c landed agent signature. v1.2 summary table line 22 was already correct; v2.0 re-syncs the narrative.

### BR-03 — Reasoning capture (Oracle AER pattern)
**Status:** `IMPLEMENTED+TESTED`
**Statement:** For LLM-mediated actions, the event schema captures intermediate reasoning chain (chain-of-thought summary, tool selection rationale, confidence signals) via the `reasoning` field on `Event`. OTel GenAI normaliser maps `forensa.reasoning` and `gen_ai.response.text` (note: `normaliser.py` finding RC-F14 — the two fields are currently conflated; tracked as IMP-F14 for separation).
**Acceptance criteria:**
- AC-1 `Event.reasoning` is a structured Pydantic v2 model with `chain_of_thought_summary`, `tool_selections[]`, `confidence_signals`
- AC-2 Schema validates against `packages/schema/` Pydantic v2 frozen models
- AC-3 OTel GenAI envelope maps cleanly into Forensa Event schema
**Edge cases:** non-LLM events (reasoning=null is valid); reasoning fields > 16KB (truncate with marker).
**Negative paths:** malformed reasoning structure → 422.
**Exit gate:** 32 schema + 18 normaliser tests.

### BR-04 — Policy snapshot at decision time
**Status:** `IMPLEMENTED+TESTED`
**Statement:** Every event records which policy bundle version + content hash was active at decision time. Six months later when policies have changed, the original policy state is reconstructible from the snapshot. `live_bundle.content_hash` is never returned in evidence reads — only the snapshot hash.
**Acceptance criteria:**
- AC-1 Receipt binds `policy_snapshot_id` referencing the snapshot active at signing time
- AC-2 Snapshot is immutable once a receipt references it (DB-level FK + no update path)
- AC-3 Replay endpoint reconstructs the snapshot state, never the live state
**Edge cases:** policy bundle updated mid-request (snapshot binds at request-start moment).
**Negative paths:** referenced snapshot not found → 422 with `snapshot_id` echoed.
**Exit gate:** 17 snapshot + 5 replay tests.

### BR-05 — Regulator-grade export
**Status:** `IMPLEMENTED+TESTED`
**Statement:** JSON-LD + PROV-O Evidence Pack export wired in Phase 6 (CP6.1/6.2/6.4). PDF render wired in CP9.21a (`packages/export/pdf_renderer.py`, 330 LOC). Accept-header content negotiation on `GET /v1/evidence-packs` wired in CP9.21b. PDF is a deterministic A4 rendering of the same pack content bound by `root_hash` — a regulator can hand the PDF to a forensic accountant and the JSON-LD to a developer in parallel and they agree on every fact.
**Acceptance criteria:**
- AC-1 `GET /v1/evidence-packs?tenant_id=…&scope_start=…&scope_end=…` returns JSON-LD with `header`, `receipts[]`, `activities[]`, `anchor`, `root_hash`
- AC-2 Same endpoint with `Accept: application/pdf` returns deterministic A4 PDF
- AC-3 Both wire forms bind the same `root_hash`
- AC-4 PDF filename includes first 12 chars of `root_hash`
- AC-5 Response carries `X-Forensa-Root-Hash` header for direct cross-check
**Edge cases:** scope window with zero receipts (returns empty pack with valid root_hash of empty set); scope window crossing a TSA anchor failure tombstone.
**Negative paths:** naive or inverted scope window → 422; cross-tenant attempt → 403.
**Exit gate:** 24 PDF renderer + 17 endpoint content-negotiation + 6 existing JSON-LD endpoint + 25 export tests = 72 evidence-pack tests.

### BR-06 — Merkle-chained ledger with RFC 3161 TSA
**Status (v2.0 supersedes v1.2 narrative):** `IMPLEMENTED+TESTED`
**Statement:** Hash-chain via `packages/crypto/merkle.py` (chain, not RFC 6962 tree — `IMP-F03 merkle-tree` tracks inclusion-proof support). **RFC 3161 TSA anchoring is live** via FreeTSA in CP9.19 (HEAD `8176502`) with deferred-tombstone fallback for failed TSA calls. **Cert-chain verification** added in CP9.51 (`d7d9aaa`) — `verify_rfc3161_timestamp_response()` in `packages/crypto/tsa.py` performs full PKIX cert-chain verification of RFC 3161 DER bytes against FreeTSA's published cert chain, with unit + live integration tests, FreeTSA cert fixtures bundled at `tests/fixtures/freetsa/`.
**Acceptance criteria:**
- AC-1 Daily TSA anchor runs against FreeTSA; success persists `AnchorEvidence` with TSR DER bytes
- AC-2 TSA failure produces a `deferred` tombstone with retry trail; ledger remains usable
- AC-3 `GET /v1/anchors/{id}` with `Accept: application/timestamp-reply` returns raw DER bytes for offline `openssl ts -verify`
- AC-4 Cert-chain verification rejects forged TSR bytes with explicit error code
**Edge cases:** TSA cert rotation; TSR with valid signature but expired cert; gap in anchor coverage.
**Negative paths:** invalid TSR DER → 422; cross-tenant anchor read → 403.
**Exit gate:** 22 merkle + 11 TSA + 14 cert-chain tests.
**v1.2 supersession:** v1.2 narrative (`_archive/BRD_v1.2_20260515_CP9.29.md` line 74) said "RFC 3161 TSA anchoring is `DEFERRED` to Phase 11 CP11.5." Reality: CP9.19 + CP9.51 landed it. v1.2 summary table line 26 was already correct; v2.0 re-syncs the narrative.

### BR-07 — Multi-agent provenance graph (LangGraph)
**Status:** `DEFERRED` to Phase 12
**Statement:** LangGraph DAG capture for multi-agent workflows. Today LangGraph is not a project dependency.
**Exit gate:** N/A — out of v1.x scope; tracked as IMP-F07.

### BR-08 — Omniverse physical-action replay (stretch)
**Status:** `DEFERRED` to Phase 13
**Statement:** NVIDIA Omniverse / Isaac Sim physical-action replay. Out of v1.x scope; was always stretch.
**Exit gate:** N/A — tracked as IMP-F08.

### BR-09 — AWS-backed bulk historical backfill
**Status:** `PARTIAL`
**Statement:** In-process throughput is `IMPLEMENTED+TESTED` — Phase 8 CP8.2 load test measured 6452 events/sec for a 1000-event chain build + pack + verify (~387× under 60-second budget). Full AWS topology (S3 + EventBridge + Glue + Step Functions + OpenSearch Serverless + Kafka) is `DEFERRED` to Phase 12 CP12.3/CP12.4.
**Acceptance criteria for PARTIAL state:**
- AC-1 In-process load test passes at 6000+ events/sec
- AC-2 AWS topology design documented in `14_deployment_topology/DEPLOYMENT_TOPOLOGY.md` even though not built
**Exit gate (full):** AC-1 + Kafka ingest sustained 10K/sec + S3 cold-storage round-trip + OpenSearch query path. Tracked as IMP-F09.

### BR-10 — Investigator UI with natural-language query
**Status (v2.0 supersedes v1.2 narrative):** `IMPLEMENTED+TESTED` for narrative API surface; **`DEFERRED` Phase 13** for free-text NL query UX in Console (the typing-question-getting-evidence-chain affordance, US-F24)
**Statement:** Live Gemini 2.5 Pro narrative client landed in CP9.1 (HEAD `4a18b67`) with 4-layer prompt-injection defence (structural isolation, role separation, output sanitisation, structural consistency assertion). SDK migrated `google.generativeai` → `google.genai` in CP9.20 (HEAD `5535329`).
**Acceptance criteria:**
- AC-1 `POST /v1/narratives` accepts a window scope + tenant + returns plain-English narrative
- AC-2 4-layer defence catches injection attempts in N=100 test corpus
- AC-3 HTTP 422 + `incident_id` returned when defence fires (CP9.6 HEAD `41fc9e7`)
**Exit gate:** 19 narrative tests including 3 negative-path injection-attempt cases.
**v1.2 supersession:** v1.2 narrative (line 99) said "today the narrative client is `MockNarrativeClient` only." Reality: live client landed CP9.1.

### BR-11 — Counterfactual narrative generation
**Status (v2.0 supersedes v1.2 narrative):** `IMPLEMENTED+TESTED`
**Statement:** Live Gemini 2.5 Pro client with 4-layer prompt-injection defence (CP9.1). Semantic hallucination guardrails (assert narrative's claimed event counts match pack's actual contents) is `DEFERRED` to IMP-F11 in the backlog (3 days estimated).
**Exit gate:** included in 19 narrative tests above.

### BR-12 — Tabletop incident response mode
**Status:** `IMPLEMENTED+TESTED`
**Statement:** Security-engineer simulation surface: replay a sequence of synthetic agent events through the configured `PolicyEnforcementClient` against a stored `PolicyBundle`, capture verdicts, return aggregate decision counts — **without persisting anything, without writing Receipts, without mutating the chain.**
**Acceptance criteria:**
- AC-1 `POST /v1/tabletop/simulate` accepts a `TabletopScenario` body (name + tenant_id + policy_bundle_id + 1..1000 actions), returns a `TabletopResult` (scenario echo + bundle metadata + per-action `TabletopActionResult` list + `TabletopSummary`)
- AC-2 Tenant isolation: scenario.tenant_id must match authenticated principal (403); resolved bundle must belong to the same tenant (404, not 403, to avoid leaking bundle ids)
- AC-3 Adapter errors captured per-action as `errored=True` rather than aborting the scenario
**Edge cases:** scenario with 0 actions → 422; scenario with >1000 actions → 422; bundle in draft state.
**Negative paths:** cross-tenant scenario → 403; empty label → 422.
**Exit gate:** 19 tests (13 unit + 6 endpoint); 100% line+branch coverage.

### BR-13 — M&A due diligence export
**Status:** `IMPLEMENTED+TESTED`
**Statement:** Full-window evidence trail export for M&A buyers. Composes a sealed bundle containing one `EvidencePack` per anchored day in scope plus the full set of `AnchorEvidence` proofs, all bound by a single `ma_root_hash` so the acquirer verifies the bundle's integrity in one operation.
**Acceptance criteria:**
- AC-1 `POST /v1/exports/ma-diligence` accepts JSON with `tenant_id` + `scope_start` + `scope_end`, returns `MaDiligenceExport` JSON
- AC-2 Tenant-scoped (403 cross-tenant)
- AC-3 Size limits: 413 when scope spans >366 anchored days OR any day has >1000 receipts
- AC-4 422 on naive or inverted scope window
- AC-5 Acquirer verifies the bundle offline via `verify_ma_diligence_export()` which recomputes `ma_root_hash` from canonical bind shape (header + every pack's root_hash + every anchor's anchor_id + every anchor's root_hash)
**Edge cases:** scope spanning mix of anchored and deferred days (deferred days included with tombstone metadata).
**Negative paths:** scope outside tenant's earliest anchor → 422.
**Exit gate:** 17 tests (12 unit + 5 endpoint); 100% line+branch coverage.

### BR-14 — Operator Console (Web + PWA — native iOS/Android deferred Phase 14+) — NEW in v2.0
**Status:** `PARTIAL` — three primary screens shipped (SCR-F02, SCR-F03 minimal, SCR-F04); enterprise list-views pattern (SCR-F01 persona landing, full SCR-F02 timeline with filters, SCR-F05..F08 planned) is the CP9.52+ work
**Statement:** Forensa exposes a Next.js 16 / React 19 Operator Console as the human-facing surface for all six named personas. **The Console is Web in v1.x and Progressive Web App (PWA) installable to phone/desktop home screens.** Native iOS / native Android clients are explicitly deferred to Phase 14+ — the architectural commitment is on record so the API (already client-agnostic per `apps/api/`) does not regress into Console-specific coupling.

**Acceptance criteria:**
- AC-1 (Web) All ten console screens SCR-F01..SCR-F10 are renderable Next.js routes
- AC-2 (Web) **Top navigation pattern is "list pages as nav links" — no sessionStorage shortcut for "active intake / active receipt".** Each link routes to a proper list view with cursor pagination, filters, URL-query persistence, sortable columns, status badges, loading skeletons, empty/error states. This pattern is adopted from mendoraci CP-9 list-views course correction (see RT-F19); the failure mode of using sessionStorage to track "active context" for top-nav deep-linking is documented as anti-pattern AP-F01 in `_archive/`.
- AC-3 (Web) Every primary persona task completes without engineer assistance: P-COMP scopes regulator inquiry → exports PDF; P-AUD samples receipts → verifies chain; P-SEC runs tabletop drill; P-COUNSEL pulls legal-hold export; P-PLAT views ingest health; P-ACQ generates diligence export
- AC-4 (PWA) `manifest.json` declares Forensa icon, theme color, display=standalone, scope; service worker caches read-only app shell
- AC-5 (PWA) Installable to iOS Safari, Android Chrome, desktop Chrome / Edge
- AC-6 (PWA) Read-only views (timeline, receipt detail, evidence pack list) render offline against last cached state; write actions (new evidence pack generation, tabletop run) clearly disabled offline with explicit affordance
- AC-7 (Web + PWA) Responsive: timeline collapses to cards <768px; header collapses to drawer
- AC-8 (Web + PWA) Auth surface (SCR-F09) gates all non-public routes; redirect to `/login` if unauth
- AC-9 (Native deferred) DEPLOYMENT_TOPOLOGY.md §Console explicitly documents native iOS / native Android as Phase 14+ roadmap item with named technical approach (React Native or Swift/Kotlin TBD at Phase 14 entry)
- AC-10 Playwright E2E specs drive the UI (not just the API) for SCR-F01..F08 happy + negative paths

**Edge cases:** offline state with stale cached data (>24h) → warning banner; PWA install prompt suppression / dismissal; deep link to receipt that's outside current tenant's scope (404, not 403).

**Negative paths:** unauthenticated route access → 401 + redirect; cross-tenant deep-link → 404; PWA service-worker registration failure → degrade to web mode with explicit notice.

**Exit gate (for PARTIAL → IMPLEMENTED+TESTED flip):**
- SCR-F01..SCR-F08 shipped with the enterprise list-views pattern
- PWA manifest + service worker landed and tested on three browser/OS combinations
- Playwright UI-driving E2E suite covers all eight screens × happy + negative
- Auth surface (SCR-F09) wired; multi-tenant SSO planning documented even if not implemented

**v1.2 status:** BR-14 did not exist in v1.2 BRD. The Console was implicitly covered by BR-10 "Investigator UI" but that BR's exit gate is narrative-API-shaped, not Console-shaped. v2.0 separates the Console as a first-class tracked surface so the gap previously named in `TRACEABILITY_LIVE` Gap 6 ("orphan RT-eligible work streams with no parent BR") is closed.

---

## 8. User Stories (summary)

The full US-F01..US-F32 expansion lives in `USE_CASES.md` §4 with the mendoraci shape (persona · story · BR · SCR · API · acceptance · negative · priority · phase · status). Summary anchors:

- **US-F01..F08** — Epic A: Ingest & Identity (BR-01, BR-02, BR-03; SCR-F02, SCR-F03)
- **US-F09..F12** — Epic B: Policy Lifecycle (BR-04; SCR-F03)
- **US-F13..F16** — Epic C: Chain Integrity & Anchoring (BR-06; SCR-F03 cryptographic-proof tab)
- **US-F17..F20** — Epic D: Evidence Pack Export (BR-05; SCR-F04)
- **US-F21..F23** — Epic E: Tabletop & Simulation (BR-12; SCR-F06) plus deferred Epic E2: Multi-agent (BR-07; deferred)
- **US-F24..F26** — Epic F: M&A Diligence (BR-13; SCR-F07) and deferred NL UX (BR-10; deferred)
- **US-F27..F32** — Epic G: Operator Console + Web/PWA + Auth (BR-14; SCR-F01, SCR-F08, SCR-F09, SCR-F10) — **NEW in v2.0**

---

## 9. Non-Functional Requirements

| NFR ID | NFR | Target | Measurement | Status |
|---|---|---|---|---|
| NFR-01 | Integrity / immutability | Append-only at application + DB layer | DB partial UNIQUE + PG triggers (CP9.16: 14 PG-integration tests) | `IMPLEMENTED+TESTED` |
| NFR-02 | Low-latency event capture (p99 < 5ms at 10K req/s) | In-process 6452/sec measured | `scripts/load_test.py` | `PARTIAL` (in-process proven; AWS topology DEFERRED — see BR-09) |
| NFR-03 | Secure encryption (at rest + in transit) | KMS envelope + TLS at gateway | Quarterly key-rotation policy | `DEFERRED` Phase 11 CP11.2 |
| NFR-04 | On-prem / VPC deployability | Helm chart | smoke test | `DEFERRED` Phase 13 CP13.6 |
| NFR-05 | Explainability and exportability | JSON-LD + PROV-O + narrative API | `verify_evidence_pack` integration tests | `IMPLEMENTED+TESTED` |
| NFR-06 | Scalable storage and search (OpenSearch backend) | Phase 12 | — | `DEFERRED`; cursor pagination meets v1.x scale |
| NFR-07 | Retention controls aligned to enterprise policy (5–10 year default) | GDPR Article 17 cryptographic shredding | `DEFERRED` Phase 13 CP13.2 |
| NFR-08 | Retry-safe ingest (idempotency dedup) | Stripe-style `Idempotency-Key`; same key + same body = original 201; same key + different body = 409 | 54 tests at 100% coverage; in-memory + Postgres store impls | `IMPLEMENTED+TESTED` (CP9.17) |
| NFR-09 | Console accessibility | WCAG 2.1 AA | Axe automated + manual sample | `DEFERRED` Phase 11 (Console hardening) |
| NFR-10 | Multi-tenant data isolation | Logical RLS on `tenant_id` everywhere | annual pen-test | `IMPLEMENTED+TESTED` (PG triggers + route-layer auth) |

---

## 10. Phase Plan and CP-anchored Timeline (v2.0 replaces v1.2 "Day 5/6" calendar narrative)

| Phase | CP range | Trigger / output | Status |
|---|---|---|---|
| Phase 1 — Scaffold | CP1.0..CP1.x | Project skeleton, schema, ingest path | ✅ complete |
| Phase 2 — Identity & Chain | CP2.0..CP2.x | Tenant signing, hash chain primitive | ✅ complete |
| Phase 3 — Policy Snapshot | CP3.0..CP3.x | BR-04 policy bundle snapshot | ✅ complete |
| Phase 4 — Console MVP | CP4.0..CP4.x | Receipts list + receipt detail console pages | ✅ complete |
| Phase 5 — Export | CP5.0..CP5.x | JSON-LD export builder | ✅ complete |
| Phase 6 — JSON-LD Pack | CP6.1..CP6.4 | Evidence pack endpoint | ✅ complete |
| Phase 7 — Mock Narrative | CP7.0..CP7.x | Mock narrative client | ✅ complete (superseded by Phase 9 CP9.1) |
| Phase 8 — Load Test | CP8.1..CP8.2 | 6452 events/sec in-process | ✅ complete |
| Phase 9 — Live Narrative + PDF + TSA + Tabletop + M&A | CP9.1..CP9.51 | BR-05 PDF / BR-06 TSA + cert verify / BR-10/11 live narrative / BR-12 tabletop / BR-13 M&A / CP9.50 evidence pack console / CP9.51 TSA cert chain | ✅ 13/13 BR-01..BR-13 at IMPLEMENTED+TESTED (BR-07, BR-08 are explicit DEFERRED-by-design; BR-09 is the PARTIAL row at AWS-topology level) |
| **Phase 9.52+ — Operator Console enterprise list views + PWA** | **CP9.52..CP9.6x** | **BR-14 (PARTIAL → IMPLEMENTED+TESTED). SCR-F01..F08 + PWA manifest/SW + Playwright UI-driving E2E. Adopts mendoraci CP-9 list-views pattern (RT-F19).** | 🟡 **next** |
| Phase 10 — Auth & Tenancy | CP10.1..CP10.4 | UC-10 multi-tenant authenticated access; SCR-F09 login; per-tenant token; SSO planning | ⏳ planned |
| Phase 11 — Security Hardening | CP11.1..CP11.6 | NFR-03 KMS envelope; NFR-09 WCAG; M&A detached platform signature; merkle tree (RFC 6962) | ⏳ planned |
| Phase 12 — Scale & AWS | CP12.1..CP12.4 | OTel traceparent; OpenSearch backend; AWS Kafka + S3 + EventBridge ingest (BR-09 full); LangGraph multi-agent (BR-07) | ⏳ planned |
| Phase 13 — On-prem & GDPR | CP13.1..CP13.6 | GDPR Art-17 cryptographic shredding; NL query UX in Console; Helm chart; Omniverse (BR-08) | ⏳ planned |
| **Phase 14 — Native Console** | **CP14.1+** | **Native iOS + Android Operator Console clients (React Native or Swift/Kotlin TBD at Phase 14 entry). Separate auth flow, app-store submission, separate test matrix.** | ⏳ **deferred — explicit roadmap item** |

### 10.1 Critical-path callouts for CP9.52+
1. **SCR-F01..F08 must adopt list-views-as-top-nav pattern** — no sessionStorage shortcuts. The mendoraci CP-9 course correction is the cautionary tale; Forensa pre-empts it.
2. **PWA manifest + service worker before Phase 10** — the auth flow on PWA needs the install context.
3. **Playwright UI-driving specs before the captioned demo recording** — current spec drives API, not UI; CP9.52 makes the recording reflect the user journey.

---

## 11. Readiness Scorecard (interim 18 May 2026 05:15 BST)

10 dimensions × 7 = 70 max.

| # | Dimension | Weight | Current | Evidence | Path to 7 |
|---|---|---|---|---|---|
| 1 | Problem clarity / market fit | 7 | 6 | §1 ROI table, §3.1 EU AI Act drivers | IMP-F18 segment validation interviews → 7 |
| 2 | AI necessity | 7 | 6 | BR-10/11 narrative + counterfactual; EVAL-F01/02 | IMP-F11 semantic hallucination guardrail → 7 |
| 3 | Cryptographic robustness | 7 | 7 | BR-06 live RFC 3161 + cert-chain verification CP9.51 | maintain |
| 4 | Technical feasibility | 7 | 7 | Stack: Python 3.14, FastAPI, PostgreSQL 16, SQLAlchemy 2.0 async, Next.js 16 / React 19 | maintain |
| 5 | Auditability / governance | 7 | 7 | Evidence Packs, RFC 3161 anchor, M&A diligence export with offline verification | maintain |
| 6 | Compliance posture | 7 | 6 | EU AI Act Art 12 + DORA Art 30 + NIST AI RMF + ISO 42001 mapped | IMP-F19 SOC 2 control evidence window → 7 Phase 14 |
| 7 | Demo readiness | 7 | 5 | Captioned demo spec exists; Console UI is thin | **CP9.52 Operator Console + PWA + UI-driving Playwright → 7** |
| 8 | Commercialisation | 7 | 5 | ACV bands in `04_pricing_and_commercial/PRICING_AND_COMMERCIAL_MODEL.md` | IMP-F20 sponsor conversations → 6 |
| 9 | Operational readiness | 7 | 5 | `18_sre_and_operations/SRE_AND_OPERATIONS.md` skeleton | IMP-F21 OTel traceparent CP12.1 → 6 |
| 10 | Risk management | 7 | 5 | §15 risk register (new in v2.0) | IMP-F22 risk-owner staffing → 6 |
| **Total** | | **70** | **61** | | **+5 achievable in Phase 9.52..Phase 11; ceiling 70 requires production evidence** |

---

## 12. Competitive Comparative Matrix

Sourced from `03_competitive_landscape/COMPETITIVE_LANDSCAPE.md`. Eight named alternatives:

| # | Competitor | Proximity | Where they win | Where Forensa wins | Switching cost |
|---|---|---|---|---|---|
| OPT-F01 | **Forensa** | 100% | reference | reference | n/a |
| OPT-F02 | Roll-your-own logging + Slack | 18% | Zero license | Cryptographic chain, RFC 3161 TSA, regulator-grade PDF, no engineering effort | Low |
| OPT-F03 | Splunk / Datadog observability | 35% | Existing footprint, infra telemetry | Policy-bound decision lineage, cryptographic integrity, evidence-pack export | High (already owned but wrong layer) |
| OPT-F04 | Credo AI / Holistic AI governance | 55% | Policy authoring UX, vendor risk scoring | Cryptographic evidence chain, RFC 3161 TSA, hands-off ingest from agents | Medium |
| OPT-F05 | Robust Intelligence / Lakera (model risk) | 30% | Model evaluation depth | Decision lineage capture, multi-agent chain (Phase 12) | Low–Med |
| OPT-F06 | OpenTelemetry GenAI + custom retention | 40% | Open standard, broad vendor adoption | Cryptographic chain on top of OTel envelope, regulator-grade pack | Low (Forensa consumes OTel as ingest wire format) |
| OPT-F07 | Auditex (pattern reference) | 60% | Polished demo UX, 2-crypto-op pattern | Real RFC 3161 cert-chain verification (CP9.51); deeper crypto layer | Medium |
| OPT-F08 | Build-in-house cryptographic logging | 28% | Bespoke fit | 18-month build vs 90-day Forensa pilot; ongoing maintenance | High over 3-year horizon |

**Insight:** Forensa's defensible wedge is **cryptographic integrity (RFC 3161 + cert-chain verification) + policy-snapshot binding + regulator-grade exportability + Operator Console for non-technical personas**. No named competitor delivers all four.

---

## 13. Commercialisation

Sourced from `04_pricing_and_commercial/PRICING_AND_COMMERCIAL_MODEL.md`. Summary:

### 13.1 Pricing tiers

| Tier | Segment | Per-month list | Anchor ACV | Inclusions | Exclusions |
|---|---|---|---|---|---|
| Pilot | ≤ 1 tenant, ≤ 500 agent actions/day | $5,000 | $60K | All BR-01..BR-06 + BR-10..BR-13; Console Web; PWA | Native; on-prem; SOC 2 audit |
| Team | 1 tenant, ≤ 5,000 agent actions/day | $14,000 | $168K | + SSO, dedicated CSM, Slack/email notify | On-prem |
| Enterprise | ≤ 5 tenants, ≤ 50,000 agent actions/day | $38,000 | $456K | + SCIM, EU data residency, SOC 2 evidence sharing | Native |
| Strategic | unlimited tenants, custom volume | Custom | $920K+ | + on-prem option + native Console (Phase 14+) + dedicated AI Lead | — |

Hybrid model (per-tenant + per-agent-action + governance flat fee). Currency USD.

### 13.2 Sales motion
- **TOFU:** EU AI Act educational content, compliance-officer LinkedIn motion, regulatory webinars
- **Pilot wedge:** 60-day paid pilot, refundable if regulator-pack verifiability proof fails
- **Expansion:** Pilot → Team → Enterprise → Strategic; NDR target 135%+
- **Channel:** Big-4 audit firms (Phase 4 partnership), regulated-sector GSI (Accenture, Deloitte) Phase 14

### 13.3 Target segments
1. UK / EU financial services (FCA, EBA, ECB perimeter) — mortgage lending, lending decisions, fraud screening
2. EU healthtech (EU AI Act high-risk class)
3. Govtech (NIST AI RMF mandatory federal AI deployments)
4. M&A acquirers requiring AI governance diligence (BR-13)

---

## 14. AI Necessity, Feasibility, Auditability, Compliance, Demo, Ops

### 14.1 AI necessity
- BR-10/BR-11 narrative + counterfactual generation requires LLM capability beyond rule-based summarisation (multi-source synthesis, plain-English regulator-ready prose)
- BR-03 reasoning capture is downstream of any LLM-mediated agent action; Forensa itself does not generate reasoning, it captures and signs what the agent emitted
- The cryptographic layer (BR-01, BR-06) is non-AI and stays so

### 14.2 Data readiness and EVAL gates
- **EVAL-F01 — Narrative quality.** Task: plain-English summary of receipt window. Gold-set N=50 (target N=250 by pilot exit). Metric: human-rated faithfulness ≥ 0.85. Slice: regulator-pack windows, M&A windows, tabletop windows.
- **EVAL-F02 — Prompt-injection defence.** Task: defence catches injection on adversarial corpus. Gold-set N=100 (CP9.1 ships with N=30 negative cases; expansion to N=500 by pilot exit). Metric: 0 leaks. Slice: structural injection, role-play injection, output-formatting injection, multi-hop injection.

### 14.3 Technical feasibility
Stack: Python 3.14, FastAPI, PostgreSQL 16.13, SQLAlchemy 2.0 async, strict Pydantic v2, pytest with 100% coverage gate, Next.js 16, React 19, vitest, Playwright. FreeTSA as external RFC 3161 source. Gemini 2.5 Pro for narrative. All proven in production stacks.

### 14.4 Auditability
Every Receipt writes to append-only ledger with `payload_hash` + `signature_b64` + `receipt_hash` + `prev_receipt_hash`. Every policy decision binds to a `policy_snapshot_id`. Every day anchored to FreeTSA RFC 3161 with cert-chain verification. M&A export computes `ma_root_hash` for offline acquirer verification. Tabletop replays are explicitly non-persisting.

### 14.5 Compliance posture
- **EU AI Act Article 12** (high-risk logging) — BR-01, BR-03, BR-04, BR-05, BR-06 satisfy. Forensa is the canonical Article 12 logging layer.
- **EU AI Act Article 14** (human oversight) — captured via human-approval events in BR-01 ingest; policy-bundle approval workflow (CP9.15)
- **EU AI Act Article 18** (10-year tech-doc retention) — supported via append-only ledger + KMS envelope (Phase 11) + retention policy
- **DORA Article 30** (ICT tabletop) — BR-12 tabletop simulation
- **NIST AI RMF** — BR-01, BR-04, BR-05 satisfy "GOVERN-DECIDE" map
- **ISO 42001:2023** — BR-01, BR-04, BR-05 satisfy AI management system clauses
- **SOC 2 Type II** — controls mapped; audit cycle requires 6-month evidence window (Phase 14)
- **HIPAA** — BR-01 + BR-05 + BR-09 (when AWS topology lands) cover BAA-able evidence
- **GDPR Art 32** — multi-tenant identity binding (BR-02)
- **GDPR Art 17** — cryptographic shredding `DEFERRED` Phase 13 CP13.2 (append-only × erasure tension)

### 14.6 Demo readiness
CP9.50 shipped `/evidence` Console page; CP9.51 shipped TSA cert-chain verification; **CP9.52 ships the Operator Console enterprise list-views + PWA + UI-driving Playwright** — that's the demo-readiness flip from 5/7 to 7/7. The native iOS/Android Console is explicitly Phase 14+ and is **not** a v1.x demo gate. The PWA install on a phone home screen at TechEx is the "Web + App" demo affordance for v1.x.

### 14.7 Operational readiness
See §17 and `18_sre_and_operations/SRE_AND_OPERATIONS.md`.

---

## 15. Risk Register

| ID | Risk | L (1–5) | I (1–5) | Score | Mitigation | Owner | Phase |
|---|---|---|---|---|---|---|---|
| R-F01 | FreeTSA outage causes daily anchor failure | 3 | 4 | 12 | Deferred-tombstone fallback (CP9.19); planning Phase 11 second TSA fallback (IMP-F12) | P-PLAT | 9 |
| R-F02 | Prompt-injection bypass on narrative endpoint | 2 | 5 | 10 | 4-layer defence (CP9.1); EVAL-F02 corpus expansion to N=500 (Phase 10) | AI Lead | 10 |
| R-F03 | Cross-tenant data leakage via 403/404 timing | 2 | 5 | 10 | Bundle-lookup uses 404 not 403 to avoid bundle-id leak (BR-12); annual pen-test | P-PLAT | 10 |
| R-F04 | Demo failure at TechEx (UI regression) | 2 | 4 | 8 | Pre-recorded fallback; Playwright UI-driving E2E pre-flight (CP9.52); deterministic seed | P-PLAT | 9.52 |
| R-F05 | sessionStorage anti-pattern adopted in Console (mendoraci CP-9 cautionary tale) | 2 | 3 | 6 | BR-14 AC-2 explicit prohibition + RT-F19 list-views pattern; pre-emptive (not reactive) | Tech Lead | 9.52 |
| R-F06 | Console-only auth coupling breaks API client-agnosticism | 2 | 4 | 8 | Per-tenant token in API layer (CP10.1) decoupled from Console; client-agnostic API tests | P-PLAT | 10 |
| R-F07 | KMS envelope deferral leaves at-rest encryption gap | 3 | 4 | 12 | Phase 11 CP11.2 commitment; interim TLS-at-gateway documented | P-PLAT + Sec Lead | 11 |
| R-F08 | M&A diligence export bundle forgery (no detached platform sig) | 2 | 4 | 8 | NEW-P11.X.ma-export-detached-platform-signature in BRD § BR-13 backlog | P-COUNSEL + P-PLAT | 11 |
| R-F09 | Native Console expectation creep (sponsors pull native into v1.x) | 3 | 3 | 9 | BR-14 AC-9 explicit Phase 14+ commitment; documented in DEPLOYMENT_TOPOLOGY + Pricing Strategic tier | Product Owner | 9.52 |
| R-F10 | PWA install adoption low (judges don't install on phone) | 3 | 2 | 6 | Pre-install demo phone for TechEx; install QR code on JUDGE_HANDOUT | P-PLAT | 9.52 |
| R-F11 | LangGraph (BR-07) deferral leaves multi-agent workflows unserved | 3 | 4 | 12 | Phase 12 CP12.x commitment; interim agent-identity-via-DID supports basic multi-agent | AI Lead | 12 |
| R-F12 | Documentation drift between canonical + LIVE (the exact pattern this v2.0 work item addresses) | 4 | 3 | 12 | Rule A.10 + Rule A.11 + LIVE-update-after-every-commit cadence in `docs/README.md` | Tech Lead | continuous |

Score: ≥15 critical (top-priority); 9–14 high; <9 monitored.

---

## 16. Data Governance Annex

### 16.1 Data classification

| Class | Examples in Forensa | Mask required? | Encryption | Retention |
|---|---|---|---|---|
| C1 — Public | Forensa product docs | No | Standard | Indefinite |
| C2 — Internal | Tenant metadata, agent identifiers | No | Standard | 24 months |
| C3 — Confidential (default for events) | Event body, reasoning, model output | No (events arrive masked at ingest by the agent platform) | KMS-rooted DEK (Phase 11) | 7-year default, 10-year for EU AI Act Article 18 |
| C4 — Restricted | Tenant private keys, agent signing keys | n/a — KMS-only | HSM / KMS | per tenant policy |
| C5 — Personal (limited) | Operator names in approval events | No (audit need) | KMS-rooted | GDPR-erasure-aware Phase 13 |

### 16.2 Lineage
Every Receipt carries `event_id` → `policy_snapshot_id` → `prev_receipt_hash`. Every Evidence Pack carries `header.tenant_id` + `header.scope_start/end` + `root_hash` + per-anchor `anchor_id`. End-to-end queryable.

### 16.3 Retention policy
- Receipts + chain: indefinite (append-only)
- Evidence Packs: regenerated on demand from receipts; not stored
- Tabletop results: NOT persisted (by design)
- Idempotency records: 24h TTL (in-memory store) or configurable per tenant (Postgres store)

### 16.4 Evaluation governance
EVAL-F01, EVAL-F02 captured to `eval_runs` table (Phase 10 — stub today). Prompt versions in `packages/narrative/prompt.py`; promotion requires AI Lead approval + EVAL gate pass.

---

## 17. Operational Readiness (summary; full doc at `18_sre_and_operations/SRE_AND_OPERATIONS.md`)

- **Two-tier on-call (Phase 14):** L1 platform, L2 AI / crypto. SLA: P1 ack 15 min, resolve 4 hours.
- **Observability:** OTel root spans (Phase 12 CP12.1); structured JSON logs; Prometheus metrics; per-tenant log buckets
- **SLOs:** chain-integrity verification rate, anchor success rate, ingest p99 latency, narrative-API p95 latency, evidence-pack-generation success rate
- **Alerts:** chain-integrity fail → page; anchor fail 2 days running → ticket; mask engine failure → page; cost-ceiling 80% → email
- **Incident runbook:** per top-10 failure mode in `19_incident_response_plan/INCIDENT_RESPONSE_PLAN.md`

---

## 18. Out of scope for v1.x (consolidated, with phase pointers)

- Full enterprise SIEM replacement
- End-to-end legal-hold platform (Forensa is the evidence layer, not the case management)
- Complete document management system
- Deep ERP workflow automation beyond evidence capture
- General observability suite for all infrastructure
- **Native iOS / native Android Operator Console clients (Phase 14+)** — PWA is v1.x scope
- Bring-your-own-LLM (Gemini 2.5 Pro is the supported model for v1.x narrative)

---

## 19. Traceability

Each BR maps to architecture component, source files, test suite, and downstream regulator mapping. See `TRACEABILITY_MATRIX.md` for the full 12-column RT-F01..RT-F22 index and the API → DB → Evidence map.

---

## 20. Change Log

| Date | Change |
|---|---|
| 2026-05-18 05:15 BST | **v2.0 ELABORATED.** Elaborated to mendoraci enterprise-BRD shape. Added §1 Executive Summary with ROI table, §2 Identifier Map summary, §3 Problem/Current/Target/Metrics, §4 Stakeholders & Personas with pain + KPI, §5 In/Out scope, §6 Business Goals + BG → BR contribution matrix, §11 Readiness Scorecard, §12 Competitive Matrix, §13 Commercialisation, §14 AI Necessity sub-sections, §15 Risk Register, §16 Data Governance Annex, §17 Operational Readiness summary. **Added BR-14 (Operator Console — Web + PWA, native iOS/Android deferred Phase 14+).** Supersession map §0.3 records the four v1.2-narrative-vs-HEAD drifts (BR-02, BR-06, BR-10, BR-11). Locked Rule A.11 (CP ↔ requirement closure). v1.2 preserved verbatim at `_archive/BRD_v1.2_20260515_CP9.29.md`. |
| 2026-05-15 11:22 | CP9.29 landed. **BR-12 flips DEFERRED → IMPLEMENTED+TESTED.** Headline 9/13 → 10/13. (See archived v1.2 change log for detail.) |
| 2026-05-15 10:55 | CP9.28 landed. **BR-13 flips STUB → IMPLEMENTED+TESTED.** Headline 8/13 → 9/13. |
| 2026-05-15 07:10 | CP9.21a+b landed. BR-05 flips PARTIAL → IMPLEMENTED+TESTED. Headline → 9/13. |
| 2026-05-14 22:02 | CP9.17 landed. NFR-08 Retry-safe ingest added at IMPLEMENTED+TESTED. |
| 2026-05-14 20:07 | CP9.16-PG-up landed. BR-01 narrative updated to reference DB-level append-only triggers. |
| 2026-05-14 09:58 | Status column first added per EnterpriseGradeReview fix #10. |
| 2026-05-12 | v1 BRD frozen with 13 BRs. |

---

**End of BRD v2.0. See companion documents:** `BRD_IDENTIFIER_MAP.md`, `USE_CASES.md` (UC-01..UC-10 + US-F01..F32 + SCR-F01..F10 + epics), `TRACEABILITY_MATRIX.md` (RT-F01..F22 + API/DB/Evidence maps), their LIVE counterparts, the per-doc folders for SYSTEM_ARCHITECTURE / DEPLOYMENT_TOPOLOGY / SECURITY_ARCHITECTURE / DATA_MODEL / EVIDENCE_PACK_SPEC, and `docs/README.md` for the full doc map and reading paths.
