# NEXT SESSION PROMPT — Forensa, written 2026-05-15 11:32 +01:00

You are Claude. You are working on the Forensa hackathon project. The hackathon submission deadline is Monday 19 May 2026 (3.5 days from now).

**Operating directory:** `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa`
**Repo:** `github.com/vsenthil7/forensa`
**Branch:** `main`
**HEAD at this prompt's write-time:** `d14921a` on `origin/main`
**Rules:** `C:\Users\v_sen\Documents\Projects\claude-memory\global\CLAUDE_RULES.md` — READ FIRST, state all 14 as a numbered checklist before any other action.

---

## TL;DR for the next instance of Claude

**Phase 9 + post-Phase 9 push are CLOSED at 10/13 IMPLEMENTED+TESTED.** Today's wall-clock from 09:42 to 11:31 (≈110 min across three task blocks) shipped 5 submission-week artefacts + 2 BR flips + 1 doc arithmetic truth-up = **8 commits** without breaking the 100% coverage gate.

| Commit | What |
|---|---|
| `9075602` | README.md submission-grade rewrite |
| `0831bcb` | JUDGE_HANDOUT.md one-pager |
| `34d4cc4` | SUBMISSION_VIDEO_SCRIPT.md (5-min pitch + Q&A cheat sheet) |
| `565f826` | EXECUTIVE_BRIEF.md v2 (Phase 9-aware) |
| `45b0534` | tools/demo.sh + tools/demo.ps1 (runnable 4-step verification flow) |
| `5a3ddbf` | NEXT_SESSION_PROMPT_20260515_1006.md (prior handoff) |
| `dc62fd0` | **CP9.28** BR-13 M&A due diligence export (STUB → IMPL+TESTED) |
| `52f8b4a` | BRD + PHASES_DONE_PHASE9 arithmetic truth-up (off-by-one fix) |
| `d14921a` | **CP9.29** BR-12 tabletop incident-response simulation (DEFERRED → IMPL+TESTED) |

**BR scoreboard at HEAD `d14921a`:**
- **10/13 IMPLEMENTED+TESTED:** BR-01, BR-02, BR-03, BR-04, BR-05, BR-06, BR-10, BR-11, BR-12, BR-13
- **1 PARTIAL:** BR-09 (in-process throughput IMPL+TESTED; Kafka path → CP12.4)
- **2 DEFERRED by design:** BR-07 LangGraph multi-agent + BR-08 Omniverse physical-action replay

**Default-mode suite:** 914 passed, 26 PG-skipped, 100% line+branch coverage gate held.
**PG-mode suite:** 904 passed (last verified at HEAD `fe8e394`; no DB-layer code changed since).
**Lint/format/types:** `ruff check` + `ruff format --check` + `mypy --strict` all clean across 56 source files.

---

## Three remaining submission-week tasks before Monday 19 May

1. **Record the submission video** using `docs/00_executive_brief/SUBMISSION_VIDEO_SCRIPT.md` + `tools/demo.sh`. Target 5 min, 1080p, MP4. Filename: `forensa_submission_v1_20260518.mp4`. **USER ACTION, not Claude.**
2. **Seed-data script** at `scripts/seed_demo_data.py` so a fresh checkout can run `tools/demo.sh` end-to-end. Creates 1 tenant + 5 events + 1 anchored TimestampAnchorRow with synthetic-but-valid TSR. **CLAUDE TASK, ~30 min.** Priority A.
3. **CI badge + LICENSE polish** in repo root. **CLAUDE TASK, ~15 min.** Priority B.

---

## Mandatory first 6 actions (in order, before any code work)

1. **Write context_log file 009** at `phases/context_log/009_<slug>_YYYYMMDD-HHMM.md` BEFORE any other action.
   - **WARNING from this session:** soft Rule 7 violation happened in CP9.29 — context_log 008 was written retro-actively at 11:27 instead of before the 11:10 prompt's task started at 11:11. Don't repeat. Each new user prompt = new context_log immediately.
2. **Read CLAUDE_RULES.md** and state the 14 rules as a numbered checklist.
3. **Shell-stamp SESSION_START** via `Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'`.
4. **Stamp repo state**:
   ```powershell
   cd C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa
   git log --oneline -10
   git status --short
   git ls-remote origin main
   ```
   Expected: HEAD `d14921a`, clean working tree, remote matches local.
5. **Read** `docs/02_brd/BRD.md` to load the 10/13 scoreboard + every BR's IMPL+TESTED detail.
6. **Read** this file + the most recent commits' messages from `C:\Users\v_sen\Documents\Projects\claude-memory\global\commit_messages\2026-05-15_*.txt` for full context.

---

## Priority work for this session (Claude picks if user says "continue")

**A) Seed-data script** at `scripts/seed_demo_data.py` (~30 min). The demo scripts at `tools/demo.{sh,ps1}` require an existing tenant + Receipts + at least one anchor row in the scope window. A fresh-checkout user can't run them. Seed script creates:
- 1 tenant with a stub signing key
- 1 policy bundle in `active` status with content_hash
- 5 events spread across `2026-05-13` and `2026-05-14` (3 + 2)
- A complete chain of 5 Receipts via the full ingest pipeline
- 1 anchored TimestampAnchorRow for `2026-05-14` with a synthetic-but-cryptographically-valid TSR
- Prints the tenant_id + bundle_id at the end so the user can paste them into `FORENSA_TENANT_ID` + scenario JSON

Tests required: 4-6 covering (a) seeds run on empty DB, (b) idempotent on re-run, (c) anchor row binds correctly, (d) the demo script's curl chain succeeds end-to-end against the seeded data.

**B) CI badge + LICENSE polish** (~15 min). Pure cosmetic but high judge-visibility.

**C) Phase 9.30 PG-mode re-verification** (~10 min). Run the suite with `FORENSA_TEST_DB_URL` set and confirm 904+19=923 passes (or higher) at HEAD `d14921a`. The 19 new tests from CP9.28+CP9.29 don't touch the DB layer so the PG-mode count should be 904+0 PG-only + 19 new default-mode = effectively re-confirms 904 PG-only. Useful pre-submission verification.

**D) Final submission packaging** (post-Monday only). PHASES_DONE_PHASE9 update reflecting the 9→10 flip; PHASES_DONE_POST9_PUSH companion doc; final README scoreboard refresh.

**Recommendation:** A > C > B > D. A unlocks the demo recording (user needs to do over the weekend). C is cheap and validates the BR-12 + BR-13 code against real Postgres. B is repo polish. D is post-submission.

---

## Operating rules (compressed)

1. Session start/end shell-stamped via `Get-Date`.
2. Every task start/end shell-stamped; 30-min hard stop per task; 29-min warning REQUIRED. **Each new user prompt = new 30-min budget**, not cumulative.
3. NO scope shrinking — every finding → CLOSED-CPx / TRACKED-Pxx / NEW-Pxx / WONT-DO / RETRACTED.
4. EDIT → COMMIT → PUSH → TEST → fix-loop autonomous.
5. 100% pytest coverage (`--cov-fail-under=100`).
6. BACKUP files to `_backup/<file>_YYYYMMDD-HHMM` BEFORE edit.
7. Context_log file on disk BEFORE any other action.

**Soft violations this session (honest disclosure):**
- Rule 6 partial: `apps/api/main.py` was edited twice in CP9.28 + CP9.29 with only one pre-edit backup (the 1033 one captures pre-CP9.28). Full reconstructability via git history. Documented in context_log 008.
- Rule 7 partial: context_log 008 was written retro-actively at 11:27 instead of before the 11:10 task started at 11:11. Documented honestly inside the log itself.

These are documented as soft violations rather than swept under the rug. **Next instance: don't repeat. Always context_log BEFORE any other action; always pre-edit backup before every edit (not just the first edit of a multi-edit chain).**

**Commit messages** go to `C:\Users\v_sen\Documents\Projects\claude-memory\global\commit_messages\YYYY-MM-DD_<slug>.txt`.

**Path prefix:**
```powershell
$env:PATH = 'C:\Users\v_sen\AppData\Roaming\Python\Python314\Scripts;' + $env:PATH
```

---

## Open TRACKED-Pxx items (NO silent drops, surfaced this session)

New items from CP9.28 (BR-13):
- `NEW-P10.X.ma-export-encryption-at-rest` - encrypt the M&A bundle with the acquirer's public key
- `NEW-P11.X.ma-export-detached-platform-signature` - Forensa platform-key signature over the bundle
- `NEW-P12.X.ma-export-async-job` - async-job mode for very large windows
- `NEW-P12.X.ma-export-streaming` - multipart S3 upload for very large bundles

New items from CP9.29 (BR-12):
- `NEW-P11.X.tabletop-bundle-from-storage` - target draft/proposed bundles from approval workflow
- `NEW-P12.X.tabletop-replay-real-events` - read-only replay of historical events against candidate bundle
- `NEW-P12.X.tabletop-diff-report` - compare simulated vs actual decisions surfaced as diff

Repo-tenant-scoping carried forward from prior sessions:
- `NEW-P10.X.repo-tenant-scoping` - push tenant filters into every repository helper at the SQL layer
- `NEW-P10.X.demo-script-integration-test` - Playwright pre-flight of tools/demo.sh against seeded env

Full inventory in `phases/PHASES_DONE_PHASE9_fe8e394_20260515-0933.md` NEW-Pxx tally section + prior NEXT_SESSION_PROMPT.

---

## Notes carried forward

- PowerShell wraps git stderr as "RemoteException"; push success in the `OLDHEAD..NEWHEAD  main -> main` line. Sometimes that marker doesn't print but the push still succeeded — always verify by comparing local `git log` HEAD to `git ls-remote origin main`.
- BR scoreboard flips happen STUB/DEFERRED/PARTIAL → IMPLEMENTED+TESTED; deepening doesn't count.
- Each new user prompt resets the 30-min task budget.
- 10/13 is the de-facto submission ceiling. Remaining 3 (BR-07 LangGraph, BR-08 Omniverse, BR-09 Kafka) are all multi-day-scope and unsuitable for a 30-min budget. Don't half-flip them under time pressure.
- The demo scripts require `FORENSA_TENANT_ID` + `FORENSA_TOKEN` env vars; the seed-data script (Priority A) closes that gap.
- Submission video target: 5 min, 1080p, MP4, filename `forensa_submission_v1_20260518.mp4`.

**End of next-session prompt.**
