# Forensa

> **The black box flight recorder for enterprise AI agents.**

Forensa is a tamper-evident, multi-party-bound, policy-aware event ledger that produces legally admissible records of every AI agent action — for regulators, auditors, and litigation.

Built for the **Google TechEx Intelligent Enterprise Solutions Hackathon** (May 11–19, 2026). Track 1 — Agent Security & AI Governance. Veea Award category.

## Status

This repository is the implementation. Strategy and product definition live in the parent project folder. The canonical product spec is the three-author master document in `docs/02_brd/BRD.md` (derived from the strategy-phase master doc).

| Phase | Status |
|---|---|
| Strategy phase | Closed (3-author convergence: Claude, ChatGPT, Perplexity) |
| Product definition | Closed (master doc compiled 12 May 2026) |
| Architecture docs | In progress |
| Repo scaffold | In progress |
| Day 1 build (OTel GenAI ingest) | Pending |
| Submission to TechEx | Mon 19 May 2026 |

## Setup

### Environment variables

Forensa reads secrets and runtime config from environment variables. The canonical list lives in `.env.example` at repo root.

```powershell
# PowerShell (Windows) - one-time setup per clone
cd C:\path\to\forensa
Copy-Item .env.example .env
# Edit .env in your editor; replace every `your_*_here` placeholder with a real value
# Restart your shell so the new vars are picked up
echo $env:FORENSA_GEMINI_API_KEY
```

```bash
# bash / zsh / WSL
cp .env.example .env
$EDITOR .env
source .env  # or use direnv / dotenv-cli to auto-load
echo $FORENSA_GEMINI_API_KEY
```

**HARD RULES:**
- `.env` is gitignored. Never commit it.
- `.env.example` IS committed and acts as the documented schema of which vars are expected.
- Never paste a real API key into chat, into a tracked file, or into a CI logs URL. Real keys live only in `.env` (local dev), GitHub Actions Secrets (CI), or KMS / Vault (production).

### Gemini API key (CP9.1+)

`FORENSA_GEMINI_API_KEY` enables the live narrative path (Gemini Pro via `google-generativeai` SDK against Google AI Studio). When unset, Forensa falls back to `MockNarrativeClient` (deterministic template; no network). The startup log line announces which client is wired so you always know which is in use.

Create a key at https://aistudio.google.com/app/apikey (free tier available). Paste into `.env` under `FORENSA_GEMINI_API_KEY=`. See [`docs/reviews/01_Rev_Claude_20260514_0919/REVIEW_FIXES_LANDED_20260514_1302.md`](docs/reviews/01_Rev_Claude_20260514_0919/REVIEW_FIXES_LANDED_20260514_1302.md) for the 4-layer prompt-injection defence that wraps every live call.

**Long-term direction:** AI Studio + API key is the hackathon path. For production / enterprise customers, Vertex AI (with GCP IAM + VPC Service Controls + Customer-Managed Encryption Keys) is the right authentication boundary. Tracked as `NEW-P13.X.vertex-migration` in the review backlog.

## Wedge

Every incumbent in the AI runtime space — Microsoft AGT, Preloop, AWS Bedrock AgentCore, Veea Lobster Trap itself — is building **enforcement**. Nobody is building **evidence**.

EU AI Act Article 12 (effective August 2026) makes evidence-grade agent logging non-negotiable for high-risk AI systems. Forensa is the evidence layer that current control planes are missing.

## Demo moneyshot

Live, on stage: an AI event record is modified after the fact. Forensa's cryptographic chain verification fires within seconds. The tamper is provable. The evidence pack is regulator-ready.

## Sponsor technology

| Sponsor | Role in Forensa |
|---|---|
| **Veea Lobster Trap** | Verdict source — every policy decision feeds the evidence ledger |
| **Google Gemini 3 Pro** | Narrative generation, counterfactual analysis, regulator-pack synthesis |
| **Google Gemini 3 Flash** | Sub-second investigator query UX |
| **Google AI Studio** | Customer-authored evidence-pack templates per regulator |
| **AWS data pipeline** | S3 + EventBridge + Glue + Step Functions + OpenSearch backbone |
| **OpenTelemetry GenAI** | Wire-format compatibility for agent traces |
| **LangGraph** | Provenance graph for multi-agent workflows |
| **MCP** | Tool-call evidence capture; auditor portal as MCP service |
| **NVIDIA Omniverse** (stretch) | Physical-action replay when robots are in scope |

Sponsor utilisation: ~90% of v1 product value.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12 + FastAPI (asyncio + asyncpg) |
| Schemas / validation | Pydantic v2 |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 + Alembic |
| Search | OpenSearch |
| Event bus | (pluggable — Kafka or AWS EventBridge) |
| Cryptography | PyCA `cryptography` (Ed25519, SHA-256, RFC 3161) — FIPS-grade, audited |
| AI orchestration | LangGraph + Google AI Studio SDK |
| Frontend | Next.js 15 + React 19 + TypeScript + Tailwind |
| Auth | OIDC + SSO + role-based access |
| Deployment | Docker + Kubernetes; VPC / on-prem option |
| Observability | OpenTelemetry (including GenAI semconv) |

### Why Python-only at enterprise scale

The throughput target is **10K events/sec sustained, 100K peak** — typical for a mid-large regulated enterprise at the $2M+ ARR tier. At horizontal microservice scale:

| Deployment | Throughput |
|---|---:|
| Single Python pod (FastAPI + asyncpg) | ~5K req/s |
| 8 pods on m6i.xlarge | ~40K req/s |
| 8 pods with Postgres COPY batching + Kafka write-ahead | ~200K req/s |
| 32 pods (large enterprise) | ~800K req/s |

At Kubernetes scale, the bottleneck is the database / disk / network — not the language. Postgres `COPY` writes at 50K rows/sec regardless of caller language. Cost per event-handled is roughly the same in Python or Go.

Production references at this throughput in Python: Instagram, Pinterest, Reddit, OpenAI API gateway, Anthropic API. AI-evidence/observability comparables (LangSmith, Langfuse, Logfire, Agno, Pydantic AI, OpenAI Agents SDK) are all Python-first.

Single-language toolchain matters more than per-process throughput at this scale: one coverage chain (`pytest`), one lint stack (`ruff` + `mypy`), one dependency manager (`poetry`), one CI lane. For a 6-day enterprise-grade delivery, this is the right tradeoff.

If a single customer drives sustained throughput above 500K events/sec at year 2, the ledger hot-path becomes a small Go service behind FastAPI. By then there's revenue to fund the rewrite. Not a v1 problem.

## Repository layout

```
forensa/
├── README.md                       <- this file
├── LICENSE                         <- MIT
├── .gitignore
├── pyproject.toml                  <- Poetry / Python dependencies
├── package.json                    <- pnpm workspace root
├── pnpm-workspace.yaml
├── pnpm-lock.yaml
├── ops.ps1                         <- single dispatcher for dev ops (Windows)
├── alembic.ini
├── pytest.ini
├── docker-compose.yml
├── .github/workflows/ci.yml        <- pytest + vitest + Playwright, 100% coverage gates
├── apps/
│   ├── api/                        <- FastAPI backend (ingest, investigator, export)
│   └── console/                    <- Next.js investigator console
├── packages/
│   ├── crypto/                     <- Merkle chain + Ed25519 + RFC 3161 TSA
│   ├── schema/                     <- Pydantic v2 schemas (source of truth for events)
│   ├── ingest/                     <- OTel GenAI ingest pipeline
│   ├── ledger/                     <- append-only event store (hash-chain writer)
│   ├── policy/                     <- Lobster Trap verdict adapter + OPA bundle
│   └── export/                     <- Evidence pack builder (JSON-LD + PDF)
├── migrations/                     <- Alembic migrations
├── tests/                          <- pytest unit + integration + e2e
├── load-tests/                     <- Locust load tests proving 10K/100K throughput
├── policies/                       <- Rego policies for OPA
├── sbom/
├── deploy/                         <- docker-compose + K8s manifests
├── tools/
├── config/
├── docs/                           <- see docs/README.md for the 22-doc index
└── _backup/                        <- timestamped backups per CLAUDE_RULES
```

## Testing

100% line + branch coverage on:

- `pytest` — Python unit + integration + contract + property-based tests (`hypothesis`)
- `vitest` — TypeScript unit + component tests
- `Playwright` — full-browser e2e tests against live FastAPI + Next.js dev servers
- `Locust` (gated) — load tests proving 10K/sec sustained + 100K/sec peak

CI runs the three coverage-gated chains in parallel on every push and PR to `main`. A single failure blocks the merge. Load tests run on `workflow_dispatch` and weekly schedule (too slow for every-commit CI).

## License

MIT. See `LICENSE`.

The Forensa client SDK, receipt schema, and verification utility are open source. Commercial extensions (audit-firm portals, regulator-specific pack templates, multi-cloud deployment automation) are reserved.

## Contact

Project root: `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\`

For the resume-in-new-Claude-page workflow, see `session_prompts/AT-Hack0018_retro_start_prompt.md` in the parent project.
