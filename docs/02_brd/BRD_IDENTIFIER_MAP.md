# Forensa — Identifier Map

**Doc:** 02b of 22 | **Companion to:** `BRD.md` | **Date stamp:** 2026-05-18 05:15 BST
**Status:** authoritative for all post-2026-05-18 identifiers
**Supersedes:** the implicit prefix scheme in `_archive/BRD_v1.2_20260515_CP9.29.md`

## 0. Purpose

This document is the single source of truth for identifier prefixes used across the Forensa docs. Every numbered ID in BRD, USE_CASES, TRACEABILITY_MATRIX, BUILD_PLAN, TESTING_AND_QA, GLOSSARY, the LIVE companion documents, and the traceability workbook draws from this table.

**Editorial rule (Rule A.10 inherited from project memory):** before adding a new identifier or changing an existing one, open this file. Identifiers that already exist must not be reassigned.

## 1. Prefix table

| Prefix | Meaning | Range allocated | Source |
|---|---|---|---|
| **BG** | Business Goal | BG-F01..BG-F06 | New in 005-01-H18 v2 |
| **BR** | Business Requirement | BR-01..BR-14 | BR-01..BR-13 pre-existing; **BR-14 (Operator Console — Web + PWA, mobile native deferred)** added 18 May 2026 |
| **UC** | Use Case | UC-01..UC-10 | UC-01..UC-08 pre-existing; **UC-09 (Operator console journey)** and **UC-10 (Multi-tenant authenticated access)** added 18 May 2026 |
| **US-F** | User Story | US-F01..US-F32 | New in 005-01-H18 v1 (17 May); extended to US-F32 in v2 (18 May) to cover Console/Web/PWA work |
| **SCR-F** | Screen (Console UI surface) | SCR-F01..SCR-F10 | New in 005-01-H18 v2 |
| **API-F** | Backend API endpoint | API-F01..API-F13 | API-F01..F10 derived from `apps/api/routes/*.py`; API-F11..F13 planned (auth, metrics, login) |
| **DB-F** | Database entity (table / migration) | DB-F01..DB-F12 | Derived from `alembic/versions/*.py` + ORM models |
| **TEST-F** | Test case | TEST-F01..TEST-F40+ | Pre-existing 38 test families in `tests/api/`, `tests/integration/`, `tests/packages/`; extended for Console journey + future surfaces |
| **EVID-F** | Evidence artefact (the product's own outputs) | EVID-F01..EVID-F06 | New in 005-01-H18 v2 |
| **RC-F** | Review Comment (from EnterpriseGradeReview cycle) | RC-F01..RC-F30 | Derived from `docs/reviews/` |
| **IMP-F** | Enhancement / forward-queue item | IMP-F01..IMP-F25+ | Derived from `NEW-P*.X` forward-queue items in LIVE traceability |
| **EVAL-F** | AI evaluation gate | EVAL-F01, EVAL-F02 | New — EVAL-F01 narrative quality, EVAL-F02 prompt-injection defence |
| **RT-F** | Trace Row (cross-cutting bundle) | RT-F01..RT-F22 | RT-F01..F18 pre-existing in LIVE traceability; RT-F19..F22 new for Console/Web/PWA/Auth |
| **OPT-F** | Competitor option | OPT-F01..OPT-F08 | Derived from `03_competitive_landscape/COMPETITIVE_LANDSCAPE.md` |
| **R-F** | Risk register entry | R-F01..R-F12 | New in 005-01-H18 v2 |
| **NFR** | Non-Functional Requirement | NFR-01..NFR-N | Pre-existing in BRD §9; numbering formalised in v2 |
| **NEW-P\<n\>.\<x\>** | Forward-queue item tied to a future Phase number | as needed | Pre-existing convention; mapped 1:1 to IMP-F\<N\> in v2 |
| **CP\<n\>.\<x\>** | Checkpoint (mini-sprint commit) | CP1.0..CP14.x+ | Pre-existing convention; **rule:** every CP must close ≥ 1 named requirement ID (BR-N / US-FN / UC-N / RT-FN / SCR-FN) — see §4 below |

## 2. Lookups for cross-doc readers

| If you see this in a doc | Look here |
|---|---|
| `BR-N` reference | `BRD.md` §7 |
| `UC-N` reference | `USE_CASES.md` §2 |
| `US-FN` reference | `USE_CASES.md` §4 (full story expansion) |
| `SCR-FN` reference | `USE_CASES.md` §3 (Screen index); detail in `07_system_architecture/SYSTEM_ARCHITECTURE.md` §Console |
| `API-FN` reference | `08_api_specification/API_SPECIFICATION.md` |
| `DB-FN` reference | `09_data_model/DATA_MODEL.md` |
| `TEST-FN` reference | `TRACEABILITY_MATRIX.md` §6 + `16_testing_and_qa/TESTING_AND_QA.md` |
| `EVID-FN` reference | `12_evidence_pack_spec/EVIDENCE_PACK_SPEC.md`; index in `TRACEABILITY_MATRIX.md` §7 |
| `RT-FN` reference | `TRACEABILITY_MATRIX.md` §1 (RT index, 12-column form) |
| `IMP-FN` reference | `TRACEABILITY_MATRIX.md` §13 forward queue |
| `EVAL-FN` reference | `BRD.md` §14.2 + `16_testing_and_qa/TESTING_AND_QA.md` |
| `R-FN` reference | `BRD.md` §15 risk register |
| `OPT-FN` reference | `BRD.md` §12 + `03_competitive_landscape/COMPETITIVE_LANDSCAPE.md` |
| `CPn.x` commit reference | `BUILD_PLAN.md` Phase section + `BRD.md` Change Log + `TRACEABILITY_MATRIX_LIVE.md` Commit Ledger |

## 3. Naming conventions

- **`-F` suffix on new prefixes** (US-F, SCR-F, RT-F, EVID-F, RC-F, IMP-F, EVAL-F, OPT-F, R-F): distinguishes Forensa-numbered IDs introduced in 005-01-H18 from BR/UC/NFR which pre-date this work item. Future docs may drop the `-F` if the project standardises, but the `-F` is preserved for now to keep audit-trail integrity against the archived v1 docs.
- **Zero-padded to two digits** for ranges ≤ 99 (e.g. `BR-14`, `US-F07`, `RT-F19`). Three digits if any range crosses 99.
- **No alphabetic suffixes inside a numbered ID**. If a story splits, use a new number; do not append `a` / `b` (this is the mendoraci pattern — see `MendoraCI_Traceability.md` RT-013, RT-014 not RT-013a / RT-013b).
- **CP numbering is project-private** to Forensa and follows the existing Phase scheme: `CP<phase>.<patch>`. CP9.51 is patch 51 of Phase 9.

## 4. The CP ↔ requirement closure rule (Rule A.11)

**This rule is the most important entry in this document.** A future maintainer reading this map must enforce it.

> **Every mini-sprint Checkpoint (CP) commit must close (or advance) at least one named requirement ID drawn from this map. The CP commit message names the ID(s) closed. The LIVE traceability document records the CP commit against those IDs.**
>
> A CP that does not close any named ID is not a tracked CP — it is engineering convenience. Engineering-convenience CPs are not forbidden, but they must be labelled as such (e.g. `CP9.52-tooling: refactor docker-compose`) and they do not advance the requirement scoreboard.

This rule is restated verbatim at the top of:
- `BRD.md` §0 (Rules)
- `USE_CASES.md` §0 (Rules)
- `TRACEABILITY_MATRIX.md` §0 (Rules)
- `TRACEABILITY_MATRIX_LIVE.md` §0 (Rules)
- `docs/README.md` Editorial principles

If you (a future assistant or human) catch yourself proposing a CP without naming the ID(s) it closes, **stop**. Re-read this map. Find or create the ID. Then propose the CP.

## 5. Cross-reference to mendoraci

The Forensa identifier scheme is structurally identical to the mendoraci prefix scheme (`MendoraCI_BRD.md` §2 "Identifier Map") with these adaptations:

- Forensa adds `EVID-F` because Forensa's product *is* evidence artefacts. Mendoraci has `EVID` too but uses it more narrowly.
- Forensa uses `RT-F` not `RT` to distinguish from mendoraci RT IDs in shared/template documents.
- Forensa does not use mendoraci's `PR` (Prompt version) — Forensa has a narrower AI surface (Gemini 2.5 Pro narrative client only) and tracks prompt versions in `packages/narrative/prompt.py` rather than as a top-level identifier.
- Mendoraci's `SCR` numbering is project-internal; Forensa's `SCR-F` numbering is independent.

## 6. Change log for this map

| Date | Change |
|---|---|
| 2026-05-18 05:15 BST | First version. Introduced BR-14, UC-09, UC-10. Introduced US-F\*, SCR-F\*, RT-F\*, EVID-F\*, RC-F\*, IMP-F\*, EVAL-F\*, OPT-F\*, R-F\* prefix families. Locked Rule A.11 (CP ↔ requirement closure). |
