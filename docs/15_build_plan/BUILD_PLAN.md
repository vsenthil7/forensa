# Forensa - Build Plan (6-day hackathon)

**Doc:** 15 of 22 | **Source:** Section A.9, D.3 of master doc | **Submission:** Mon 19 May 2026

## Day-by-day plan

### Day 1 (Tue 13 May) - OTel GenAI ingest
- Repo scaffold (apps/api, packages/*, deploy/, tests/)
- FastAPI service with OTLP gRPC + HTTP/protobuf endpoints
- Pydantic v2 Receipt + Event schemas
- PostgreSQL schema + Alembic migrations
- Single-event endpoint + batch endpoint working
- BR-01, BR-09 partial coverage
- pytest: 100% on packages/schema + ingest happy path
- Push status: should hit ~30 commits by EoD

### Day 2 (Wed 14 May) - Cryptographic chain + Lobster Trap **CHECKPOINT**
- packages/crypto: Ed25519 sign/verify, SHA-256, Merkle tree builder
- packages/ledger: append-only writer, chain verifier
- Daily RFC 3161 TSA anchor stub (mocked TSA for hackathon; real-TSA path documented)
- Lobster Trap verdict adapter in packages/policy
- Policy snapshot binding (BR-04)
- BR-02, BR-04, BR-06 covered
- pytest + hypothesis: 100% on crypto + ledger; property-based on chain integrity
- **Wed 14 May checkpoint: ingest -> chain -> verdict working end-to-end. If slipped: switch to AegisOne fallback.**

### Day 3 (Thu 15 May) - Investigator console + Gemini Flash
- apps/console: Next.js 15 + React 19 + TS + Tailwind scaffold
- Investigation Console screen (BR-10)
- Incident Replay screen
- Evidence Receipt Viewer screen
- Gemini Flash query integration
- LangGraph multi-agent provenance graph (BR-07)
- BR-07, BR-10 covered
- vitest + Playwright: 100% on console; e2e on query roundtrip

### Day 4 (Fri 16 May) - Evidence pack export + Gemini Pro narrative
- packages/export: JSON-LD + PROV-O builder, PDF generator with signatures
- Evidence pack templates (eu-ai-act-art12 priority; nist + iso42001 stubs)
- Gemini Pro narrative generation (BR-11)
- Policy Correlation Panel screen
- Export Center screen
- BR-05, BR-11 covered
- Integration tests: full pack generation + verification

### Day 5 (Sat 17 May) - Demo polish + tabletop + tamper detection
- Tamper detection demo: edit a Receipt, chain verification fires, evidence pack rebuild fails
- Tabletop scenario builder (BR-12)
- Admin & Retention Console screen
- M&A inventory export (BR-13)
- Sponsor utilisation polish: each sponsor logo + role visible in demo flow
- forensa-verify utility (open-source verifier for evidence packs)
- BR-12, BR-13 covered
- e2e Playwright: tamper detection scenario
- Stretch: Omniverse physical-action replay (BR-08) if time permits

### Day 6 (Sun 18 May) - Documentation + video + submission package
- Slide deck (10 slides, EU AI Act anchor)
- 7-minute demo video (UK mortgage lender journey)
- Submission form completion
- Final commit push + tag v0.1.0
- TechEx portal submission

### Submission day (Mon 19 May)
- Final review at 09:00
- TechEx submission deadline (varies by TZ - confirm by Sun)
- Backup video upload to YouTube unlisted
- Public GitHub repo final check

## Pivot triggers

### Wed 14 May checkpoint
If ingest -> chain -> Lobster Trap verdict not working end-to-end by EoD Wed:
- **Switch to AegisOne fallback** (BRD already drafted in assessment/05_* and assessment/10_*)
- AegisOne is the simpler Pre-Mortem Bench product
- Same submission deadline, different architecture

### Fri 16 May go/no-go on stretch goals
If by EoD Fri the BR-08 (Omniverse) integration not started:
- Drop BR-08 from demo
- Mention as v1.1 roadmap in slide deck
- Focus polish on tamper detection demo

## Coverage gates (CI)

Every push to main runs:
- pytest --cov=packages,apps/api --cov-fail-under=100
- vitest --coverage --coverageThreshold=100
- Playwright e2e on live FastAPI + Next.js dev servers

Single test failure blocks merge. Load tests (Locust, BR-09 proof) on workflow_dispatch and weekly schedule.

## Sponsor utilisation checklist

Each sponsor tech must be visible in at least one screen / commit / demo segment:
- [x] Veea Lobster Trap - verdict feed (Day 2)
- [x] Gemini 3 Pro - narrative + counterfactual (Day 4)
- [x] Gemini 3 Flash - investigator query (Day 3)
- [x] Google AI Studio - regulator pack template authoring (Day 5)
- [x] AWS data pipeline - S3 + EventBridge + Glue + Step Functions + OpenSearch (Day 1 + 2)
- [x] LangGraph - multi-agent provenance (Day 3)
- [x] MCP - auditor portal (Day 5)
- [x] OpenTelemetry GenAI - ingest wire format (Day 1)
- [ ] NVIDIA Omniverse + Isaac Sim - physical replay (Day 5 stretch)
- [ ] NVIDIA GR00T VLA - VLA evaluation evidence (mention only)
- [ ] DT Consortium / XMPro - twin semantics (mention only)

Target: 90% v1 product value on sponsor primitives (see doc 00).

## Risk register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Day 2 checkpoint slip | Medium | High | AegisOne pivot |
| Gemini API quota | Low | Medium | Cache + fallback to Sonnet 4.6 |
| RFC 3161 TSA latency | Low | Medium | Mocked TSA for demo |
| Playwright flakes | Medium | Low | Retry budget; quarantine flakes |
| Single-developer fatigue | High | High | Sleep schedule; do not skip Day 6 polish |

