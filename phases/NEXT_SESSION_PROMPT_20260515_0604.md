# Forensa — Next Session Starter Prompt

Generated: 2026-05-15 06:04 +01:00  |  HEAD at close: `8176502`
Author: Claude (this session)
Deadline: Monday 19/05/2026 (4 days)

---

## CRITICAL — Before you start a new session

1. **Close ALL other Claude desktop windows.** Only ONE Claude conversation can have MCP access at a time. Symptom of violation: "Another response is already running" + 4-minute timeouts.
2. **Wait 30 seconds after closing** before opening the new session. The MCP server needs time to release the lock.
3. **Verify only one Claude window is running** in Task Manager (`Claude.exe` process count = 1).

---

## Section 1: Paste-verbatim starter prompt for the next session

Copy everything between the triple-backticks below into a fresh single Claude desktop window.

```
Resume Forensa hackathon build.

Repo:   C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa
Rules:  C:\Users\v_sen\Documents\Projects\claude-memory\global\CLAUDE_RULES.md
Deadline: Mon 19/05/2026

==============================================================================
MANDATORY FIRST 5 ACTIONS, IN ORDER, NO EXCEPTIONS
==============================================================================

1. READ CLAUDE_RULES.md FULL TEXT
   Use filesystem:read_text_file on:
     C:\Users\v_sen\Documents\Projects\claude-memory\global\CLAUDE_RULES.md
   Read every rule top-to-bottom. State them back as a numbered checklist
   in your first reply. Do NOT skip this even if the conversation feels
   like it can pick up cleanly. The rules drift IS the failure mode.

2. STAMP SESSION START VIA SHELL (NEVER trust user message timestamps)
   tool_search for `shell:run_command` to load the deferred shell tool.
   Then run:
     powershell -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'"
   Record the output as SESSION_START. Every task starts with another
   Get-Date stamp; every task ends with one. At the 28-minute mark
   surface a warning to the user; at 29 minutes wrap the current step
   to a clean checkpoint; at 30 minutes hard-stop and commit-or-stash.

3. STAMP REPO STATE VIA SHELL (raw git, no PR semantics)
   powershell -Command "cd C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa; git log --oneline -5; git status --short; git ls-remote origin main"
   Expected HEAD at start: 8176502 (or later if a follow-up landed).
   Working tree should be clean. Remote should match HEAD.

4. READ THE PHASE / REVIEW STATUS DOC FROM LAST SESSION
   filesystem:read_text_file on:
     C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\PHASES_REVIEW_BEFORE_AFTER_20260515_0604.md
   This is the single-pane status doc that covers every phase, every CP,
   the two reviews filed, the before-vs-after of every review fix,
   pending review items, and general pending work. Read it BEFORE
   touching code so you don't re-do CPs that already landed.

5. CONFIRM THE BACKLOG IS CURRENT
   filesystem:read_text_file on:
     C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md
   Cross-check CP9.20, CP9.21, CP9.22 (the pending hackathon-window
   items) against the status doc.

==============================================================================
SESSION TASK
==============================================================================

PRIMARY: CP9.21 — PDF render of evidence pack (closes BR-05 second half,
closes the CP6.3 deferral from Phase 6).

Why CP9.21 first (not CP9.20):
- Closes a long-deferred BR (BR-05), bumping IMPLEMENTED+TESTED from
  8/13 to 9/13.
- Smaller integration surface than the Gemini SDK migration.
- Demoable artefact for the Monday judge handout.

Approach:
- Add reportlab to pyproject.toml deps.
- New module packages/export/pdf_renderer.py: render_evidence_pack_pdf(pack)
  takes an EvidencePack and returns bytes (PDF). Page layout: title +
  header table (tenant + scope + root_hash) + receipt summary table +
  PROV-O activity list + signature footer with tsa_identifier if anchored.
- Wire into GET /v1/evidence-packs with Accept: application/pdf branch.
- ~25 unit tests covering: pack with 0 receipts; pack with N receipts;
  malformed pack rejected; missing anchor renders gracefully; long
  reasoning truncates; Unicode names render; pack root_hash printed
  exactly as hex; integrity verifiable by re-parsing.

ESTIMATE: 90-120 minutes. 100% coverage gate must pass. 3x flake-free
both default mode AND PG mode before commit.

IF CP9.21 finishes with time to spare:
- CP9.20: Live Narrative SDK migration google.generativeai -> google.genai.
- CP9.22: GET /v1/anchors REST endpoint exposing TimestampAnchorRow.
- Anchor integration into evidence packs (so packs verify offline).

==============================================================================
DISCIPLINE THAT MUST NOT DRIFT
==============================================================================

(A) TIME RITUAL
   - SESSION_START stamped via shell at message 1.
   - Every TASK_START stamped before the first edit/test/commit.
   - Every TASK_END stamped before the wrap-up sentence.
   - 28-minute warning. 29-minute wrap. 30-minute hard-stop.
   - NEVER use user-message-header timestamps. ALWAYS shell:run_command +
     Get-Date.

(B) NO SCOPE SHRINK (Rule 3)
   - Every review finding gets a destination: CLOSED-CP9.x or
     TRACKED-Pxx or NEW-Pxx or WONT-DO-RATIONALE or RETRACTED.
   - Zero silent drops. If you don't have time for an item, name where
     it goes (which CP, which phase) in the commit message.
   - If user pushes back on time, do NOT promise CP9.21 and deliver only
     half. Either commit the half as CP9.21a and queue CP9.21b, or
     descope explicitly with the user.

(C) 100% COVERAGE GATE
   - pyproject.toml has --cov-fail-under=100. Do not weaken it.
   - Every new prod line lands with its tests in the SAME CP.
   - Acceptable exceptions: # pragma: no cover on integration-only paths
     that wrap an external SDK (like _default_generate_call wrapping
     google.generativeai). Document why in a comment on the line.
   - Run the full suite both modes 3x flake-free BEFORE every commit:
       Default mode (no env var set):
         poetry run pytest
       PG mode (Postgres on localhost:5433):
         $env:FORENSA_TEST_DB_URL = 'postgresql+asyncpg://forensa:forensa@localhost:5433/forensa'
         poetry run pytest -q --no-cov
   - 3 consecutive clean passes per mode = ready to commit.

(D) GIT VIA SHELL (raw, no PR semantics, never-amend)
   - git log / status / add / commit / push / ls-remote ALL via
     shell:run_command + powershell -Command.
   - NEVER git commit --amend. If a fix is needed, land it as a new
     commit (e.g. [FIX] CP9.21.1 ...). The append-only commit history
     IS part of the audit trail.
   - Commit messages live OUTSIDE the repo at:
       C:\Users\v_sen\Documents\Projects\claude-memory\global\commit_messages\
     File name: YYYY-MM-DD_cpX.Y_description.txt
   - Commit with:
       git commit -F <full-path-to-message-file>
     Never use here-docs or temp files inside the repo for this.
   - Backup before edit (Rule A.9):
       Copy-Item -Path <file> -Destination "_backup\<file>_<YYYYMMDD-HHMM>" -Force
     Skip backup only for brand-new files.

(E) HOW THE 100% COVERAGE WAS HELD (precedent — keep doing this)
   - Every CP added prod code + tests in the SAME commit, sized so the
     suite was always strictly increasing in test count.
   - Tests covered: happy path + every documented branch + every
     raise path + every Pydantic validator + every CHECK constraint.
   - Hypothesis property tests where deterministic invariants existed
     (canonical_json determinism, chain hash linkage, sequence
     monotonicity, dual-signature recompute).
   - For async code: @pytest.mark.asyncio NOT manual event loops
     (manual loops leaked ProactorEventLoop on Windows -> ResourceWarning
     -> filterwarnings=error -> false-flake on unrelated tests). This
     was a real bug fixed in CP9.10.
   - For PG-only paths (RLS, triggers, partial UNIQUE, migrations):
     tests/integration/ with @pytest.mark.pg + conftest skip logic.
     They don't run when FORENSA_TEST_DB_URL is unset, so default mode
     still hits 100% coverage on what it can reach. PG mode hits the
     paths the mock session can't.
   - Module-level mocks injected via app.dependency_overrides — never
     monkeypatch internal symbols.
   - When a test surface is genuinely integration-only (Gemini API,
     google.genai SDK), wrap the impl in # pragma: no cover and seam
     out a test-injectable callable.

(F) MEMORY ABOUT THE PROJECT (read in session start, don't reinvent)
   - 22-doc pack lives in docs/00_executive_brief through docs/20_glossary
   - BRD: docs/02_brd/BRD.md (with Status column per BR — DO NOT erase)
   - Reviews: docs/reviews/01_Rev_Claude_20260514_0919/
     (next review subfolder: 02_Rev_<LLM>_<YYYYMMDD>_<HHMM>/)
   - Phase docs live in phases/ at repo root, NOT under docs/
   - 9 phases done; current work is Phase 9 hackathon close
   - 8/13 BRs IMPLEMENTED+TESTED, 1 PARTIAL (BR-05 → CP9.21), 1 PARTIAL
     (BR-09 needs Kafka → Phase 12), 3 STUB (BR-07, BR-08, BR-12, BR-13
     all out-of-scope-for-hackathon)
   - 796 default tests / 822 PG tests / 36 vitest / 2 Playwright

==============================================================================
THE 14 CLAUDE_RULES (full list lives in CLAUDE_RULES.md — re-read each session)
==============================================================================

 1. Session start/end Get-Date stamp (via shell)
 2. Task start/end Get-Date + 30-min ceiling + 28/29-min warning
 3. NO scope shrink — every finding gets a named destination
 4. Commit code → push → test → FIX commit if needed → push → next task
 5. 100% pytest + TypeScript + Playwright coverage
 6. BACKUP tracked files to _backup/ BEFORE edit
 7. context_log file on disk before any other action
 8. Hackathon raw git, no PRs (direct push to main)
 9. Start-Sleep cap ~120s
10. Anchor-disambiguate edit_file old_str
11. No date/time ritual prose (USE the shell stamp, don't narrate it)
12. No secrets in commits
13. No raw evidence packs in tests
14. Append-only ledger via _backup/

==============================================================================
END OF STARTER PROMPT
==============================================================================
```

---

## Section 2: Verification commands the next session must run

After the starter prompt's first 5 actions, the next session should verify state with these one-liners:

```powershell
# 1. Time stamp
powershell -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'"

# 2. HEAD + working tree + remote sync
powershell -Command "cd C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa; git log --oneline -5; Write-Host '---status---'; git status --short; Write-Host '---remote---'; git ls-remote origin main"

# 3. Test suite green in default mode
powershell -Command "cd C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa; `$env:PATH = 'C:\Users\v_sen\AppData\Roaming\Python\Python314\Scripts;' + `$env:PATH; Remove-Item Env:FORENSA_TEST_DB_URL -ErrorAction SilentlyContinue; poetry run pytest -q 2>&1 | Select-Object -Last 3"
# Expected: 796 passed, 26 skipped (PG-only)

# 4. Test suite green in PG mode (only if Postgres container is up)
powershell -Command "cd C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa; `$env:PATH = 'C:\Users\v_sen\AppData\Roaming\Python\Python314\Scripts;' + `$env:PATH; `$env:FORENSA_TEST_DB_URL = 'postgresql+asyncpg://forensa:forensa@localhost:5433/forensa'; poetry run pytest -q --no-cov 2>&1 | Select-Object -Last 3"
# Expected: 822 passed

# 5. Lint + type-check + format
powershell -Command "cd C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa; `$env:PATH = 'C:\Users\v_sen\AppData\Roaming\Python\Python314\Scripts;' + `$env:PATH; poetry run ruff check . 2>&1 | Select-Object -Last 2; poetry run ruff format --check . 2>&1 | Select-Object -Last 2; poetry run mypy packages apps/api 2>&1 | Select-Object -Last 2"
# Expected: All checks passed / 121 files already formatted / Success no issues found in 50 source files
```

---

## Section 3: Absolute paths to read in order

1. **Rules:** `C:\Users\v_sen\Documents\Projects\claude-memory\global\CLAUDE_RULES.md`
   *Click-and-copy:* `C:\Users\v_sen\Documents\Projects\claude-memory\global\CLAUDE_RULES.md`

2. **This session's status doc:** `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\PHASES_REVIEW_BEFORE_AFTER_20260515_0604.md`
   *Click-and-copy:* `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\PHASES_REVIEW_BEFORE_AFTER_20260515_0604.md`

3. **This next-session prompt:** `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\NEXT_SESSION_PROMPT_20260515_0604.md`
   *Click-and-copy:* `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\NEXT_SESSION_PROMPT_20260515_0604.md`

4. **Roadmap:** `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md`
   *Click-and-copy:* `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md`

---

## Section 4: Save-session ritual checklist (do this at END of every session)

1. Stamp session end via shell.
2. Verify all work is committed and pushed (`git status --short` shows empty, `git ls-remote origin main` matches `git log -1 --format=%H`).
3. Update or create the next-session prompt at `phases/NEXT_SESSION_PROMPT_<YYYYMMDD>_<HHMM>.md`.
4. Update the status doc at `phases/PHASES_REVIEW_BEFORE_AFTER_<YYYYMMDD>_<HHMM>.md` if any CPs landed.
5. Final commit (the docs themselves count as a commit unless they're inside an existing CP scope).
6. Push.
7. State the close-out summary (HEAD, test counts, BR scoreboard, what's pending).
8. Leave the user with the click-and-copy path to the next-session prompt.

---

**End of next-session prompt.**
**HEAD at write-time:** `8176502`
**Author:** Claude, 2026-05-15 06:04 +01:00
