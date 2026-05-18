# Forensa - Use Cases and User Stories

**Doc:** 05 of 22 | **Source:** Section A.6, A.7, B.10, B.11, C.10, C.19, D.2 of master doc

## 8 core use cases

### UC-01 - Regulator evidence pack (canonical demo)
European bank receives FCA inquiry about an AI mortgage decline 6 months prior. Compliance officer scopes inquiry, Forensa returns full evidence chain in 90 seconds. 3-day response vs 6 weeks of forensic reconstruction.
BR coverage: BR-01, BR-04, BR-05, BR-10, BR-11. **Demo moneyshot anchor.**

### UC-02 - Customer dispute reconstruction
Customer claims AI assistant exposed competitor pricing. Forensa retrieves exact agent interaction + policy verdicts. Legal exports cryptographically-verified evidence pack.
BR: BR-01, BR-02, BR-05, BR-10

### UC-03 - Multi-agent chain audit
5-agent procurement workflow misbehaves. LangGraph provenance graph shows which agent caused cascade, what each downstream agent saw, which policies fired at each step.
BR: BR-07, BR-10, BR-11

### UC-04 - Policy drift detection
Quarterly governance review surfaces: policy v2.3.1 active during 47% of high-stakes Q1 decisions, but policy v2.4 was documented standard. Drift invisible until Forensa surfaced it.
BR: BR-04, BR-10

### UC-05 - Model deprecation evidence preservation
Vendor announces Gemini 2.5 deprecation. Customer preserves evidence of past decisions under deprecated model. Forensa exports with model-version metadata frozen.
BR: BR-01, BR-05, BR-09

### UC-06 - Tabletop incident response (DORA Article 30)
DORA Article 30 annual tabletop exercises for critical third-party AI dependencies. Forensa tabletop mode runs synthetic incidents through production evidence pipeline.
BR: BR-12

### UC-07 - M&A due diligence
Acquiring company asks "list every AI system, who governs it, what evidence exists." Forensa exports inventory + 90-day evidence sample in days, not months.
BR: BR-13

### UC-08 - Prompt injection investigation
Support agent receives malicious prompt. Lobster Trap flags injection pattern; Forensa records block verdict, policy version, model context, analyst follow-up. Security exports timeline.
BR: BR-01, BR-04, BR-07

## End-to-end - UK Mortgage Lender (canonical demo)

**Setup.** UK mortgage lender uses AI agent to triage applications. Six months ago applicant X was declined. Today X filed FCA complaint claiming algorithmic discrimination.

**Without Forensa:** Compliance spends 6 weeks reconstructing. Source systems rotated, dbt models refactored, reconstruction partial, FCA escalates.

**With Forensa:**
- Day 1 morning: Compliance officer queries by application ID
- 90 seconds: full evidence chain returned - prompt template v2.3.1 (hashed, bound), Gemini Pro reasoning with confidence scores, Lobster Trap rule credit-eligibility-v4 returned ALLOW risk 0.34, no human review (sub-threshold), final outcome
- Day 1 afternoon: Asks for 100 similar declines. Gemini Pro counterfactual analysis shows model behaviour consistent across protected demographic categories
- Day 2: AWS bulk historical scan finds 31 similar applications
- Day 3: Compliance exports signed regulator pack - chain verified, narrative generated, cohort included
- FCA closes inquiry without escalation

Reconstruction time: 6 weeks -> 3 days. Confidence: forensic-grade.

## User personas

| Persona | Role | Use of Forensa |
|---|---|---|
| Compliance Officer | Owns regulatory exposure | Pulls evidence packs for regulator inquiries |
| Internal Auditor | Audits AI deployments | Samples receipts, verifies cryptographic integrity |
| Security Engineer | Investigates AI misuse | Queries timeline, reconstructs attack chains |
| General Counsel | Defends in disputes | Exports legally admissible evidence |
| AI Platform Owner | Operates AI infrastructure | Production incidents, infra telemetry correlation |

## Persona success metrics

- Compliance: audit preparation time reduced 60-80%
- CISO: mean-time-to-investigate AI incident reduced from days to minutes
- AI Governance Lead: 95%+ AI actions have policy-linked evidence
- Legal Counsel: evidence packet accepted as legal review artefact
- Platform Engineer: agent integration completed with SDK/proxy within one sprint
