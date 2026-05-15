# Forensa — Judge Handout

**Track 1 — Agent Security & AI Governance · Veea Award · Submission Mon 19 May 2026**

---

## What it is, in one sentence

**The black box flight recorder for enterprise AI agents** — a tamper-evident, multi-party-bound, policy-aware event ledger producing legally admissible records of every agent action, for regulators, auditors, and litigation.

## The wedge

Every incumbent in the AI runtime space — Microsoft AGT, Preloop, AWS Bedrock AgentCore, Veea Lobster Trap itself — is building **enforcement**. Nobody is building **evidence**.

**EU AI Act Article 12 (Aug 2026) makes evidence-grade agent logging non-negotiable.** Forensa is the layer current control planes are missing.

## The demo, in one curl + one openssl

> An agent denies a policy violation today. Six months later a regulator asks: *prove the denial really happened on this day, on this chain, with this policy version.*

```bash
# 1. Pull the evidence pack with embedded RFC 3161 TSA proof
curl -H "Authorization: Bearer $TOKEN" \
     "$FORENSA/v1/evidence-packs?tenant_id=$T&scope_start=$START&scope_end=$END"

# 2. Pull the raw TSR DER bytes and pipe directly to openssl
curl -H "Accept: application/timestamp-reply" \
     "$FORENSA/v1/anchors/$ANCHOR_ID" \
  | openssl ts -verify -in /dev/stdin -CAfile $TSA_CA -data <(echo -n $ROOT_HASH)
```

The math agrees. Without Forensa, that proof chain doesn't exist.

## What's shipped (status at submission)

| Metric | Value |
|---|---:|
| **Business requirements IMPLEMENTED+TESTED** | **9 / 13** |
| Default-mode test suite | **878 passed**, 100% line + branch coverage gate |
| PG-mode integration suite | **904 passed** (878 default + 26 PG-only) |
| Code review status | `ruff` + `ruff format` + `mypy --strict` + `bandit` + `pip-audit`: clean |
| Phase 9 CPs | **25 across 36 commits** in 46 hours |
| HEAD at submission | `9075602` on `origin/main` |

### BR scoreboard

✅ **9 IMPLEMENTED+TESTED:** Cryptographic chain · Dual signature (tenant+agent) · Per-tenant signing keys · Ingest-time policy binding · Regulator-grade evidence pack (JSON-LD + PDF) · RFC 3161 TSA daily anchoring · Gemini 2.5 Pro narrative · 4-layer prompt-injection defence

⏸ **4 DEFERRED out-of-hackathon** by design: LangGraph multi-agent · Omniverse physical replay · Tabletop incident response · M&A export

🟡 **0 PARTIAL outside roadmap** (BR-09 throughput → CP12.4 Kafka path, named in Phase 10–13 plan)

## 8 fully-wired REST endpoints

| Endpoint | What it does | Wire forms |
|---|---|---|
| `POST /v1/events` | Ingest event → enforce → snapshot → Ed25519 Receipt → atomic write. Idempotency-Key. | JSON |
| `GET /v1/receipts` | Cursor pagination · `signed_after`/`signed_before` window | JSON |
| `GET /v1/receipts/{id}` | Detail with **live tamper-detection** on every read | JSON |
| `GET /v1/evidence-packs` | PROV-O lineage pack with **embedded TSA proof** (offline-verifiable) | JSON-LD **or** PDF |
| `POST /v1/narratives` | Gemini 2.5 Pro narrative · 4-layer defence · `incident_id` if defence fires | JSON |
| `GET /v1/anchors` | List TSA anchor rows · window filter · DESC by `anchor_date` | JSON |
| `GET /v1/anchors/{id}` | Anchor detail · **raw DER pipe** for `openssl ts -verify` | JSON **or** `application/timestamp-reply` |
| `GET /healthz` | Liveness + which narrative client is wired | JSON |

## Architectural highlights

- **3-anchor verifiability chain.** Every evidence pack binds `(pack_root_hash, prompt_hash, content_hash)` — three independent verification anchors a regulator can check.
- **Vendor-neutral `PolicyEnforcementClient` ABC.** Veea Lobster Trap is one provider via `VeeaLobsterTrapClient`. Microsoft AGT, AWS Bedrock AgentCore, custom enforcement: all drop in as subclasses. No lock-in.
- **Append-only by code AND by database trigger.** App layer never issues `UPDATE`/`DELETE` on `receipts` or `events`. PG triggers enforce the same at the privilege layer. Defence in depth. Verified by 26 PG-mode integration tests.
- **Deferred-tombstone anchor rows.** Failed TSA calls don't make a day un-anchored — they create a `status='deferred'` row recording "we tried, here's when, here's why". Auditable failure, not silent failure.
- **Two evidence-pack wire forms via content negotiation.** JSON-LD by default. PDF when `Accept: application/pdf` (deterministic A4 with pinned timestamps; byte-identical re-renders). Same `root_hash` cross-checks both.
- **Raw RFC 3161 DER pipe via `Accept: application/timestamp-reply`.** Regulators with `curl … | openssl ts -verify` workflows get a clean one-liner. No base64 step.

## Sponsor utilisation

| Sponsor | Role in Forensa |
|---|---|
| **Veea Lobster Trap** | Policy enforcement verdict source; every decision feeds the evidence ledger |
| **Google Gemini 2.5 Pro** | Narrative generation with 4-layer prompt-injection defence |
| **Google AI Studio** | Live API path for hackathon submission |
| **RFC 3161 TSA** | Daily timestamp anchoring of chain root |
| **OpenTelemetry GenAI** | Wire-format compatibility for agent traces |
| **PostgreSQL 16** | Multi-tenant tamper-evident store with RLS-ready models |

## Award alignment

| Category | Why Forensa fits |
|---|---|
| **Veea Award (Track 1)** | Forensa is the evidence layer downstream of Lobster Trap. The enforcement vendor's verdicts become the source records in Forensa's ledger. Direct integration; vendor-neutral ABC means Veea is one of N providers, not the only one. |
| **Gemini Award** | Live Gemini 2.5 Pro narrative generation with a non-trivial product surface: 4-layer prompt-injection defence + `ThinkingConfig(thinking_budget=0)` for deterministic completions + 3-anchor verifiability binding. Not a hello-world LLM demo. |
| **Best Use of NVIDIA** (if applicable) | Physical-action replay (BR-08) tracked as out-of-hackathon scope. Omniverse integration is in the Phase 10–13 roadmap. |

## What's next (Phase 10–13)

| Priority | Item | Sprint |
|---|---|---|
| 1 | CP10.1 — Real auth provider (Auth0/Okta) replacing stub `Principal` | Q3 2026 |
| 2 | CP10.2 — KMS adapter for tenant signing keys (AWS KMS / GCP KMS / Vault) | Q3 2026 |
| 3 | CP10.3 — PostgreSQL Row-Level Security on every tenant-scoped table | Q3 2026 |
| 4 | CP11.6 — Detached platform signature on JSON-LD + PDF (auditor verifies origin) | Q4 2026 |
| 5 | CP12.4 — Kafka ingest queue + async COPY-batched writer (BR-09 throughput) | Q4 2026 |

Total Phase 10–13: ~52 team-weeks for 2 engineers; +8,670 production LOC, +12,540 test LOC, +483 tests.

---

**Repo:** `github.com/vsenthil7/forensa`
**Submission:** Monday 19 May 2026 · Google TechEx Intelligent Enterprise Solutions
**Contact:** in repo `README.md`
