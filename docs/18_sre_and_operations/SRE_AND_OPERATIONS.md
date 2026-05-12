# Forensa - SRE and Operations

**Doc:** 18 of 22 | **Source:** Section C.16, ops patterns from Verixa

## SLOs (Service Level Objectives)

| Service | Metric | SLO |
|---|---|---:|
| Ingest API | Availability | 99.9% monthly |
| Ingest API | p99 latency | < 5ms |
| Investigator API | Availability | 99.9% monthly |
| Investigator API | p99 query | < 2 sec |
| Export API | Availability | 99.5% monthly |
| Export API | Pack generation (1000 receipts) | < 5 min |
| Chain verification | Correctness | 100% (no SLO violation tolerated) |
| Daily TSA anchor | Success | 100% (paged if missed) |
| Evidence pack download | Availability | 99.5% monthly |

## Error budget

- 99.9% monthly = 43m 49s downtime budget
- Burn rate alerts: 2% in 1h, 5% in 6h, 10% in 24h
- Frozen deploys when budget < 25%

## Alerting (PagerDuty / Opsgenie)

| Alert | Severity | Action |
|---|---|---|
| Chain verification fail | P1 | Page on-call immediately + customer success notification |
| TSA anchor missed (>24h) | P1 | Page on-call + customer notification |
| Ingest API down | P1 | Page on-call |
| Ingest p99 > 50ms (>10 min) | P2 | Page on-call (latency degradation) |
| OpenSearch query failures | P2 | Page on-call (investigator UX) |
| PostgreSQL replication lag > 5 min | P2 | Page on-call |
| Disk usage > 80% | P2 | Page on-call |
| Disk usage > 90% | P1 | Page on-call |
| KMS rate limit | P2 | Page on-call (key derivation failures) |

## Runbooks

Living docs under docs/runbooks/ (created during Day 6):
- chain-verification-failure.md
- tsa-anchor-missed.md
- tenant-key-compromise.md
- database-failover.md
- opensearch-cluster-recovery.md
- customer-incident-export.md

## On-call rotation

Year 1: founders + 1 senior engineer, 7-day rotation
Year 2: 4-engineer rotation, 7-day rotation, weekend escalation policy
Year 3+: regional on-call (EU + US), follow-the-sun

## Operational metrics

Dashboards (Grafana):
- Ingest throughput per tenant (events/sec, last 24h)
- Latency p50/p95/p99 per endpoint
- Chain verification success rate
- TSA anchor age (time since last successful anchor)
- Storage growth per tenant (PostgreSQL + S3)
- Evidence pack generation queue depth
- Export request success rate

## Backup + restore

| Asset | Backup cadence | Retention | RTO | RPO |
|---|---|---|---:|---:|
| PostgreSQL | Streaming + hourly snapshots | 30 days | 30 min | 5 min |
| S3 evidence packs | Cross-region replication | retention period | 1h | 15 min |
| Configuration (Helm values) | Git versioned | indefinitely | n/a | n/a |
| KMS keys | KMS-managed (AWS, never deleted) | indefinitely | n/a | n/a |

DR drills: quarterly tabletop, annually live failover.

## Capacity planning

Watch: events/sec per tenant, growth rate, storage growth, KMS request rate.

Auto-scaling triggers:
- forensa-api: HPA on CPU + req/s
- PostgreSQL: read replicas auto-added at >70% CPU sustained
- OpenSearch: cluster nodes added at >75% disk

## Deployment

- Blue-green via Argo Rollouts
- Canary 5% -> 25% -> 100% over 30 min
- Automatic rollback on: error rate > baseline + 50%, latency p99 > baseline + 100%
- Database migrations: backward-compatible + forward-compatible window (one release)

## Cost monitoring

Per-tenant cost attribution via Kubernetes labels + AWS Cost Allocation Tags.
Margin target: gross margin > 70% by end of Year 2.

## ops.ps1 dispatcher

Hackathon repo includes ops.ps1 with 28 actions (Windows-only for hackathon environment; Linux equivalent in ops.sh for production):

verify-chain, ingest-smoke, evidence-pack, lobstertrap-pipe, tamper-demo, gemini-narrative, generate-openapi, db-migrate, run-api, run-console, run-worker, test-all, test-python, test-typescript, test-e2e, test-load, build-docker, deploy-helm, ... (full list when ops.ps1 is pushed)

## Customer success operations

- New customer onboarding: 2-week pilot scoping + integration session
- Quarterly business reviews (Regulated tier+)
- Annual evidence pack audit (Forensa-side independent check)
- Incident hotline: 24/7 for Regulated + Strategic tiers

