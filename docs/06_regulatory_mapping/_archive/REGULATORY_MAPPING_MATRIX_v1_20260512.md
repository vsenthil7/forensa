# Forensa - Regulatory Mapping Matrix

**Doc:** 06 of 22 | **Source:** Section A.3, C.3 of master doc

## Regulatory anchors

| Framework | Forensa BRs | Compliance contribution |
|---|---|---|
| EU AI Act Article 12 (Aug 2026) | BR-01, BR-03, BR-04, BR-05, BR-06 | Automatic logging for high-risk AI, 10-year retention |
| DORA Article 30 (Jan 2025+) | BR-05, BR-12 | Third-party ICT risk, tabletop exercises |
| NIST AI RMF (1.0) | BR-01, BR-04, BR-05 | Govern/Map/Measure/Manage |
| ISO 42001 | BR-01, BR-04, BR-05 | AI management system |
| SOC 2 Type II | BR-01, BR-02, BR-06 | Security/Availability/Integrity |
| HIPAA | BR-01, BR-05, BR-09 | 6-year audit log retention |
| MAR / Reg FD | BR-01, BR-04, BR-05 | Pre-publication blackout |
| GDPR | BR-05, retention controls | Right to erasure, PII hashing |
| UK FCA Algorithmic Trading | BR-01, BR-04, BR-05 | Algorithmic decision audit |

## EU AI Act Article 12 - the anchor

Article 12 requires high-risk AI systems "automatically record events (logs) over the lifetime of the system" appropriate to the intended purpose. Logs must include:
1. Period of each use (start/end timestamp)
2. Reference database against which input data has been checked
3. Input data that resulted in a match
4. Identification of natural persons involved in verification

**Effective:** August 2026 (24-month grandfathering for pre-existing systems)
**Retention:** 10 years
**Penalties:** up to 7% global turnover for non-compliance

**Forensa conformance map:**
- BR-01 (tamper-evident recording) satisfies (1) period of use
- BR-04 (policy snapshot) satisfies (2) reference database state
- BR-03 (reasoning capture) satisfies (3) input data leading to match
- BR-02 (multi-party identity binding) satisfies (4) natural persons involved
- BR-05 (regulator export) delivers the conformance artefact

## DORA Article 30 - financial services

DORA requires:
- Register of contractual arrangements for ICT services
- Annual TLPT (Threat-Led Penetration Testing)
- Tabletop exercises for critical AI dependencies

Forensa: BR-12 (tabletop mode) and BR-05 (DORA register exports).

## EU AI Act Annex III high-risk categories - all covered

Biometric identification, critical infrastructure, education, employment, essential services, law enforcement, migration, justice administration - all 8 require Article 12 logging conformance.

## Sovereign deployment

EU customers may require:
- VPC or on-prem (no SaaS egress)
- EU data residency (EU-based RFC 3161 TSA)
- KMS with HSM backing (EU-resident HSMs)
- GDPR Article 28 processor agreement

Architecture (doc 07) and Deployment Topology (doc 14) detail these patterns.
