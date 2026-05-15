# NEXT SESSION PROMPT — Forensa, written 2026-05-15 10:06 +01:00

You are Claude. You are working on the Forensa hackathon project. The hackathon submission deadline is Monday 19 May 2026 (3 days from now).

**Operating directory:** `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa`
**Repo:** `github.com/vsenthil7/forensa`
**Branch:** `main`
**HEAD at this prompt's write-time:** `45b0534` on `origin/main`
**Rules:** `C:\Users\v_sen\Documents\Projects\claude-memory\global\CLAUDE_RULES.md` — READ FIRST, state all 14 as a numbered checklist before any other action.

---

## TL;DR for the next instance of Claude

**Phase 9 is CLOSED.** Submission-week polish is **5 artefacts in**. The product is on `origin/main` at HEAD `45b0534`. BR scoreboard: **9/13 IMPLEMENTED+TESTED**. Default suite: 878 passed. PG-mode: 904 passed. Coverage: 100%.

This morning's session (09:42 → 10:06) landed 5 submission-week docs/scripts in 24 minutes:

| Commit | Artefact |
|---|---|
| `9075602` | README.md submission-grade rewrite (first thing a judge sees on GitHub) |
| `0831bcb` | docs/00_executive_brief/JUDGE_HANDOUT.md (one-pager for the pitch room) |
| `34d4cc4` | docs/00_executive_brief/SUBMISSION_VIDEO_SCRIPT.md (5-min spoken-word pitch + Q&A cheat sheet) |
| `565f826` | docs/00_executive_brief/EXECUTIVE_BRIEF.md v2 (revised to reflect what shipped) |
| `45b0534` | tools/demo.sh + tools/demo.ps1 (runnable 4-step verification flow for the recording) |

**Three remaining submission-week tasks before Monday 19 May:**

1. **Record the submission video** using the script at `docs/00_executive_brief/SUBMISSION_VIDEO_SCRIPT.md` + the demo at `tools/demo.sh`. Target 5 min, 1080p, MP4. Filename: `forensa_submission_v1_20260518.mp4`. **User action, not Claude.**
2. **Seed-data script** at `scripts/seed_demo_data.py` so a fresh checkout can run `tools/demo.sh` end-to-end. Creates 1 tenant + 5 events spread over 2 days + 1 anchored day with a synthetic-but-cryptographically-valid TSA proof. **Claude task, ~30 min.**
3. **CI badge + LICENSE file polish** in the repo root for judge professionalism. **Claude task, ~15 min.**

---

## Mandatory first 6 actions (in order, before any code work)

1. **Write context_log file 007** at `phases/context_log/007_<slug>_YYYYMMDD-HHMM.md` BEFORE any other action.
2. **Read CLAUDE_RULES.md** and state the 14 rules as a numbered checklist.
3. **Shell-stamp SESSION_START** via `Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'`.
4. **Stamp repo state**:
   ```powershell
   cd C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa
   git log --oneline -8
   git status --short
   git ls-remote origin main
   ```
   Expected: HEAD `45b0534`, clean working tree, remote matches local.
5. **Read** `phases/PHASES_DONE_PHASE9_fe8e394_20260515-0933.md` to load the full Phase 9 closure picture.
6. **Read** this file + the 5 submission-week artefacts from the morning's commits (README + JUDGE_HANDOUT + SUBMISSION_VIDEO_SCRIPT + EXECUTIVE_BRIEF + tools/demo.sh) so you have the full submission-pack context.

---

## Current state snapshot at HEAD `45b0534`

- **Default suite:** 878 passed, 26 PG-skipped, 100% coverage gate held.
- **PG-mode suite:** 904 passed (verified at HEAD `fe8e394`, unchanged since because all commits since are docs-only).
- **BR scoreboard:** **9/13 IMPLEMENTED+TESTED**. 4 STUB DEFERRED, 1 PARTIAL → CP12.4.
- **Lint/format/types:** all green (`ruff check` + `ruff format --check` + `mypy --strict`).
- **Submission-week artefacts:** 5/8 done.

Last 10 commits:
```
45b0534 [DOCS] tools/demo.sh + tools/demo.ps1 - runnable submission-demo scripts
565f826 [DOCS] EXECUTIVE_BRIEF.md v2 - revised at Phase 9 close-out to reflect what actually shipped
34d4cc4 [DOCS] docs/00_executive_brief/SUBMISSION_VIDEO_SCRIPT.md - 5-minute pitch narrative
0831bcb [DOCS] docs/00_executive_brief/JUDGE_HANDOUT.md - one-pager for the TechEx pitch room
9075602 [DOCS] README.md submission-grade rewrite at HEAD 7bbca8e
7bbca8e [DOCS] phases/NEXT_SESSION_PROMPT_20260515_0937.md
1c656e0 [DOCS] PHASES_DONE_PHASE9_fe8e394_20260515-0933.md - Phase 9 close-out
fe8e394 [VERIFY] CP9.26 PG-mode verification re-run at HEAD 67b6bca - all green
67b6bca [FEAT] CP9.27 NEW-P9.22.anchor-detail-endpoint
c9d34b9 [FEAT] CP9.24 wire anchor lookup into GET /v1/evidence-packs
```

---

## Operating rules (compressed)

1. Session start/end shell-stamped via `Get-Date`.
2. Every task start/end shell-stamped; 30-min hard stop per task; 29-min warning REQUIRED. **Each new user prompt = new 30-min budget**, not cumulative.
3. NO scope shrinking — every finding → CLOSED-CPx / TRACKED-Pxx / NEW-Pxx / WONT-DO / RETRACTED.
4. EDIT → COMMIT → PUSH → TEST → fix-loop autonomous.
5. 100% pytest coverage (`--cov-fail-under=100`).
6. BACKUP files to `_backup/<file>_YYYYMMDD-HHMM` BEFORE edit.
7. Context_log file on disk BEFORE any other action.

**Commit messages** go to `C:\Users\v_sen\Documents\Projects\claude-memory\global\commit_messages\YYYY-MM-DD_<slug>.txt`.

**Path prefix:**
```powershell
$env:PATH = 'C:\Users\v_sen\AppData\Roaming\Python\Python314\Scripts;' + $env:PATH
```

---

## Priority work for this session (ASK USER, but if user says "continue" pick A)

**A) Seed-data script** at `scripts/seed_demo_data.py` (~30 min). The demo scripts at `tools/demo.{sh,ps1}` require an existing tenant + Receipts + at least one anchor row in the scope window. A fresh-checkout user can't run them. Seed script creates:
- 1 tenant with a stub signing key
- 5 events spread across `2026-05-13` and `2026-05-14` (3 + 2)
- A complete chain of 5 Receipts via the full ingest pipeline
- 1 anchored TimestampAnchorRow for `2026-05-14` with a synthetic-but-cryptographically-valid TSR (use the existing test TSA mock or generate one with `cryptography`'s certificate machinery)
- Prints the tenant_id at the end so the user can paste it into `FORENSA_TENANT_ID` and run `tools/demo.sh`

Tests required: 4-6 covering (a) seeds run on empty DB, (b) idempotent on re-run, (c) anchor row binds correctly, (d) the demo script's curl chain succeeds end-to-end against the seeded data (this is essentially an integration test of the demo arc).

**B) CI badge + LICENSE polish** (~15 min). README references `LICENSE` but the file may not be properly MIT-formatted; CI status badge from GitHub Actions is missing from the README header. Pure cosmetic but high judge-visibility.

**C) Final repo housekeeping** (~30 min):
- `.github/PULL_REQUEST_TEMPLATE.md` for future contributors
- `.github/ISSUE_TEMPLATE/bug_report.md` + `feature_request.md`
- `CONTRIBUTING.md` referencing the CP discipline
- `CODE_OF_CONDUCT.md` (standard Contributor Covenant)

**D) Phase 10 starter work** (post-submission scope):
- CP10.1 Real auth provider integration (Auth0/Okta)
- CP10.2 KMS adapter for tenant signing keys
- CP10.3 PostgreSQL Row-Level Security policies

**Recommendation:** A > B > C > D. A unlocks the demo recording (which the user needs to do over the weekend). B + C are repo polish. D is post-submission work and should NOT be started until after Monday.

---

## Open TRACKED-Pxx items (NO silent drops)

Same set as the prior NEXT_SESSION_PROMPT (HEAD `7bbca8e`). 25 items across P10/P11/P12/P13. Full inventory in `phases/PHASES_DONE_PHASE9_fe8e394_20260515-0933.md` NEW-Pxx tally section.

New item surfaced this morning:
- `NEW-P10.X.demo-script-integration-test` - Playwright test that pre-flights `tools/demo.sh` against a seeded environment so future API-shape changes can't silently break the demo arc. ~1 day work; not hackathon-window. (Named in the `45b0534` commit message.)

---

## Path inventory (verbatim, all live on origin/main at `45b0534`)

**Submission-week artefacts (this morning's session):**
- `README.md` — submission-grade rewrite
- `docs/00_executive_brief/EXECUTIVE_BRIEF.md` — v2, Phase 9-aware
- `docs/00_executive_brief/JUDGE_HANDOUT.md` — pitch-room one-pager
- `docs/00_executive_brief/SUBMISSION_VIDEO_SCRIPT.md` — 5-min spoken-word script
- `tools/demo.sh` — bash 4-step verification flow
- `tools/demo.ps1` — PowerShell companion

**Production code surface (unchanged since Phase 9 close):** see prior NEXT_SESSION_PROMPT for full list.

**phases/ status-doc series (newest at top):**
- `phases/NEXT_SESSION_PROMPT_20260515_1006.md` (this file)
- `phases/PHASES_DONE_PHASE9_fe8e394_20260515-0933.md` (Phase 9 close-out)
- `phases/PHASES_REVIEW_BEFORE_AFTER_20260515_0902.md`
- `phases/ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md`

**Context-log audit trail:**
- `phases/context_log/001..006_*.md` (six logs landed)
- Next: `phases/context_log/007_<slug>_<stamp>.md`

---

## Notes carried forward

- PowerShell wraps git stderr as "RemoteException" — push success in the `OLDHEAD..NEWHEAD  main -> main` line.
- BR scoreboard flips only happen STUB/PARTIAL → IMPLEMENTED+TESTED; deepening doesn't count.
- Each new user prompt resets the 30-min task budget.
- Tool-use limits can interrupt mid-CP — commit early, note working-tree state.
- The demo scripts at `tools/demo.{sh,ps1}` require `FORENSA_TENANT_ID` + `FORENSA_TOKEN` env vars; the seed-data script (Priority A) closes the gap.
- Submission video target: 5 min, 1080p, MP4, filename `forensa_submission_v1_20260518.mp4`.

**End of next-session prompt.**
