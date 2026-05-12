# Forensa - Security Architecture

**Doc:** 10 of 22 | **Source:** Section C.14 of master doc

## Security goals

1. **Tamper-evidence** - any modification of a Receipt is cryptographically detectable
2. **Non-repudiation** - neither agent nor tenant can deny a recorded action
3. **Confidentiality** - prompt/response content encrypted at rest and in transit
4. **Tenant isolation** - cross-tenant data access architecturally prevented
5. **Audit-grade access logging** - every Forensa-side action is itself a Receipt

## Cryptographic primitives

| Use | Algorithm | Library | Key length |
|---|---|---|---:|
| Receipt signing (agent) | Ed25519 | PyCA cryptography | 256-bit |
| Receipt signing (tenant) | Ed25519 | PyCA cryptography | 256-bit |
| Content hashing | SHA-256 | PyCA cryptography | 256-bit |
| Merkle tree | SHA-256 | PyCA cryptography | 256-bit |
| TSA anchoring | RFC 3161 | PyCA cryptography | n/a |
| At-rest encryption | AES-256-GCM | KMS-managed | 256-bit |
| TLS in transit | TLS 1.3 | rustls / OpenSSL | 256-bit |
| Optional FIPS | PyCA cryptography FIPS-validated build | OpenSSL FIPS module | - |

## Key management

- Tenant root key in AWS KMS (or Azure Key Vault, GCP Cloud KMS for multi-cloud Year 2)
- Optional HSM backing for Regulated Enterprise / Strategic Deployment tiers (CloudHSM)
- Agent keys derived per-agent from tenant root via KDF (HKDF-SHA-256)
- Key rotation: tenant root every 12 months, agent keys every 6 months
- Compromised key: revocation list signed by tenant root, distributed via OpenSearch index

## Identity and access

- **Authentication:** OIDC (Okta, Azure AD, Google Workspace), SAML for legacy
- **MFA:** required for Compliance, GC, Admin roles
- **Service-to-service:** mutual TLS + service mesh (Istio in K8s deployments)
- **Agent identity:** DID with public key registered before any events accepted

## RBAC roles

| Role | Permissions |
|---|---|
| ForensaAdmin | Full admin within tenant |
| ComplianceOfficer | Read all receipts, export regulator packs |
| InternalAuditor | Read receipts, verify chain, sample audits |
| SecurityEngineer | Read receipts, investigate incidents, replay |
| GeneralCounsel | Read receipts, legal hold, export |
| AIPlatformOwner | Read receipts (own agents), configure ingest |
| AgentOperator | Submit events (only own agent identity) |
| AuditorExternal | Read receipts (read-only, scoped cohort) |

## Threat model anchors (full detail in doc 11)

Primary threats:
- **Insider modifies historical Receipt** -> Merkle chain detects within seconds; TSA anchor prevents backdating
- **Tenant key compromise** -> KMS audit log + revocation list; new agent keys derived
- **Ingest endpoint flood (DoS)** -> rate limit per tenant + per agent; circuit breakers
- **Prompt injection in narrative input** -> Gemini Pro called with system prompt that flags hallucination; narrative is *commentary on chain*, not source of truth
- **TSA compromise** -> Section C.7 explicit mitigation: use multiple TSAs (one EU, one US); record both; require quorum

## Defence in depth

| Layer | Control |
|---|---|
| Network | VPC, security groups, WAF, DDoS protection (CloudFront/CloudFlare) |
| App | OWASP Top 10 mitigations, dependency scanning (pip-audit, npm-audit), SAST (CodeQL) |
| Data | Encryption at rest + in transit, per-tenant keys, per-cohort retention |
| Identity | OIDC + MFA + RBAC + short-lived service tokens |
| Audit | Every Forensa action is itself a Receipt (introspection) |
| SBOM | Generated per release (CycloneDX format), signed |
| Compliance | SOC 2 Type II target Year 2, ISO 27001 Year 3 |

## Specific design decisions

### Why centralised Merkle, not blockchain (Section C.7)
- Throughput: PostgreSQL + S3 handles 100K+ events/sec; public chains do not
- Cost: per-event blockchain anchoring is economically unviable at enterprise scale
- Tamper-evidence: Merkle + TSA achieves the same property without DLT complexity
- Regulator preference: explicit DLT prohibition in several EU jurisdictions for personal data

### Why both agent AND tenant signatures
- Agent signature: proves which agent took the action
- Tenant signature: proves the enterprise acknowledged the action
- Either can prove non-repudiation independently to a court

### Why RFC 3161 daily anchoring, not per-event
- Per-event TSA call would add ~100ms latency per receipt
- Daily Merkle root anchor proves "all receipts before this date were committed by this time"
- Sufficient for regulatory time-grade evidence

## Incident response (high-level; full plan in doc 19)

1. Tamper detection: chain verification fires alert in <60 seconds
2. Containment: tenant signing key rotated; affected agent IDs flagged
3. Investigation: Forensa's own Receipts (introspection) reveal who/what/when
4. Notification: customer notified within 4h; regulator within 72h (GDPR-aligned)
5. Postmortem: shared with customer; tamper proof in evidence pack
