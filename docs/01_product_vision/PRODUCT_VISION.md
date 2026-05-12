# Forensa - Product Vision

**Doc:** 01 of 22 | **Date:** 12 May 2026 | **Status:** v1

Forensa is the **system of record for agentic enterprise actions** - the cryptographic evidence layer for every AI agent decision, prompt, tool call, human approval, and business outcome inside enterprise workflows.

## Vision

By 2030, every Fortune 2000 enterprise running AI agents in regulated workflows will have a forensa-equivalent layer. Just as audit logs became table stakes after SOX, cryptographic AI evidence becomes table stakes after EU AI Act Article 12.

## 4-year roadmap

| Year | Focus | Outcome |
|---|---|---|
| 1 (2026-27) | EU AI Act Article 12 design partners; native Lobster Trap + Gemini + AWS stack | 8 customers at 200K-500K ARR |
| 2 (2027-28) | DORA Article 30 financial-services play; audit-firm channel (Big 4 white-label); multi-cloud | 30+ customers, 8M ARR |
| 3 (2028-29) | Open standard for AI evidence (Forensa Standard); audit-firm-recommended format; insurance integration | Category leader |
| 4 (2029-30) | Standards positioning, M&A target, IPO path | Default evidence layer |

## Long-term moat

1. Bilateral ledger history switching cost (customer + vendor both retain receipts)
2. Audit-firm familiarity (Big 4 white-label deployments)
3. Regulator-recommended format
4. Insurance carrier integration (premiums priced on Forensa conformance)
5. Standards positioning (Forensa Standard becomes IETF/ISO track)

## Category framing

Forensa belongs to **AI EvidenceOps** - a category that will become as normal as:
- Audit logs (post-SOX)
- Transaction logs (post-PCI DSS)
- SIEM events (post-breach disclosure rules)
- Financial ledgers (always)
- Provenance records (post-supply-chain compliance)

The category expands from agent evidence into enterprise AI accountability infrastructure.

## What Forensa is NOT

- A SIEM replacement
- A chatbot
- A RAG app
- A model registry
- An observability platform
- A runtime firewall (Lobster Trap is the firewall; Forensa is the evidence sink)
- A generic logging tool

## Reference architecture lineage

- Trillian (Google CT log) - tamper-evident append-only log proven at billions of events
- Oracle AER (Agent Event Records) - reasoning capture pattern
- Microsoft AGT - inspiration for the enforcement layer Forensa sits behind
- AAGATE paper (arXiv 2510.25863, CSA Nov 2025) - architecture for agent governance

## Source

Derived from Section A.10, B.18, C.4, C.21, C.22, D.1 of the three-author master document (docs/02_brd/BRD.md references the master).
