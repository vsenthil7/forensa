# Forensa - Competitive Landscape

**Doc:** 03 of 22 | **Date:** 12 May 2026 | **Status:** v1 | **Source:** Section B.21, C.20 of master doc

## The competitive picture

Forensa sits in the AI runtime governance space alongside enforcement-focused incumbents, but occupies a distinct wedge - **evidence**, not enforcement.

## 5-category competitive matrix (ChatGPT framing, Section B.21)

| vs Category | Example incumbents | Forensa's distinction |
|---|---|---|
| Observability tools | Datadog, New Relic, Dynatrace, Coralogix, Langfuse, Logfire | Observability shows behaviour. Forensa proves evidence. |
| SIEM | Splunk, IBM QRadar, Microsoft Sentinel | SIEM handles security events. Forensa handles AI-specific evidence chains. |
| AI Governance Platforms | Credo AI, IBM watsonx.governance, Holistic AI | Governance defines controls. Forensa proves what happened. |
| Runtime Firewalls | Microsoft AGT, Preloop, AWS Bedrock AgentCore, Veea Lobster Trap | Firewalls block actions. Forensa preserves proof and replay. |
| Audit Logs | Native audit logs in every SaaS product | Audit logs are often mutable and fragmented. Forensa creates cryptographically linked evidence. |

## The enforcement-vs-evidence gap (the wedge)

Every incumbent in the AI runtime space is building enforcement primitives. None is building evidence primitives. The two are different products:

| Dimension | Enforcement (incumbents) | Evidence (Forensa) |
|---|---|---|
| Question answered | Should the agent be allowed to do X? | Six months later, can we prove what happened? |
| Latency requirement | Inline, microseconds | Async, eventual consistency OK |
| Buyer | CISO, AI Platform Engineering | Compliance, Internal Audit, GC, Risk |
| Success metric | Block rate, false positive rate | Reconstruction time, hash chain integrity |
| Regulator anchor | None | EU AI Act Art 12, DORA Art 30 |
| Pricing model | Per-agent-run | Per-tenant, per-retention-year |

## Detailed comparisons

### vs Microsoft AGT (AI Governance Toolkit)
- AGT is enforcement-focused: policy-as-code, runtime gates, blocking behaviour
- Forensa sits BEHIND AGT and captures every AGT verdict into the ledger
- Complementary, not competitive
- Forensa cites AGT in its sales motion: "We make AGT's verdicts admissible evidence"

### vs Veea Lobster Trap
- Lobster Trap is inline policy inspection
- Forensa is the verdict-feed consumer and tamper-evident archive
- Direct sponsor relationship; Lobster Trap is named in Section A.2 (BR-01, BR-04, BR-07) as the verdict source
- Strategically: Lobster Trap's success drives Forensa's TAM

### vs AWS Bedrock AgentCore
- AgentCore is enforcement + observability for Bedrock-hosted agents
- Forensa is multi-cloud and multi-runtime by design (works with OpenAI, Anthropic, Gemini, Bedrock, self-hosted)
- Customer journey: AgentCore for Bedrock-only deployments, Forensa for multi-cloud regulated enterprises

### vs LangSmith / Langfuse / Logfire
- These are AI observability platforms - debugging, latency tracking, cost tracking
- They are not tamper-evident, not policy-aware, not regulator-grade
- Forensa exports to all three formats via the OpenTelemetry GenAI semconv (no rip-and-replace)
- Different buyer (CISO/Compliance) than observability (Platform Engineering)

### vs IBM watsonx.governance / Credo AI
- These are AI governance platforms - model inventory, risk classification, policy authoring
- They are not runtime; they live in the AI lifecycle management layer
- Forensa receives policy verdicts FROM these platforms and writes them into receipts
- Complementary; Forensa is the runtime evidence layer below the governance layer

### vs SIEM (Splunk, Sentinel, QRadar)
- SIEMs accept Forensa exports via Common Event Format
- SIEMs handle security-event correlation; Forensa handles AI-action correlation
- Different schemas, different retention requirements, different buyer

## Category positioning (Perplexity framing, Section C.20)

Forensa should be positioned as **evidence infrastructure**, not just governance, observability, or logging.

That distinction matters:
- Governance tools try to control behaviour
- Observability tools try to monitor systems
- Log tools collect events
- **Forensa converts agent operations into a tamper-evident, explainable, enterprise-usable evidence layer**

## Risk: being miscategorised as "another control plane"

Mitigation:
- Open the sales pitch with "we are not the firewall, we are the black box"
- Show hash-chain verification on stage at every demo
- Use evidence-pack export (PDF + JSON-LD) as the proof artefact in every sales conversation
- Avoid "AI governance" language; use "AI evidence" and "AI accountability"

## Why Forensa wins

1. **Open wedge** - no direct competitor (every incumbent builds enforcement)
2. **Regulator urgency** - EU AI Act Article 12 mandates this from August 2026
3. **Sponsor convergence** - Lobster Trap + Gemini + AWS + MCP + LangGraph all directly applicable
4. **Switching cost** - bilateral ledger history grows with deployment age
5. **Audit-firm channel** - Big 4 white-label is a defensible distribution moat by Year 2
6. **Standards positioning** - Forensa Standard candidacy in Year 3 locks in category leadership
