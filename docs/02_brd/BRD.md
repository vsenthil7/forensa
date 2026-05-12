# Forensa - Business Requirements Document (BRD)

**Doc:** 02 of 22 | **Date:** 12 May 2026 | **Status:** v1, frozen | **Source:** Section A.2 of three-author master doc

## 13 Business Requirements (BR-01 through BR-13)

### BR-01 - Tamper-evident event recording
Every agent action (prompt, model response, tool call, policy verdict, human approval, business outcome) is captured as a structured event and appended to a cryptographically-chained ledger (Merkle tree with RFC 3161 TSA anchoring).
**Architecture component:** packages/ingest, packages/ledger
**Test coverage:** unit + property-based on chain integrity

### BR-02 - Multi-party identity binding
Every event is signed by both the originating agent identity (DID/HDP-bound) and the enterprise tenant. No agent action can be repudiated by either party.
**Architecture component:** packages/crypto, apps/api/auth
**Test coverage:** unit + integration on signature verification

### BR-03 - Reasoning capture (Oracle AER pattern)
For LLM-mediated actions, capture not just the input/output but the agent's intermediate reasoning chain (chain-of-thought summary, tool selection rationale, confidence signals).
**Architecture component:** packages/schema, packages/ingest
**Test coverage:** unit + e2e via Playwright on capture path

### BR-04 - Policy snapshot at decision time
Every event records which policy version was active when the decision was made. Six months later when policies have changed, the original policy state is reconstructible.
**Architecture component:** packages/policy, packages/ledger
**Test coverage:** integration on snapshot binding

### BR-05 - Regulator-grade export
Generate signed evidence packs aligned to EU AI Act Article 12, NIST AI RMF, ISO 42001, SOC 2 Type II, HIPAA, DORA, MAR/Reg FD.
**Architecture component:** packages/export
**Test coverage:** integration on JSON-LD + PDF generation

### BR-06 - Merkle-chained ledger with RFC 3161 TSA
Every receipt is hash-chained to the previous one and anchored to an external time-stamping authority on a daily cadence.
**Architecture component:** packages/crypto, packages/ledger
**Test coverage:** property-based on chain verification

### BR-07 - Multi-agent provenance graph (LangGraph)
For multi-agent workflows, the evidence graph captures the full DAG of agent-to-agent handoffs, with each edge signed.
**Architecture component:** packages/ingest, apps/api
**Test coverage:** integration on graph reconstruction

### BR-08 - Omniverse physical-action replay (stretch)
When the action chain culminates in a physical effect (robot motion, logistics dispatch), the digital twin replay reconstructs the physical race conditions in the same evidence pack.
**Architecture component:** apps/console (replay viewer)
**Test coverage:** e2e on replay UI; cut from v1 demo if Day 5 slips

### BR-09 - AWS-backed bulk historical backfill
S3 + EventBridge + Glue + Step Functions + SageMaker Feature Store + OpenSearch Serverless backbone. 18+ months evidence retention with sub-second query latency.
**Architecture component:** deploy/, packages/ledger
**Test coverage:** load tests via Locust proving 10K sustained + 100K peak

### BR-10 - Investigator UI with natural-language query
Gemini Flash drives the analyst console. "Show me every refund over five thousand processed by agent X in Q1" returns the evidence chain in seconds.
**Architecture component:** apps/console
**Test coverage:** Playwright e2e on query roundtrip

### BR-11 - Counterfactual narrative generation
Gemini Pro generates regulator-readable narratives from raw evidence - NOT as source of truth (cryptographic chain is) but as the human-readable interpretation layer.
**Architecture component:** packages/export
**Test coverage:** integration on narrative generation + hallucination guardrails

### BR-12 - Tabletop incident response mode
Pre-built scenarios let CISO teams rehearse AI incident response against synthetic evidence. Used for DORA Article 30 tabletop certification.
**Architecture component:** packages/policy/tabletop
**Test coverage:** integration on synthetic event generation

### BR-13 - M&A due diligence export
Acquiring company asks "what AI is in this target's stack and what evidence exists." Forensa generates full inventory + 90-day evidence sample in days, not months.
**Architecture component:** packages/export
**Test coverage:** integration on inventory export

## Non-functional requirements (from Section C.16)

- High integrity and immutability (BR-01, BR-06)
- Low-latency event capture (p99 < 5ms at 10K req/s)
- Secure encryption (at rest + in transit)
- On-prem or VPC deployability for sensitive environments
- Explainability and exportability
- Scalable storage and search (OpenSearch backend)
- Retention and deletion controls aligned to enterprise policy (5-10 year default)

## Out of scope for v1

- Full enterprise SIEM replacement
- End-to-end legal hold platform
- Complete document management system
- Deep ERP workflow automation beyond evidence capture
- General observability suite for all infrastructure

## Traceability

Each BR maps to architecture component + test suite. See docs/17_traceability_matrix/TRACEABILITY_MATRIX.md for the full BR -> component -> test -> code-file mapping.
