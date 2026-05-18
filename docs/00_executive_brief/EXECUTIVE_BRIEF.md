# Forensa — Executive Brief

**Document:** 00 of 22 in the Forensa doc pack
**Date:** 18 May 2026 (refreshed at CP9.51 close-out as part of v2 doc elaboration)
**Status:** authoritative against HEAD CP9.51 `d7d9aaa`
**Audience:** TechEx judges, Veea Award reviewers, Gemini Award reviewers, prospective design partners, sponsor leads
**Supersedes:** `_archive/EXECUTIVE_BRIEF_v1_20260512.md`
**Companion docs:** `BRD.md`, `BRD_IDENTIFIER_MAP.md`, `JUDGE_HANDOUT.md`, `docs/README.md`

---

## The one-paragraph pitch

Forensa is the **cryptographic evidence layer for enterprise AI agents**. Every prompt, model response, tool call, policy verdict, human approval, and business action gets captured as a tamper-evident, multi-party-bound, policy-aware Receipt and appended to a hash-chained ledger; every day is anchored to a public RFC 3161 Time-Stamping Authority (FreeTSA) with full certificate-chain verification. When a regulator, auditor, or court asks "what did your AI do, why, on whose authority", the enterprise answers with cryptographic proof in minutes instead of weeks. Built for EU AI Act Article 12 (binding August 2026), DORA Article 30 (binding since January 2025), NIST AI RMF, ISO 42001, SOC 2 Type II.

---

## The market problem

Enterprises are deploying AI agents into workflows that touch regulated data, financial actions, customer communications, and tool-connected operations. When something goes wrong, they cannot prove what happened, which model produced the outcome, who approved the step, which controls were active, or whether the agent crossed policy boundaries. The reconstruction is forensic work that takes weeks; by the time a regulator inquires six months later, source systems have rotated and the evidence has decayed.

**EU AI Act Article 12** (binding August 2026) makes this non-negotiable. Article 12 requires "automatic logging appropriate to the intended purpose" for high-risk AI systems, and the documentation retention obligation extends ten years (Article 18). **DORA Article 30** (binding since January 2025) requires evidence of ICT third-party tabletop exercises; AI agents are ICT third-party. Forensa is the layer that satisfies both.

## The wedge

Every incumbent in the AI runtime space — Microsoft AGT, Preloop, AWS Bedrock AgentCore, Veea Lobster Trap itself — is building **enforcement**. Nobody is building **evidence**.

Enforcement answers "should the agent be allowed to do X?" Evidence answers "six months later, can we prove what actually happened?" They are different products with different buyers and different success criteria. Forensa owns the evidence layer.

## The product (as shipped at HEAD CP9.51 `d7d9aaa`)

Forensa has shipped **ten** fully-wired BR surfaces at this submission. Scoreboard against the 13-BR plan + new BR-14:

- **BR-01..BR-06, BR-10..BR-13 — `IMPLEMENTED+TESTED` (10 of 13)**
  - BR-01 tamper-evident event recording
  - BR-02 multi-party identity binding (tenant + agent signatures, agent identity wired in CP9.18a/b/c)
  - BR-03 reasoning capture (Oracle AER pattern)
  - BR-04 policy snapshot binding (PG triggers append-only)
  - BR-05 regulator-grade export (JSON-LD + deterministic A4 PDF, CP9.21a/b)
  - BR-06 Merkle-chained ledger + RFC 3161 TSA anchoring (FreeTSA, CP9.19) + **full certificate-chain verification (CP9.51 `d7d9aaa`)**
  - BR-10 investigator narrative — live Gemini 2.5 Pro client + 4-layer prompt-injection defence (CP9.1, SDK migrated CP9.20)
  - BR-11 counterfactual narrative — live Gemini 2.5 Pro
  - BR-12 tabletop simulation (CP9.29)
  - BR-13 M&A diligence export with `ma_root_hash` (CP9.28)
- **BR-07 LangGraph multi-agent provenance — `DEFERRED` Phase 12** (by design)
- **BR-08 Omniverse physical-action replay — `DEFERRED` Phase 13** (always stretch)
- **BR-09 AWS bulk historical backfill — `PARTIAL`** (in-process 6452 events/sec proven CP8.2; AWS topology `DEFERRED` Phase 12)
- **BR-14 Operator Console (Web + PWA, native iOS/Android deferred Phase 14+) — `PARTIAL` (NEW in v2 doc elaboration)**
  - Three primary screens shipped at MVP level (`/`, `/receipts/[id]`, `/evidence`)
  - Enterprise list-views pattern (timeline with cursor pagination + filters + URL-query persistence, Compliance-view toggle on `/evidence`, persona-aware landing, PWA shell) is the **CP9.52 work item** — the demo-readiness flip from 5/7 to 7/7

**Test telemetry at HEAD:** 914+ default tests at 100% line+branch coverage on the crypto + ledger + idempotency + tabletop + ma-export packages. 79 additional Playwright UI-driving cases planned for CP9.52+.

## Why Web + PWA and not native today

Forensa's Operator Console is **Next.js 16 / React 19 in v1.x, with a Progressive Web App (PWA) shell installable to phone, tablet, and desktop home screens**. Native iOS and native Android clients are **explicitly deferred to Phase 14+** — they are a separate engineering investment (separate auth flow, separate test matrix, app-store submission cycle), and committing to native in v1.x would crowd out enterprise hardening. The architectural commitment to native as a future surface is on record in `BRD.md` BR-14 AC-9 and `14_deployment_topology/DEPLOYMENT_TOPOLOGY.md` §Console so the API surface stays client-agnostic.

## What's different vs the 12 May v1 of this brief

- HEAD bumped from `34d4cc4` to CP9.51 `d7d9aaa`
- Scoreboard 9/13 → **10/13** BR-01..BR-13 (BR-13 flipped at CP9.28, BR-12 flipped at CP9.29, BR-06 grew cert-chain verification at CP9.51)
- New **BR-14 Operator Console (Web + PWA)** introduced as first-class tracked surface
- Pointer to new `BRD_IDENTIFIER_MAP.md` and elaborated `USE_CASES.md` (US-F01..F32 + SCR-F01..F10) and `TRACEABILITY_MATRIX.md` (RT-F01..F22)
- Native iOS / native Android explicitly named as **Phase 14+** so sponsors and judges have a clear expectation
- v1 preserved verbatim at `_archive/EXECUTIVE_BRIEF_v1_20260512.md`

## Where to go next in the doc pack

| Reader | Start here | Then |
|---|---|---|
| Buyer / executive | `01_product_vision/PRODUCT_VISION.md` → `02_brd/BRD.md` §1 + §11 + §13 | `04_pricing_and_commercial/PRICING_AND_COMMERCIAL_MODEL.md` |
| Implementer | `02_brd/BRD.md` §7 + §10 | `07_system_architecture/SYSTEM_ARCHITECTURE.md` → `08_api_specification/API_SPECIFICATION.md` |
| Auditor / regulator | `02_brd/BRD.md` §14.5 | `06_regulatory_mapping/REGULATORY_MAPPING_MATRIX.md` → `12_evidence_pack_spec/EVIDENCE_PACK_SPEC.md` |
| AI lead | `02_brd/BRD.md` BR-10/BR-11 + §14.1 + §14.2 | `11_threat_model/THREAT_MODEL.md` |
| TechEx judge | `00_executive_brief/JUDGE_HANDOUT.md` | `00_executive_brief/SUBMISSION_VIDEO_SCRIPT.md` |
| Sponsor lead | this brief + `BRD.md` §13 | `03_competitive_landscape/COMPETITIVE_LANDSCAPE.md` |
