# Forensa - Documentation Index

**The 22-doc pack.** Each doc has a single owner, single source-of-truth section in the master document, and direct mapping to architecture + tests.

## How to navigate

**Starting here? Read in this order:**
1. [00 Executive Brief](00_executive_brief/EXECUTIVE_BRIEF.md) - what Forensa is, why now
2. [01 Product Vision](01_product_vision/PRODUCT_VISION.md) - 4-year roadmap, AI EvidenceOps category
3. [02 BRD](02_brd/BRD.md) - 13 Business Requirements (BR-01 to BR-13)
4. [07 System Architecture](07_system_architecture/SYSTEM_ARCHITECTURE.md) - how it is built
5. [15 Build Plan](15_build_plan/BUILD_PLAN.md) - 6-day delivery, checkpoint on Wed 14 May

**For specific roles:**
- **Compliance / Regulators** -> [06 Regulatory Mapping](06_regulatory_mapping/REGULATORY_MAPPING_MATRIX.md), [12 Evidence Pack Spec](12_evidence_pack_spec/EVIDENCE_PACK_SPEC.md)
- **Security teams** -> [10 Security Architecture](10_security_architecture/SECURITY_ARCHITECTURE.md), [11 Threat Model](11_threat_model/THREAT_MODEL.md), [19 Incident Response](19_incident_response_plan/INCIDENT_RESPONSE_PLAN.md)
- **Procurement / Legal** -> [04 Pricing](04_pricing_and_commercial/PRICING_AND_COMMERCIAL_MODEL.md), [13 Data Protection](13_data_protection_and_privacy/DATA_PROTECTION_AND_PRIVACY.md)
- **Engineering** -> [08 API Spec](08_api_specification/API_SPECIFICATION.md), [09 Data Model](09_data_model/DATA_MODEL.md), [14 Deployment](14_deployment_topology/DEPLOYMENT_TOPOLOGY.md), [16 Testing](16_testing_and_qa/TESTING_AND_QA.md), [18 SRE](18_sre_and_operations/SRE_AND_OPERATIONS.md)
- **Sales / Commercial** -> [00 Executive Brief](00_executive_brief/EXECUTIVE_BRIEF.md), [03 Competitive](03_competitive_landscape/COMPETITIVE_LANDSCAPE.md), [04 Pricing](04_pricing_and_commercial/PRICING_AND_COMMERCIAL_MODEL.md), [05 Use Cases](05_use_cases_and_user_stories/USE_CASES.md)

## Full 22-doc index

| # | Doc | Status | Purpose | Source (master doc section) |
|---:|---|---|---|---|
| 00 | [Executive Brief](00_executive_brief/EXECUTIVE_BRIEF.md) | v1 | TechEx submission summary | A.0, D.1 |
| 01 | [Product Vision](01_product_vision/PRODUCT_VISION.md) | v1 | 4-year roadmap + AI EvidenceOps framing | A.10, B.18, C.4, C.21, C.22 |
| 02 | [BRD](02_brd/BRD.md) | v1 | 13 Business Requirements | A.2 |
| 03 | [Competitive Landscape](03_competitive_landscape/COMPETITIVE_LANDSCAPE.md) | v1 | Enforcement-vs-evidence wedge | B.21, C.20 |
| 04 | [Pricing & Commercial](04_pricing_and_commercial/PRICING_AND_COMMERCIAL_MODEL.md) | v1 | 4 tiers, KPIs | A.5, B.19, B.20 |
| 05 | [Use Cases](05_use_cases_and_user_stories/USE_CASES.md) | v1 | 8 UCs, 5 personas, demo journey | A.6, A.7, B.10, B.11, C.10, C.19, D.2 |
| 06 | [Regulatory Mapping](06_regulatory_mapping/REGULATORY_MAPPING_MATRIX.md) | v1 | EU AI Act Art 12 + 8 others | A.3, C.3 |
| 07 | [System Architecture](07_system_architecture/SYSTEM_ARCHITECTURE.md) | v1 | Components, capture loop, throughput | A.4, A.10, B.13, C.7 |
| 08 | [API Specification](08_api_specification/API_SPECIFICATION.md) | v1 | Endpoints, MCP, webhooks, SDKs | A.4, B.13, C.7 |
| 09 | [Data Model](09_data_model/DATA_MODEL.md) | v1 | 7 entities, indexes, retention | A.4, C.7 |
| 10 | [Security Architecture](10_security_architecture/SECURITY_ARCHITECTURE.md) | v1 | Crypto, KMS, RBAC, defence in depth | C.14 |
| 11 | [Threat Model](11_threat_model/THREAT_MODEL.md) | v1 | 15 STRIDE threats + top-5 | C.14 |
| 12 | [Evidence Pack Spec](12_evidence_pack_spec/EVIDENCE_PACK_SPEC.md) | v1 | Pack structure, 8 templates, verifier | A.8, B.14 |
| 13 | [Data Protection](13_data_protection_and_privacy/DATA_PROTECTION_AND_PRIVACY.md) | v1 | GDPR, subprocessors, residency | C.15 |
| 14 | [Deployment Topology](14_deployment_topology/DEPLOYMENT_TOPOLOGY.md) | v1 | 4 modes, K8s, HA, DR | C.7, C.16 |
| 15 | [Build Plan](15_build_plan/BUILD_PLAN.md) | v1 | 6-day hackathon plan + pivot triggers | A.9, D.3 |
| 16 | [Testing & QA](16_testing_and_qa/TESTING_AND_QA.md) | v1 | 100% coverage, 6-layer taxonomy | (Verixa pattern) |
| 17 | [Traceability Matrix](17_traceability_matrix/TRACEABILITY_MATRIX.md) | v1 | BR -> UC -> arch -> test | A.2, A.6 |
| 18 | [SRE & Operations](18_sre_and_operations/SRE_AND_OPERATIONS.md) | v1 | 9 SLOs, runbooks, ops.ps1 | C.16 |
| 19 | [Incident Response Plan](19_incident_response_plan/INCIDENT_RESPONSE_PLAN.md) | v1 | IR-01 to IR-05, regulator timelines | (Verixa carryover) |
| 20 | [Glossary](20_glossary/GLOSSARY.md) | v1 | A-X terms | (cross-pack) |
| 21 | [openapi.json](openapi.json) | stub | Machine-readable API; CI-generated on Day 1 | (build phase) |
| 22 | [SBOM.md](SBOM.md) | v1 | Dependency inventory, SLSA L3 | (per release) |

## Key claims preserved across docs

- **EU AI Act Article 12** effective Aug 2026 - the anchor regulation
- **90% sponsor utilisation** of v1 product value (see doc 00 sponsor table)
- **10K events/sec sustained, 100K peak** throughput target (BR-09)
- **p99 capture < 5ms** latency target
- **8 design partners at 200K-500K ARR** Year 1 target
- **Wed 14 May checkpoint**: ingest -> chain -> Lobster Trap verdict working end-to-end. If slipped: AegisOne pivot.
- **Submission**: Mon 19 May 2026

## Repo layout reference

Implementation directories described in /README.md. This doc pack lives in /docs/.

## Versioning

Doc pack is versioned alongside code via git tags. v0.1.0 = hackathon submission state (Mon 19 May 2026). Each doc carries its own version line at the top.

## Master product document

The 3-author master spec (Claude + ChatGPT + Perplexity) is at:
`C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\docs\AT-Hack0018_Forensa_Master_Product_Doc_3Authors_20260512.md`

That document is the canonical source. Each doc here is a focused projection of its master sections.

## How to contribute

- Open PR with proposed changes
- Reference master doc section if adding new claims
- Update Traceability Matrix (17) if changing BR coverage
- Update this index if adding/removing docs
- CI runs spell-check + link-check on /docs/

