# Forensa - Traceability Matrix

**Doc:** 17 of 22 | **Source:** Section A.2, A.6 of master doc
**Last status sweep:** 14 May 2026 22:02 after CP9.16-PG-up + CP9.17 Idempotency-Key (see `docs/02_brd/BRD.md` change log)

## BR -> UC -> Architecture -> Test mapping

| BR | UC | Architecture component | Test suite | Source files |
|---|---|---|---|---|
| BR-01 Tamper-evident recording | UC-01, UC-02, UC-05, UC-08 | packages/ingest, packages/ledger, alembic/0004 + 0005 triggers/constraints | pytest unit + property hypothesis + 14 PG-integration | packages/ingest/*.py, packages/ledger/*.py, alembic/versions/20260514_1744_bundle_approval_workflow.py, alembic/versions/20260514_2120_idempotency_records.py, tests/integration/test_pg_append_only_triggers.py, tests/integration/test_pg_partial_unique_active.py, tests/integration/test_pg_migrations.py |
| BR-02 Multi-party identity binding | UC-02 | packages/crypto, apps/api/auth (stub) | pytest unit + integration | packages/crypto/sign.py, apps/api/auth/ (Phase 10 CP10.1) |
| BR-03 Reasoning capture | UC-01 | packages/schema, packages/ingest | pytest + Playwright e2e | packages/schema/receipt.py, packages/ingest/normaliser.py |
| BR-04 Policy snapshot binding | UC-01, UC-04, UC-08 | packages/policy, packages/ledger | pytest integration | packages/policy/snapshot.py, packages/ledger/repositories.py |
| BR-05 Regulator-grade export | UC-01, UC-02, UC-07 | packages/export | pytest integration | packages/export/builder.py, packages/export/pdf.py (Phase 9 CP9.2) |
| BR-06 Merkle chain + RFC 3161 TSA | UC-01 (and demo) | packages/crypto, packages/ledger | pytest property hypothesis | packages/crypto/merkle.py, packages/crypto/tsa.py (Phase 11 CP11.5) |
| BR-07 Multi-agent provenance graph | UC-03, UC-08 | packages/ingest, apps/api | pytest integration | packages/ingest/langgraph_adapter.py (Phase 12) |
| BR-08 Omniverse physical replay (stretch) | (future) | apps/console (replay viewer) | Playwright e2e | apps/console/src/replay/ (deferred) |
| BR-09 AWS bulk historical backfill | UC-05 | deploy/, packages/ledger | Locust load tests | deploy/aws/ (Phase 12 CP12.3/4), scripts/load_test.py |
| BR-10 Investigator UI + Gemini Flash | UC-01, UC-02, UC-03, UC-04 | apps/console, packages/narrative | Playwright e2e + pytest | apps/console/src/investigation/, packages/narrative/client.py |
| BR-11 Counterfactual narrative (Gemini Pro) | UC-01, UC-04 | packages/narrative | pytest integration | packages/narrative/client.py, packages/narrative/prompt.py |
| BR-12 Tabletop incident response | UC-06 | packages/policy/tabletop | pytest integration | packages/policy/tabletop.py (Phase 10 stretch) |
| BR-13 M&A due diligence export | UC-07 | packages/export | pytest integration | packages/export/inventory.py (Phase 13 stretch) |
| **Retry-safe ingest (NFR; CP9.17)** | UC-01, UC-05 | apps/api (route layer), packages/crypto/hash (binding primitive), alembic/0005 | pytest unit + route-level | apps/api/idempotency_store.py, apps/api/routes/events.py, tests/api/test_idempotency_store.py, tests/api/test_events_idempotency.py, alembic/versions/20260514_2120_idempotency_records.py |

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
| Integrity / immutability | BR-01, BR-06 | property-based + PG-integration (CP9.16: 14 tests verifying append-only triggers, partial UNIQUE race-safety, migration round-trip on real Postgres 16.13) |
| Low latency capture (p99 < 5ms at 10K/s) | BR-01, BR-09 | Locust |
| Encryption at rest + in transit | (security architecture) | integration |
| On-prem / VPC deployable | (deployment topology) | Helm chart smoke test |
| Explainability | BR-11 | integration |
| Scalable search | BR-10 | Locust + Playwright |
| Retention controls | (data protection) | integration |
| **Retry-safe ingest (idempotency dedup; CP9.17)** | BR-01 (no double-counting in the evidence ledger under retry storms) | pytest unit + route-level (35 store tests + 19 route tests; total 54 at 100% coverage) |

## Persona -> UC mapping

| Persona | UCs |
|---|---|
| Compliance Officer | UC-01, UC-02, UC-04, UC-05 |
| Internal Auditor | UC-04, UC-07 |
| Security Engineer | UC-02, UC-03, UC-08 |
| General Counsel | UC-02 |
| AI Platform Owner | UC-03, UC-04, UC-08 |

## Status legend (hackathon timeline reflective)

- **Day 1**: scaffold + ingest path (BR-01, BR-09 partial)
- **Day 2**: chain + Lobster Trap (BR-02 tenant-side, BR-04, BR-06 chain part)
- **Day 3**: console scaffold + export + narrative mock (BR-05 JSON-LD, BR-10 stub, BR-11 stub)
- **Day 4** (today, 14 May 2026): bundle approval workflow CP9.15 + PG-integration verification CP9.16 + idempotency CP9.17. 669 tests passing in PG mode (654 default + 15 PG-integration) at 100% coverage. The Status legend was originally planned per the master doc; reality has reshuffled the day-by-day mapping but the BR coverage rate is on track.
- **Day 5** (15 May 2026): Live narrative client CP9.1 (BR-10/11 -> IMPLEMENTED), PDF export CP9.2 (BR-05), demo polish.
- **Day 6** (16 May 2026): docs + video; submission.
- **Stretch**: BR-08 Omniverse if time.

## Coverage requirement

Every BR must have:
- At least one source file (code)
- At least one test (covering happy + failure paths)
- At least one CI run that passes
- At least one mention in evidence pack / demo

