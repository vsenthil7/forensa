# Forensa - Incident Response Plan

**Doc:** 19 of 22 | **Source:** master doc + Verixa carryover

## Incident classification

| Severity | Definition | Response time | Escalation |
|---|---|---:|---|
| P1 - Critical | Chain integrity broken, tenant data exposed, system down | 15 min | Founders + customer hotline |
| P2 - Major | Degraded service, SLO violation imminent, partial feature unavailable | 1 hour | On-call + customer success |
| P3 - Minor | Single-tenant non-critical issue, cosmetic UI bug | 1 business day | Standard support queue |
| P4 - Info | Telemetry anomaly, no customer impact | Next business day | Engineering review |

## P1 incident types and runbooks

### IR-01 Chain verification failure (tamper detected)
Detection: chain-verifier emits CRITICAL alert; webhook fires verification.failed.
Containment:
1. Mark affected receipts as quarantined (does not delete; flag in status column)
2. Rotate tenant signing key in KMS
3. Notify affected tenant within 1h via secure channel
4. Trigger forensic snapshot (PostgreSQL + S3 frozen state)
Investigation:
1. Forensa own audit Receipts reveal who/what/when (introspection)
2. Compare TSA anchor timestamps to PostgreSQL row mtime
3. If insider: HR + Legal looped in within 4h
Notification:
1. Customer within 4h (initial); detailed report within 72h
2. Regulator within 72h (GDPR Article 33-aligned) if PII exposed
3. Public disclosure if affecting standards-conformance claims

### IR-02 Tenant key compromise
Detection: KMS audit log shows unexpected access; revocation list signed by tenant root.
Containment:
1. Revoke compromised key immediately
2. Derive new agent keys from new tenant root
3. Re-sign rolling window of receipts (last 30 days) with new key
4. Publish revocation Receipt to chain

### IR-03 Cross-tenant data leak
Detection: customer reports seeing data not theirs, or automated tenant-boundary check fails.
Containment:
1. Disable affected query endpoint immediately
2. Snapshot logs of all queries by suspected leak source
3. Notify both tenants within 1h
Investigation:
1. RLS policy review
2. API gateway tenant-header verification
3. Database connection pool tenant binding

### IR-04 Ingest endpoint flood (DoS)
Detection: ingest API > 100K req/s sustained for >5 min; circuit breaker engaged.
Containment:
1. WAF rate limiting tightened
2. Per-tenant cap enforced
3. Degraded-mode: queue-only, signature deferred
4. Capacity scale-out triggered

### IR-05 TSA endpoint failure
Detection: daily TSA anchor missed for >24h.
Containment:
1. Failover to secondary TSA endpoint
2. Backfill missed anchors when primary recovers
3. Customer notification if missing window > 48h

## Communication plan

### Internal
- Slack #forensa-incidents channel (private)
- PagerDuty / Opsgenie escalation
- Founders Slack DM for P1
- StatusPage.io for external communication

### External
- StatusPage.io public for service degradation
- Direct customer email + phone for P1 affecting their tenant
- Regulator notification template (pre-drafted in docs/legal/)
- Press / media: founders only; PR firm on retainer Year 2+

## Forensic preservation

Every incident triggers:
1. PostgreSQL pg_dump snapshot of affected tenant
2. S3 object lock on evidence pack range
3. Audit Receipt of incident itself (Forensa eats its own dog food)
4. 7-year retention on incident artefacts (independent of customer retention)

## Post-mortem template

docs/runbooks/post-mortem-template.md includes:
- Timeline (UTC, all events)
- Root cause analysis (5-whys)
- Contributing factors
- Detection lag (how long from incident -> detection)
- Mitigation effectiveness
- Customer-facing impact
- Action items with owners and due dates
- Lessons learned
- Regulator-grade summary (if external disclosure)

Published to customers within 14 days; internal version retained indefinitely.

## Tabletop exercises

Quarterly internal: simulate IR-01 through IR-05 against synthetic data.
Annual external: DORA Article 30 TLPT with red team firm.

Both produce signed evidence packs that demonstrate IR readiness for regulator/audit purposes.

## Regulator reporting timelines

| Framework | Reporting deadline | Trigger |
|---|---:|---|
| GDPR Article 33 | 72h | Personal data breach affecting EU subjects |
| DORA Article 19 | 4h initial, 24h intermediate, 1 month final | Major ICT incident affecting financial services |
| NIS2 | 24h | Substantial cybersecurity incident |
| SEC (US) | 4 business days | Material cybersecurity incident |

Pre-drafted templates for each available in docs/legal/incident-reports/.

## Drill cadence

- Monthly: chaos engineering on staging (random pod kill, AZ failure)
- Quarterly: full incident response tabletop
- Annually: external red team (TLPT)
- Annually: DR live failover (RTO/RPO validation)

