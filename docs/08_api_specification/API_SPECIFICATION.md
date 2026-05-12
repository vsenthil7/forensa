# Forensa - API Specification

**Doc:** 08 of 22 | **Source:** Section A.4, B.13, C.7 of master doc

OpenAPI spec at `docs/openapi.json`. This doc summarises the endpoint surface.

## Authentication

All endpoints require:
- `Authorization: Bearer <token>` (OIDC access token, scope-based)
- `X-Forensa-Tenant: <tenant-id>` header for tenant binding
- Mutual TLS for ingest endpoints (production)

## Ingest API (Python FastAPI service)

### POST /v1/events
OTel GenAI semconv batch ingest. Accepts OTLP gRPC or HTTP/protobuf.
- Body: OTLP ExportTraceServiceRequest with GenAI spans
- Response: 202 Accepted with `receipt_id` per event
- Idempotent on `event_id` (client-supplied UUIDv7)
- Latency target: p99 < 5ms

### POST /v1/events/single
Single-event ingest for low-volume agents.
- Body: Pydantic Event schema (see packages/schema)
- Response: 200 OK with `receipt_id`, `merkle_leaf`, `signature`
- Returns full Receipt for client-side retention

### POST /v1/policy/snapshot
Register active policy bundle at decision time.
- Body: `{ tenant_id, policy_bundle_hash, policy_version, captured_at }`
- Returns: `snapshot_id` for binding to subsequent events

## Investigator API

### POST /v1/query
Natural-language query via Gemini Flash.
- Body: `{ tenant_id, query_text, time_range, agent_filter? }`
- Response: SSE stream of matching receipts with reasoning

### POST /v1/query/structured
Structured event search (no LLM).
- Body: PostgreSQL/OpenSearch DSL query
- Response: paginated receipts

### GET /v1/receipts/{receipt_id}
Fetch single receipt with full chain proof.
- Response: Receipt + Merkle path + TSA anchor proof

### GET /v1/receipts/{receipt_id}/verify
Cryptographic verification.
- Response: `{ chain_valid, signatures_valid, tsa_valid, verified_at }`

### POST /v1/replay/{receipt_id}
Reconstruct decision context as of receipt time.
- Response: Receipt + policy snapshot + model version + tool catalog

## Export API

### POST /v1/export/regulator
Generate signed evidence pack.
- Body: `{ template, time_range, agent_ids, cohort_filter, format: json-ld|pdf|both }`
- Templates: eu-ai-act-art12, nist-ai-rmf, iso-42001, soc2-type2, hipaa, dora-art30, mar-reg-fd, custom (from Google AI Studio)
- Response: Async job; webhook on completion with download URL
- All exports are themselves signed and recorded as Receipts

### GET /v1/export/{export_id}
Download status and signed URL.

### POST /v1/narrative/generate
Gemini Pro narrative generation for evidence pack.
- Body: `{ cohort_of_receipts, narrative_style: regulator|legal|executive }`
- Response: Markdown narrative + hallucination guardrails report

## Admin API

### POST /v1/tenants
Provision new tenant (admin only).

### POST /v1/agents/register
Register agent identity (DID).
- Body: `{ tenant_id, agent_name, did, public_key, policy_bundles[] }`

### POST /v1/retention/policy
Set retention policy per cohort/agent.
- Body: `{ retention_years, deletion_policy: hard|soft, cohort_filter }`

### GET /v1/admin/chain/verify
Full-ledger chain verification (operational).

## MCP server endpoints (auditor portal)

Forensa exposes a Model Context Protocol server for auditor tools:
- `forensa://receipts/list` - list receipts in scope
- `forensa://receipts/get` - fetch receipt by ID
- `forensa://export/regulator` - trigger regulator pack
- `forensa://chain/verify` - cryptographic verification

Auditors connect via Claude, ChatGPT, or any MCP-compliant client.

## Webhooks

| Event | Payload |
|---|---|
| `receipt.created` | Receipt summary + ID |
| `chain.anchored` | Daily TSA anchor proof |
| `export.completed` | Download URL + signature |
| `policy.drift.detected` | Drift alert |
| `verification.failed` | Tamper alert (high priority) |

## SDKs

Python client (`forensa-python`) wraps OTel + REST.
TypeScript client (`@forensa/client`) for browser + Node.
Go client (`forensa-go`) for high-throughput services (year 2).

## Rate limits

| Endpoint | Limit |
|---|---:|
| POST /v1/events | 10K req/s per tenant |
| POST /v1/query | 100 req/s per tenant |
| POST /v1/export | 10 concurrent jobs per tenant |
| GET /v1/receipts | 1K req/s per tenant |

## Errors

Standard error envelope:
```json
{
  "error": {
    "code": "INVALID_SIGNATURE",
    "message": "Agent signature does not verify",
    "receipt_id": "01HV...",
    "trace_id": "..."
  }
}
```

Error codes: INVALID_SIGNATURE, CHAIN_BROKEN, POLICY_SNAPSHOT_MISSING, TENANT_NOT_FOUND, RETENTION_VIOLATION, RATE_LIMITED.

## OpenAPI

Full machine-readable spec: `docs/openapi.json` (will be generated from FastAPI app at build time).
