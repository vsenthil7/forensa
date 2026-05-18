# Forensa - System Architecture

**Doc:** 07 of 22 | **Source:** Section A.4, A.10, B.13, C.7 of master doc

## Architecture in one diagram (text form)

```
[ AI Agents ]   [ Human Approvers ]   [ Tool Calls (MCP) ]
       \              |                /
        \             |               /
         v            v              v
    +-------------------------------------+
    |  OTel GenAI Ingest Pipeline (BR-01) |  <- Python FastAPI
    +-------------------------------------+
                      |
                      v
    +-------------------------------------+
    |  Pydantic v2 schema validation      |
    |  + Lobster Trap verdict adapter     |
    |  + Policy snapshot binding (BR-04)  |
    +-------------------------------------+
                      |
                      v
    +-------------------------------------+
    |  packages/crypto: Ed25519 sign +    |
    |  SHA-256 hash + Merkle aggregation  |
    +-------------------------------------+
                      |
                      v
    +-------------------------------------+
    |  PostgreSQL append-only ledger      |
    |  + S3 cold storage (BR-09)          |
    |  + OpenSearch index                 |
    +-------------------------------------+
                      |
       (daily RFC 3161 TSA anchor)
                      |
                      v
    +-------------------------------------+
    | RFC 3161 Timestamp Authority anchor |
    +-------------------------------------+

    Investigator side:
                      ^
    +-------------------------------------+
    |  Next.js 15 Investigator Console    |
    |  + Gemini Flash query (BR-10)       |
    |  + Gemini Pro narrative (BR-11)     |
    +-------------------------------------+
                      |
                      v
    +-------------------------------------+
    |  Evidence Pack Builder (BR-05)      |
    |  -> JSON-LD + PDF + signatures      |
    +-------------------------------------+
```

## Component breakdown

### Backend (Python 3.12)
- **apps/api** - FastAPI service with async OTel handlers, investigator query API, export API
- **packages/ingest** - OTel GenAI semconv ingest, event normaliser, batch buffer
- **packages/ledger** - append-only writer, Merkle tree aggregator, chain verifier
- **packages/crypto** - Ed25519 sign/verify, SHA-256, RFC 3161 TSA client
- **packages/policy** - Lobster Trap adapter, OPA bundle loader, policy snapshot capture
- **packages/schema** - Pydantic v2 schemas (Receipt, Event, Cohort, Tenant, Agent)
- **packages/export** - JSON-LD + PROV-O + PDF generator, regulator pack templates

### Frontend (Next.js 15 + React 19 + TS + Tailwind)
- **apps/console** - 6 screens: Investigation Console, Incident Replay, Evidence Receipt Viewer, Policy Correlation Panel, Export Center, Admin & Retention Console

### Data plane
- **PostgreSQL 16** - hot ledger (last 90 days), event index, agent registry, policy bundles
- **S3** - cold ledger (90 days to 10 years), encrypted with KMS per tenant
- **OpenSearch** - investigator query backend, full-text on prompt/reasoning fields
- **Kafka or AWS EventBridge** - pluggable event bus (BR-09)
- **Glue + Step Functions** - bulk historical backfill orchestration

### Identity and trust
- **OIDC + SSO** - enterprise auth
- **RBAC** - role-based access (Compliance, Auditor, Security, GC, Platform)
- **DID/HDP** - decentralised agent identity (BR-02)
- **KMS** - per-tenant signing key, optional HSM backing
- **RFC 3161 TSA** - external timestamping authority (Section C.7)

## Critical path - event capture loop

1. Agent makes call -> OTel SDK emits GenAI span
2. Forensa FastAPI receives span via OTLP gRPC
3. Pydantic v2 validates schema
4. Policy snapshot captured (current OPA bundle hash)
5. Event hashed (SHA-256)
6. Receipt signed (Ed25519 with agent key + tenant key)
7. Appended to PostgreSQL ledger
8. Merkle leaf added to current tree
9. Daily: Merkle root submitted to RFC 3161 TSA
10. TSA response anchored back into ledger as proof entry

Target latency: p99 capture < 5ms at 10K req/s sustained.

## Throughput model

| Deployment | Throughput |
|---|---:|
| Single Python pod (FastAPI + asyncpg) | ~5K req/s |
| 8 pods on m6i.xlarge | ~40K req/s |
| 8 pods + Postgres COPY batching + Kafka write-ahead | ~200K req/s |
| 32 pods | ~800K req/s |

References: Instagram, Pinterest, Reddit, OpenAI API gateway, Anthropic API.

## Reference architectures referenced

- **Trillian / Certificate Transparency** - tamper-evident append-only log; proven at billions of events
- **Oracle AER** - Agent Event Records; reasoning capture pattern
- **AAGATE (arXiv 2510.25863, CSA Nov 2025)** - architecture pattern for agent governance
- **W3C PROV-O** - provenance ontology for evidence pack export
- **OpenTelemetry GenAI semantic conventions** - wire format

## Deployment topology

| Mode | Use |
|---|---|
| SaaS (multi-tenant, EU region) | Default for Year 1 design partners |
| Single-tenant VPC | Regulated Enterprise tier |
| On-prem (Kubernetes) | Sovereign deployments |
| Air-gapped | Government / defence |

Detail: Deployment Topology doc (14).

## Out of scope for v1 architecture

- Distributed-ledger (DLT/blockchain) backend - explicit rejection in Section C.7. Centralised Merkle tree is sufficient and performant
- Real-time streaming export to SIEMs - batch export at minute granularity
- Custom regulator dashboards (regulator imports the JSON-LD pack themselves)
