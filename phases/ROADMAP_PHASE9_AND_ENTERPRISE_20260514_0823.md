# Forensa - Pending hackathon work + Enterprise-grade roadmap

Generated: Wed 14/05/2026 08:23  |  HEAD: 437e8d7  |  Hackathon deadline: Mon 19/05/2026

Two tables side-by-side:

1. **Phase 9** = the 2 deferred CPs from Phases 6 + 8 plus demo-day polish. Closes the hackathon scope.
2. **Phases 10-13** = enterprise grade roadmap. What is missing today to take Forensa from hackathon MVP (~3 KLOC, 502 tests) to production enterprise SaaS (~25-40 KLOC, thousands of tests, SOC2 + ISO 27001 ready).

LOC + test estimates are calibrated against actual Phase 0-8 throughput in this repo: ~125 LOC production / day, ~5 tests / 100 LOC production.

---

## Part 1 - Pending hackathon work (Phase 9)

| CP | Title | Description | Est code LOC | Est test LOC | Functional | Negative | Property | Playwright | User-case | Total tests |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CP9.1 | Live Gemini Pro client | google-generativeai under existing NarrativeClient ABC; gated by FORENSA_GEMINI_API_KEY env var; same wire-form contract as MockNarrativeClient so swap-in is transparent | 60 | 120 | 3 (success path with mocked SDK, env var resolution, timeout retry) | 3 (missing key, SDK exception, rate limit) | 0 | 0 | 1 (CFO Q1 reports demo with real prose) | 7 |
| CP9.2 | CP6.3 PDF render | ReportLab-based A4 PDF render of evidence pack: header + hash chain table + signature block + QR code linking to /v1/evidence-packs JSON | 220 | 180 | 4 (1-page, multi-page, empty pack, large pack 100+ receipts) | 2 (malformed pack, missing fonts) | 0 | 1 (download + visual snapshot test) | 1 (regulator hands PDF to forensic accountant) | 8 |
| CP9.3 | Seed demo data | scripts/seed_demo.py that POSTs 50 events across 2 tenants, deliberately tampers 1 receipt so integrity badge renders red on stage | 80 | 60 | 2 (clean seed + tampered seed) | 1 (idempotent re-seed) | 0 | 1 (full demo flow: seed -> view receipts -> click tampered -> red badge) | 2 (judge view sequence + recovery if seed already exists) | 6 |
| CP9.4 | LiveNarrativeClient wiring + env var swap | apps/api/main.py conditionally registers LiveNarrativeClient when FORENSA_GEMINI_API_KEY is set, else MockNarrativeClient; integration test confirms swap | 30 | 80 | 2 (env-set -> live registered, env-unset -> mock registered) | 1 (env-set but key invalid -> startup fails fast) | 0 | 0 | 1 (full POST /v1/narratives against live API in staging) | 4 |
| CP9.5 | Pre-recorded 90-sec demo MP4 | OBS-recorded clean run of demo_tabletop + console + integrity-badge flip; for fallback if conference wifi fails | n/a | n/a | n/a | n/a | n/a | n/a | n/a | manual deliverable |
| CP9.6 | 1-page judge handout PDF | Architecture diagram + 3-anchor verifiability chain + EU AI Act Article 12 hook + QR to repo | n/a | n/a | n/a | n/a | n/a | n/a | n/a | manual deliverable |
| CP9.7 | Pitch rehearsal | 5 dry runs against the timed slot; ensure contract-runtime opener + Article 12 hook land in first 30 sec; verify on-stage hash recomputation works | n/a | n/a | n/a | n/a | n/a | n/a | n/a | manual deliverable |
| CP9.8 | Phase 9 DONE doc | phase9_DONE.md with deliverables + lessons | n/a | n/a | n/a | n/a | n/a | n/a | n/a | DOC |
| **Phase 9 total** | - | **~6h estimated** | **390 LOC** | **440 LOC** | **11** | **7** | **0** | **2** | **5** | **25 tests** |

Step-by-step for Phase 9:

1. CP9.1 ships the only remaining production code change: 60 LOC under the existing NarrativeClient ABC. All test paths are already proven via MockNarrativeClient; LiveNarrativeClient only adds the google-generativeai call + retry/timeout/error mapping.
2. CP9.2 (PDF render) is the only large code item left in scope. ReportLab + standard A4 layout; reuses pack.root_hash + receipts already produced by Phase 6 code. 220 LOC is a calibrated estimate from comparable ReportLab work.
3. CP9.3 + CP9.4 are stitching: data seeding + env-conditional client wiring. Together ~110 LOC.
4. CP9.5 + CP9.6 + CP9.7 are manual deliverables - no code, just videos and slides and rehearsal.
5. CP9.8 closes the phase with the standard DONE doc.

Total Phase 9 code: ~390 LOC production + ~440 LOC tests + 25 new tests. Estimated 6 working hours.

---

## Part 2 - Enterprise-grade roadmap (Phases 10-13)

What is missing today to take Forensa from hackathon MVP to enterprise production:

- Multi-tenant isolation at the data plane (row-level security)
- Authentication + authorisation (SSO + RBAC + service accounts)
- Observability (metrics + tracing + structured logs)
- HSM + KMS for tenant signing keys (currently in-memory keypair)
- Multi-region failover + disaster recovery
- SOC 2 + ISO 27001 + GDPR + EU AI Act compliance evidence
- Customer admin console (tenant onboarding, key rotation, audit log download)
- Per-tenant SLAs + rate limiting + quota enforcement
- Long-haul evidence retention (S3 + Glacier + WORM lock)
- Customer migration tooling (zero-downtime schema upgrades)

### Phase 10 - Security + auth + multi-tenant isolation

| CP | Title | Description | Est code LOC | Est test LOC | Functional | Negative | Property | Playwright | User-case | Total tests |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CP10.1 | SSO via OIDC (Auth0/Okta) | google + microsoft + okta IdP support; JWT validation; refresh tokens | 450 | 600 | 8 | 12 (expired, wrong-aud, wrong-issuer, malformed, replay) | 0 | 3 (login flow, logout, 401 redirect) | 4 (SOC2 admin, compliance officer, dev, auditor) | 27 |
| CP10.2 | RBAC + permissions middleware | role -> permission map; FastAPI dependency for every endpoint; 5 roles (admin, compliance, auditor, viewer, service) | 380 | 720 | 12 | 15 (each role x each endpoint mismatch) | 0 | 2 (forbidden UI elements hidden) | 5 (each role doing day-job) | 34 |
| CP10.3 | Tenant data isolation via RLS | Postgres row-level security on all tenant-scoped tables; CHECK constraints; per-request tenant binding | 280 | 540 | 8 | 18 (cross-tenant read/write/delete blocked at DB) | 4 (hypothesis: any 2 tenants stay isolated) | 1 (cross-tenant URL guessing returns 404) | 3 (multi-tenant SaaS admin sequence) | 34 |
| CP10.4 | Service account + API key issuance | machine identities for agent ingestion; key rotation; revocation; per-key rate limit | 320 | 480 | 6 | 10 (revoked key, expired, wrong scope) | 0 | 1 (key creation -> use -> rotate -> revoke flow) | 3 (SRE provisioning, security team rotation, breach response) | 20 |
| CP10.5 | Audit log of admin actions | every config change, key rotation, role assignment logged immutably; appended to same receipt chain | 180 | 320 | 5 | 4 (tampered audit, missing audit, replay) | 1 (audit chain hashes verify like receipts) | 1 (audit log download flow) | 2 (compliance officer reviewing change history) | 13 |
| CP10.6 | Secret management (Vault/Secrets Manager) | tenant signing keys + DB creds + API keys backed by Vault; no secrets in env | 220 | 380 | 4 | 8 (Vault unreachable, lease expired, rotation mid-request) | 0 | 0 | 3 (key rotation playbook, Vault outage, audit of secret access) | 15 |
| **Phase 10 total** | - | **~12 weeks team-effort** | **1830 LOC** | **3040 LOC** | **43** | **67** | **5** | **8** | **20** | **143 tests** |

### Phase 11 - Cryptographic hardening + key management

| CP | Title | Description | Est code LOC | Est test LOC | Functional | Negative | Property | Playwright | User-case | Total tests |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CP11.1 | HSM-backed tenant signing keys | AWS CloudHSM or Azure Dedicated HSM; tenant signing key never leaves HSM; sign() goes via PKCS#11 | 380 | 580 | 6 | 12 (HSM down, slot full, wrong PIN, key wrap fail) | 2 (sign-verify still round-trips through HSM boundary) | 0 | 3 (tenant onboarding key gen, rotation, escrow recovery) | 23 |
| CP11.2 | KMS envelope encryption at rest | DEK per tenant, KEK in KMS; column-level encryption for PII; transparent decrypt in repo layer | 290 | 480 | 5 | 8 (KMS down, key revoked, wrong region) | 1 (encrypt-decrypt round-trip) | 0 | 2 (incident response decrypt, key rotation under load) | 16 |
| CP11.3 | Tenant key rotation playbook | online rotation; old key still verifies historical receipts; new key signs going forward; key version field on Receipt | 240 | 420 | 4 | 6 (rotation mid-burst, old-key verify post-rotation, key version mismatch) | 1 (chain integrity across rotation boundary) | 0 | 2 (annual rotation, compromise-response rotation) | 13 |
| CP11.4 | Quantum-safe roadmap | Dilithium signature alongside Ed25519; dual-sign mode; receipts carry both | 320 | 540 | 5 | 4 (one sig valid one not, version negotiation) | 2 (dual-sign verifies under both schemes) | 0 | 2 (NIST PQC transition, regulator request for PQC) | 13 |
| CP11.5 | Time anchoring via RFC 3161 / OpenTimestamps | timestamp service for receipts; anchor signed_at to a public chain (Bitcoin OTS) | 260 | 380 | 4 | 5 (TSA unreachable, anchor fails, OTS verification) | 0 | 0 | 2 (forensic timestamp dispute, regulator audit) | 11 |
| **Phase 11 total** | - | **~10 weeks team-effort** | **1490 LOC** | **2400 LOC** | **24** | **35** | **6** | **0** | **11** | **76 tests** |

### Phase 12 - Observability + reliability + scale

| CP | Title | Description | Est code LOC | Est test LOC | Functional | Negative | Property | Playwright | User-case | Total tests |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CP12.1 | OpenTelemetry tracing + metrics | every request traced; receipt issuance histogram; chain length gauge; export to Honeycomb/Datadog | 280 | 380 | 5 | 4 (collector down, OTLP malformed, drop policy) | 0 | 0 | 3 (slow query investigation, alert chain, capacity planning) | 12 |
| CP12.2 | Structured JSON logs with correlation IDs | every log line has tenant_id + trace_id + receipt_id; redact PII; shipped to ELK/CloudWatch | 180 | 240 | 4 | 5 (PII leak prevention, sampling under load) | 1 (no PII appears in logs across 1000-event run) | 0 | 2 (post-incident log search, GDPR redaction audit) | 12 |
| CP12.3 | Postgres + replicas + read-write split | primary-replica topology; read repository goes to replicas; write goes to primary; failover playbook | 320 | 520 | 5 | 6 (replica lag, primary failover, split-brain) | 2 (read-after-write consistency for same session) | 0 | 3 (planned failover, unplanned failover, region degradation) | 16 |
| CP12.4 | Kafka-backed event ingestion | high-throughput ingestion via Kafka; consumer commits to receipt chain; exactly-once semantics | 480 | 720 | 8 | 12 (consumer crash, duplicate event, out-of-order, poison pill) | 3 (chain integrity holds under 100K events / sec) | 0 | 3 (Kafka outage, backpressure, replay from offset) | 26 |
| CP12.5 | Horizontal API auto-scale | k8s HPA on api pods; per-tenant rate limit at gateway; circuit breakers on downstream | 220 | 340 | 4 | 6 (rate limit breach, circuit open, retry storm) | 0 | 0 | 2 (Black Friday-style burst, slow downstream) | 12 |
| CP12.6 | Multi-region active-active | api running in 3 regions; tenant home region + DR region; data replication; geo-routing | 420 | 580 | 6 | 8 (region down, cross-region replication lag, DNS failover) | 2 (eventual consistency tolerated by clients) | 0 | 3 (regional outage drill, compliance routing, customer migration) | 19 |
| **Phase 12 total** | - | **~14 weeks team-effort** | **1900 LOC** | **2780 LOC** | **32** | **41** | **8** | **0** | **16** | **97 tests** |

### Phase 13 - Compliance + enterprise SaaS

| CP | Title | Description | Est code LOC | Est test LOC | Functional | Negative | Property | Playwright | User-case | Total tests |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CP13.1 | SOC 2 Type II evidence automation | continuous evidence collection: access reviews, change tickets, vuln scans; auditor-friendly export | 380 | 480 | 5 | 6 (evidence gap, stale evidence, export malformed) | 0 | 1 (auditor downloads quarterly evidence pack) | 3 (initial SOC2, annual renewal, customer audit request) | 15 |
| CP13.2 | GDPR right-to-erasure + data portability | crypto-shredding for PII (delete tenant DEK); audit-log retention exempt; data export endpoint | 280 | 480 | 5 | 8 (active receipts cant be deleted, audit log preserved, export schema versioned) | 1 (after erasure no PII anywhere) | 1 (full erasure + export flow) | 3 (DPO request, customer offboarding, regulator inquiry) | 18 |
| CP13.3 | EU AI Act Article 12 conformance pack | bundled evidence pack format that matches Article 12 record-keeping requirements; pre-filled fields | 220 | 380 | 4 | 4 (missing required field, scope window invalid) | 1 (every pack passes Article 12 schema validation) | 1 (Article 12 export download flow) | 3 (national authority request, ESMA inquiry, internal compliance) | 13 |
| CP13.4 | Tenant admin console | self-service tenant onboarding; user provisioning; key rotation UI; audit log viewer; billing | 720 | 880 | 12 | 14 (forbidden actions for non-admins, audit before delete, etc) | 0 | 6 (admin tour: onboard tenant, add user, rotate key, view audit, request data export) | 4 (CRO onboarding new BU, CISO incident drill, ops daily, billing) | 36 |
| CP13.5 | Billing + metering + usage analytics | per-tenant event count + storage + narrative tokens; Stripe billing; invoice generation; usage dashboard | 380 | 480 | 6 | 5 (metering drift, double-charge, refund) | 1 (usage matches Stripe at month boundary) | 2 (sign-up to first invoice flow) | 3 (CFO usage report, billing dispute, plan change) | 17 |
| CP13.6 | Customer onboarding playbook | white-glove onboarding script; SDK in 3 languages (Python/TS/Go); curl recipe; Helm chart for on-prem | 480 | 520 | 8 | 4 (SDK version mismatch, network drop mid-onboard) | 0 | 2 (full SDK install + first-receipt flow) | 4 (cloud-native customer, on-prem bank customer, hybrid pharma, regulated EU) | 18 |
| CP13.7 | Disaster recovery + business continuity | RPO/RTO targets; cross-region backups + restore drills; runbook | 280 | 380 | 4 | 6 (region loss, backup corruption, restore-incomplete) | 1 (chain integrity holds after full restore) | 0 | 3 (regional outage drill, full DR drill, partial corruption) | 14 |
| CP13.8 | Customer-facing API SDK + docs | OpenAPI 3.1 spec + auto-generated SDKs (Python/TS/Go/Java) + docs site (docusaurus) | 320 | 280 | 4 | 3 (SDK version mismatch, schema breaking change, deprecated path) | 0 | 1 (SDK quickstart copy-paste compiles + runs) | 3 (Python integrator, TS frontend, Go ops) | 11 |
| **Phase 13 total** | - | **~16 weeks team-effort** | **3060 LOC** | **3880 LOC** | **48** | **50** | **6** | **14** | **24** | **142 tests** |

---

## Grand totals (enterprise roadmap)

| Phase | Title | Team-weeks | Code LOC | Test LOC | Total tests |
|---|---|---:|---:|---:|---:|
| 9 | Hackathon close (Live Gemini + PDF + seed + manual) | 1 dev-week | 390 | 440 | 25 |
| 10 | Security + auth + multi-tenant isolation | 12 | 1830 | 3040 | 143 |
| 11 | Cryptographic hardening + key management | 10 | 1490 | 2400 | 76 |
| 12 | Observability + reliability + scale | 14 | 1900 | 2780 | 97 |
| 13 | Compliance + enterprise SaaS | 16 | 3060 | 3880 | 142 |
| **Hackathon + enterprise total** | - | **~53 team-weeks** | **+8670 LOC** | **+12540 LOC** | **+483 tests** |

## Cumulative state at end of Phase 13

| Metric | Today (Phase 8) | At Phase 13 end | Delta |
|---|---:|---:|---|
| Production code LOC | ~3,005 | ~11,675 | 3.9x |
| Test code LOC | ~3,717 | ~16,257 | 4.4x |
| Total tests | 502 | ~985 | 2.0x |
| API endpoints | 6 | ~25 | 4.2x |
| Production phases | 8 | 13 | + 5 phases |
| Team months | ~0.2 (5 days solo) | ~13 team-months | enterprise SaaS scope |
| Compliance posture | None | SOC2 + GDPR + EU AI Act | audit-ready |

Step-by-step:

1. Phase 9 closes the hackathon. ~6 hours of dev work plus presentation polish. Single-person.
2. Phase 10 is the first must-have for enterprise: auth + RBAC + tenant isolation. No enterprise customer signs without this.
3. Phase 11 hardens the cryptographic core: HSM-backed keys, KMS envelope encryption, quantum-safe roadmap, RFC 3161 time anchoring. The chain is only as good as its keys.
4. Phase 12 makes the system reliable at scale: OTel, structured logs, replicas, Kafka ingestion, multi-region. Today the chain runs at 6452 events/sec in-process; Phase 12 takes that to ~50K+/sec sustained across regions.
5. Phase 13 ships the enterprise SaaS surface: SOC2 + GDPR + EU AI Act compliance evidence, tenant admin console, billing + metering, customer onboarding, DR/BC.

---

## Cross-cutting things required to call it enterprise-grade

Items that span multiple phases or are non-code deliverables required for enterprise sales:

| Area | What is needed | When | Effort |
|---|---|---|---|
| Security questionnaire (SIG / CAIQ) | 200+ question response covering data handling, encryption, access control, incident response | Before first enterprise pilot | 1 person-week |
| Pen test | External pen test (CREST or equivalent); remediation cycle; retest | Quarterly after Phase 11 | 2 person-weeks per cycle |
| Vulnerability management | weekly Snyk / Trivy scans; SLA-bound remediation; CVE response runbook | Continuous | 0.5 FTE perpetually |
| Bug bounty programme | HackerOne or Bugcrowd; scoped; payouts | After Phase 13 | 1 person-week setup + ongoing triage |
| Security training | annual all-hands secure-coding; CISSP / CCSK for senior engineers | Annual | 1 day per person per year |
| Incident response runbook | tabletop exercises 2x per year; written runbook; on-call rotation; pager | Before first paying customer | 2 person-weeks initial + ongoing drills |
| Privacy programme | DPIA per processing activity; DPO appointed (EU requirement above 250 employees); ROPA | Before EU customers | 2 person-weeks initial + 0.2 FTE perpetually |
| Contracts + MSA + DPA | enterprise MSA template; DPA per GDPR Article 28; SCCs for non-EU; BAA for healthcare | Before first paying customer | 4 person-weeks legal |
| Customer support | tier-1/2/3 support model; SLA-bound; ticketing system; in-app chat | Before first paying customer | 2 person-weeks setup + ongoing |
| Status page | status.forensa.dev; auto-updated from health checks; incident communication | Before first paying customer | 1 person-week |
| Documentation site | docs.forensa.dev with SDK reference + tutorials + architecture + compliance + security | Continuous | 0.3 FTE perpetually |
| Customer reference architecture diagrams | per industry (FS, healthcare, pharma, manufacturing) showing how Forensa fits | Pre-sales | 1 person-week per industry |
| Solution engineering team | pre-sales technical engineers; integration help; POC support | After first 10 customers | 1 SE per 20 customers |
| Customer success | onboarding + adoption + renewal; CSM per top-tier customer | After first 5 paying customers | 1 CSM per 10 customers |
| Partner programme | system integrator + reseller channels; partner training + certification | After Phase 13 | 1 person-month setup |

Step-by-step:

1. Code work (Phases 10-13) is ~52 team-weeks (~12-13 team-months with a 4-5 person engineering team).
2. The cross-cutting non-code work above adds ~20 person-weeks of initial setup PLUS ongoing roles (security 0.5 FTE + privacy 0.2 FTE + docs 0.3 FTE + SE per 20 customers + CSM per 10 customers).
3. Calendar time to first enterprise paying customer: realistically 6-9 months from end-of-hackathon with a 5-person team.
4. Calendar time to SOC 2 Type II: 12 months minimum (6 months observation period after controls are in place).
5. Calendar time to feature-complete enterprise SaaS as described: 18-24 months.

---

## What is already done that does NOT need re-doing

Items below are already at enterprise quality and do not appear in any of Phases 10-13 because they are complete:

| Capability | Status today | Why it is already enterprise-grade |
|---|---|---|
| Cryptographic chain (Ed25519 + JCS + SHA-256 + Merkle) | DONE in Phase 1 | RFC-grade primitives; 65 tests including hypothesis-based property tests |
| Per-tenant chain isolation | DONE in Phase 4 | (tenant_id, sequence) unique constraint enforced at DB level; cross-tenant tests in test_receipt_chain.py |
| Receipt issuance + integrity verification | DONE in Phase 4 | 40 tests; recompute_receipt_hash works end-to-end; ~6450 events/sec measured |
| JSON-LD + PROV-O evidence pack | DONE in Phase 6 | root_hash binds whole pack; verify_evidence_pack is independent of Forensa |
| 3-anchor verifiability chain (pack_root_hash + prompt_hash + content_hash) | DONE in Phase 7 | Regulator-verifiable from public bytes; no Forensa trust required |
| 100pct test coverage gate enforced on CI | DONE in Phase 0 + maintained throughout | Gate is hard-failing; no degradation possible |
| mypy --strict + ruff format + ESLint + tsc strict | DONE in Phase 0 + maintained | All lint and type-check gates pass on every commit |
| Append-only ledger via Alembic migrations | DONE in Phase 3 | 2 versioned migrations; downgrade tested |
| OTel GenAI span normalisation | DONE in early units | 26 tests on tests/packages/test_normaliser.py |
| Audit-grade commit message + CI run discipline | DONE throughout | Every commit names rule + CP + test delta; every CI run ID logged |

Step-by-step:

1. The cryptographic core is done. Phase 11 hardens key STORAGE (HSM, KMS) but does not change the cryptographic primitives.
2. The chain integrity logic is done. Phase 12 scales it; the underlying invariants are unchanged.
3. The evidence-pack format is done. Phase 13 wraps compliance-grade packaging around the same JSON-LD payload.
4. This is what makes Forensa a viable starting point for enterprise: the hard cryptography + correctness work is paid down. Phases 10-13 are mostly platform engineering, not cryptographic engineering.

---

## End of roadmap

Phase 9 closes the hackathon in ~6 hours of code plus presentation polish. Phases 10-13 take Forensa from hackathon-MVP to enterprise-production-ready over ~12 calendar months with a 5-person team. The cryptographic and chain-integrity foundations laid in Phases 1-8 do not need re-doing.
