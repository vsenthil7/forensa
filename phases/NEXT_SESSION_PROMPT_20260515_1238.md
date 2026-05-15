# NEXT SESSION PROMPT — Forensa, written 2026-05-15 12:38 +01:00

You are Claude. You are working on the Forensa hackathon project. The hackathon submission deadline is Monday 19 May 2026 (3.5 days from now).

**Operating directory:** `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa`
**Repo:** `github.com/vsenthil7/forensa`
**Branch:** `main`
**HEAD at this prompt's write-time:** `e35a032` on `origin/main`
**Rules:** `C:\Users\v_sen\Documents\Projects\claude-memory\global\CLAUDE_RULES.md` — READ FIRST, state all 14 as a numbered checklist before any other action.

**Supersedes:** `phases/NEXT_SESSION_PROMPT_20260515_1132.md` (written at HEAD `d14921a`; superseded after 4 more CPs landed in the IP-completion block that ran 11:39→12:37).

---

## TL;DR for the next instance of Claude

**13 commits today** across three task blocks (09:42→12:37). BR scoreboard: **6/13 → 10/13 IMPLEMENTED+TESTED**. Default-mode suite: **464 → 921 passed**, +457 tests across Phase 9 + IP-completion block. 100% coverage gate held throughout. PG-mode verified at this HEAD: **947 passed** (921 default + 26 PG-only).

| HEAD | What |
|---|---|
| `9075602` | README.md submission-grade rewrite |
| `0831bcb` | JUDGE_HANDOUT.md one-pager |
| `34d4cc4` | SUBMISSION_VIDEO_SCRIPT.md (5-min pitch + Q&A cheat sheet) |
| `565f826` | EXECUTIVE_BRIEF.md v2 (Phase 9-aware) |
| `45b0534` | tools/demo.sh + tools/demo.ps1 (runnable 4-step verification flow) |
| `5a3ddbf` | NEXT_SESSION_PROMPT_20260515_1006.md (early handoff, superseded) |
| `dc62fd0` | **CP9.28** BR-13 M&A due diligence export (STUB → IMPL+TESTED) |
| `52f8b4a` | BRD + PHASES_DONE_PHASE9 arithmetic truth-up (off-by-one fix) |
| `d14921a` | **CP9.29** BR-12 tabletop incident-response simulation (DEFERRED → IMPL+TESTED) |
| `9816ee1` | NEXT_SESSION_PROMPT_20260515_1132.md (superseded by this doc) |
| `53c3207` | **CP9.30** scripts/seed_demo_data.py — closes IP #1 (tools/demo.sh prerequisite) |
| `aecab85` | README.md badges + truth-up vs HEAD 53c3207 — closes IP #4 |
| `b523482` | **CP9.31** seed_demo_data.py dual-sign receipts (BR-02) — closes IP #15 |
| `4bcada6` | **PG-mode verification 947 passed at HEAD b523482** — closes IP #3 |
| `e35a032` | **CP9.32** widen lobstertrap latency test tolerance — closes NEW-P10.X.lobstertrap-latency |

**BR scoreboard at HEAD `e35a032`:**
- **10/13 IMPLEMENTED+TESTED:** BR-01, BR-02, BR-03, BR-04, BR-05, BR-06, BR-10, BR-11, BR-12, BR-13
- **1 PARTIAL:** BR-09 (in-process throughput IMPL+TESTED; Kafka path → CP12.4)
- **2 DEFERRED by design:** BR-07 LangGraph multi-agent + BR-08 Omniverse physical-action replay

**Default-mode suite:** 921 passed, 26 PG-skipped, 100% line+branch coverage gate held.
**PG-mode suite:** 947 passed (921 default + 26 PG-only) verified at HEAD `b523482` and reconfirmed at HEAD `e35a032` for the lobstertrap-latency test fix (default-mode only test, no PG impact).
**Lint/format/types:** `ruff check` + `ruff format --check` + `mypy --strict` all clean across 56 source files.

---

## Submission-week tasks remaining before Monday 19 May

1. **Record the submission video** using `docs/00_executive_brief/SUBMISSION_VIDEO_SCRIPT.md` + `tools/demo.sh`. Target 5 min, 1080p, MP4. Filename: `forensa_submission_v1_20260518.mp4`. **USER ACTION, not Claude.**
2. **Run the seeder against a clean DB and verify env-var output before recording** — `poetry run python scripts/seed_demo_data.py` (needs `FORENSA_DB_URL` + `FORENSA_DEMO_HMAC_SECRET` exported). Should print copy-pasteable PowerShell + bash env-var blocks. **USER ACTION.**
3. (Optional) **PHASES_DONE_PHASE9 second update** reflecting the IP-completion block CPs (9.30/9.31/9.32 + the PG-verify + the README + the arithmetic truth-up). Not strictly required since PHASES_DONE_PHASE9 stamps the close of Phase 9 proper at HEAD `fe8e394`; the post-Phase-9 work is captured in commit messages + this prompt. **CLAUDE TASK if requested, ~30 min.**

---

## Mandatory first 6 actions (in order, before any code work)

1. **Write context_log file 009** at `phases/context_log/009_<slug>_YYYYMMDD-HHMM.md` BEFORE any other action.
   - **WARNING from prior session:** context_log 008 was written retro-actively at 11:27 in the BR-12 block (soft Rule 7 violation; documented inside the log itself). Don't repeat.
2. **Read CLAUDE_RULES.md** and state the 14 rules as a numbered checklist.
3. **Shell-stamp SESSION_START** via `Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'`.
4. **Stamp repo state:**
   ```powershell
   cd C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa
   git log --oneline -15
   git status --short
   git ls-remote origin main
   ```
   Expected: HEAD `e35a032`, clean working tree, remote matches local.
5. **Read** `docs/02_brd/BRD.md` to load the 10/13 scoreboard + every BR's IMPL+TESTED detail (BR-12 + BR-13 sections were rewritten in CP9.28 + CP9.29).
6. **Read** this file + the most recent commits' messages from `C:\Users\v_sen\Documents\Projects\claude-memory\global\commit_messages\2026-05-15_*.txt` for full context.

---

## Priority work for this session (if user says "continue")

The IP table from earlier today is mostly closed. Remaining IP items in priority order:

**A) Final submission packaging — PHASES_DONE_PHASE9 second sweep + PHASES_DONE_POST9_PUSH companion doc** (~30 min). Phase 9 closed at HEAD `fe8e394` (878 tests, 8/13). Post-Phase-9 IP-completion ran from 11:11 to 12:37 and added 7 more commits taking us to 947 PG-mode at 10/13. The PHASES_DONE_PHASE9 doc already got an arithmetic truth-up in commit `52f8b4a` but does not name CP9.28-CP9.32. A companion doc capturing the IP-completion block would close that loop.

**B) Seed-data PG-integration test** at `tests/integration/test_seed_demo_data_pg.py` (~2-3 hours). This is `NEW-P10.X.seed-demo-data-pg-integration-test` from the CP9.30/CP9.31 commit bodies. Runs `seed_demo_data.seed()` against a clean Postgres and asserts row counts + `receipt.agent_signature IS NOT NULL` on every row. Validates the seeder end-to-end. Skips when `FORENSA_TEST_DB_URL` is unset (same pattern as other PG-only tests). **Multi-hour, post-submission scope.**

**C) Real-TSA support in seed script** (~half-day to multi-day). `NEW-P11.X.real-tsa-in-seed-script`. Swap `MockTimestampClient` for `Rfc3161TimestampClient` against FreeTSA so the `openssl ts -verify` step in `tools/demo.sh` actually works end-to-end. Today `Rfc3161TimestampClient.request_timestamp` raises immediately (`TimestampClientError` with a "PRODUCTION-DEFERRED" message). A half-step is to implement the HTTPS POST + ASN.1 DER request body using `rfc3161ng` or `asn1crypto`; full real TSA is `CP10.x`. **Multi-day, post-submission unless prioritised.**

**D) BR-07/BR-08/BR-09 deepening** (multi-day to multi-week per BR). The remaining DEFERRED/PARTIAL items. **Out of hackathon scope by design.**

**Recommendation:** A if a tidy submission-day documentation set matters; otherwise let the submission ship at HEAD `e35a032` and pick up post-Monday.

---

## Operating rules (compressed)

1. Session start/end shell-stamped via `Get-Date`.
2. Every task start/end shell-stamped; 30-min hard stop per task; 29-min warning REQUIRED. **Each new user prompt = new 30-min budget**, not cumulative.
3. NO scope shrinking — every finding → CLOSED-CPx / TRACKED-Pxx / NEW-Pxx / WONT-DO / RETRACTED.
4. EDIT → COMMIT → PUSH → TEST → fix-loop autonomous.
5. 100% pytest coverage (`--cov-fail-under=100`).
6. BACKUP files to `_backup/<file>_YYYYMMDD-HHMM` BEFORE edit.
7. Context_log file on disk BEFORE any other action.

**Soft violations during 2026-05-15 (honest disclosure):**
- Rule 6 partial: `apps/api/main.py` edited twice in CP9.28 + CP9.29 with only one pre-edit backup (1033 captures pre-CP9.28). Full reconstructability via git history. Documented in context_log 008.
- Rule 7 partial: context_log 008 written retro-actively at 11:27. Documented inside the log itself.

These are documented as soft violations rather than swept under the rug. **Next instance: don't repeat. Always context_log BEFORE any other action; always pre-edit backup before every edit (not just the first edit of a multi-edit chain).**

**Commit messages** go to `C:\Users\v_sen\Documents\Projects\claude-memory\global\commit_messages\YYYY-MM-DD_<slug>.txt`.

**Path prefix:**
```powershell
$env:PATH = 'C:\Users\v_sen\AppData\Roaming\Python\Python314\Scripts;' + $env:PATH
```

---

## Open TRACKED-Pxx items (NO silent drops)

Items SURFACED today that remain open:

From CP9.28 (BR-13 M&A export):
- `NEW-P10.X.ma-export-encryption-at-rest` — encrypt M&A bundle with acquirer's public key
- `NEW-P11.X.ma-export-detached-platform-signature` — Forensa platform-key signature over bundle
- `NEW-P12.X.ma-export-async-job` — async-job mode for very large windows
- `NEW-P12.X.ma-export-streaming` — multipart S3 upload for very large bundles

From CP9.29 (BR-12 tabletop):
- `NEW-P11.X.tabletop-bundle-from-storage` — target draft/proposed bundles from approval workflow
- `NEW-P12.X.tabletop-replay-real-events` — read-only replay of historical events against candidate bundle
- `NEW-P12.X.tabletop-diff-report` — compare simulated vs actual decisions surfaced as diff

From CP9.30 (seed-data script):
- `NEW-P10.X.seed-demo-data-pg-integration-test` — `tests/integration/test_seed_demo_data_pg.py` end-to-end
- `NEW-P11.X.real-tsa-in-seed-script` — swap MockTimestampClient for Rfc3161TimestampClient against FreeTSA

Repo-wide carry-overs from earlier sessions:
- `NEW-P10.X.repo-tenant-scoping` — push tenant filters into every repository helper at the SQL layer
- `NEW-P10.X.demo-script-integration-test` — Playwright pre-flight of tools/demo.sh against seeded env
- `NEW-P10.X.kms-adapter` — replace in-process bytes with AWS KMS / GCP KMS / HashiCorp Vault adapters

Items CLOSED today (12 total):
- IP #1, #2, #3, #4, #15 from the IP table written at 11:43
- CP9.28, CP9.29, CP9.30, CP9.31, CP9.32 (5 substantive CPs)
- NEW-P10.X.lobstertrap-latency-test-robustness (CP9.32)
- One doc arithmetic truth-up (commit `52f8b4a`)

Full inventory: `phases/PHASES_DONE_PHASE9_fe8e394_20260515-0933.md` NEW-Pxx tally section + the commit message bodies under `C:\Users\v_sen\Documents\Projects\claude-memory\global\commit_messages\2026-05-15_*.txt`.

---

## Notes carried forward

- PowerShell wraps git stderr as "RemoteException"; push success in the `OLDHEAD..NEWHEAD  main -> main` line. Sometimes that marker doesn't print but the push still succeeded — always verify by comparing local `git log` HEAD to `git ls-remote origin main`.
- BR scoreboard flips happen STUB/DEFERRED/PARTIAL → IMPLEMENTED+TESTED; deepening doesn't count.
- Each new user prompt resets the 30-min task budget.
- 10/13 is the de-facto submission ceiling. Remaining 3 (BR-07 LangGraph, BR-08 Omniverse, BR-09 Kafka) are all multi-day-to-multi-week-scope and unsuitable for a 30-min budget. Don't half-flip them under time pressure.
- The demo scripts (`tools/demo.{sh,ps1}`) require `FORENSA_TENANT_ID` + `FORENSA_TOKEN` env vars; the seed-data script (CP9.30 + CP9.31) populates them. User exports env vars via the seeder's printed PowerShell or bash block.
- Submission video target: 5 min, 1080p, MP4, filename `forensa_submission_v1_20260518.mp4`.
- The seed script's MockTimestampClient means `openssl ts -verify` in tools/demo.sh WILL FAIL against the seeded data; this is expected and documented. Real-TSA support is NEW-P11.X above.

**End of next-session prompt.**
