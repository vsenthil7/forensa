# Forensa - Traceability Matrix

**Doc:** 17 of 22 | **Source:** Section A.2, A.6 of master doc

## BR -> UC -> Architecture -> Test mapping

| BR | UC | Architecture component | Test suite | Source files (planned) |
|---|---|---|---|---|
| BR-01 Tamper-evident recording | UC-01, UC-02, UC-05, UC-08 | packages/ingest, packages/ledger | pytest unit + property hypothesis | packages/ingest/*.py, packages/ledger/writer.py |
| BR-02 Multi-party identity binding | UC-02 | packages/crypto, apps/api/auth | pytest unit + integration | packages/crypto/sign.py, apps/api/auth/agents.py |
| BR-03 Reasoning capture | UC-01 | packages/schema, packages/ingest | pytest + Playwright e2e | packages/schema/receipt.py, packages/ingest/normaliser.py |
| BR-04 Policy snapshot binding | UC-01, UC-04, UC-08 | packages/policy, packages/ledger | pytest integration | packages/policy/snapshot.py, packages/ledger/writer.py |
| BR-05 Regulator-grade export | UC-01, UC-02, UC-07 | packages/export | pytest integration | packages/export/builder.py, packages/export/pdf.py |
| BR-06 Merkle chain + RFC 3161 TSA | UC-01 (and demo) | packages/crypto, packages/ledger | pytest property hypothesis | packages/crypto/merkle.py, packages/crypto/tsa.py |
| BR-07 Multi-agent provenance graph | UC-03, UC-08 | packages/ingest, apps/api | pytest integration | packages/ingest/langgraph_adapter.py |
| BR-08 Omniverse physical replay (stretch) | (future) | apps/console (replay viewer) | Playwright e2e | apps/console/src/replay/ |
| BR-09 AWS bulk historical backfill | UC-05 | deploy/, packages/ledger | Locust load tests | deploy/aws/, packages/ledger/backfill.py |
| BR-10 Investigator UI + Gemini Flash | UC-01, UC-02, UC-03, UC-04 | apps/console | Playwright e2e | apps/console/src/investigation/ |
| BR-11 Counterfactual narrative (Gemini Pro) | UC-01, UC-04 | packages/export | pytest integration | packages/export/narrative.py |
| BR-12 Tabletop incident response | UC-06 | packages/policy/tabletop | pytest integration | packages/policy/tabletop.py |
| BR-13 M&A due diligence export | UC-07 | packages/export | pytest integration | packages/export/inventory.py |

## Sponsor utilisation -> BR mapping

| Sponsor | BRs primarily served |
|---|---|
| Veea Lobster Trap | BR-01, BR-04, BR-07 |
| Gemini 3 Pro (long context) | BR-11 |
| Gemini 3 Pro (multimodal) | BR-03 (PDF binding) |
| Gemini 3 Flash | BR-10 |
| Google AI Studio | BR-05 (custom templates) |
| AWS data pipeline | BR-09 |
| LangGraph | BR-07 |
| MCP | BR-05 (auditor portal) |
| OpenTelemetry GenAI | BR-01 (wire format) |
| NVIDIA Omniverse + Isaac Sim | BR-08 (stretch) |
| NVIDIA GR00T VLA | BR-03 (VLA reasoning eval) |
| DT Consortium / XMPro | BR-08 (semantics) |

## Regulator -> BR mapping (cross-reference doc 06)

| Framework | BRs |
|---|---|
| EU AI Act Article 12 | BR-01, BR-03, BR-04, BR-05, BR-06 |
| DORA Article 30 | BR-05, BR-12 |
| NIST AI RMF | BR-01, BR-04, BR-05 |
| ISO 42001 | BR-01, BR-04, BR-05 |
| SOC 2 Type II | BR-01, BR-02, BR-06 |
| HIPAA | BR-01, BR-05, BR-09 |
| MAR / Reg FD | BR-01, BR-04, BR-05 |
| GDPR Article 32 | BR-02, security architecture |
| GDPR Article 17 | retention controls (cryptographic shredding) |

## NFR coverage

| NFR | BR linkage | Test layer |
|---|---|---|
| Integrity / immutability | BR-01, BR-06 | property-based |
| Low latency capture (p99 < 5ms at 10K/s) | BR-01, BR-09 | Locust |
| Encryption at rest + in transit | (security architecture) | integration |
| On-prem / VPC deployable | (deployment topology) | Helm chart smoke test |
| Explainability | BR-11 | integration |
| Scalable search | BR-10 | Locust + Playwright |
| Retention controls | (data protection) | integration |

## Persona -> UC mapping

| Persona | UCs |
|---|---|
| Compliance Officer | UC-01, UC-02, UC-04, UC-05 |
| Internal Auditor | UC-04, UC-07 |
| Security Engineer | UC-02, UC-03, UC-08 |
| General Counsel | UC-02 |
| AI Platform Owner | UC-03, UC-04, UC-08 |

## Status legend

- **Day 1**: scaffold + ingest path (BR-01, BR-09 partial)
- **Day 2**: chain + Lobster Trap (BR-02, BR-04, BR-06) **CHECKPOINT**
- **Day 3**: console + LangGraph (BR-07, BR-10)
- **Day 4**: export + narrative (BR-05, BR-11)
- **Day 5**: tamper demo + tabletop (BR-12, BR-13)
- **Day 6**: docs + video
- **Stretch**: BR-08 Omniverse if time

## Coverage requirement

Every BR must have:
- At least one source file (code)
- At least one test (covering happy + failure paths)
- At least one CI run that passes
- At least one mention in evidence pack / demo

