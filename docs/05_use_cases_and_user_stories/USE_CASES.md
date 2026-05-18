# Forensa — Use Cases, Screens, and User Stories

**Doc:** 05 of 22 | **Version:** v2.0 ELABORATED — 2026-05-18 05:15 BST
**Status:** authoritative against HEAD CP9.51
**Supersedes:** `_archive/USE_CASES_v1_20260512.md` — preserved verbatim in archive
**Companion docs:** `BRD.md` (BR-01..BR-14), `BRD_IDENTIFIER_MAP.md`, `TRACEABILITY_MATRIX.md` (RT-F01..F22), and `USE_CASES_LIVE.md`

---

## 0. Rules — read this before editing or extending

### 0.1 Rule A.10 (inherited) — requirement-traceability discipline
Before each Checkpoint (CP), open this document + `BRD.md` + `TRACEABILITY_MATRIX.md`. CP selection driven by which user stories (US-F\*) need closing.

### 0.2 Rule A.11 — CP ↔ requirement closure (NEW in v2.0)
Every CP commit must close (or advance) at least one US-F\* and/or UC-F\* and/or SCR-F\*. The commit message names the IDs. The LIVE traceability records the CP commit against those IDs.

A CP that does not close any named ID is not a tracked CP. (See `BRD_IDENTIFIER_MAP.md` §4 for the full statement of this rule.)

### 0.3 Editorial principle for this document
- Section 2 (8 UCs) is preserved verbatim from v1, with UC-09 and UC-10 added in v2.0
- Section 3 (SCR-F\* screen index) is new in v2.0
- Section 4 (US-F\* full expansion) is new in v2.0
- Section 5 (personas) preserves v1 5 personas, promotes P-ACQ, adds P-REG

---

## 1. Personas

| Persona | Code | Role | Pain | Primary console screens (SCR-F\*) |
|---|---|---|---|---|
| Compliance Officer | P-COMP | Owns regulatory exposure | FCA inquiry response time | SCR-F01 landing, SCR-F02 timeline, SCR-F04 evidence pack |
| Internal Auditor | P-AUD | Audits AI deployments | Sample-pull time, chain verifiability | SCR-F02, SCR-F03 receipt detail |
| Security Engineer | P-SEC | Investigates AI misuse | DORA tabletop turnaround | SCR-F02, SCR-F06 tabletop |
| General Counsel | P-COUNSEL | Defends in disputes, legal hold | Discovery turnaround, chain-of-custody | SCR-F04, SCR-F07 diligence |
| AI Platform Owner | P-PLAT | Operates AI infra | Ingest reliability, evidence story | SCR-F10 ops dashboard, all screens |
| M&A Acquirer | P-ACQ | Provides AI governance evidence in M&A | Diligence turnaround (11 weeks → 4 hours) | SCR-F07 diligence workspace |
| Regulator / external auditor | P-REG | Reviews exported evidence | Offline verifiability | (consumer of exports — no direct console use) |

**Persona success metrics (from v1, preserved):**

- P-COMP: audit preparation time reduced 60–80%
- P-PLAT (CISO sub-role): mean-time-to-investigate AI incident reduced from days to minutes
- AI Governance Lead: 95%+ AI actions have policy-linked evidence
- P-COUNSEL: evidence packet accepted as legal review artefact
- P-PLAT (Platform Engineer sub-role): agent integration completed with SDK/proxy within one sprint
- **NEW v2.0** P-ACQ: AI governance diligence turnaround ≤ 4 business hours
- **NEW v2.0** P-REG: offline pack verification passes on every received pack

---

## 2. Use Cases (10 total — UC-01..UC-10)

### UC-01 — Regulator evidence pack (canonical demo)
European bank receives FCA inquiry about an AI mortgage decline 6 months prior. Compliance officer scopes inquiry, Forensa returns full evidence chain in 90 seconds. 3-day response vs 6 weeks of forensic reconstruction.
**BR coverage:** BR-01, BR-04, BR-05, BR-10, BR-11. **Demo moneyshot anchor.**
**Personas:** P-COMP primary, P-REG consumer
**Screens used:** SCR-F01 → SCR-F02 → SCR-F04

### UC-02 — Customer dispute reconstruction
Customer claims AI assistant exposed competitor pricing. Forensa retrieves exact agent interaction + policy verdicts. Legal exports cryptographically-verified evidence pack.
**BR:** BR-01, BR-02, BR-05, BR-10
**Personas:** P-COUNSEL primary, P-SEC support
**Screens:** SCR-F02 → SCR-F03 → SCR-F04

### UC-03 — Multi-agent chain audit
5-agent procurement workflow misbehaves. LangGraph provenance graph shows which agent caused cascade, what each downstream agent saw, which policies fired at each step.
**BR:** BR-07, BR-10, BR-11
**Status:** UC-03 itself partially supported (single-agent chain audit available today); LangGraph multi-agent capture **DEFERRED Phase 12**
**Personas:** P-SEC primary, P-PLAT support
**Screens:** SCR-F02 (filtered by agent), SCR-F03

### UC-04 — Policy drift detection
Quarterly governance review surfaces: policy v2.3.1 active during 47% of high-stakes Q1 decisions, but policy v2.4 was documented standard. Drift invisible until Forensa surfaced it.
**BR:** BR-04, BR-10
**Personas:** P-COMP primary, P-AUD support
**Screens:** SCR-F02 (filtered by policy version), SCR-F08 narrative viewer

### UC-05 — Model deprecation evidence preservation
Vendor announces Gemini 2.5 deprecation. Customer preserves evidence of past decisions under deprecated model. Forensa exports with model-version metadata frozen.
**BR:** BR-01, BR-05, BR-09 (PARTIAL — in-process scope only; AWS bulk backfill Phase 12)
**Personas:** P-COMP, P-PLAT
**Screens:** SCR-F02, SCR-F04

### UC-06 — Tabletop incident response (DORA Article 30)
DORA Article 30 annual tabletop exercises for critical third-party AI dependencies. Forensa tabletop mode runs synthetic incidents through production evidence pipeline.
**BR:** BR-12
**Personas:** P-SEC primary
**Screens:** SCR-F06 tabletop

### UC-07 — M&A due diligence
Acquiring company asks "list every AI system, who governs it, what evidence exists." Forensa exports inventory + 90-day evidence sample in days, not months.
**BR:** BR-13
**Personas:** P-ACQ primary, P-COUNSEL support
**Screens:** SCR-F07 diligence workspace

### UC-08 — Prompt injection investigation
Support agent receives malicious prompt. Lobster Trap flags injection pattern; Forensa records block verdict, policy version, model context, analyst follow-up. Security exports timeline.
**BR:** BR-01, BR-04, BR-07 (BR-07 DEFERRED — basic single-agent injection investigation works without BR-07)
**Personas:** P-SEC primary
**Screens:** SCR-F02, SCR-F03

### UC-09 — Operator console journey (NEW v2.0)
A non-technical compliance officer arrives at Forensa for the first time. Lands on the persona-aware home page (SCR-F01), selects "Compliance Officer", sees a curated dashboard. Scopes an inquiry window via filter bar on the timeline (SCR-F02), reviews three suspect receipts (SCR-F03), generates an evidence pack (SCR-F04 with Compliance view toggle), downloads PDF, hands to FCA. **All without touching JSON or hash strings.** Completes in 8 minutes.
**BR:** BR-14 (Operator Console — Web + PWA)
**Personas:** P-COMP primary, P-AUD secondary, P-COUNSEL tertiary
**Screens:** SCR-F01 → SCR-F02 → SCR-F03 → SCR-F04
**Acceptance:** task completion without engineer assistance (BR-14 AC-3)

### UC-10 — Multi-tenant authenticated access (NEW v2.0)
P-PLAT operates Forensa across three tenants (UK mortgage business, US lending business, EU healthtech subsidiary). Logs in via SSO (Phase 10), selects tenant via top-right tenant picker, sees only that tenant's data, switches tenant without re-auth, exports per-tenant evidence pack. Cross-tenant attempts (e.g. direct URL with another tenant's UUID) return 404 or 403 per BR-02 / BR-12 isolation rules.
**BR:** BR-02, BR-14 (auth surface SCR-F09)
**Status:** `DEFERRED` Phase 10 CP10.1..CP10.4
**Personas:** P-PLAT primary, all other personas secondary
**Screens:** SCR-F09 login → tenant picker in SCR-F01 → all other SCR-F\*

---

## 3. Screen Index (SCR-F\* — NEW in v2.0)

The Operator Console (BR-14) exposes ten screens. Five are partial today, three are planned for CP9.52, one is planned for Phase 10, one for Phase 12. The architectural pattern is **list-views-as-top-nav** (no sessionStorage shortcuts — see BR-14 AC-2 in BRD.md for the cautionary tale from mendoraci CP-9).

| SCR | Title | Route | Persona | Status | Backed by API-F\* | Notes |
|---|---|---|---|---|---|---|
| SCR-F01 | Persona landing + tenant picker | `/` | All | `PLANNED` CP9.52 | API-F05 receipts list (preview) | Currently `/` shows the receipts table directly. CP9.52 promotes a persona-aware landing above it. |
| SCR-F02 | Receipts timeline (replaces v1 receipts table) | `/receipts` | P-COMP, P-AUD, P-SEC | `PARTIAL` (table exists, timeline + filters CP9.52) | API-F05 `GET /v1/receipts` | Adopts list-views-as-top-nav pattern. Cursor pagination, filters (date / agent / policy outcome / chain status), URL-query persistence, sortable columns, status chips. |
| SCR-F03 | Receipt detail with tabs | `/receipts/[id]` | P-AUD, P-SEC | `PARTIAL` (page exists, tabs CP9.52) | API-F06 `GET /v1/receipts/{id}` | Three tabs: Summary (human prose), Cryptographic proof (hashes + signature + chain link), Raw JSON. Default to Summary. |
| SCR-F04 | Evidence pack generator with Compliance view toggle | `/evidence` | P-COMP, P-COUNSEL | `PARTIAL` (page exists, toggle CP9.52) | API-F07 `GET /v1/evidence-packs` (JSON-LD + Accept: application/pdf) | Compliance view (default): plain English summary + big Download PDF CTA. Technical view: full JSON-LD pack. |
| SCR-F05 | Anchors view (per-day RFC 3161 anchor list) | `/anchors` | P-AUD, P-PLAT | `PLANNED` CP9.53 | API-F08 `GET /v1/anchors` | List of anchored days, click → per-anchor TSR DER bytes downloadable. |
| SCR-F06 | Tabletop drill / replay UI | `/tabletop` | P-SEC | `PLANNED` CP9.55 | API-F11 `POST /v1/tabletop/simulate`, API-F12 `POST /v1/tabletop/replay-window` | Pick policy bundle, define synthetic actions, run, see verdict counts. |
| SCR-F07 | M&A diligence workspace | `/diligence` | P-ACQ, P-COUNSEL | `PLANNED` CP9.56 | API-F09 `POST /v1/exports/ma-diligence`, API-F10 jobs endpoints | Create export job, list jobs, view result, download bundle. |
| SCR-F08 | Narrative viewer | `/narratives` | P-COMP, P-SEC | `PLANNED` CP9.57 | API-F13 `POST /v1/narratives` | Pick a receipt window, click "Explain this window", render plain English. |
| SCR-F09 | Login / auth surface | `/login` | All | `PLANNED` Phase 10 CP10.1 | API-F14 `POST /v1/auth/login` (planned) | SSO + bearer-token fallback. Redirect target preserved. |
| SCR-F10 | Status / ops dashboard | `/status` | P-PLAT | `PLANNED` CP9.58 | API-F15 `GET /v1/metrics` (planned, extending `/healthz`) | Ingest rate, signing latency, anchor success/failure, chain integrity, last 24h sparkline. |

**Console navigation pattern (BR-14 AC-2 — list-views-as-top-nav):**

```
[Forensa logo] | Receipts · Evidence · Anchors · Narratives · Diligence · Tabletop · Status   [tenant picker] [user]
```

Each top-nav link goes directly to a list view that always works. No "active receipt" or "active intake" sessionStorage. Drill-down from list view to detail (SCR-F03, SCR-F04) is via row click → deep-linked URL with the ID in the path.

---

## 4. User Stories — US-F01..US-F32 (full expansion, mendoraci shape)

**How to read:** persona · story · BR · SCR / API · acceptance · negative · priority · phase · status

Priority: P0 demo-critical / P1 MVP / P2 Pilot / P3 Enterprise.
Phase: maps to BRD §10 phase plan.
Status: `IMPLEMENTED+TESTED` / `PARTIAL` / `PLANNED CP\<n.x\>` / `DEFERRED Phase \<n\>`.

### Epic A — Ingest & Identity (BR-01, BR-02, BR-03; SCR-F02, SCR-F03)

#### US-F01 — Agent action ingested as signed Receipt
- **As** P-PLAT **I want** every agent action my agent platform posts to be persisted as a signed Receipt in the ledger **so that** I have an evidence record for every decision the agent took.
- **BR:** BR-01, BR-02 · **API:** API-F01 `POST /v1/events`
- **Acceptance:** AC-1 201 Created with `event_id`, `receipt_id`, `receipt_hash`, `integrity_ok=true`; AC-2 monotonic sequence per tenant; AC-3 signed by tenant key + (optional) agent key.
- **Negative path:** missing principal → 401; cross-tenant principal → 403; idempotency-key+different body → 409.
- **Priority:** P0 · **Phase:** 1 · **Status:** `IMPLEMENTED+TESTED`

#### US-F02 — Retry-safe ingest
- **As** P-PLAT **I want** retries with the same `Idempotency-Key` to return the original 201 response **so that** retry storms do not duplicate receipts.
- **BR:** BR-01 / NFR-08 · **API:** API-F01
- **Acceptance:** AC-1 same key + same body within TTL → original 201; AC-2 same key + different body → 409.
- **Negative path:** missing `Idempotency-Key` header on `POST /v1/events` → 400.
- **Priority:** P0 · **Phase:** 9 · **Status:** `IMPLEMENTED+TESTED` (CP9.17)

#### US-F03 — Tenant signature verification
- **As** P-AUD **I want** to verify a Receipt's tenant signature offline **so that** I can prove the chain wasn't forged.
- **BR:** BR-02 · **SCR:** SCR-F03
- **Acceptance:** verifier reproduces signature from `payload_hash` + tenant public key.
- **Priority:** P1 · **Phase:** 2 · **Status:** `IMPLEMENTED+TESTED`

#### US-F04 — Agent identity signature
- **As** P-AUD **I want** each Receipt to also carry the agent's identity signature (when present) **so that** multi-party identity binding is provable.
- **BR:** BR-02 · **API:** API-F01
- **Acceptance:** `agent_signature_b64` present when agent identity provided; verifiable independently.
- **Priority:** P1 · **Phase:** 9 · **Status:** `IMPLEMENTED+TESTED` (CP9.18a/b/c)

#### US-F05 — Reasoning capture in event
- **As** P-AUD **I want** LLM agent events to include their chain-of-thought summary **so that** I can audit how the model decided.
- **BR:** BR-03 · **API:** API-F01 (event schema)
- **Acceptance:** `Event.reasoning` accepts structured COT summary; non-LLM events accept null.
- **Priority:** P1 · **Phase:** 1 · **Status:** `IMPLEMENTED+TESTED`

#### US-F06 — OTel GenAI envelope ingest
- **As** P-PLAT **I want** to POST OpenTelemetry GenAI envelopes directly **so that** I do not have to maintain a custom event schema mapping.
- **BR:** BR-01, BR-03 · **API:** API-F01
- **Acceptance:** OTel envelope mapped into Forensa Event schema; `forensa.reasoning` and `gen_ai.response.text` both captured (separation tracked as IMP-F14).
- **Priority:** P2 · **Phase:** 1 · **Status:** `IMPLEMENTED+TESTED` (with named finding)

#### US-F07 — Receipt list view for tenant
- **As** P-COMP **I want** a list of receipts for my tenant **so that** I can browse what my agents have done.
- **BR:** BR-01 · **SCR:** SCR-F02 · **API:** API-F05 `GET /v1/receipts`
- **Acceptance (current PARTIAL):** AC-1 returns paginated receipts. **Acceptance (CP9.52 full):** AC-2 cursor pagination; AC-3 filters by date / agent / outcome / status; AC-4 URL-query persistence; AC-5 sortable columns.
- **Priority:** P0 · **Phase:** 4 (basic) / 9.52 (enterprise) · **Status:** `PARTIAL`

#### US-F08 — Single-receipt detail with verification
- **As** P-AUD **I want** to open a receipt and verify its chain links **so that** I trust the integrity.
- **BR:** BR-01, BR-06 · **SCR:** SCR-F03 · **API:** API-F06 `GET /v1/receipts/{id}`
- **Acceptance (current PARTIAL):** AC-1 shows seq, hash, sig. **Acceptance (CP9.52 full):** AC-2 tabbed Summary / Proof / Raw view; AC-3 chain-integrity badge with hover-explain.
- **Priority:** P0 · **Phase:** 4 (basic) / 9.52 (full) · **Status:** `PARTIAL`

### Epic B — Policy Lifecycle (BR-04; SCR-F03)

#### US-F09 — Policy bundle snapshot at decision
- **As** P-AUD **I want** every Receipt to bind to the policy snapshot active at decision time **so that** I can reconstruct historical policy state.
- **BR:** BR-04 · **API:** API-F01
- **Acceptance:** `policy_snapshot_id` on Receipt; snapshot immutable.
- **Priority:** P0 · **Phase:** 3 · **Status:** `IMPLEMENTED+TESTED`

#### US-F10 — Policy bundle approval workflow
- **As** P-COMP **I want** a draft → proposed → approved workflow for policy bundles **so that** policy changes are governed.
- **BR:** BR-04 · **DB:** DB-F03 `policy_bundle_approvals` (append-only triggers)
- **Acceptance:** approval row append-only; UPDATE/DELETE rejected at DB level.
- **Priority:** P1 · **Phase:** 9 · **Status:** `IMPLEMENTED+TESTED` (CP9.15)

#### US-F11 — Policy drift surfaced in narrative
- **As** P-COMP **I want** the narrative for a quarter window to surface policy version distribution **so that** I see drift between documented and actual policy.
- **BR:** BR-04, BR-10 · **SCR:** SCR-F08
- **Acceptance:** narrative names the dominant policy version + drift percentage.
- **Priority:** P2 · **Phase:** 9 · **Status:** `IMPLEMENTED+TESTED`

#### US-F12 — Policy replay never returns live state
- **As** P-AUD **I want** replay endpoints to return snapshot state only (never live) **so that** "what was the policy 6 months ago" is answerable.
- **BR:** BR-04
- **Acceptance:** 5 replay tests prove `live_bundle.content_hash` never returned.
- **Priority:** P1 · **Phase:** 3 · **Status:** `IMPLEMENTED+TESTED`

### Epic C — Chain Integrity & Anchoring (BR-06; SCR-F03, SCR-F05)

#### US-F13 — Hash chain verifiable offline
- **As** P-REG **I want** to verify the receipt hash chain offline **so that** I don't depend on Forensa being live.
- **BR:** BR-06
- **Acceptance:** chain verifier accepts a receipt list and validates `prev_receipt_hash` links + signatures.
- **Priority:** P0 · **Phase:** 2 · **Status:** `IMPLEMENTED+TESTED`

#### US-F14 — Daily RFC 3161 anchor against FreeTSA
- **As** P-PLAT **I want** the day's chain head anchored to FreeTSA every 24h **so that** a regulator with T+1 year doubt cannot dispute server-clock tampering.
- **BR:** BR-06 · **API:** API-F08 `GET /v1/anchors`
- **Acceptance:** daily cron writes `AnchorEvidence` with TSR DER; on TSA failure writes `deferred` tombstone.
- **Priority:** P0 · **Phase:** 9 · **Status:** `IMPLEMENTED+TESTED` (CP9.19)

#### US-F15 — Cert-chain verification of TSR
- **As** P-REG **I want** the TSR's signature validated against the published FreeTSA cert chain **so that** I cannot accept a forged TSR.
- **BR:** BR-06
- **Acceptance:** `verify_rfc3161_timestamp_response()` performs full PKIX cert-chain verification; unit + live integration tests; FreeTSA cert fixtures bundled.
- **Priority:** P1 · **Phase:** 9 · **Status:** `IMPLEMENTED+TESTED` (CP9.51 — `d7d9aaa`)

#### US-F16 — Raw TSR DER bytes downloadable
- **As** P-AUD **I want** to download raw RFC 3161 TSR bytes **so that** I run `openssl ts -verify` independently.
- **BR:** BR-06 · **SCR:** SCR-F05 · **API:** API-F08
- **Acceptance:** `Accept: application/timestamp-reply` returns DER bytes with filename header; X-Forensa-Anchor-Root-Hash carries root.
- **Priority:** P1 · **Phase:** 9 · **Status:** `IMPLEMENTED+TESTED` (CP9.27)

### Epic D — Evidence Pack Export (BR-05; SCR-F04)

#### US-F17 — JSON-LD evidence pack
- **As** P-COMP **I want** a JSON-LD + PROV-O evidence pack for a window **so that** my regulator team can parse it programmatically.
- **BR:** BR-05 · **API:** API-F07 `GET /v1/evidence-packs`
- **Acceptance:** returns JSON-LD with header + receipts + activities + anchor + root_hash.
- **Priority:** P0 · **Phase:** 6 · **Status:** `IMPLEMENTED+TESTED`

#### US-F18 — Regulator-grade PDF
- **As** P-COMP **I want** the same evidence pack as a deterministic A4 PDF **so that** I hand it to FCA as a single artefact.
- **BR:** BR-05 · **API:** API-F07 (Accept: application/pdf)
- **Acceptance:** PDF binds same root_hash as JSON-LD; filename includes first 12 chars of root_hash; X-Forensa-Root-Hash header echoed.
- **Priority:** P0 · **Phase:** 9 · **Status:** `IMPLEMENTED+TESTED` (CP9.21a + CP9.21b)

#### US-F19 — Evidence-pack Compliance view (NEW v2.0 — Console UX)
- **As** P-COMP **I want** the `/evidence` page to default to a Compliance view (plain English + big Download PDF CTA) **so that** I don't see JSON-LD I can't read.
- **BR:** BR-05, BR-14 · **SCR:** SCR-F04
- **Acceptance:** Compliance view default; toggle reveals technical JSON-LD view; loading-state narration ("Building Merkle tree... Verifying TSA anchor... Rendering PDF...").
- **Priority:** P0 · **Phase:** 9.52 · **Status:** `PLANNED`

#### US-F20 — Offline pack verification
- **As** P-REG **I want** `verify_evidence_pack()` to validate a downloaded pack offline **so that** I don't trust Forensa's live state.
- **BR:** BR-05, BR-06
- **Acceptance:** recomputes root_hash from canonical bind shape; integration tests prove tamper detection.
- **Priority:** P0 · **Phase:** 6 · **Status:** `IMPLEMENTED+TESTED`

### Epic E — Tabletop & Simulation (BR-12; SCR-F06)

#### US-F21 — Tabletop drill via API
- **As** P-SEC **I want** to POST a tabletop scenario and get back per-action verdicts **so that** I can validate a candidate policy without production risk.
- **BR:** BR-12 · **API:** API-F11 `POST /v1/tabletop/simulate`
- **Acceptance:** scenario echo + bundle metadata + per-action result + summary; nothing persisted.
- **Priority:** P1 · **Phase:** 9 · **Status:** `IMPLEMENTED+TESTED` (CP9.29)

#### US-F22 — Tabletop replay window
- **As** P-SEC **I want** to replay a historical window of real events against a candidate bundle **so that** I see what would have happened.
- **BR:** BR-12 · **API:** API-F12 `POST /v1/tabletop/replay-window`
- **Acceptance:** read-only on ledger; returns per-receipt comparison.
- **Priority:** P2 · **Phase:** 9 · **Status:** `IMPLEMENTED+TESTED` (CP9.29 includes replay)

#### US-F23 — Tabletop UI in Console
- **As** P-SEC **I want** the tabletop screen in the Console **so that** I don't need to curl JSON.
- **BR:** BR-12, BR-14 · **SCR:** SCR-F06
- **Acceptance:** UI to pick bundle, define action list, run, see verdicts.
- **Priority:** P2 · **Phase:** 9.55 · **Status:** `PLANNED`

### Epic E2 — Multi-agent provenance (DEFERRED)

#### US-F24 — LangGraph multi-agent capture
- **As** P-SEC **I want** to see which downstream agent received which output **so that** I can debug cascades.
- **BR:** BR-07
- **Status:** `DEFERRED` Phase 12

### Epic F — M&A Diligence (BR-13; SCR-F07) and deferred NL UX

#### US-F25 — M&A diligence export bundle
- **As** P-ACQ **I want** a sealed multi-day bundle bound by `ma_root_hash` **so that** I verify acquirer-side in one operation.
- **BR:** BR-13 · **API:** API-F09 `POST /v1/exports/ma-diligence`
- **Acceptance:** bundle composes one EvidencePack per anchored day + every AnchorEvidence; ma_root_hash binds all.
- **Priority:** P1 · **Phase:** 9 · **Status:** `IMPLEMENTED+TESTED` (CP9.28)

#### US-F26 — M&A diligence UI in Console
- **As** P-ACQ **I want** a `/diligence` workspace to create + list + view export jobs **so that** the operator UX matches the API.
- **BR:** BR-13, BR-14 · **SCR:** SCR-F07
- **Acceptance:** create job → list → view detail → download bundle.
- **Priority:** P2 · **Phase:** 9.56 · **Status:** `PLANNED`

#### US-F27 — Free-text NL query in Console
- **As** P-COMP **I want** to type "show me all high-stakes decisions last quarter" and get receipt chains **so that** I don't construct JSON filters.
- **BR:** BR-10
- **Status:** `DEFERRED` Phase 13

### Epic G — Operator Console (BR-14) — NEW in v2.0

#### US-F28 — Persona-aware landing page
- **As** P-COMP (or any persona) on first login **I want** to see cards labelled with my role and a primary action **so that** I know what Forensa is for me.
- **BR:** BR-14 · **SCR:** SCR-F01
- **Acceptance:** 6 persona cards + "Open my workspace" CTA each; routes to persona-relevant first screen.
- **Negative path:** unauthenticated → redirect to SCR-F09 login.
- **Priority:** P1 · **Phase:** 9.52 · **Status:** `PLANNED`

#### US-F29 — Enterprise timeline replaces v1 table (the mendoraci CP-9 pattern)
- **As** P-COMP **I want** the receipt list to show agent action + policy outcome + timestamp in readable form **so that** I don't see raw UUIDs and hex.
- **BR:** BR-14 · **SCR:** SCR-F02 (replaces v1 ReceiptList.tsx table)
- **Acceptance:** AC-1 cursor pagination (limit default 50, max 200); AC-2 filters: date / agent / outcome / chain status / policy version; AC-3 URL-query persistence (back button + bookmarkable); AC-4 sortable columns; AC-5 status chips (green anchored / amber pending / grey deferred); AC-6 loading skeleton (no flash of blank); AC-7 empty state with clear CTA; AC-8 error state with retry; AC-9 hash collapsed behind disclosure ("🔐 Verify").
- **Negative path:** filter combination with zero results → empty state copy ("No agent activity matched. Try widening your date range.").
- **Anti-pattern explicitly prohibited:** sessionStorage tracking of "active receipt" for top-nav deep-linking. See BR-14 AC-2 in BRD.md and `_archive/` for the cautionary tale.
- **Priority:** P0 · **Phase:** 9.52 · **Status:** `PLANNED`

#### US-F30 — Receipt detail tabbed view
- **As** P-AUD **I want** Summary / Proof / Raw tabs on the receipt detail **so that** I choose my depth.
- **BR:** BR-14 · **SCR:** SCR-F03
- **Acceptance:** AC-1 Summary tab default with plain English; AC-2 Proof tab with prev→current hash visual; AC-3 Raw tab with copy-to-clipboard.
- **Priority:** P1 · **Phase:** 9.52 · **Status:** `PLANNED`

#### US-F31 — PWA installable to phone home screen
- **As** P-COMP on the move **I want** to install Forensa as an app on my iPhone **so that** I open it from the home screen during an inquiry.
- **BR:** BR-14 · **SCR:** all
- **Acceptance:** AC-1 `manifest.json` declares Forensa icon, theme color, display=standalone, scope; AC-2 service worker caches read-only shell; AC-3 installable on iOS Safari, Android Chrome, desktop Chrome/Edge; AC-4 read-only views render offline against last cached state; AC-5 write actions disabled offline with explicit affordance.
- **Negative path:** service-worker registration failure → degrade to web mode with explicit notice.
- **Priority:** P1 · **Phase:** 9.52 · **Status:** `PLANNED`
- **Cross-reference:** Native iOS / native Android Console is **`DEFERRED` Phase 14+** — see BR-14 AC-9 and DEPLOYMENT_TOPOLOGY.md §Console for the architectural commitment.

#### US-F32 — Multi-tenant auth + tenant picker
- **As** P-PLAT operating multiple tenants **I want** SSO + tenant picker **so that** I switch tenants without re-auth and cross-tenant URLs are blocked.
- **BR:** BR-02, BR-14 · **SCR:** SCR-F09 login + tenant picker in SCR-F01 · **API:** API-F14 `POST /v1/auth/login`
- **Acceptance:** AC-1 SSO + bearer-token fallback; AC-2 redirect target preserved through login; AC-3 tenant picker visible in header when principal has >1 tenant; AC-4 cross-tenant URL → 404 (not 403, per BR-12 isolation pattern).
- **Negative path:** expired session → 401 + redirect to login.
- **Priority:** P1 · **Phase:** 10 · **Status:** `DEFERRED` Phase 10 CP10.1..CP10.4

---

## 5. Story → BR coverage check

Every BR has at least one named story.

| BR | Stories that cover it |
|---|---|
| BR-01 | US-F01, US-F02, US-F05, US-F06, US-F07, US-F08 |
| BR-02 | US-F03, US-F04, US-F32 |
| BR-03 | US-F05, US-F06 |
| BR-04 | US-F09, US-F10, US-F11, US-F12 |
| BR-05 | US-F17, US-F18, US-F19, US-F20 |
| BR-06 | US-F13, US-F14, US-F15, US-F16 |
| BR-07 | US-F24 (deferred) |
| BR-08 | (deferred, no story today — out of v1.x scope) |
| BR-09 | (covered by US-F01..F02 in-process; AWS deferred to Phase 12) |
| BR-10 | US-F11, US-F27 (deferred), implicit in narrative tests |
| BR-11 | implicit in narrative tests; future US-F33 counterfactual UI |
| BR-12 | US-F21, US-F22, US-F23 |
| BR-13 | US-F25, US-F26 |
| **BR-14** | **US-F28, US-F29, US-F30, US-F31, US-F32** |

## 6. UC → story rollup

| UC | Stories | Status |
|---|---|---|
| UC-01 Regulator pack | US-F07, US-F17, US-F18, US-F19, US-F20 | IMPLEMENTED+TESTED (UI Compliance view PLANNED CP9.52) |
| UC-02 Customer dispute | US-F03, US-F08, US-F17 | IMPLEMENTED+TESTED |
| UC-03 Multi-agent audit | US-F24 (DEFERRED) | PARTIAL — single-agent works |
| UC-04 Policy drift | US-F11, US-F12 | IMPLEMENTED+TESTED |
| UC-05 Model deprecation | US-F01, US-F17 | IMPLEMENTED+TESTED (in-process); AWS bulk DEFERRED |
| UC-06 DORA tabletop | US-F21, US-F22 | IMPLEMENTED+TESTED (UI PLANNED CP9.55) |
| UC-07 M&A diligence | US-F25 | IMPLEMENTED+TESTED (UI PLANNED CP9.56) |
| UC-08 Prompt injection | implicit in narrative defence tests | IMPLEMENTED+TESTED |
| **UC-09 Operator console journey** | **US-F28, US-F29, US-F30, US-F19** | **PLANNED CP9.52** |
| **UC-10 Multi-tenant auth** | **US-F32** | **DEFERRED Phase 10** |

## 7. Change log

| Date | Change |
|---|---|
| 2026-05-18 05:15 BST | **v2.0 ELABORATED.** Preserved 8 original UCs verbatim. Added UC-09 (Operator console journey), UC-10 (Multi-tenant auth). Added §3 Screen Index (SCR-F01..F10). Added §4 full US-F01..F32 expansion with mendoraci shape (persona · BR · SCR · API · acceptance · negative · priority · phase · status), organised into 7 epics. Added §1 persona table extension (P-ACQ M&A Acquirer + P-REG Regulator). Added §5 BR coverage check + §6 UC → story rollup. Rule A.11 locked at top. **Console anti-pattern (sessionStorage for top-nav) explicitly named in US-F29 to pre-empt the mendoraci CP-9 trap.** v1 preserved at `_archive/USE_CASES_v1_20260512.md`. |
| 2026-05-12 | v1 frozen with 8 UCs + 5 personas. |
