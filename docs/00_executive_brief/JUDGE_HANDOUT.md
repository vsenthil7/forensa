# Forensa — Judge Handout

**Track 1 — Agent Security & AI Governance · Veea Award · Submission Mon 19 May 2026**
**Refreshed at:** 18 May 2026 against HEAD CP9.51 `d7d9aaa`
**Supersedes:** `_archive/JUDGE_HANDOUT_v1_20260512.md`

---

## What it is, in one sentence

**The black box flight recorder for enterprise AI agents** — a tamper-evident, multi-party-bound, policy-aware event ledger producing legally admissible records of every agent action, for regulators, auditors, and litigation.

## The wedge

Every incumbent in the AI runtime space — Microsoft AGT, Preloop, AWS Bedrock AgentCore, Veea Lobster Trap itself — is building **enforcement**. Nobody is building **evidence**.

**EU AI Act Article 12 (binding Aug 2026) makes evidence-grade agent logging non-negotiable. DORA Article 30 (binding since Jan 2025) makes tabletop evidence non-negotiable.** Forensa is the layer current control planes are missing.

## The demo, in one curl + one openssl

> An agent denies a policy violation today. Six months later a regulator asks: *prove the denial really happened on this day, on this chain, with this policy version, signed by a Time-Stamping Authority whose certificate chain we can independently verify.*

```bash
# 1. Pull the evidence pack with embedded RFC 3161 TSA proof
curl -H "Authorization: Bearer $TOKEN" \
     "$FORENSA/v1/evidence-packs?tenant_id=$T&scope_start=$START&scope_end=$END"

# 2. Pull the raw TSR DER bytes and pipe directly to openssl
curl -H "Accept: application/timestamp-reply" \
     "$FORENSA/v1/anchors/$ANCHOR_ID" \
  | openssl ts -verify -in /dev/stdin -CAfile $TSA_CA -data <(echo -n $ROOT_HASH)
```

The math agrees. Without Forensa, that proof chain doesn't exist. **New in CP9.51:** Forensa now performs full PKIX certificate-chain verification of the TSR against FreeTSA's published cert chain server-side too, so a forged TSR is rejected at ingest of evidence, not only at the regulator's `openssl` later.

## What's shipped (status at submission)

| Metric | Value |
|---|---:|
| **Business requirements IMPLEMENTED+TESTED (BR-01..BR-13)** | **10 / 13** |
| Plus: **BR-14 Operator Console (Web + PWA)** | `PARTIAL` (3 screens shipped; enterprise list-views the CP9.52 work) |
| Default-mode test suite | **914+ passed**, 100% line + branch coverage gate |
| Code review status | `ruff` + `ruff format` + `mypy --strict` + `bandit` + `pip-audit`: clean |
| Phase 9 CPs to date | **51 patches across Phase 9** (CP9.1 → CP9.51) |
| HEAD at submission | `d7d9aaa` on `origin/main` |
| Anchor verification | FreeTSA live RFC 3161 + full PKIX cert-chain verification (CP9.51) |

### BR scoreboard

✅ **10 IMPLEMENTED+TESTED:** Cryptographic chain · Dual signature (tenant+agent) · Per-tenant signing keys · Ingest-time policy binding · Regulator-grade evidence pack (JSON-LD + PDF) · RFC 3161 TSA daily anchoring **+ cert-chain verification (CP9.51)** · Gemini 2.5 Pro narrative · 4-layer prompt-injection defence · **Tabletop simulation (BR-12, CP9.29)** · **M&A diligence export with `ma_root_hash` (BR-13, CP9.28)**

🟡 **1 PARTIAL on roadmap:** BR-09 throughput — in-process 6452 events/sec proven (387× under 60s budget); AWS Kafka topology DEFERRED Phase 12 CP12.3/CP12.4

⏸ **2 DEFERRED out-of-hackathon by design:** LangGraph multi-agent (BR-07, Phase 12) · Omniverse physical replay (BR-08, Phase 13)

🆕 **BR-14 Operator Console (Web + PWA) introduced as first-class tracked surface in v2 doc elaboration** — see [Operator Console](#operator-console-web--pwa-native-deferred) below.

## 11+ fully-wired REST endpoints

| Endpoint | What it does | Wire forms |
|---|---|---|
| `POST /v1/events` | Ingest event → enforce → snapshot → Ed25519 Receipt → atomic write. Idempotency-Key. | JSON |
| `GET /v1/receipts` | Cursor pagination · `signed_after`/`signed_before` window | JSON |
| `GET /v1/receipts/{id}` | Detail with **live tamper-detection** on every read | JSON |
| `GET /v1/evidence-packs` | PROV-O lineage pack with **embedded TSA proof** (offline-verifiable) | JSON-LD **or** PDF |
| `POST /v1/narratives` | Gemini 2.5 Pro narrative · 4-layer defence · `incident_id` if defence fires | JSON |
| `GET /v1/anchors` | List TSA anchor rows · window filter · DESC by `anchor_date` | JSON |
| `GET /v1/anchors/{id}` | Anchor detail · **raw DER pipe** for `openssl ts -verify` | JSON **or** `application/timestamp-reply` |
| `POST /v1/tabletop/simulate` | DORA Art-30 tabletop drill · no chain mutation · returns scenario verdicts | JSON |
| `POST /v1/tabletop/replay-window` | Replay historical window against candidate bundle · read-only | JSON |
| `POST /v1/exports/ma-diligence` | Sealed multi-day diligence bundle bound by `ma_root_hash` | JSON |
| `POST /v1/exports/ma-diligence/jobs`, `GET .../jobs/{id}`, `GET .../jobs` | Async-job mode for large exports | JSON |
| `GET /healthz` | Liveness + which narrative client is wired | JSON |

## Architectural highlights

- **3-anchor verifiability chain.** Every evidence pack binds `(pack_root_hash, prompt_hash, content_hash)` — three independent verification anchors a regulator can check.
- **Cert-chain-verified TSA anchor (CP9.51).** TSR bytes are validated against FreeTSA's published cert chain server-side, with FreeTSA cert fixtures bundled at `tests/fixtures/freetsa/`. A forged TSR is rejected at ingest, not only at the regulator's `openssl` later.
- **Vendor-neutral `PolicyEnforcementClient` ABC.** Veea Lobster Trap is one provider via `VeeaLobsterTrapClient`. Microsoft AGT, AWS Bedrock AgentCore, custom enforcement: all drop in as subclasses. No lock-in.
- **Append-only by code AND by database trigger.** App layer never issues `UPDATE`/`DELETE` on `receipts` or `events`. PG triggers enforce the same at the privilege layer. Defence in depth. Verified by 14 PG-mode integration tests.
- **Deferred-tombstone anchor rows.** Failed TSA calls don't make a day un-anchored — they create a `status='deferred'` row recording "we tried, here's when, here's why". Auditable failure, not silent failure.
- **Two evidence-pack wire forms via content negotiation.** JSON-LD by default. PDF when `Accept: application/pdf` (deterministic A4 with pinned timestamps; byte-identical re-renders). Same `root_hash` cross-checks both.
- **Raw RFC 3161 DER pipe via `Accept: application/timestamp-reply`.** Regulators with `curl … | openssl ts -verify` workflows get a clean one-liner. No base64 step.
- **Tabletop without persistence.** BR-12 runs synthetic scenarios through the same `PolicyEnforcementClient` adapter that production uses — but never writes Receipts, never mutates the chain. Pure simulation surface for DORA Article 30 drills.
- **M&A `ma_root_hash` composability.** BR-13 composes 1..N anchored days into a sealed bundle bound by a single `ma_root_hash` — the acquirer verifies the whole bundle in one operation. Acquisitions get AI governance evidence in 4 hours, not 11 weeks.

## Operator Console (Web + PWA, native deferred)

Forensa exposes a **Next.js 16 / React 19 Operator Console** as the human-facing surface for six named personas (Compliance Officer, Internal Auditor, Security Engineer, General Counsel, AI Platform Owner, M&A Acquirer). The Console is **Web in v1.x, with a Progressive Web App (PWA) shell installable to phone, tablet, and desktop home screens**.

**Native iOS / native Android Operator Console clients are explicitly deferred to Phase 14+** — a separate engineering investment (separate auth flow, separate app-store submission, separate test matrix). The architectural commitment to native as a future surface is on record so the API stays client-agnostic.

Three primary screens are shipped at MVP level today; the enterprise list-views pattern (cursor pagination + filters + URL-query persistence + sortable cols + status chips + loading skeletons + persona-aware landing + PWA shell) is the **CP9.52 work item** — the demo-readiness flip from 5/7 to 7/7 in the readiness scorecard.

## Sponsor utilisation

| Sponsor | Role in Forensa |
|---|---|
| **Veea Lobster Trap** | Policy enforcement verdict source; every decision feeds the evidence ledger |
| **Google Gemini 2.5 Pro** | Narrative generation with 4-layer prompt-injection defence; SDK migrated `google.generativeai` → `google.genai` in CP9.20 |
| **Google AI Studio** | Live API path for hackathon submission |
| **RFC 3161 TSA (FreeTSA)** | Daily timestamp anchoring of chain root; full cert-chain verification (CP9.51) |
| **OpenTelemetry GenAI** | Wire-format compatibility for agent traces |
| **PostgreSQL 16** | Multi-tenant tamper-evident store with RLS-ready models + append-only triggers (14 PG-integration tests) |

## Award alignment

| Category | Why Forensa fits |
|---|---|
| **Veea Award (Track 1)** | Forensa is the evidence layer downstream of Lobster Trap. The enforcement vendor's verdicts become the source records in Forensa's ledger. Direct integration; vendor-neutral ABC means Veea is one of N providers, not the only one. |
| **Gemini Award** | Live Gemini 2.5 Pro narrative generation with a non-trivial product surface: 4-layer prompt-injection defence + 3-anchor verifiability binding + cert-chain-verified TSA anchor. Not a hello-world LLM demo. |
| **Best Use of NVIDIA** (if applicable) | Physical-action replay (BR-08) tracked as out-of-hackathon scope; Omniverse integration is in the Phase 13 roadmap. |

## What's next (Phase 10–14)

| Priority | Item | Phase |
|---|---|---|
| 1 | **CP9.52 Operator Console enterprise list-views + PWA + Playwright UI-driving E2E** (closes BR-14 PARTIAL → IMPLEMENTED+TESTED for v1.x scope) | 9 |
| 2 | CP10.1 — Multi-tenant auth surface (UC-10): SSO + tenant picker + login screen | 10 |
| 3 | CP10.2 — KMS adapter for tenant signing keys (AWS KMS / GCP KMS / Vault) | 10 |
| 4 | CP11.6 — Detached platform signature on JSON-LD + PDF + M&A bundle | 11 |
| 5 | CP12.4 — Kafka ingest queue + async writer (BR-09 AWS topology) | 12 |
| 6 | CP12.x — LangGraph multi-agent provenance (BR-07) | 12 |
| 7 | CP13.6 — On-prem / VPC Helm chart deploy | 13 |
| 8 | **CP14.1+ — Native iOS + Android Operator Console clients** (React Native or Swift/Kotlin TBD at Phase 14 entry) | **14** |

---

**Repo:** `github.com/vsenthil7/forensa`
**Submission:** Monday 19 May 2026 · Google TechEx Intelligent Enterprise Solutions
**Doc pack root:** `docs/README.md`
**Contact:** in repo `README.md`
