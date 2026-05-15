# Forensa

[![CI](https://github.com/vsenthil7/forensa/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/vsenthil7/forensa/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Coverage 100%25](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](#testing)
[![Tests 921](https://img.shields.io/badge/tests-921%20passed-brightgreen.svg)](#testing)
[![BRs 10%2F13](https://img.shields.io/badge/BRs-10%2F13%20implemented-brightgreen.svg)](docs/02_brd/BRD.md)
[![License MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **The black box flight recorder for enterprise AI agents.**

Tamper-evident, multi-party-bound, policy-aware event ledger that produces legally admissible records of every AI agent action — for regulators, auditors, and litigation.

Built for the **Google TechEx Intelligent Enterprise Solutions Hackathon** (11–19 May 2026). Track 1 — Agent Security & AI Governance. Veea Award category.

---

## The wedge

Every incumbent in the AI runtime space — Microsoft AGT, Preloop, AWS Bedrock AgentCore, Veea Lobster Trap itself — is building **enforcement**. Nobody is building **evidence**.

EU AI Act Article 12 (effective August 2026) makes evidence-grade agent logging non-negotiable for high-risk AI systems. Forensa is the evidence layer that current control planes are missing.

## The demo, in one curl + one openssl

> An agent denies a policy violation today. Six months later a regulator asks: *prove the denial really happened on this day, on this chain, with this policy version.*

```bash
# 1. Fetch the evidence pack (JSON-LD form)
curl -H "Authorization: Bearer $TOKEN" \
     "$FORENSA/v1/evidence-packs?tenant_id=$T&scope_start=$START&scope_end=$END"

# 2. Pipe the day's RFC 3161 TSR straight to openssl
curl -H "Authorization: Bearer $TOKEN" \
     -H "Accept: application/timestamp-reply" \
     "$FORENSA/v1/anchors/$ANCHOR_ID" \
  | openssl ts -verify -in /dev/stdin -CAfile $TSA_CA -data <(echo -n $ROOT_HASH)
```

The math agrees. Without Forensa, that proof chain doesn't exist. With Forensa, it's literally one `curl` + one `openssl`.

---

## Status at submission

**Phase 9 closed + Phase 9-stretch landed.** HEAD: `53c3207` on `main`. 4 days before TechEx submission (Monday 19 May 2026).

| Metric | Value |
|---|---:|
| BR scoreboard | **10 / 13 IMPLEMENTED+TESTED** (2 DEFERRED, 1 PARTIAL with named CP12.4 destination) |
| Default-mode tests | **921 passed**, 100% line + branch coverage gate held |
| PG-mode integration tests | **947 total** (921 default + 26 PG-only) |
| Lint / format / types | `ruff check` + `ruff format --check` + `mypy --strict` on 56 source files: all clean |
| Security scan | `bandit` + `pip-audit`: clean |
| CPs landed in Phase 9 + stretch | **28 across 39 commits**; full audit trail in `phases/PHASES_DONE_PHASE9_*.md` |

### BR scoreboard

| BR | Description | Status |
|---|---|---|
| BR-01 | Cryptographic hash chain on every Receipt | ✅ IMPLEMENTED+TESTED |
| BR-02 | Multi-party identity binding (tenant + agent dual signature) | ✅ IMPLEMENTED+TESTED |
| BR-03 | Per-tenant signing keys | ✅ IMPLEMENTED+TESTED |
| BR-04 | Ingest-time policy binding via PolicySnapshot | ✅ IMPLEMENTED+TESTED |
| BR-05 | Regulator-grade evidence pack (JSON-LD + PDF) | ✅ IMPLEMENTED+TESTED |
| BR-06 | Merkle-chained ledger with RFC 3161 TSA daily anchoring | ✅ IMPLEMENTED+TESTED |
| BR-07 | LangGraph multi-agent provenance | ⏸ DEFERRED out-of-hackathon |
| BR-08 | Omniverse physical-action replay | ⏸ DEFERRED out-of-hackathon |
| BR-09 | 10K events/sec sustained, 100K peak (Kafka path) | 🟡 PARTIAL → CP12.4 |
| BR-10 | Gemini 2.5 Pro narrative generation | ✅ IMPLEMENTED+TESTED |
| BR-11 | Counterfactual narrative with 4-layer prompt-injection defence | ✅ IMPLEMENTED+TESTED |
| BR-12 | Tabletop incident response mode | ✅ IMPLEMENTED+TESTED (CP9.29) |
| BR-13 | M&A due diligence export | ✅ IMPLEMENTED+TESTED (CP9.28) |

Full BRD with Status column at `docs/02_brd/BRD.md`.

---

## What you can do with the running service

8 fully-wired REST endpoints, all authenticated, all tenant-scoped:

| Method + path | What it does | Wire forms |
|---|---|---|
| `POST /v1/events` | Ingest an agent event; full pipeline → policy bundle resolve → enforcement → snapshot → Ed25519-signed Receipt → atomic write. Idempotency-Key honoured. | `application/json` |
| `GET  /v1/receipts` | List Receipts for tenant; cursor pagination; `signed_after`/`signed_before` window. | `application/json` |
| `GET  /v1/receipts/{id}` | Detail with live `integrity_ok` recompute (tamper-detection on every read). | `application/json` |
| `GET  /v1/evidence-packs` | Compose an evidence pack with PROV-O lineage. The latest TSA anchor in the window is **embedded inline** so the pack is offline-verifiable. | `application/json` (JSON-LD) **or** `application/pdf` |
| `POST /v1/narratives` | Generate a regulator-grade prose narrative via Gemini 2.5 Pro. 4-layer prompt-injection defence; 422 + `incident_id` if defence fires. | `application/json` |
| `GET  /v1/anchors` | List TSA anchor rows; window filter; DESC by `anchor_date`. | `application/json` |
| `GET  /v1/anchors/{id}` | Anchor detail with full TSR. Default wire form is JSON; `Accept: application/timestamp-reply` returns **raw RFC 3161 DER bytes** for direct `openssl ts -verify` piping. | `application/json` **or** `application/timestamp-reply` |
| `GET  /healthz` | Liveness + which narrative client is wired (live Gemini vs mock). | `application/json` |

OpenAPI schema is auto-generated by FastAPI at `/docs` and `/openapi.json`.

---

## Architectural highlights

- **3-anchor verifiability chain.** Every evidence pack binds `(pack_root_hash, prompt_hash, content_hash)` so a regulator can independently verify (a) the pack hasn't been tampered with, (b) the prompt used was deterministic from the pack, and (c) the narrative content hasn't been tampered with after generation.
- **Vendor-neutral `PolicyEnforcementClient` ABC.** Veea Lobster Trap is one provider via `VeeaLobsterTrapClient`; Microsoft AGT / AWS Bedrock AgentCore / custom enforcement can drop in as ABC subclasses. No vendor lock-in at the API surface.
- **Append-only-by-shape AND append-only-by-database-trigger.** App-layer code never issues `UPDATE`/`DELETE` on `receipts` or `events`. PG-level triggers enforce the same guarantee at the privilege layer (verified by 26 PG-mode integration tests). Defence in depth.
- **Deferred-tombstone anchor rows.** A failed TSA call doesn't make the day un-anchored; it creates a `status='deferred'` row that records "we tried, here's when, here's why". Auditable failure, not silent failure.
- **Two wire forms for evidence packs via content negotiation.** JSON-LD by default. PDF when `Accept: application/pdf` (deterministic A4, pinned `/CreationDate`+`/ModDate` for byte-identical re-renders). Both share `root_hash` so they cross-check.
- **Raw DER pipe via `Accept: application/timestamp-reply`.** Regulators with `curl ... | openssl ts -verify` workflows get a clean one-liner; no intermediate base64 step.

---

## Sponsor technology utilisation

| Sponsor | Role in Forensa | Surface |
|---|---|---|
| **Veea Lobster Trap** | Policy enforcement verdict source — every decision feeds the evidence ledger | `packages/policy/lobstertrap.py` + `VeeaLobsterTrapClient` |
| **Google Gemini 2.5 Pro** | Narrative generation with 4-layer prompt-injection defence | `packages/narrative/live_client.py` (`google.genai` SDK) |
| **Google AI Studio** | Live API path for hackathon submission | `apps/api/narrative_selector.py` |
| **RFC 3161 TSA** | Daily timestamp anchoring of chain root | `packages/crypto/tsa.py` + `packages/ledger/tsa_anchor.py` |
| **OpenTelemetry GenAI** | Wire-format compatibility for agent traces | `packages/ingest/normaliser.py` |
| **PostgreSQL 16** | Multi-tenant tamper-evident store with RLS-ready models | `packages/ledger/models.py` + alembic |
| **OpenAI / Anthropic / Vertex** | Multi-LLM selector pattern (Vertex path tracked for production) | `apps/api/narrative_selector.py` |

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12 + FastAPI (async + asyncpg) |
| Schemas / validation | Pydantic v2 (frozen, `extra="forbid"`) |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 + Alembic |
| Cryptography | PyCA `cryptography` (Ed25519, SHA-256), RFC 3161 TSA client (audited, FIPS-grade) |
| AI / LLM | Google Gemini 2.5 Pro via `google.genai` SDK; `ThinkingConfig(thinking_budget=0)` for fast deterministic completions |
| Frontend (console) | Next.js 15 + React 19 + TypeScript + Tailwind |
| Auth | OIDC + JWT (Auth0/Okta-ready; real provider integration → CP10.1) |
| PDF rendering | `reportlab` with deterministic timestamp pinning |
| Deployment | Docker + Kubernetes; VPC / on-prem option |
| Observability | OpenTelemetry (including GenAI semconv) |
| Testing | `pytest` + `hypothesis` + `vitest` + `Playwright` + `Locust` |

### Why Python-only at enterprise scale

The throughput target is 10K events/sec sustained, 100K peak — typical for a mid-large regulated enterprise at the $2M+ ARR tier.

| Deployment | Throughput |
|---|---:|
| Single Python pod (FastAPI + asyncpg) | ~5K req/s |
| 8 pods on m6i.xlarge | ~40K req/s |
| 8 pods + Postgres `COPY` batching + Kafka write-ahead | ~200K req/s |
| 32 pods (large enterprise tier) | ~800K req/s |

At Kubernetes scale, the bottleneck is database / disk / network — not the language. Postgres `COPY` writes at 50K rows/sec regardless of caller language. Production references in Python at this throughput: Instagram, Pinterest, Reddit, OpenAI API gateway, Anthropic API. AI-evidence/observability comparables (LangSmith, Langfuse, Logfire, Pydantic AI, OpenAI Agents SDK) are all Python-first.

A single-language toolchain (one coverage chain, one lint stack, one dependency manager, one CI lane) matters more than per-process throughput at this scale. If a single customer drives sustained throughput above 500K events/sec at year 2, the ledger hot-path becomes a small Go service behind FastAPI. By then there's revenue to fund the rewrite. Not a v1 problem. BR-09 → CP12.4 (Kafka ingest queue) is the next step.

---

## Quick start

### Prerequisites
- Python 3.12
- Poetry
- Docker (for PostgreSQL 16 + integration tests)
- A Google AI Studio API key (free tier) for the live narrative path

### Setup

```powershell
# Clone
git clone https://github.com/vsenthil7/forensa.git
cd forensa

# Install
poetry install

# Configure
Copy-Item .env.example .env
# Edit .env: set FORENSA_GEMINI_API_KEY, FORENSA_DB_URL, etc.

# Bring up Postgres
docker compose up -d forensa-pg

# Run migrations
poetry run alembic upgrade head

# Default-mode tests (no DB; 921 tests, 100% coverage gate)
poetry run pytest -q

# PG-mode integration tests (947 total; needs FORENSA_TEST_DB_URL)
$env:FORENSA_TEST_DB_URL = 'postgresql+asyncpg://forensa:forensa@localhost:5433/forensa'
poetry run pytest -q --no-cov

# Seed demo data (CP9.30) and grab env vars for tools/demo.sh
poetry run python scripts/seed_demo_data.py

# Run the API
poetry run forensa-api
# → http://localhost:8000/docs
```

### Environment variables

`.env.example` at repo root documents the full set. Highlights:

| Variable | Purpose | Required? |
|---|---|---|
| `FORENSA_DB_URL` | Async Postgres URL | Yes (for ingest + persistence) |
| `FORENSA_GEMINI_API_KEY` | Live Gemini path; unset = mock narrative client | No (mock fallback) |
| `FORENSA_GEMINI_MODEL_ID` | Default `gemini-2.5-pro` | No |
| `FORENSA_TSA_URL` | RFC 3161 TSA endpoint | No (defaults to FreeTSA) |
| `FORENSA_AUTH_PROVIDER` | OIDC issuer (CP10.1+) | No (stub principal in dev) |

**Hard rules:** `.env` is gitignored; `.env.example` is committed; never paste real keys into chat, tracked files, or CI logs. Real keys live in `.env` (local), GitHub Actions Secrets (CI), or KMS / Vault (production).

---

## Repository layout

```
forensa/
├── README.md                       ← this file
├── LICENSE                         ← MIT
├── pyproject.toml                  ← Poetry / Python deps
├── docker-compose.yml              ← Postgres 16 for local dev
├── alembic.ini                     ← migration config
├── .env.example                    ← documented env-var schema
├── .github/workflows/ci.yml        ← pytest + 100% coverage gate
│
├── apps/
│   ├── api/                        ← FastAPI backend (8 endpoints; see above)
│   │   ├── main.py                 ← factory + lifespan + healthz
│   │   ├── auth/                   ← Principal + TokenVerifier + Depends
│   │   ├── routes/                 ← events, receipts, evidence, narratives, anchors
│   │   ├── ingest_service.py       ← bundle provider + signing key + enforcement bridge
│   │   └── narrative_selector.py   ← live Gemini selector
│   └── console/                    ← Next.js investigator console
│
├── packages/
│   ├── crypto/                     ← hash + merkle (chain) + sign (Ed25519) + tsa (RFC 3161)
│   ├── schema/                     ← Pydantic v2 frozen models (Event, Receipt, Tenant, Agent, PolicyBundle)
│   ├── ingest/                     ← OTel GenAI normaliser
│   ├── ledger/                     ← models + receipt_builder + bundle_repository + bundle_workflow + tsa_anchor + repositories + session
│   ├── policy/                     ← enforcement (canonical ABC) + lobstertrap (legacy alias) + snapshot + bundle_builder + replay
│   ├── export/                     ← schema (AnchorEvidence + EvidencePack) + builder + pdf_renderer
│   └── narrative/                  ← client (mock) + live_client (Gemini) + prompt (3-anchor bind)
│
├── alembic/                        ← migrations (8 heads)
├── tests/                          ← 921 default + 26 PG-only = 947 total
│   ├── packages/                   ← unit tests
│   ├── api/                        ← endpoint tests (mocked sessions)
│   └── integration/                ← PG-only tests (triggers, RLS-ready)
├── load-tests/                     ← Locust (BR-09 throughput target)
├── policies/                       ← Rego policies for OPA
├── docs/                           ← 22-doc enterprise governance pack; see docs/README.md
├── phases/                         ← phase/CP history + status docs + close-out
│   ├── PHASES_DONE_PHASE9_*.md     ← submission-package summary
│   ├── PHASES_REVIEW_BEFORE_AFTER_* ← session-by-session scoreboard
│   ├── NEXT_SESSION_PROMPT_*.md    ← session-resume starter prompts
│   ├── ROADMAP_PHASE9_AND_ENTERPRISE_*.md  ← Phase 10–13 roadmap
│   └── context_log/                ← per-prompt audit trail (Rule 7)
└── _backup/                        ← timestamped backups before every edit (Rule 6)
```

---

## Governance docs (22-doc enterprise pack)

The `docs/` tree is the artefact a procurement / GRC officer would receive. Each doc has a single owner and a known location. Highlights:

| Doc | Purpose |
|---|---|
| `00_executive_brief/EXEC_BRIEF.md` | One-page pitch |
| `01_vision/VISION.md` | Long-form positioning |
| `02_brd/BRD.md` | 13 BRs with **IMPLEMENTED+TESTED / PARTIAL / STUB / DEFERRED** status column |
| `03_competitive/COMPETITIVE.md` | Microsoft AGT, Preloop, AWS Bedrock AgentCore comparison |
| `06_regulatory_mapping/REG_MAPPING.md` | EU AI Act Article 12, DORA, SEC Cyber, GDPR mappings |
| `07_system_architecture/SYSTEM_ARCHITECTURE.md` | Component diagram + data flows |
| `08_api_spec/API_SPEC.md` | All 8 endpoints with request/response schemas |
| `09_data_model/DATA_MODEL.md` | 7 core tables + indexes + constraints |
| `10_security_architecture/SECURITY_ARCHITECTURE.md` | Auth + crypto + secrets |
| `11_threat_model/THREAT_MODEL.md` | 15 STRIDE threats with mitigations + residual risk |
| `12_evidence_pack_spec/EVIDENCE_PACK_SPEC.md` | JSON-LD wire-form spec for offline verifiers |
| `17_traceability/TRACEABILITY.md` | BR ↔ code ↔ test ↔ commit mapping |
| `19_incident_response/IR_PLAN.md` | Detection → triage → recovery playbook |
| `22_sbom/SBOM.md` | Software bill of materials |

See `docs/README.md` for the full 22-doc index.

---

## Testing

100% line + branch coverage on every commit. CI runs three coverage-gated test chains in parallel; a single failure blocks merge to `main`.

- **`pytest`** — 921 unit + integration + property-based tests (`hypothesis`). Coverage gate `--cov-fail-under=100`.
- **`pytest` (PG-mode)** — 26 additional PG-only integration tests proving DB triggers, partial unique indexes, alembic migration runners. Coverage skipped (`--no-cov`) since PG-mode coverage targets differ.
- **`vitest`** — TypeScript unit + component tests for the console.
- **`Playwright`** — full-browser e2e tests against live FastAPI + Next.js dev servers.
- **`Locust`** (gated; weekly) — load tests proving BR-09 throughput targets.

All four chains green at HEAD `53c3207`.

---

## Architecture decisions worth knowing about

These were judgement calls; each has a one-paragraph rationale in the commit history.

| Decision | Where |
|---|---|
| Hash chain vs Merkle tree | `packages/crypto/merkle.py` docstring; tree upgrade tracked as `NEW-P11.X.merkle-tree` for O(log N) inclusion proofs |
| Empty-string sentinels for `None` in canonical JSON binding | `packages/crypto/hash.py` + `packages/export/builder.py:_canonicalise_anchor` |
| Anchored vs deferred-tombstone TSA rows | `packages/ledger/tsa_anchor.py` |
| Bind `anchor` into `root_hash` of evidence pack | `packages/export/builder.py` + 5 regression tests in `test_anchor_in_evidence_pack.py` |
| 403 distinguishable from 404 (anchor detail endpoint) | `apps/api/routes/anchors.py:get_anchor_detail` + commit msg `67b6bca` |
| Pin PDF `/CreationDate`+`/ModDate` for byte-deterministic output | `packages/export/pdf_renderer.py:_pin_pdf_timestamps` |
| Vendor-neutral `PolicyEnforcementClient` ABC | `packages/policy/enforcement.py` + legacy `LobsterTrapClient` alias for backwards compat |
| Disable Gemini 2.5 `ThinkingConfig` for narrative completions | `packages/narrative/live_client.py:_default_generate_call` |

---

## Roadmap (Phase 10–13, post-submission)

Full plan at `phases/ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md`. Top 5 items for the first Q3 design partner:

1. **CP10.1** — Real auth provider integration (Auth0/Okta); replaces today's stub `Principal` verifier
2. **CP10.2** — KMS adapter for tenant signing keys (AWS KMS / GCP KMS / HashiCorp Vault); replaces today's in-process bytes
3. **CP10.3** — PostgreSQL Row-Level Security policies on every tenant-scoped table; defence in depth beyond app-layer
4. **CP11.6** — Detached platform signature on JSON-LD + PDF evidence packs (auditor proves "this came from Forensa")
5. **CP12.4** — Kafka ingest queue + async COPY-batched writer (BR-09 throughput)

Total Phase 10–13 estimate: ~52 team-weeks for 2 engineers; +8,670 production LOC, +12,540 test LOC, +483 tests.

### Remaining DEFERRED business requirements

| BR | Why deferred | Destination |
|---|---|---|
| BR-07 LangGraph multi-agent provenance | LangGraph + multi-agent DAG capture is multi-day; not hackathon-window | Phase 12 |
| BR-08 Omniverse physical-action replay | NVIDIA Isaac Sim integration is multi-day | Phase 11 |
| BR-09 PARTIAL — Kafka throughput | In-process throughput shipped + measured; Kafka ingest path is multi-week | CP12.4 |

---

## License

MIT. See `LICENSE`.

The Forensa client SDK, Receipt schema, and verification utility (offline JSON-LD verifier + openssl-ts-verify pipe) are open source. Commercial extensions (audit-firm portals, regulator-specific pack templates, multi-cloud deployment automation, BR-07/08/12/13 implementations) are reserved.

---

## Contact

Repo: https://github.com/vsenthil7/forensa
Hackathon submission: Monday 19 May 2026 — Google TechEx Intelligent Enterprise Solutions, Track 1, Veea Award category.
