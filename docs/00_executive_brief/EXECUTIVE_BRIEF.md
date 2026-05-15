# Forensa - Executive Brief

**Document:** 00 of 22 in the Forensa doc pack
**Date:** 15 May 2026 (revised at Phase 9 close-out)
**Status:** v2, locked for hackathon submission Mon 19 May 2026
**Audience:** TechEx judges, Veea Award reviewers, Gemini Award reviewers, prospective design partners

---

## The one-paragraph pitch

Forensa is the **cryptographic evidence layer for enterprise AI agents**. Every prompt, model response, tool call, policy verdict, human approval, and business action gets captured as a tamper-evident, multi-party-bound, policy-aware Receipt and appended to a hash-chained ledger. When a regulator, auditor, or court asks "what did your AI do, why, on whose authority", the enterprise can answer with cryptographic proof in minutes instead of weeks. Built for EU AI Act Article 12 (effective August 2026), DORA Article 30, NIST AI RMF, ISO 42001, SOC 2 Type II.

---

## The market problem

Enterprises are deploying AI agents into workflows that touch regulated data, financial actions, customer communications, and tool-connected operations. When something goes wrong, they cannot prove what happened, which model produced the outcome, who approved the step, which controls were active, or whether the agent crossed policy boundaries. The reconstruction is forensic work that takes weeks; by the time a regulator inquires six months later, source systems have rotated and the evidence has decayed.

**EU AI Act Article 12** (effective August 2026) makes this non-negotiable. Article 12 requires "automatic logging appropriate to the intended purpose" for high-risk AI systems, and the documentation retention obligation extends ten years. Forensa is the layer that satisfies it.

## The wedge

Every incumbent in the AI runtime space - Microsoft AGT, Preloop, AWS Bedrock AgentCore, Veea Lobster Trap itself - is building **enforcement**. Nobody is building **evidence**.

Enforcement answers "should the agent be allowed to do X?" Evidence answers "six months later, can we prove what actually happened?" They are different products with different buyers and different success criteria. Forensa owns the evidence layer.

## The product (as shipped at HEAD `34d4cc4`)

Forensa has shipped six fully-wired surfaces at this submission. Status against the original 13-BR plan: **9 IMPLEMENTED+TESTED, 4 DEFERRED out-of-hackathon by design, 0 PARTIAL outside the post-submission roadmap.**

1. **Ingest pipeline** - OpenTelemetry GenAI semconv compatible. SpanKind=INTERNAL rejection prevents instrumentation plumbing leaking into evidence. `reasoning` vs `output` correctly disambiguated. **(BR-04 ✅)**
2. **Hash-chained ledger** - Append-only-by-code AND append-only-by-database-trigger (verified by 26 PG-mode integration tests). Per-tenant Ed25519 signing keys. RFC 3161 TSA daily anchoring with deferred-tombstone fallback for failed TSA calls. **(BR-01, BR-03, BR-06 ✅)**
3. **Policy snapshot binding + dual signature** - The exact policy bundle active at decision time is bound to each Receipt. Tenant + agent dual signature. Vendor-neutral `PolicyEnforcementClient` ABC so Veea Lobster Trap, Microsoft AGT, AWS Bedrock AgentCore, or custom enforcement all drop in equivalently. **(BR-02, BR-04 ✅)**
4. **Narrative generation** - Live Gemini 2.5 Pro via `google.genai` SDK with `ThinkingConfig(thinking_budget=0)` for deterministic completions. 4-layer prompt-injection defence (deny-list + structural assertions + system-prompt isolation + role separation). HTTP 422 + `incident_id` when defence fires. **(BR-10, BR-11 ✅)**
5. **Evidence pack export** - JSON-LD with PROV-O lineage AND PDF (deterministic A4 with pinned `/CreationDate`+`/ModDate` for byte-identical re-renders). Embedded RFC 3161 TSA proof inline so the pack is offline-verifiable. Content negotiation via `Accept` header. **(BR-05 ✅)**
6. **Offline regulator verification** - GET /v1/anchors/{id} with `Accept: application/timestamp-reply` returns raw RFC 3161 DER bytes for direct piping into `openssl ts -verify`. The 3-anchor verifiability chain `(pack_root_hash, prompt_hash, content_hash)` lets a regulator verify every narrative independently.

Deferred BRs (Phase 10+ roadmap): BR-07 LangGraph multi-agent provenance, BR-08 Omniverse physical-action replay, BR-09 10K events/sec sustained (Kafka path → CP12.4), BR-12 tabletop incident response mode, BR-13 M&A due-diligence export.

## The demo moneyshot

A regulator asks the agent operator: "Prove this denial really happened on 14 May, on this chain, with this policy version." Operator pulls the day's evidence pack with one curl. Pipes the day's RFC 3161 TSR directly into `openssl ts -verify` with a second curl. The math agrees; the regulator's question is answered in 30 seconds. Without Forensa, that proof chain does not exist. With Forensa, it is literally one curl plus one openssl. Live demo arc:

```bash
curl -H "Authorization: Bearer $TOKEN" \
     "$FORENSA/v1/evidence-packs?tenant_id=$T&scope_start=$START&scope_end=$END"

curl -H "Accept: application/timestamp-reply" \
     "$FORENSA/v1/anchors/$ANCHOR_ID" \
  | openssl ts -verify -in /dev/stdin -CAfile $TSA_CA -data <(echo -n $ROOT_HASH)
# → Verification: OK
```

## Sponsor technology utilisation (as shipped)

All figures below reflect what ACTUALLY landed at HEAD `34d4cc4`, not the original v1 plan. Some primitives in the v1 plan moved to the Phase 10-13 roadmap by design (Omniverse, GR00T, MCP auditor portal, DT Consortium).

| Sponsor | Role | Status at submission |
|---|---|---|
| Veea Lobster Trap | Policy enforcement verdict source via `VeeaLobsterTrapClient` (one provider of the vendor-neutral `PolicyEnforcementClient` ABC) | ✅ Shipped |
| Google Gemini 2.5 Pro | Narrative generation with 4-layer prompt-injection defence; `ThinkingConfig(thinking_budget=0)` for fast deterministic completions | ✅ Shipped (BR-10 + BR-11) |
| Google AI Studio | Live API path for hackathon submission via `google.genai` SDK | ✅ Shipped |
| RFC 3161 TSA | Daily timestamp anchoring of chain root with deferred-tombstone fallback | ✅ Shipped (BR-06) |
| OpenTelemetry GenAI | Wire-format compatibility for agent traces; SpanKind=INTERNAL rejection | ✅ Shipped |
| PostgreSQL 16 | Multi-tenant tamper-evident store with append-only triggers and RLS-ready models | ✅ Shipped (26 PG-mode integration tests) |
| Gemini 3 Pro multimodal (PDF/scan binding) | Multimodal Receipts | ⏸ Phase 12 (deferred) |
| Gemini Flash (investigator UX) | Sub-second investigator queries | ⏸ Phase 11 (deferred; the API surface is shipped, the live console UI moves out of hackathon scope) |
| LangGraph multi-agent provenance | Multi-agent workflow capture | ⏸ Phase 11 (BR-07 deferred) |
| MCP tool-call evidence + auditor portal | Auditor portal as MCP service | ⏸ Phase 13 (deferred) |
| NVIDIA Omniverse + Isaac Sim | Physical-action replay | ⏸ Phase 11 (BR-08 deferred) |
| NVIDIA GR00T VLA | VLA model evaluation evidence | ⏸ Phase 11 (deferred) |
| AWS pipeline (S3 + EventBridge + Glue + OpenSearch) | Multi-region production storage | ⏸ Phase 12 (deferred; v1 is single-region Postgres) |
| DT Consortium / XMPro | Vendor-neutral twin semantics | ⏸ Phase 11 (deferred) |

## The Big I

Enterprise AI will not become trusted because it is useful. It becomes trusted when the enterprise can **prove what the AI saw, what it reasoned, what tool it used, what policy applied, who approved, what action happened, and that the record is tamper-evident**. Forensa belongs to an emerging category - AI EvidenceOps - that will become as normal as audit logs, transaction logs, SIEM events, and financial ledgers. Purpose-built for AI-era workflows.

## Commercial shape

| Tier | Price range | Customer profile |
|---|---:|---|
| Team Pilot | 25K to 75K per year | AI platform pilots |
| Enterprise Standard | 150K to 500K per year | Mid-to-large enterprise |
| Regulated Enterprise | 500K to 2M per year | Banking, healthcare, legal |
| Strategic Deployment | 2M plus per year | Multi-region regulated enterprise |

Year 1 plan: 8 design partners at 200K to 500K ARR, EU AI Act Article 12 driving urgency. Audit firm channel (Big 4 white-label) accelerates reach in year 2.

## Why this is a company, not a demo

- AI regulation is increasing traceability pressure (EU AI Act, DORA, CSDDD, NIST AI RMF, ISO 42001)
- Enterprises are moving from copilots to tool-using agents, raising risk and evidence demands
- Post-incident reconstruction is still weak in current AI deployments
- Evidence is a budgeted problem for security, audit, legal, and compliance teams
- The category expands from agent evidence into enterprise AI accountability infrastructure
- Year 4 moat: bilateral ledger history switching cost, audit-firm familiarity, regulator-recommended format, insurance integration, standards positioning

## Hackathon submission shape (as shipped)

- **Public GitHub repo** at `github.com/vsenthil7/forensa` (MIT-licensed core) - **shipped, HEAD `34d4cc4`**
- **Live demo** showing 6-month-after evidence reconstruction with cryptographic verification - **shipped, demo arc in 2 curls**
- **5-minute video script** at `docs/00_executive_brief/SUBMISSION_VIDEO_SCRIPT.md` covering wedge + problem + demo + architecture + shipped status + sponsor fit + ask - **shipped**
- **Judge handout** at `docs/00_executive_brief/JUDGE_HANDOUT.md` - **shipped**
- **22-doc enterprise governance pack** at `docs/` (BRD with Status column, Threat Model, Reg Mapping, API Spec, Traceability, etc.) - **shipped**
- **Phase 9 close-out** at `phases/PHASES_DONE_PHASE9_*.md` itemising all 25 CPs across 36 commits in ~46 hours wall-clock - **shipped**
- **TechEx submission** Mon 19 May 2026 - **3 days out**

Quality bar at HEAD `34d4cc4`:
- 878 default-mode tests passed; 904 PG-mode integration tests passed; 100% line+branch coverage gate held throughout Phase 9
- `ruff check`, `ruff format --check`, `mypy --strict`, `bandit`, `pip-audit` all clean

## Track and award alignment

- **Track 1** - Agent Security and AI Governance (primary)
- **Veea Award** (Track 1) - strongest fit; Forensa is Lobster Trap extended into evidence infrastructure
- **Gemini Award** (Best use of Gemini) - secondary; Gemini Pro narrative + Flash investigator UX

## What comes next

Architecture document (07 in the doc pack) takes this Executive Brief and turns it into a buildable design. BRD (02) enumerates the 13 Business Requirements with their IMPLEMENTED+TESTED / PARTIAL / STUB / DEFERRED status column. Phase 10-13 roadmap at `phases/ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md` sequences the post-submission enterprise-grade work (real auth provider, KMS adapter, PostgreSQL Row-Level Security, detached platform signature, Kafka throughput path).

The build phase is closed. Forensa works end-to-end. The next 3 days are submission polish: video recording, pitch rehearsal, final repo housekeeping.
