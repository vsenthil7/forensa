# Forensa - Threat Model

**Doc:** 11 of 22 | **Source:** Section C.14 of master doc | **Format:** STRIDE

## Asset inventory

| Asset | Sensitivity | Owner |
|---|---|---|
| Receipt ledger (PostgreSQL + S3) | Critical | Forensa Platform |
| Tenant signing keys | Critical | KMS / HSM |
| Agent signing keys | High | KMS |
| Policy bundles | High | Tenant |
| Investigator query logs | Medium | Forensa Platform |
| Evidence packs | High | Tenant |
| Customer enterprise PII (prompt content) | Critical | Tenant |

## STRIDE analysis

### Spoofing
- **T1**: Attacker impersonates a registered agent (forged Ed25519 signature)
  - **Mitigation**: Private key in KMS; signature verified at ingest; key never leaves KMS
  - **Residual**: Insider exfiltrating KMS access -> KMS audit log + alerting
- **T2**: Attacker impersonates a Forensa user (stolen OIDC token)
  - **Mitigation**: Short-lived tokens (1h), MFA, IP allow-listing for admin roles

### Tampering
- **T3**: Insider modifies historical Receipt
  - **Mitigation**: Append-only ledger; chain verification on every read; Merkle anchor proves no insertion/modification before TSA timestamp
  - **Detection time**: <60 seconds (chain check on read)
- **T4**: Attacker corrupts S3 cold storage
  - **Mitigation**: S3 versioning + Object Lock; cross-region replication; chain verification at restore time
- **T5**: TSA backdates a timestamp
  - **Mitigation**: Use 2+ independent TSAs; quorum required; record all responses

### Repudiation
- **T6**: Agent denies an action
  - **Mitigation**: Ed25519 signature + DID registry; signature is binding under eIDAS / ESIGN
- **T7**: Tenant denies receiving an event
  - **Mitigation**: Tenant signature on each Receipt; webhook delivery confirmation

### Information disclosure
- **T8**: Cross-tenant data leak
  - **Mitigation**: Row-level security in PostgreSQL on `tenant_id`; per-tenant KMS keys; tenant boundary enforced in API gateway
- **T9**: Prompt/response content exfiltration via investigator query
  - **Mitigation**: RBAC + query audit (every query is a Receipt); investigator API rate-limited; cohort-scoped tokens for auditors
- **T10**: Side-channel: timing attack on signature verification
  - **Mitigation**: Constant-time crypto (PyCA cryptography defaults)

### Denial of service
- **T11**: Ingest endpoint flooded
  - **Mitigation**: Per-tenant + per-agent rate limits; ALB + WAF; circuit breakers; degraded-mode (queue-only, signature deferred)
- **T12**: OpenSearch query bomb
  - **Mitigation**: Query cost limits; investigator quota; cached aggregations
- **T13**: TSA endpoint unavailable
  - **Mitigation**: Multi-TSA fallback; daily anchor batched (not per-event)

### Elevation of privilege
- **T14**: Agent operator escalates to admin
  - **Mitigation**: Separation of duties; admin role requires MFA + separate auth domain
- **T15**: Lobster Trap verdict spoofed
  - **Mitigation**: Lobster Trap verdicts themselves are signed receipts; Forensa verifies signature

## Highest-risk threats (top 5)

1. **T3 Insider tampering** - mitigated by chain + TSA; residual: TSA quorum prevents collusion
2. **T8 Cross-tenant leak** - mitigated by per-tenant keys + RLS; residual: privileged Forensa engineer access
3. **T1 Agent key compromise** - mitigated by KMS; residual: KMS service compromise (out of scope - AWS/Azure responsibility)
4. **T11 Ingest DoS** - mitigated by rate limit + circuit breaker; residual: legitimate traffic spike at fiscal year-end
5. **T5 TSA backdating** - mitigated by 2+ TSA quorum; residual: nation-state collusion (acceptable risk for v1)

## Threat intelligence sources

- MITRE ATLAS (AI threat matrix)
- OWASP ML Top 10
- NIST AI RMF threat library
- Cloud Security Alliance AAGATE threat catalog

## Pen-test cadence

- Internal red team: quarterly (Year 1+)
- External pen test (NCC Group or Trail of Bits): annually
- Bug bounty (HackerOne): Year 2+
- TLPT (DORA Article 30): annually for financial-services customers

## Threat-to-test mapping

Each STRIDE threat has corresponding test coverage:
- Tampering threats -> property-based tests on chain integrity (`hypothesis`)
- Spoofing -> signature verification unit tests
- Information disclosure -> tenant isolation integration tests
- DoS -> load tests via Locust (BR-09)

See doc 16 Testing and QA for the full mapping.
