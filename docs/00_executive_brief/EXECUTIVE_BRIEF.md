# Forensa - Executive Brief

**Document:** 00 of 22 in the Forensa doc pack
**Date:** 12 May 2026
**Status:** v1, frozen for hackathon submission
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

## The product

Forensa has six surfaces:

1. **Ingest pipeline** - OpenTelemetry GenAI semconv compatible. Captures every agent event with its full context: prompt hash, model version, tool arguments, policy verdict, approval state.
2. **Hash-chained ledger** - Merkle tree with RFC 3161 timestamp authority anchoring. Every event signed by both agent identity (DID/HDP-bound) and enterprise tenant. Tamper-evident by construction.
3. **Policy snapshot binding** - The exact policy bundle active at decision time is bound to each Receipt. Six months later when policies have changed, the original decision context is reconstructible.
4. **Investigation console** - Natural-language query via Gemini Flash. "Show me every refund over five thousand processed by agent X in Q1" returns the full evidence chain in seconds.
5. **Evidence pack export** - Signed JSON-LD with PROV-O ontology, plus PDF with embedded signatures. Pre-built templates for EU AI Act Article 12, NIST AI RMF, ISO 42001, SOC 2 Type II, HIPAA, DORA, MAR/Reg FD.
6. **Tamper detection demo** - Live on stage: an event is modified after the fact, chain verification fires within seconds, the breach is provable.

## The demo moneyshot

A UK mortgage lender's compliance officer is asked by the FCA about an algorithmic decline from six months ago. They open Forensa, query by application ID, and in 90 seconds get the full evidence chain: the original prompt template (hashed and bound), the Gemini reasoning chain with confidence scores, the Lobster Trap policy verdict, the absence of human review (sub-threshold), the final outcome. Gemini Pro then generates the regulator-readable narrative. Live tamper attempt fails verification on stage. Evidence pack exported in three days versus six weeks of forensic reconstruction.

## Sponsor technology utilisation

90 percent of the v1 product value sits on sponsor primitives:

| Sponsor | Role | % of v1 value |
|---|---|---:|
| Veea Lobster Trap | Verdict source feeding the ledger | 18% |
| Gemini 3 Pro (long context) | Narrative generation, counterfactual analysis | 10% |
| Gemini 3 Pro (multimodal) | Bind PDFs and signed scans to Receipts | 6% |
| Gemini 3 Flash | Investigator natural-language UX | 6% |
| Google AI Studio | Regulator-pack templates | 2% |
| AWS data pipeline | S3 + EventBridge + Glue + Step Functions + OpenSearch backbone | 14% |
| LangGraph | Multi-agent provenance graph | 8% |
| MCP | Tool-call evidence capture, auditor portal as MCP service | 8% |
| OpenTelemetry GenAI | Wire-format compatibility | 3% |
| NVIDIA Omniverse + Isaac Sim | Physical-action replay (stretch) | 7% |
| NVIDIA GR00T VLA | VLA model evaluation evidence | 3% |
| DT Consortium / XMPro | Vendor-neutral twin semantics | 5% |

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

## Hackathon submission shape

- **Public GitHub repo** at github.com/vsenthil7/forensa (MIT-licensed core)
- **Live demo** showing 6-month-after evidence reconstruction with cryptographic verification
- **7-minute video** following the European bank mortgage decline journey
- **Slide deck** anchored on EU AI Act Article 12 deadline
- **TechEx submission** Mon 19 May 2026

## Track and award alignment

- **Track 1** - Agent Security and AI Governance (primary)
- **Veea Award** (Track 1) - strongest fit; Forensa is Lobster Trap extended into evidence infrastructure
- **Gemini Award** (Best use of Gemini) - secondary; Gemini Pro narrative + Flash investigator UX

## What comes next

Architecture document (07 in the doc pack) takes this Executive Brief and turns it into a buildable design. BRD (02) enumerates the 13 Business Requirements. Build Plan (15) sequences the 6-day delivery.

The strategy phase is closed. Forensa is the product. The next 6 days are execution.
