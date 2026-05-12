# Forensa - Data Model

**Doc:** 09 of 22 | **Source:** Section A.4, C.7 of master doc

## Core entities (Pydantic v2 schemas in packages/schema)

### Tenant
- `tenant_id` (UUIDv7, pk)
- `name`, `region`, `tier` (team_pilot|enterprise|regulated|strategic)
- `signing_key_arn`, `kms_arn` (per-tenant key in KMS)
- `retention_policy_default_years`, `tsa_endpoint`
- `created_at`, `subscription_expires_at`

### Agent
- `agent_id` (UUIDv7, pk), `tenant_id` (fk)
- `did` (decentralised identifier, indexed)
- `public_key` (Ed25519, PEM)
- `name`, `description`, `agent_type` (llm|tool|workflow|composite)
- `policy_bundle_ids` (array of fk)
- `created_at`, `last_active_at`

### PolicyBundle
- `policy_bundle_id` (UUIDv7, pk), `tenant_id` (fk)
- `name`, `version` (semver), `bundle_hash` (SHA-256)
- `opa_rego_text` (the actual policy)
- `valid_from`, `valid_until`
- `bundle_signature` (signed by tenant key)

### Receipt (the core entity)
- `receipt_id` (UUIDv7, pk)
- `tenant_id` (fk), `agent_id` (fk)
- `event_type` (prompt|response|tool_call|policy_verdict|human_approval|business_outcome)
- `parent_receipt_id` (fk, nullable - for chain continuity)
- `policy_bundle_id` (fk - which policy snapshot applied)
- `prompt_hash`, `response_hash`, `tool_args_hash` (SHA-256 of content)
- `prompt_content_ref` (S3 URI - actual content encrypted at rest)
- `model_version`, `model_id` (e.g. gemini-3-pro-2025-12)
- `lobster_trap_verdict` (allow|deny|warn|error|null)
- `reasoning_chain` (Oracle AER pattern - jsonb)
- `human_approver_id` (fk, nullable)
- `business_outcome` (jsonb)
- `created_at` (microsecond precision)
- `agent_signature` (Ed25519, hex)
- `tenant_signature` (Ed25519, hex)
- `merkle_leaf_index` (bigint - position in tree)
- `previous_receipt_hash` (SHA-256 - chain pointer)

### MerkleAnchor (daily TSA anchoring)
- `anchor_id` (UUIDv7, pk), `tenant_id` (fk)
- `merkle_root_hash` (SHA-256)
- `leaf_count`, `first_receipt_id`, `last_receipt_id`
- `tsa_endpoint`, `tsa_response_blob` (RFC 3161 binary)
- `anchored_at`

### EvidencePack (BR-05 exports)
- `pack_id` (UUIDv7, pk), `tenant_id` (fk)
- `template` (eu-ai-act-art12|nist|iso42001|...|custom)
- `cohort_filter` (jsonb - query that produced cohort)
- `receipt_ids` (array, indexed)
- `narrative_text` (Gemini Pro output)
- `narrative_hash`, `narrative_signature`
- `pdf_s3_uri`, `jsonld_s3_uri`
- `requestor_id` (user fk), `requested_at`, `completed_at`
- `pack_signature` (signed pack manifest)

### Investigation
- `investigation_id` (UUIDv7, pk), `tenant_id` (fk)
- `title`, `status` (open|closed|escalated)
- `query_history` (jsonb)
- `receipts_examined` (array)
- `legal_hold` (boolean)
- `created_by` (user fk), `created_at`, `closed_at`

### TabletopScenario (BR-12)
- `scenario_id` (UUIDv7, pk), `tenant_id` (fk)
- `name`, `description`, `regulator` (dora|nist|iso)
- `synthetic_events_count`, `expected_outcomes`
- `playbook_jsonld`

## Indexes (PostgreSQL)

Critical indexes for hot-path queries:
- `receipts(tenant_id, created_at DESC)` - investigator timeline
- `receipts(agent_id, created_at DESC)` - per-agent history
- `receipts(prompt_hash)` - dedup + similar-prompt search
- `receipts(parent_receipt_id)` - chain walks
- `receipts(merkle_leaf_index)` - chain verification
- `agents(did)` UNIQUE - identity lookup
- `policy_bundles(bundle_hash)` UNIQUE - dedup
- `evidence_packs(tenant_id, requested_at DESC)`

GIN indexes on jsonb fields: `reasoning_chain`, `business_outcome`.

OpenSearch holds searchable copies of `prompt_content`, `response_content`, `reasoning_chain.summary`.

## Partitioning

PostgreSQL: `receipts` table partitioned by `(tenant_id, created_at)` monthly.
S3: cold ledger keyed `s3://forensa-ledger/{tenant_id}/{yyyy}/{mm}/{dd}/{receipt_id}.json.gz.enc`.

## Encryption

- At rest: AES-256-GCM, per-tenant KMS key
- In transit: TLS 1.3 enforced
- Signing: Ed25519 (agent + tenant), keys in KMS or HSM
- Sensitive payload columns (`prompt_content_ref`) point to encrypted S3 objects, not stored inline

## Retention

| Cohort | Default retention |
|---|---:|
| High-risk AI (EU AI Act Annex III) | 10 years |
| HIPAA workflows | 6 years |
| SOC 2 audit evidence | 7 years |
| General enterprise | 5 years |
| Tabletop synthetic | 1 year |

Soft delete sets `deleted_at`; hard delete after retention expiry. GDPR Article 17 (right to erasure) is handled via cryptographic shredding of per-record KMS data keys.

## Migration strategy (Alembic)

- Each release: forward + reverse migrations
- Receipt schema additions: never break existing receipts
- Receipt removal: never (append-only)
- Index changes: blue-green via CREATE INDEX CONCURRENTLY
