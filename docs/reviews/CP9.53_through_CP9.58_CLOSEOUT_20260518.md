# CP9.53 → CP9.58 — Remaining Operator Console screens

**Commit message stub** (per Rule A.11):

```
CP9.53..9.58: Anchors / Diligence / Narratives / Tabletop / Status

Closes US-F16 (UI access), US-F26, US-F23, RT-F21.
Advances SCR-F05, SCR-F06, SCR-F07, SCR-F08, SCR-F10 to IMPLEMENTED+TESTED.
Closes BR-14 v1.x scope (all 8 Console-relevant screens, excluding SCR-F09 auth).

Components added (5):
  - AnchorsList (SCR-F05, US-F16) — list of daily TSA anchors with
    Download-TSR-DER button that sets Accept: application/timestamp-reply.
  - DiligenceWorkspace (SCR-F07, US-F26) — create / list / view / download
    bundle; auto-polls while jobs are pending or running.
  - NarrativeViewer (SCR-F08) — window picker + Generate Narrative;
    surfaces the 4-layer defence 422 incident_id pattern from BR-10.
  - TabletopSimulator (SCR-F06, US-F23) — paste TabletopScenario JSON,
    run, render per-action verdicts + summary counts. Power-user UX
    chosen because action payloads are open-ended dicts.
  - StatusDashboard (SCR-F10) — what /healthz shows today + clearly
    labelled "API-F15 planned" placeholders for the ops-metrics panels
    (ingest rate, signing latency, anchor success/failure, chain
    integrity sparkline). Honest about what's wired.

Pages: /anchors, /diligence, /narratives, /tabletop, /status.

TopNav: all five planned-disabled labels removed; every link in
DEFAULT_NAV_ITEMS now resolves to a real page. The `planned: true`
rendering path is preserved in TopNav.tsx for future RT-F* items
and is unit-tested via a custom items prop.

Tests
  - 210 vitest tests passing (17 test files); 100% coverage on 17
    components against the strict 100/100/100/100 gate.
  - 210 Playwright tests across 3 device projects × 14 spec files
    (desktop Chrome + iPhone 15 WebKit + Pixel 7 Chromium).
  - TypeScript: tsc --noEmit clean.

Honest gaps named in the v2.0 forward queue and NOT closed:
  - API-F15 GET /v1/metrics: not yet built. Status page surfaces
    /healthz only; the operational-metrics panels are explicit
    "API-F15 planned" placeholders, not stubs.
  - SCR-F09 /login + tenant picker: explicitly DEFERRED Phase 10
    CP10.1..CP10.4 per the v2.0 plan. UC-10 itself is DEFERRED.
```

---

## Cumulative scoreboard (after CP9.52 + this batch)

| ID | Status | Closed by |
|---|---|---|
| US-F19 | ✅ IMPLEMENTED+TESTED | CP9.52d |
| US-F28 | ✅ IMPLEMENTED+TESTED | CP9.52e |
| US-F29 (AC-1..AC-9) | ✅ IMPLEMENTED+TESTED | CP9.52a-b |
| US-F30 | ✅ IMPLEMENTED+TESTED | CP9.52c |
| US-F31 | ✅ IMPLEMENTED+TESTED | CP9.52f |
| **US-F16 (UI access)** | ✅ IMPLEMENTED+TESTED | **CP9.53** |
| **US-F23** | ✅ IMPLEMENTED+TESTED | **CP9.55** |
| **US-F26** | ✅ IMPLEMENTED+TESTED | **CP9.56** |
| US-F32 | ⏸ DEFERRED Phase 10 | CP10.1..CP10.4 |
| RT-F19 | ✅ IMPLEMENTED+TESTED | CP9.52a-b |
| RT-F20 | ✅ IMPLEMENTED+TESTED | CP9.52f |
| **RT-F21** | ✅ IMPLEMENTED+TESTED | **CP9.55 + CP9.57** |
| RT-F22 | ⏸ DEFERRED Phase 10 | CP10.1..CP10.4 |
| SCR-F01 | ✅ IMPLEMENTED+TESTED | CP9.52e |
| SCR-F02 | ✅ IMPLEMENTED+TESTED | CP9.52a-b |
| SCR-F03 | ✅ IMPLEMENTED+TESTED | CP9.52c |
| SCR-F04 | ✅ IMPLEMENTED+TESTED | CP9.52d |
| **SCR-F05** | ✅ IMPLEMENTED+TESTED | **CP9.53** |
| **SCR-F06** | ✅ IMPLEMENTED+TESTED | **CP9.55** |
| **SCR-F07** | ✅ IMPLEMENTED+TESTED | **CP9.56** |
| **SCR-F08** | ✅ IMPLEMENTED+TESTED | **CP9.57** |
| SCR-F09 | ⏸ DEFERRED Phase 10 | CP10.1 |
| **SCR-F10** | ✅ IMPLEMENTED+TESTED (with API-F15 gap) | **CP9.58** |
| BR-14 | ✅ IMPLEMENTED+TESTED for v1.x scope | CP9.52 + CP9.53..9.58 |

**8 of 9 SCR-F screens shipped.** SCR-F09 is by-design Phase-10 work.

---

## LIVE traceability matrix updates

Append to `docs/17_traceability_matrix/TRACEABILITY_MATRIX_LIVE.md` §1 commit ledger:

```
| <new sha> | <date> | **CP9.53** | **US-F16 (UI access), SCR-F05** | /anchors list view with Download-TSR-DER button; full TSA verification UX. |
| <new sha> | <date> | **CP9.55** | **US-F23, SCR-F06, RT-F21 advance** | /tabletop simulator; paste scenario JSON, run, render verdicts + summary. |
| <new sha> | <date> | **CP9.56** | **US-F26, SCR-F07** | /diligence workspace; create/list/view/download bundle with auto-polling. |
| <new sha> | <date> | **CP9.57** | **SCR-F08, RT-F21 close** | /narratives viewer; window picker + 4-layer defence 422 incident UI. |
| <new sha> | <date> | **CP9.58** | **SCR-F10 partial (API-F15 gap)** | /status dashboard from /healthz; ops-metrics panels labelled "API-F15 planned". |
```

§2 RT roll-up: flip RT-F21 from `🔵 PLANNED` to `✅ IMPLEMENTED+TESTED`.

§3 honest gaps: close Gap 8 fully (all RT-F19..F21 now green); leave Gap 11 / Gap 12 (API spec drift) open as documented; **add new Gap 14: API-F15 `GET /v1/metrics` not yet built; /status surfaces /healthz only and labels missing panels.**

§4 forward queue: remove CP9.53..9.58 rows. CP10.1..CP10.4 (Phase 10 auth) remains.

---

## How to validate locally

```powershell
cd apps/console
npm install
npx vitest run --coverage       # 210/210 passing, 100% across 17 components
npx tsc --noEmit                # 0 errors
npx playwright test --list      # 210 tests in 14 spec files
```

Live Playwright (needs API + Next dev + optional seed):
```powershell
poetry run python scripts\seed_demo_data.py
$env:FORENSA_TENANT_ID = "<from seed>"
$env:FORENSA_TOKEN = "<from seed>"
npx playwright install chromium webkit
npx playwright test
```

Specs requiring real data skip cleanly when the seed env vars are
unset, so a no-seed sanity run still validates every structural
assertion (page mounts, form validation, planned-link state).

---

## Files added in this batch (CP9.53..CP9.58)

```
apps/console/src/components/
  AnchorsList.tsx              + tests
  DiligenceWorkspace.tsx       + tests
  NarrativeViewer.tsx          + tests
  TabletopSimulator.tsx        + tests
  StatusDashboard.tsx          + tests

apps/console/src/app/
  anchors/page.tsx
  diligence/page.tsx
  narratives/page.tsx
  tabletop/page.tsx
  status/page.tsx

apps/console/tests-e2e/
  anchors.spec.ts
  diligence.spec.ts
  narratives.spec.ts
  tabletop.spec.ts
  status.spec.ts

apps/console/src/components/TopNav.tsx       (modified — all promotions)
apps/console/tests-e2e/topnav.spec.ts        (modified — reflects active state)
apps/console/src/components/__tests__/TopNav.test.tsx  (modified)
```

## What is preserved (the supersedence pair)

`ReceiptList.tsx`, `ReceiptDetail.tsx`, `EvidencePack.tsx` and their tests
remain untouched (kept from CP9.52). Phase 10 cleanup can remove them
after a deprecation window.
