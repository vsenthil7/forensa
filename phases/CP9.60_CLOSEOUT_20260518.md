# CP9.60 — CLOSEOUT (apply 6 pending zips + LIVE doc reconciliation)

**Pushed:** 2026-05-18 17:16 BST
**HEAD at start:** `d7d9aaa` (CP9.51)
**HEAD at close:** `626cd10`
**Net commits this CP:** 10 ([OPS] x 3, [FIX] x 1, [DOCS] x 4, [FEAT] x 3)

---

## What CP9.60 did

Apply six zips that had been authored by web Claude between 05:58 and 16:35 BST on 2026-05-18 but were sitting in `C:\Users\v_sen\Downloads\` unapplied to the working tree.

| Source zip | Effective payload | Landed as |
|---|---|---|
| `forsensa_claude_upgraded_BRD_usecase_tracibility_otherdocs_20260518_0558.zip` (379 KB) | Nested `forensa_docs_v2.0_20260518.zip` → 47 files in `forensa/docs/` (loose outer files were SHA-identical duplicates, dropped) | `b7c78cb` CP9.60a |
| `forensa_CP9.52_upgrade_20260518_1445.zip` (94 KB) | 56 files in `apps/console/` — Operator Console + PWA shell | `1b8a2f5` CP9.52 |
| `forensa_CP9.53-CP9.58_upgrade_20260518_1521.zip` (131 KB) | 76 files in `apps/console/` — 5 more screens (Anchors, Diligence, Narratives, Tabletop, Status) | `aefb18c` CP9.53..58 |
| `forensa_LIVE_doc_patches_20260518_1605.zip` (13 KB) | 2 LIVE doc files | SUPERSEDED by zip #6 (intentionally skipped) |
| `forensa_CP9.59_API-F15_metrics_20260518_1630.zip` (16 KB) | 6 files — API-F15 `/v1/metrics` + Status panel wire | SUPERSEDED by zip #6 (identical code) |
| `forensa_CP9.59_plus_LIVE_docs_20260518_1635.zip` (30 KB) | Same 6 code files + 2 newest LIVE doc updates | `321ceb7` CP9.59 |

Plus three engineering-convenience commits:
- `29eb35d` `[OPS] CP9.60 scripts/cp960_apply_tree.py` — zip-tree applier with backup discipline
- `1388501` `[FIX] CP9.60 backup path bug` — backup path now uses git-relative parent
- `fbdfe79` `[OPS] CP9.60 Dockerfile.test` — dev-deps test image for CI-parity pytest
- `0ad9183` `[OPS] CP9.60 scripts/cp960b_sweep_live_matrix.py` — LIVE SHA reconciler
- `b4403bc` `[DOCS] CP9.60b LIVE matrix SHA sweep`
- `626cd10` `[DOCS] CP9.60b self-reference fix`

---

## Requirements closed (per Rule A.11)

**BR scoreboard:** 10/13 BR-01..BR-13 + **BR-14 IMPLEMENTED+TESTED for v1.x scope** (8 of 9 screens, SCR-F09 Phase-10 by design).

| ID | Status before | Status after | Closed by |
|---|---|---|---|
| Rule A.11 (BRD §0.2) | not yet defined | LOCKED | `b7c78cb` CP9.60a |
| Supersession map for narrative drift (BR-02, BR-06, BR-10, BR-11) | informal | formal in BRD §0.3 | `b7c78cb` CP9.60a |
| US-F19 | not impl | IMPLEMENTED+TESTED | `1b8a2f5` CP9.52d |
| US-F28 | not impl | IMPLEMENTED+TESTED | `1b8a2f5` CP9.52e |
| US-F29 (AC-1..AC-9) | not impl | IMPLEMENTED+TESTED | `1b8a2f5` CP9.52a-b |
| US-F30 | not impl | IMPLEMENTED+TESTED | `1b8a2f5` CP9.52c |
| US-F31 | not impl | IMPLEMENTED+TESTED | `1b8a2f5` CP9.52f |
| RT-F19 (Console list-views-as-top-nav) | PLANNED | IMPLEMENTED+TESTED | `1b8a2f5` CP9.52 |
| RT-F20 (PWA shell) | PLANNED | IMPLEMENTED+TESTED | `1b8a2f5` CP9.52 |
| US-F16 (UI access for TSA anchor download) | not impl | IMPLEMENTED+TESTED | `aefb18c` CP9.53 |
| US-F23 (tabletop scenario sim) | not impl | IMPLEMENTED+TESTED | `aefb18c` CP9.55 |
| US-F26 (M&A diligence workspace) | not impl | IMPLEMENTED+TESTED | `aefb18c` CP9.56 |
| RT-F21 (investigation surface UI) | PLANNED | IMPLEMENTED+TESTED | `aefb18c` CP9.55+9.57 |
| SCR-F05 /anchors | not impl | IMPLEMENTED+TESTED | `aefb18c` CP9.53 |
| SCR-F06 /tabletop | not impl | IMPLEMENTED+TESTED | `aefb18c` CP9.55 |
| SCR-F07 /diligence | not impl | IMPLEMENTED+TESTED | `aefb18c` CP9.56 |
| SCR-F08 /narratives | not impl | IMPLEMENTED+TESTED | `aefb18c` CP9.57 |
| SCR-F10 /status (with API-F15 gap labelled) | partial / API-F15 placeholder | IMPLEMENTED+TESTED | `aefb18c` CP9.58 |
| API-F15 GET /v1/metrics | not impl | IMPLEMENTED+TESTED | `321ceb7` CP9.59 |
| SCR-F10 fully closed (real metrics wired) | partial | IMPLEMENTED+TESTED | `321ceb7` CP9.59 |
| Gap 14 (Status placeholder) | OPEN | CLOSED | `321ceb7` CP9.59 |
| BR-14 (Operator console) | partial | IMPLEMENTED+TESTED for v1.x | sum of above |

---

## Test gate results

| Suite | Result | Where |
|---|---|---|
| Console vitest (after CP9.52) | **146/146 @ 100/100/100/100 in 7.16s** | host |
| Console tsc --noEmit (after CP9.52) | **EXIT 0** | host |
| Console vitest (after CP9.53..58) | **210/210 @ 100/100/100/100 in 7.22s** | host |
| Console tsc --noEmit (after CP9.53..58) | **EXIT 0** | host |
| API pytest `test_metrics_route.py` (after CP9.59) | **8/8 in 3.24s** | host (poetry) |
| API pytest `test_metrics_route.py` (after CP9.59) | **8/8 in 2.91s** | Docker (CI parity) |
| Full pytest suite | **1148 passed / 1 pre-existing flake / 59 skipped (real-PG + live-TSA)** | host + Docker (same numbers) |

**The 1 pre-existing flake** is an asyncio event-loop-leak ordering issue:
- Host = `test_lobstertrap_client_is_abstract` (CP9.32 origin, not touched today)
- Container = `test_create_job_rejects_inverted_scope` (CP9.43 origin, not touched today)
- Both pass in isolation → classic pytest-asyncio strict-filterwarnings flake
- Pre-existed at HEAD `d7d9aaa` before CP9.60

**No regression introduced by CP9.60.**

---

## Backup discipline applied

- 31 doc files backed up in `_backup/docs/<rel>/<file>_20260518-1653.<ext>` (after path-bug fix in `1388501`)
- 28 console files backed up in `_backup/apps/console/<rel>/<file>_20260518-1658.<ext>` for CP9.52
- 55 console files backed up in `_backup/apps/console/<rel>/<file>_20260518-1705.<ext>` for CP9.53..58
- 6 mixed files backed up in `_backup/<rel>/<file>_20260518-1708.<ext>` for CP9.59
- 1 LIVE doc backed up at `_backup/docs/17_traceability_matrix/TRACEABILITY_MATRIX_LIVE_20260518-1715.md` before CP9.60b

Initial backups for CP9.60a landed at the slightly-shallow path `_backup/02_brd/…` (missing the `docs/` prefix). These were manually moved to `_backup/docs/02_brd/…` at 16:59. The script was fixed (commit `1388501`) so all subsequent applies (CP9.52, CP9.53..58, CP9.59) wrote backups to the rule-correct path.

---

## What is now in the working tree (committed + pushed)

- `apps/console/` — 8 of 9 v1.x screens (Persona, Receipts list + detail, Evidence pack, Anchors, Diligence, Narratives, Tabletop, Status) + PWA manifest + service worker + offline banner; 17 components, 210 vitest tests at 100/100/100/100, 210 Playwright across 3 device projects
- `apps/api/routes/metrics.py` + `tests/api/test_metrics_route.py` — new GET /v1/metrics endpoint, 8 pytest tests
- `docs/` — full v2.0 elaborated doc pack (BRD 486 lines, USE_CASES 328 lines, TRACEABILITY_MATRIX 241 lines, both LIVE companions, 13-sheet workbook, 12 _archive/ snapshots, 3rd-pass enterprise-grade review at HEAD 96c5d60)
- Rule A.11 LOCKED in BRD §0.2

---

## What remains open (handed forward, per Rule A.11 forward queue)

| CP | IDs to close | Scope |
|---|---|---|
| `CP10.1` | US-F32 partial, DB-F08, API-F14, SCR-F09, RT-F22 advance | Auth surface MVP: `/login` page + `POST /v1/auth/login` + `users` / `sessions` tables |
| `CP10.2` | US-F32 close, RC-F26, RT-F22 close | Tenant picker + token-derived tenant |
| `CP10.3` | NFR-10 close | Postgres row-level security policies |
| `CP10.4` | UC-10 close | Full multi-tenant auth E2E |
| `CP11.x` | Phase 11 observability sweep | Signing latency p50/p95/p99 request middleware |
| `CP-doc1` | Gap 11 + Gap 12 close | API_SPECIFICATION refresh with new POST/GET endpoints |
| `CP-flake-fix` | Pre-existing pytest-asyncio flake | Triage `test_lobstertrap_client_is_abstract` / `test_create_job_rejects_inverted_scope` event-loop ordering issue |

---

## Honest closing note

This CP was a **reconciliation CP** — taking work that web Claude had authored over several preceding sessions and grounding it in the actual git repo. No new feature work was done; six pre-authored upgrades were applied with backup discipline, tested, committed, pushed, and traced. The hard work (writing 17 console components, building API-F15 metrics, drafting BRD v2.0) was done by web Claude. CP9.60 was the careful application of that work.

The discipline that matters most here: **Rule A.11 is now LOCKED in BRD §0.2** and every commit landed today names the IDs it closed. The LIVE traceability matrix is grounded against `origin/main` HEAD `626cd10` with real SHAs in every row.

**Tests green. Backups preserved. Origin in sync. CP9.60 closed.**
