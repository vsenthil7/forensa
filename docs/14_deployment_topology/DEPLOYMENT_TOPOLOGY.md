# Forensa - Deployment Topology

**Doc:** 14 of 22 | **Source:** Section C.7, C.16 of master doc

## 4 deployment modes

### 1. SaaS multi-tenant (default Year 1)
- Forensa-hosted on AWS (eu-west-1 default, us-east-1 for US customers)
- Per-tenant KMS keys (cross-tenant isolation)
- Per-tenant logical PostgreSQL schemas
- Shared OpenSearch cluster (tenant-scoped indices)
- TLS 1.3 ingress
- Suitable: Team Pilot, Enterprise Standard tiers

### 2. Single-tenant VPC
- Customer AWS / Azure / GCP VPC
- Forensa control plane in customer cloud account
- Dedicated infrastructure per tenant
- Customer KMS or HSM
- VPN / Direct Connect optional
- Suitable: Regulated Enterprise tier

### 3. On-prem Kubernetes
- Customer-controlled Kubernetes cluster
- Forensa Helm chart deploys all components
- Air-gapped option (image registry pre-loaded)
- Customer-managed PostgreSQL + S3-compatible storage (MinIO, Ceph)
- Suitable: Sovereign deployments, government

### 4. Air-gapped
- No internet egress
- Customer-provided RFC 3161 TSA (or self-signed time anchoring with regulator-approved fallback)
- Customer-provided HSM
- Suitable: Defence, classified workloads

## Kubernetes deployment shape

Helm chart components (deploy/):
- forensa-api (FastAPI ingest + investigator + export) - 3-20 replicas, HPA on CPU + req/s
- forensa-console (Next.js 15) - 2 replicas, behind Ingress
- forensa-worker (Celery for async exports, narratives, anchoring) - 2-10 replicas
- forensa-scheduler (cron-like daily TSA anchor, retention sweeps) - 1 replica, leader-elected
- PostgreSQL 16 StatefulSet (or external RDS / Cloud SQL)
- OpenSearch StatefulSet (or external managed)
- Redis (cache, Celery broker)
- Kafka (optional event bus; default direct DB writes)

## Network topology

```
                       Internet
                          |
                       [ WAF ]
                          |
                       [ ALB ]
                          |
              ----------------------
              |                    |
       [ forensa-api ]      [ forensa-console ]
              |                    |
              v                    |
     [ PostgreSQL ] <--+          |
     [ OpenSearch ] <--|----------+
     [ S3 ] <----------+
              |
              v
     [ External TSA ]
     [ KMS / HSM ]
```

## Resource requirements

| Component | CPU | Memory | Disk |
|---|---:|---:|---:|
| forensa-api (per pod) | 2 vCPU | 4 GiB | n/a |
| forensa-worker (per pod) | 1 vCPU | 2 GiB | n/a |
| forensa-console (per pod) | 1 vCPU | 1 GiB | n/a |
| PostgreSQL primary | 16 vCPU | 64 GiB | 2 TiB SSD |
| PostgreSQL replica | 16 vCPU | 64 GiB | 2 TiB SSD |
| OpenSearch (3 nodes) | 8 vCPU each | 32 GiB each | 1 TiB each |
| Redis | 2 vCPU | 8 GiB | 100 GiB |

Sizing for 10K events/sec sustained + 100K peak (BR-09).

## High availability

- Multi-AZ deployment standard
- PostgreSQL streaming replication (1 sync + 2 async)
- OpenSearch 3-node cluster minimum
- S3 cross-region replication for evidence packs
- Forensa-api stateless; horizontal scale

## Disaster recovery

- RPO (Recovery Point Objective): 5 minutes (PostgreSQL streaming replication)
- RTO (Recovery Time Objective): 30 minutes (automated failover)
- Backup: hourly PostgreSQL snapshots; daily full + WAL streaming
- Retention: 7 days hot backups, 30 days cold backups, evidence in S3 for retention period
- DR drill: quarterly

## Observability

- Metrics: OpenTelemetry -> Prometheus + Grafana (or Datadog)
- Logs: structured JSON -> CloudWatch / Loki
- Traces: OpenTelemetry -> Tempo / Jaeger / Datadog APM
- Forensa own self-observability is metered (event throughput, chain latency, TSA anchor success)

## Networking + connectivity

- Egress allow-list: KMS, TSA endpoints, Gemini API (if narrative enabled), customer webhooks
- No outbound to internet from ingest endpoint (only customer-side)
- Private link / Service Connect / Private Endpoint supported for major cloud connections

