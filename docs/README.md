# Forensa — Documentation Pack

**Doc:** root README · **Date:** 2026-05-18 05:15 BST · **Pack version:** v2.0 ELABORATED
**Status:** authoritative against HEAD CP9.51 `d7d9aaa`
**Codebase root (in workspace):** `forensa/`
**This pack lives at:** `forensa/docs/`

---

## 0. Most-important rules (read before editing any doc)

### 0.1 Rule A.10 (inherited) — requirement-traceability discipline

Before each Checkpoint (CP), open `02_brd/BRD.md` + `05_use_cases_and_user_stories/USE_CASES.md` + `17_traceability_matrix/TRACEABILITY_MATRIX.md`. CP selection is driven by which named requirement IDs need closing, **not** by engineering convenience.

### 0.2 Rule A.11 — CP ↔ requirement closure (LOCKED in v2.0)

**Every mini-sprint Checkpoint (CP) commit must close (or advance) at least one named requirement ID drawn from `02_brd/BRD_IDENTIFIER_MAP.md`.** The CP commit message names the ID(s) closed. The LIVE traceability document records the CP commit against those IDs.

A CP that does not close any named ID is engineering-convenience-labelled (`CPx.y-tooling: ...`) and does **NOT** advance the requirement scoreboard.

This rule is restated verbatim at the top of:
- `02_brd/BRD.md` §0
- `02_brd/BRD_IDENTIFIER_MAP.md` §4
- `05_use_cases_and_user_stories/USE_CASES.md` §0
- `05_use_cases_and_user_stories/USE_CASES_LIVE.md` §0
- `17_traceability_matrix/TRACEABILITY_MATRIX.md` §0
- `17_traceability_matrix/TRACEABILITY_MATRIX_LIVE.md` §0

If you (a future maintainer, human or AI assistant) catch yourself proposing a CP without naming the IDs it closes, **stop**. Re-read `BRD_IDENTIFIER_MAP.md`. Find or create the ID. Then propose the CP.

### 0.3 LIVE doc update cadence (strict, no exceptions)

Both `USE_CASES_LIVE.md` and `TRACEABILITY_MATRIX_LIVE.md` are updated **immediately after every dev commit**, before the next mini-sprint starts. Inherited from mendoraci CLAUDE_RULES discipline; the failure mode it prevents is documentation drift between canonical and LIVE (R-F12 in BRD risk register).

---

## 1. What this doc pack is

Forensa is the **cryptographic evidence layer for enterprise AI agents** — a tamper-evident, multi-party-bound, policy-aware event ledger producing legally admissible records of every agent action, designed for EU AI Act Article 12, DORA Article 30, NIST AI RMF, ISO 42001, SOC 2 Type II compliance.

This pack contains 22 numbered topics + 2 supporting files (SBOM, openapi.json) + 1 reviews directory. The pack is the single source of truth for:

- **What Forensa is** (executive brief, product vision, judge handout, demo video script)
- **Why it matters** (regulatory mapping, competitive landscape, pricing & commercial)
- **What it does** (BRD, BRD identifier map, use cases & user stories, evidence pack spec, API specification, data model)
- **How it's built** (system architecture, security architecture, threat model, deployment topology, build plan)
- **How it's tested** (testing & QA, traceability matrix + LIVE companion)
- **How it operates** (SRE & operations, incident response plan, data protection & privacy)
- **Definitions** (glossary)
- **Trace workbook** (xlsx artefact)

---

## 2. Folder map

```
forensa/docs/
├── README.md                                     ← this file
├── SBOM.md
├── openapi.json
├── reviews/                                      ← code & doc review artefacts
│
├── 00_executive_brief/
│   ├── EXECUTIVE_BRIEF.md
│   ├── JUDGE_HANDOUT.md
│   ├── SUBMISSION_VIDEO_SCRIPT.md
│   └── _archive/
│       ├── EXECUTIVE_BRIEF_v1_20260512.md
│       └── JUDGE_HANDOUT_v1_20260512.md
│
├── 01_product_vision/
│   ├── PRODUCT_VISION.md
│   └── _archive/                                 (empty — no v1 supersession)
│
├── 02_brd/
│   ├── BRD.md                                    ← canonical Business Requirements v2.0
│   ├── BRD_IDENTIFIER_MAP.md                     ← canonical identifier scheme (NEW v2.0)
│   └── _archive/
│       └── BRD_v1.2_20260515_CP9.29.md
│
├── 03_competitive_landscape/
│   ├── COMPETITIVE_LANDSCAPE.md
│   └── _archive/
│
├── 04_pricing_and_commercial/
│   ├── PRICING_AND_COMMERCIAL_MODEL.md
│   └── _archive/
│
├── 05_use_cases_and_user_stories/
│   ├── USE_CASES.md                              ← canonical UCs + SCRs + US-Fs v2.0
│   ├── USE_CASES_LIVE.md                         ← live per-story progress (NEW v2.0)
│   └── _archive/
│       └── USE_CASES_v1_20260512.md
│
├── 06_regulatory_mapping/
│   ├── REGULATORY_MAPPING_MATRIX.md              (with v2.0 RT-F addendum)
│   └── _archive/
│       └── REGULATORY_MAPPING_MATRIX_v1_20260512.md
│
├── 07_system_architecture/
│   ├── SYSTEM_ARCHITECTURE.md                    (with v2.0 Console + PWA + native-deferred addendum)
│   └── _archive/
│       └── SYSTEM_ARCHITECTURE_v1_20260512.md
│
├── 08_api_specification/
│   ├── API_SPECIFICATION.md                      (unchanged at v2.0 sweep; Gaps 11 + 12 named in LIVE)
│   └── _archive/
│
├── 09_data_model/
│   ├── DATA_MODEL.md
│   └── _archive/
│
├── 10_security_architecture/
│   ├── SECURITY_ARCHITECTURE.md
│   └── _archive/
│
├── 11_threat_model/
│   ├── THREAT_MODEL.md
│   └── _archive/
│
├── 12_evidence_pack_spec/
│   ├── EVIDENCE_PACK_SPEC.md
│   └── _archive/
│
├── 13_data_protection_and_privacy/
│   ├── DATA_PROTECTION_AND_PRIVACY.md
│   └── _archive/
│
├── 14_deployment_topology/
│   ├── DEPLOYMENT_TOPOLOGY.md                    (with v2.0 PWA + native-deferred addendum)
│   └── _archive/
│       └── DEPLOYMENT_TOPOLOGY_v1_20260512.md
│
├── 15_build_plan/
│   ├── BUILD_PLAN.md                             (with v2.0 phase-plan refresh + CP9.52 sub-sprint breakdown)
│   ├── CP9.15.1_migration_0004_sql_preview.md
│   └── _archive/
│       └── BUILD_PLAN_v1_20260512.md
│
├── 16_testing_and_qa/
│   ├── TESTING_AND_QA.md                         (with v2.0 Playwright UI-driving + PWA + auth test plans)
│   └── _archive/
│       └── TESTING_AND_QA_v1_20260512.md
│
├── 17_traceability_matrix/
│   ├── TRACEABILITY_MATRIX.md                    ← canonical 22-row matrix v2.0
│   ├── TRACEABILITY_MATRIX_LIVE.md               ← live commit ledger + RT status (NEW v2.0)
│   └── _archive/
│       └── TRACEABILITY_MATRIX_v1_20260514_22h02.md
│
├── 18_sre_and_operations/
│   ├── SRE_AND_OPERATIONS.md
│   └── _archive/
│
├── 19_incident_response_plan/
│   ├── INCIDENT_RESPONSE_PLAN.md
│   └── _archive/
│
├── 20_glossary/
│   ├── GLOSSARY.md                               (with v2.0 identifier-prefix + Console/PWA/Rule terminology addendum)
│   └── _archive/
│       └── GLOSSARY_v1_20260512.md
│
└── 21_traceability_workbook/
    ├── Forensa_TraceabilityMaster_20260518.xlsx  ← canonical workbook (NEW v2.0)
    └── _archive/
```

---

## 3. Reading paths by audience

| Audience | Start here | Then |
|---|---|---|
| **TechEx judge** | `00_executive_brief/JUDGE_HANDOUT.md` | → `00_executive_brief/SUBMISSION_VIDEO_SCRIPT.md` → `02_brd/BRD.md` §1 + §11 |
| **Buyer / executive** | `00_executive_brief/EXECUTIVE_BRIEF.md` → `01_product_vision/PRODUCT_VISION.md` | → `02_brd/BRD.md` §1 + §11 + §13 → `04_pricing_and_commercial/PRICING_AND_COMMERCIAL_MODEL.md` → `03_competitive_landscape/COMPETITIVE_LANDSCAPE.md` |
| **Implementer / engineer** | `02_brd/BRD.md` §7 + §10 | → `07_system_architecture/SYSTEM_ARCHITECTURE.md` → `08_api_specification/API_SPECIFICATION.md` → `09_data_model/DATA_MODEL.md` |
| **Auditor / regulator** | `02_brd/BRD.md` §14.5 | → `06_regulatory_mapping/REGULATORY_MAPPING_MATRIX.md` → `12_evidence_pack_spec/EVIDENCE_PACK_SPEC.md` → `13_data_protection_and_privacy/DATA_PROTECTION_AND_PRIVACY.md` |
| **AI lead** | `02_brd/BRD.md` BR-10/BR-11 + §14.1 + §14.2 + §14.4 | → `11_threat_model/THREAT_MODEL.md` → `16_testing_and_qa/TESTING_AND_QA.md` (EVAL-F01, EVAL-F02 sections) |
| **Compliance officer (P-COMP)** | `00_executive_brief/EXECUTIVE_BRIEF.md` | → `02_brd/BRD.md` §14.5 → `06_regulatory_mapping/REGULATORY_MAPPING_MATRIX.md` → `12_evidence_pack_spec/EVIDENCE_PACK_SPEC.md` |
| **Security engineer (P-SEC)** | `10_security_architecture/SECURITY_ARCHITECTURE.md` | → `11_threat_model/THREAT_MODEL.md` → `19_incident_response_plan/INCIDENT_RESPONSE_PLAN.md` → `02_brd/BRD.md` BR-12 (tabletop) |
| **AI platform owner (P-PLAT)** | `02_brd/BRD.md` §7 + §10 + §17 | → `07_system_architecture/SYSTEM_ARCHITECTURE.md` → `14_deployment_topology/DEPLOYMENT_TOPOLOGY.md` → `18_sre_and_operations/SRE_AND_OPERATIONS.md` |
| **Future Claude assistant resuming this work** | this README §0 + §6 + §7 | → `05_use_cases_and_user_stories/USE_CASES_LIVE.md` (most recent state) → `17_traceability_matrix/TRACEABILITY_MATRIX_LIVE.md` (commit ledger + forward queue) |

---

## 4. Identifier scheme summary

The full identifier map lives in `02_brd/BRD_IDENTIFIER_MAP.md`. Summary at a glance:

| Prefix | Meaning | Anchor doc |
|---|---|---|
| BG | Business Goal | BRD §6 |
| BR | Business Requirement | BRD §7 |
| UC | Use Case | USE_CASES §2 |
| US-F | User Story | USE_CASES §4 |
| SCR-F | Console Screen | USE_CASES §3 |
| API-F | Backend API | API_SPECIFICATION |
| DB-F | Database entity | DATA_MODEL |
| TEST-F | Test case family | TRACEABILITY_MATRIX §6 |
| EVID-F | Evidence artefact | TRACEABILITY_MATRIX §7 + EVIDENCE_PACK_SPEC |
| RC-F | Review Comment | reviews/ |
| IMP-F | Forward-queue enhancement | TRACEABILITY_MATRIX §13 |
| EVAL-F | AI evaluation gate | BRD §14.2 |
| RT-F | Trace Row bundle | TRACEABILITY_MATRIX §1 |
| OPT-F | Competitor option | COMPETITIVE_LANDSCAPE |
| R-F | Risk register entry | BRD §15 |
| NFR | Non-Functional Requirement | BRD §9 + TRACEABILITY_MATRIX §11 |
| CP | Checkpoint (mini-sprint commit) | BUILD_PLAN + LIVE docs |

---

## 5. Web + PWA in v1.x · Native iOS / Android deferred Phase 14+

**This is a key architectural commitment. It is on record in every relevant document so it cannot drift.**

Forensa's Operator Console (BR-14) is shipped in two tiers in v1.x:

1. **Tier 1 — Web** (Next.js 16 SSR / React 19) — `IMPLEMENTED+TESTED` for three screens at MVP level; CP9.52 closes the enterprise list-views pattern for full v1.x scope
2. **Tier 2 — PWA shell** (manifest.json + service worker on the same Next.js codebase) — `PLANNED` CP9.52f, installable to iOS Safari, Android Chrome, desktop Chrome / Edge / macOS Safari home screens

**Tier 3 — Native iOS / native Android Console clients are explicitly DEFERRED to Phase 14+.** They are a separate engineering investment (separate auth flow, separate app-store cycle, separate test matrix). Committing to native in v1.x would crowd out enterprise hardening (auth, RLS, KMS).

This commitment is recorded in:
- `02_brd/BRD.md` BR-14 AC-9
- `05_use_cases_and_user_stories/USE_CASES.md` US-F31 cross-reference
- `07_system_architecture/SYSTEM_ARCHITECTURE.md` §Console surface architecture
- `14_deployment_topology/DEPLOYMENT_TOPOLOGY.md` §Console deployment matrix + §Why native is Phase 14+
- `15_build_plan/BUILD_PLAN.md` Phase 14 row
- `20_glossary/GLOSSARY.md` Operator Console + PWA definitions
- `00_executive_brief/JUDGE_HANDOUT.md` §Operator Console

If a sponsor or stakeholder asks for native in v1.x, the conversation goes:

1. Acknowledge the ask
2. Point to the recorded commitment above
3. Show that PWA gives them "installs as an app on the home screen" without paying any of the native costs
4. Show the Phase 14 row in BUILD_PLAN and offer to negotiate Phase 14 entry conditions

---

## 6. Archival policy — git mv, not git rm

**Principle:** older versions of canonical docs that are superseded by v2.0 (or later) are **moved** into a `_archive/` subdirectory inside the same numbered folder. They are not deleted. They remain under version control.

Why:
- Cross-doc references (BR / UC / US / RT IDs) need to be resolvable historically. If someone reads an old commit message that says "closes US-F12", that ID must still mean the same thing.
- Traceability of changes — "what did v1 BRD say about BR-06?" must be answerable without `git log -p`
- Audit posture — regulators may ask to see what was claimed at submission time vs what was claimed three months later

How the archival names work:
- `BRD_v1.2_20260515_CP9.29.md` — version + date + closing CP at the time of archival
- `USE_CASES_v1_20260512.md` — version + date (CP not yet introduced at that point)
- `TRACEABILITY_MATRIX_v1_20260514_22h02.md` — version + date + last-sweep-time stamp

Archival index (mapping current → archived):

| Current doc | Archive (preserved verbatim) |
|---|---|
| `02_brd/BRD.md` (v2.0) | `02_brd/_archive/BRD_v1.2_20260515_CP9.29.md` |
| `05_use_cases_and_user_stories/USE_CASES.md` (v2.0) | `05_use_cases_and_user_stories/_archive/USE_CASES_v1_20260512.md` |
| `17_traceability_matrix/TRACEABILITY_MATRIX.md` (v2.0) | `17_traceability_matrix/_archive/TRACEABILITY_MATRIX_v1_20260514_22h02.md` |
| `00_executive_brief/EXECUTIVE_BRIEF.md` (refreshed 18 May) | `00_executive_brief/_archive/EXECUTIVE_BRIEF_v1_20260512.md` |
| `00_executive_brief/JUDGE_HANDOUT.md` (refreshed 18 May) | `00_executive_brief/_archive/JUDGE_HANDOUT_v1_20260512.md` |
| `07_system_architecture/SYSTEM_ARCHITECTURE.md` (with v2.0 addendum) | `07_system_architecture/_archive/SYSTEM_ARCHITECTURE_v1_20260512.md` |
| `14_deployment_topology/DEPLOYMENT_TOPOLOGY.md` (with v2.0 addendum) | `14_deployment_topology/_archive/DEPLOYMENT_TOPOLOGY_v1_20260512.md` |
| `15_build_plan/BUILD_PLAN.md` (with v2.0 addendum) | `15_build_plan/_archive/BUILD_PLAN_v1_20260512.md` |
| `16_testing_and_qa/TESTING_AND_QA.md` (with v2.0 addendum) | `16_testing_and_qa/_archive/TESTING_AND_QA_v1_20260512.md` |
| `06_regulatory_mapping/REGULATORY_MAPPING_MATRIX.md` (with v2.0 addendum) | `06_regulatory_mapping/_archive/REGULATORY_MAPPING_MATRIX_v1_20260512.md` |
| `20_glossary/GLOSSARY.md` (with v2.0 addendum) | `20_glossary/_archive/GLOSSARY_v1_20260512.md` |

**To execute the archival in git** (when this folder reshape is committed to the actual repo):

```bash
# Example for the BRD (do this once when committing the reshape):
git mv docs/02_brd/BRD.md docs/02_brd/_archive/BRD_v1.2_20260515_CP9.29.md
# then copy the new v2.0 BRD into place
git add docs/02_brd/BRD.md docs/02_brd/BRD_IDENTIFIER_MAP.md
git commit -m "docs: reshape v2.0 — BRD elaborated, identifier map, BR-14 Operator Console"
```

The `git mv` preserves blame and rename detection. **Never `rm` an archived doc.**

---

## 7. What changed in v2.0 (this work item)

The v2.0 elaboration is a structural rebuild, not a content rewrite. v1 content is preserved verbatim in `_archive/`; v2.0 elaborates the shape to mendoraci's enterprise-BRD pattern.

**Adds (entirely new in v2.0):**

- `02_brd/BRD_IDENTIFIER_MAP.md` — canonical identifier scheme
- `05_use_cases_and_user_stories/USE_CASES_LIVE.md` — live per-story progress companion
- `17_traceability_matrix/TRACEABILITY_MATRIX_LIVE.md` — live commit ledger + RT roll-up companion
- `21_traceability_workbook/Forensa_TraceabilityMaster_20260518.xlsx` — canonical workbook
- BR-14 (Operator Console — Web + PWA, native deferred Phase 14+) as first-class BR
- UC-09 (Operator console journey), UC-10 (Multi-tenant auth)
- US-F01..US-F32 numbered user stories
- SCR-F01..SCR-F10 console screen index
- RT-F19..RT-F22 trace bundles for Console / PWA / Tabletop+M&A+Narrative UI / Auth
- EVID-F01..EVID-F06 evidence artefact index
- BG-F01..BG-F06 business goals with BG → BR weighted contribution matrix
- R-F01..R-F12 risk register
- OPT-F01..OPT-F08 competitor options
- IMP-F\* forward queue per RT
- EVAL-F01, EVAL-F02 AI evaluation gates
- Rule A.11 (CP ↔ requirement closure)

**Refreshes (existing docs, structural pass-through + addenda):**

- BRD v1.2 → v2.0: full mendoraci shape (20 sections including Executive Summary, Identifier Map, Problem/Current/Target/Metrics, Stakeholders & Personas, Scope, Business Goals + BG→BR matrix, Functional Requirements with full AC/edge/negative/exit-gate per BR, Stories summary, NFRs, Phase plan replacing Day 1–6 calendar, Readiness Scorecard, Competitive matrix, Commercialisation, AI Necessity sub-sections, Risk Register, Data Governance Annex, Operational Readiness, Out of scope, Traceability, Change log) — and **supersession map (BRD §0.3)** recording where v1.2 narrative drifted from HEAD
- USE_CASES v1 → v2.0: 8 UCs preserved + UC-09 / UC-10 added; SCR-F index added; US-F01..F32 added with mendoraci shape
- TRACEABILITY_MATRIX v1 → v2.0: extended to 22-row 12-column matrix; added API→DB→Evidence, DB→migration→test, persona→RT, sponsor→BR+RT, regulator→BR+RT, NFR+RT cross-refs; IMP-F forward queue per RT
- EXECUTIVE_BRIEF refresh: scoreboard 9→10/13; CP9.51 cert chain; Operator Console + PWA + native deferred section
- JUDGE_HANDOUT refresh: matched updates; Operator Console + PWA section
- SYSTEM_ARCHITECTURE: v2.0 addendum on Console surface tiers + PWA + auth surface + API client-agnosticism
- DEPLOYMENT_TOPOLOGY: v2.0 addendum on Console deployment matrix + native-deferred rationale + PWA install matrix
- BUILD_PLAN: v2.0 addendum with CP-anchored phase plan + CP9.52 sub-sprint breakdown + Phase 10 auth sub-CPs + Rule A.11 compliance per row
- TESTING_AND_QA: v2.0 addendum on Playwright UI-driving plan (replaces today's API-driving) + PWA tests + auth tests
- REGULATORY_MAPPING_MATRIX: v2.0 addendum with RT-F cross-references per framework
- GLOSSARY: v2.0 addendum on identifier-prefix scheme + Console / PWA / Rule A.11 terminology

**Doc drift surfaced and named (not silently fixed):**

- v1.2 BRD narrative said BR-02 PARTIAL, BR-06 DEFERRED, BR-10/11 STUB → all actually IMPLEMENTED+TESTED at HEAD CP9.51. v2.0 BRD §0.3 (supersession map) records the discrepancy openly and re-syncs the narrative
- Calendar-anchored "Day 1..Day 6" timeline in v1.2 → replaced by CP-anchored phase plan in v2.0 BRD §10
- API_SPECIFICATION.md does not yet list `POST /v1/tabletop/simulate`, `POST /v1/tabletop/replay-window`, or `POST /v1/exports/ma-diligence` (CP9.28 / CP9.29 shipped backend without updating the canonical API doc) — recorded as Gap 11 and Gap 12 in `TRACEABILITY_MATRIX_LIVE.md` §3 for next light-task closure

---

## 8. Cross-document reference table

Use this when the same identifier is mentioned in multiple places, to find the authoritative definition.

| Identifier or concept | Defined in | Cross-referenced in |
|---|---|---|
| Any BR-N | `02_brd/BRD.md` §7 | TRACEABILITY_MATRIX §1, USE_CASES §5, REGULATORY_MAPPING |
| Any UC-N | `USE_CASES.md` §2 | TRACEABILITY_MATRIX §1, BRD §3 |
| Any US-FN | `USE_CASES.md` §4 | USE_CASES_LIVE §2, TRACEABILITY_MATRIX §3 |
| Any SCR-FN | `USE_CASES.md` §3 | SYSTEM_ARCHITECTURE §Console, TRACEABILITY_MATRIX §1 |
| Any RT-FN | `TRACEABILITY_MATRIX.md` §1 | TRACEABILITY_MATRIX_LIVE §2, BRD §15 (risk cross-ref) |
| Any API-FN | `08_api_specification/API_SPECIFICATION.md` | TRACEABILITY_MATRIX §4, openapi.json |
| Any DB-FN | `09_data_model/DATA_MODEL.md` | TRACEABILITY_MATRIX §5 |
| Any TEST-FN | `TRACEABILITY_MATRIX.md` §6 | TESTING_AND_QA |
| Any EVID-FN | `TRACEABILITY_MATRIX.md` §7 | EVIDENCE_PACK_SPEC |
| Any R-FN | `BRD.md` §15 | INCIDENT_RESPONSE_PLAN |
| Any OPT-FN | `BRD.md` §12 | COMPETITIVE_LANDSCAPE |
| Any EVAL-FN | `BRD.md` §14.2 | TESTING_AND_QA |
| Any IMP-FN | `TRACEABILITY_MATRIX.md` §13 | TRACEABILITY_MATRIX_LIVE §5, BUILD_PLAN |
| Any CPn.x | `BUILD_PLAN.md` Phase section | BRD §10 + change log; LIVE doc commit ledgers |
| Rule A.10 / A.11 | this README §0 + `BRD_IDENTIFIER_MAP.md` §4 | every editable doc top-of-file |

---

## 9. Workbook

`21_traceability_workbook/Forensa_TraceabilityMaster_20260518.xlsx` is the canonical multi-sheet workbook for the v2.0 identifier scheme. Sheets:

| Sheet | What |
|---|---|
| 00_README | Workbook readme + Rule A.10 + A.11 |
| 01_Identifier_Map | BRD_IDENTIFIER_MAP table reproduced as filterable spreadsheet |
| 02_BG_to_BR | Business goals + BG→BR contribution matrix |
| 03_BR_status | BR-01..BR-14 status board |
| 04_UC_status | UC-01..UC-10 status board |
| 05_US_status | US-F01..F32 with persona / BR / SCR / API / status / phase / CP |
| 06_SCR_index | SCR-F01..F10 with route / status / API / persona |
| 07_API_DB_Evidence | API → DB → Evidence map |
| 08_RT_index | RT-F01..F22 with full 12-column expansion |
| 09_TEST_coverage | TEST-F01..F40+ |
| 10_EVID_index | EVID-F01..F06 |
| 11_IMP_forward_queue | IMP-F\* by RT |
| 12_Risk_register | R-F01..F12 |
| 13_Change_log | full change log across docs |

---

## 10. How to resume this work if you're a future assistant or human

1. Read this README §0 carefully. Rule A.10 + Rule A.11 + LIVE update cadence are the most important things in the entire pack.
2. Read `BRD_IDENTIFIER_MAP.md` to anchor the identifier scheme.
3. Read `USE_CASES_LIVE.md` and `TRACEABILITY_MATRIX_LIVE.md` to see what's done and what's next at HEAD.
4. The next mini-sprint is **CP9.52a** — close US-F29 AC-1..AC-4 (Receipts list view with cursor pagination + filters + URL-query + sortable columns). Source files to edit are in `apps/web/` (Next.js); the backend API `GET /v1/receipts` is already wired.
5. After the commit lands, update §1 commit ledger and §2 RT roll-up of `TRACEABILITY_MATRIX_LIVE.md` and §2 US roll-up of `USE_CASES_LIVE.md` in the same shell session.
6. Then move to CP9.52b. And so on through CP9.52g, then CP9.53..CP9.58, then Phase 10.
