# Forensa - Next Session Starter Prompt

Generated: Wed 14/05/2026 08:35  |  HEAD at close: 6efa7b3

---

## CRITICAL - Before you start a new session

1. **Close ALL other Claude desktop windows.** Only ONE Claude conversation can have MCP access at a time. Symptom of violation: "Tool result could not be submitted" + 4-minute timeouts (exactly what happened at 08:25 today when a second desktop review task was running in parallel).
2. **Wait 30 seconds after closing** before opening the new session. The MCP server needs time to release the lock.
3. **Verify only one Claude window is running** in Task Manager (`Claude.exe` process count = 1).

---

## Section 1: Paste-verbatim starter prompt for the next session

Copy everything between the lines below into a fresh single Claude desktop window.

---

```
Resume Forensa hackathon build.

Repo:   C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa
Rules:  C:\Users\v_sen\Documents\Projects\claude-memory\global\CLAUDE_RULES.md
Deadline: Mon 19/05/2026 (5 days)

First three actions (in order):

1. Read CLAUDE_RULES.md via filesystem:read_text_file from
   C:\Users\v_sen\Documents\Projects\claude-memory\global\CLAUDE_RULES.md
   Confirm you have read all 14 rules. State them back as a checklist.

2. tool_search for `shell:run_command` to load the deferred shell tool.

3. Run this command to stamp session start and verify HEAD:
   powershell -Command "cd C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa; Get-Date -Format 'yyyy-MM-dd HH:mm:ss'; git log --oneline -3; git status --short"

Expected HEAD at start: 6efa7b3 (or later if the close-out from last session has landed)

Then read the current phase status from these files (in order):
   C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\NEXT_SESSION_PROMPT_20260514_0835.md
   C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md
   C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\PROJECT_STATUS_TABLE_20260514_0735.md

State today (end of session 08:33 on 14/05/2026):
- 8 of 8 phases CI-green
- 34 of 36 CPs DONE (CP6.3 PDF + CP8.3 Live Gemini deferred to Phase 9)
- 464 pytest + 36 vitest + 2 Playwright = 502 tests at 100pct coverage
- BR-09 load test: 1000 events in 0.155s = 6452 events/sec
- Last commit: 6efa7b3 (ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md)

Work to do (Phase 9, ~6 dev-hours + 3 hours presentation polish):
- CP9.1 Live Gemini Pro client (60 LOC + 120 LOC tests + 7 tests)
- CP9.2 PDF render via ReportLab (220 LOC + 180 LOC tests + 8 tests)
- CP9.3 Seed demo data script (80 LOC + 60 LOC tests + 6 tests)
- CP9.4 LiveNarrativeClient env-var swap (30 LOC + 80 LOC tests + 4 tests)
- CP9.5-9.7 manual deliverables (MP4 recording, judge handout, pitch rehearsal)
- CP9.8 phase9_DONE.md

Start with CP9.1 (smallest code change; reuses NarrativeClient ABC).

Rules to honour (full list in CLAUDE_RULES.md):
 1. Session start/end Get-Date stamp
 2. Task start/end Get-Date + 30-min ceiling + 28/29-min warning
 3. NO scope shrink
 4. Commit code -> push -> test -> FIX commit if needed -> push -> next task
 5. 100pct pytest + TypeScript + Playwright coverage
 6. BACKUP tracked files to _backup/ BEFORE edit
 7. context_log file on disk before any other action
 8. Hackathon raw git, no PRs
 9. Start-Sleep cap ~120s
10. Anchor-disambiguate edit_file old_str
11. No date/time ritual prose
12. No secrets in commits
13. No raw evidence packs in tests
14. Append-only ledger via _backup/

Known environment quirks:
- shell:run_command needs `powershell -Command "..."` wrapper on Windows
- Files >5KB write via chunked Add-Content + BOM strip via UTF8Encoding $false
- gh run watch hangs MCP; poll `gh run view <id> --json status,conclusion` every <=120s
- FastAPI Query(literal_default) does NOT need # noqa: B008; only Query(...) Ellipsis and Depends do
- MagicMock(spec=ReceiptRow) must set ALL Receipt fields when repo constructs domain models
- PowerShell `&` in URL query strings breaks parsing; use filesystem:edit_file for URL-heavy test code
- PS paths with literal [id] need -LiteralPath or backtick-escape `[id`]
- Poetry binary at C:\Users\v_sen\AppData\Roaming\Python\Python314\Scripts - prepend to PATH at start of each shell call
```

---

## Section 2: Verification commands

Paste any of these to confirm state after starter prompt:

| What to verify | Command |
|---|---|
| HEAD on origin/main | `git log --oneline -1` should show 6efa7b3 or later |
| All tests pass at 100pct | `poetry run pytest` -> 464 passed; 100pct coverage |
| vitest passes | `cd apps/console && pnpm exec vitest run` -> 36 passed |
| mypy strict clean | `poetry run mypy packages apps/api` -> Success: no issues |
| Lint clean | `poetry run ruff format --check . && poetry run ruff check .` -> clean |
| Latest CI green | `gh run list --limit 5` -> latest is success |
| Demo runs end-to-end | `poetry run python scripts/demo_tabletop.py` -> ALL CHECKS PASSED |
| Load test BR-09 | `poetry run python scripts/load_test.py 1000` -> budget honoured |

---

## Section 3: Repo paths (absolute, copy-pasteable)

| Purpose | Absolute path |
|---|---|
| Repo root | `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa` |
| Rules file | `C:\Users\v_sen\Documents\Projects\claude-memory\global\CLAUDE_RULES.md` |
| Context log root | `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\context_log` |
| Master plan | `forensa/phases/MASTER_PLAN.md` |
| Final status table | `forensa/phases/PROJECT_STATUS_TABLE_20260514_0735.md` |
| Per-CP file map | `forensa/phases/PROJECT_CP_FILE_MAP_20260514_0755.md` |
| Phase 9 + enterprise roadmap | `forensa/phases/ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md` |
| This file (next-session prompt) | `forensa/phases/NEXT_SESSION_PROMPT_20260514_0835.md` |
| Phase 0-8 DONE docs | `forensa/phases/phase{0..8}_DONE.md` |
| Final status report | `forensa/phases/STATUS_REPORT_20260514_0420.md` |

---

## Section 4: How to access git (one-liner cheat sheet)

| Action | Command (run from repo root) |
|---|---|
| Check status | `git status --short` |
| See last 5 commits | `git log --oneline -5` |
| Stage everything changed | `git add -A` |
| Stage one file | `git add path/to/file` |
| Commit | `git commit -m "[TYPE] subject"` where TYPE is FEAT or FIX or DOC |
| Push to origin/main | `git push` (ExecaError stderr-on-success is normal; look for `SHA..SHA main -> main`) |
| Latest CI runs | `gh run list --limit 5 --json databaseId,headSha,status,conclusion` |
| Poll specific CI | `gh run view <id> --json status,conclusion,jobs` |
| Backup tracked file BEFORE edit | `Copy-Item path _backup/$(Get-Date -Format yyyyMMdd_HHmmss)__<sha>__<flat-path>.ext` |

---

## Section 5: How to handle MCP timeout (the issue that broke 08:25)

| Symptom | Cause | Recovery |
|---|---|---|
| "Tool result could not be submitted. The request may have expired or the connection was interrupted" | Dual Claude desktop windows fighting for MCP lock | Close all other Claude windows; wait 30 sec; restart THIS session |
| 4-minute timeout on simple shell:run_command | MCP server wedged | Close + reopen Claude desktop; verify Task Manager shows only 1 Claude.exe |
| Filesystem MCP works but shell doesn't | Shell MCP wedged but filesystem still responsive | Use filesystem:edit_file / filesystem:read_text_file to keep working on disk; commit later |
| All MCP wedged | Full MCP crash | Restart Claude desktop entirely |

**Golden rule: one Claude conversation per active project at a time.**

---

## Section 6: Save-session ritual checklist (verify before closing this window)

| Item | Status |
|---|---|
| HEAD on origin/main | 6efa7b3 (ROADMAP doc) |
| Working tree at session close | this file `NEXT_SESSION_PROMPT_20260514_0835.md` is uncommitted; will be first commit of next session |
| 502 tests passing at 100pct cov | verified locally during session |
| All phase DONE docs on disk | phase0-phase8_DONE.md all present |
| Status table on disk | yes |
| Per-CP map on disk | yes |
| Roadmap on disk | yes |
| Next-session prompt | this file |

---

## Section 7: Why 08:25 went wrong (root cause analysis)

**Root cause: two Claude desktop sessions running concurrently.**

When the user opened a second desktop window for a review task at ~08:25, both windows tried to share the same MCP server. The MCP filesystem and shell servers are single-instance per Claude desktop installation. The second window grabbed the lock; this session started timing out.

**Evidence chain:**
- 08:23 - last successful command (TASK START roadmap doc)
- 08:25 - user started parallel desktop session
- 08:25 - this session received "Your previous message wasn't sent" warning
- 08:29 - shell briefly recovered, roadmap doc committed as 6efa7b3
- 08:33 - user reported issue
- 08:35 - shell MCP wedged on simple `git log`; filesystem MCP still responsive
- 08:54 - shell briefly recovered enough to create empty next-session-prompt file

**Fix: never run two Claude desktops against the same project at once.**

If parallel work is needed, use a separate user profile or wait for the first session to finish.

---

## End of next-session prompt

Close this session safely now. The doc above is on disk at
`C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\NEXT_SESSION_PROMPT_20260514_0835.md`.

When ready to resume: open ONE fresh Claude desktop window, paste the Section 1 starter prompt block, and confirm Claude reads CLAUDE_RULES.md as its first action.
