# Forensa - Data Protection and Privacy

**Doc:** 13 of 22 | **Source:** Section C.15 of master doc

## Privacy posture

Forensa is a **data processor** under GDPR Article 28. The customer (tenant) is the controller. Forensa processes prompt content, model output, and identity metadata on the controller instructions.

## Data categories handled

| Category | Examples | Sensitivity |
|---|---|---|
| Identifiers | DID, agent ID, tenant ID, user ID | Medium |
| Content | Prompts, model responses, tool args | High (may contain PII) |
| Decisions | Policy verdicts, approvals, outcomes | High |
| Metadata | Timestamps, model versions, latencies | Low |
| Cryptographic | Signatures, hashes, public keys | Low |

## Personal data handling

### Pseudonymisation
- User identifiers stored as opaque IDs (`user-uuid-...`), no plaintext names
- Prompt content may contain PII; treated as such
- Forensa offers PII redaction layer (optional, per-cohort) that hashes detected PII before storage

### Minimisation
- Only fields necessary for evidence chain are stored
- Reasoning chain stored as structured summary, not full transcript by default (BR-03 captures summary; full transcript optional)
- Configurable per-tenant retention to minimum required by applicable framework

### Retention
- Default 10 years for high-risk AI (EU AI Act Annex III)
- 6 years HIPAA, 7 years SOC 2
- Customer-configurable per cohort
- After retention: cryptographic shredding of per-record KMS data key -> ciphertext becomes permanently unreadable

### Right to erasure (GDPR Article 17)
- Receipt cannot be deleted from chain (would break Merkle tree)
- Instead: per-record KMS data key is destroyed -> ciphertext unrecoverable
- Receipt metadata remains in chain (proof of past existence) but content is cryptographically gone
- Erasure event itself is a Receipt (transparency)

### Data residency
- Default tenant region selected at provisioning
- EU customers: EU-only S3 buckets, EU-resident KMS, EU TSA endpoint
- US customers: US S3 + KMS
- No cross-region replication without customer opt-in

## DPIA template

Forensa publishes a Data Protection Impact Assessment template that customers can use as the starting point for their own DPIA under GDPR Article 35. Available at `docs/legal/DPIA_TEMPLATE.md` (future addition; not in v1).

## Subprocessors

Forensa publishes a subprocessor list. Customers are notified 30 days before changes. Current subprocessors:
- AWS (cloud infrastructure)
- Google (Gemini API for narrative generation - opt-in per tenant)
- RFC 3161 TSA providers (DigiCert, Sectigo, EU-based equivalents)

Customers can opt out of any subprocessor (Gemini opt-out disables narrative generation; chain integrity unaffected).

## Cross-border transfer

EU -> US transfers governed by:
- EU-US Data Privacy Framework (where Forensa is certified)
- Standard Contractual Clauses (default)
- Adequacy decisions (UK, Switzerland)

## GDPR Article 32 (security of processing)

Mapped to Security Architecture (doc 10):
- Encryption at rest and in transit
- Pseudonymisation
- Restoration capability (backups)
- Regular testing (load + pen tests, doc 16)
- Access controls (RBAC + MFA)

## Right of access (GDPR Article 15)

Data subjects can request the prompts/responses they were involved in. Forensa provides tenant admin a query endpoint that surfaces all Receipts referencing a given user_id. Tenant fulfils the request to the data subject directly.

## Sensitive categories

If a tenant uses Forensa for workflows touching:
- Health data (HIPAA + GDPR Article 9)
- Children data (COPPA + GDPR Article 8)
- Special category data (GDPR Article 9)

Additional configuration applies: separate KMS key, separate retention, mandatory PII redaction, separate audit log.

## Customer-facing privacy artefacts

- Privacy Notice (Forensa-side)
- DPA (Data Processing Agreement) with Article 28 mandatory clauses
- DPIA template
- Subprocessor list
- Sub-region certifications (SOC 2 Year 2, ISO 27001 Year 3, ISO 27701 Year 3)