# Forensa — Next Session Starter Prompt

Generated: 2026-05-15 07:51 +01:00  |  HEAD at close: `fd24031`
Author: Claude (this session)
Deadline: Monday 19/05/2026

---

## CRITICAL — Before you start a new session

1. **Close ALL other Claude desktop windows.** Only ONE Claude conversation can have MCP access at a time.
2. **Wait 30 seconds after closing** before opening the new session.
3. **Verify only one Claude window is running** in Task Manager (`Claude.exe` process count = 1).

---

## Section 1: Paste-verbatim starter prompt

Copy the block between the triple-backticks below into a fresh single Claude desktop window.

```
Resume Forensa hackathon build.

Repo:   C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa
Rules:  C:\Users\v_sen\Documents\Projects\claude-memory\global\CLAUDE_RULES.md
Deadline: Mon 19/05/2026

==============================================================================
MANDATORY FIRST 6 ACTIONS, IN ORDER, NO EXCEPTIONS
==============================================================================

1. WRITE context_log file BEFORE any other action
   filesystem:write_file to
     C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\context_log\NNN_<kebab-slug>_YYYYMMDD-HHMM.md
   Counter starts at the next NNN after the highest already on disk. The
   file must contain: verbatim user prompt, category tag, what it
   triggered, live state, rule-compliance self-check, next planned action.
   This is the on-disk recovery mechanism that survives auto-compact.

2. READ CLAUDE_RULES.md FULL TEXT
   filesystem:read_text_file on
     C:\Users\v_sen\Documents\Projects\claude-memory\global\CLAUDE_RULES.md
   State the 14 rules back as a numbered checklist in your first reply.
   The rules drift IS the failure mode.

3. STAMP SESSION START VIA SHELL
   tool_search for `shell:run_command` to load the deferred shell tool.
   Then:
     powershell -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'"
   Record output as SESSION_START. Every task starts + ends with another
   Get-Date. 28-min warning + 29-min wrap + 30-min hard-stop. The 29-min
   warning MUST be shell-stamped and visible to the user.

4. STAMP REPO STATE
   powershell -Command "cd C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa; git log --oneline -5; git status --short; git ls-remote origin main"
   Expected HEAD at start: fd24031 (or later if a follow-up landed).
   Working tree should be clean. Remote should match HEAD.

5. READ THIS SESSION'S STATUS DOC
   filesystem:read_text_file on
     C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\PHASES_REVIEW_BEFORE_AFTER_20260515_0748.md
   Covers the BR scoreboard at HEAD fd24031 (9/13 IMPLEMENTED+TESTED),
   what landed in the last session (CP9.21a + CP9.21b + CP9.22), pending
   items, NEW-Pxx surfaced, and what the next session should pick up.

6. CONFIRM BACKLOG
   filesystem:read_text_file on
     C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md
   Cross-check CP9.20 against the status doc. The roadmap's CP numbering
   is the 14 May plan; live numbering at HEAD fd24031 has shifted - the
   status doc is canonical.

==============================================================================
SESSION TASK
==============================================================================

PRIMARY: CP9.20 - Live Narrative SDK migration google.generativeai -> google.genai.

Why CP9.20 now:
- Largest remaining hackathon-window code item.
- The mock client path is unaffected; LiveNarrativeClient swap is gated
  by # pragma: no cover already so the test surface is small.
- google.generativeai is deprecated; google.genai is the supported SDK.

Approach:
- Replace google-generativeai >=0.8.3,<0.9 with google-genai (latest) in pyproject.toml.
- poetry lock --no-update; poetry install.
- Update packages/narrative/live_client.py to use google.genai.Client
  pattern instead of google.generativeai.GenerativeModel pattern. The
  wire-form contract (NarrativeClient ABC) is unchanged.
- Update apps/api/narrative_selector.py if it imports anything SDK-shaped.
- Update tests/packages/test_live_narrative_client.py to patch the new
  client class. The 29 tests there test the 4-layer prompt-injection
  defence + retry/timeout/error mapping, not the SDK call itself.
- 3x flake-free both default AND PG mode before commit.

ESTIMATE: 60-90 minutes. Single commit if possible, two commits
(CP9.20a deps + CP9.20b client) if needed.

IF CP9.20 finishes with time to spare:
- Anchor integration into evidence packs (offline-verifiable). Schema bump
  on EvidencePack + new bind field in root_hash. Customer-visible.
- NEW-P9.22.anchor-detail-endpoint: GET /v1/anchors/{id} returning full
  TSR DER bytes. ~40 LOC + 6 tests.
- PG-mode verification run (no code change, just confirms PG suite still
  passes against HEAD fd24031).

==============================================================================
DISCIPLINE THAT MUST NOT DRIFT (the 7 rules user re-stated 15 May 07:38)
==============================================================================

(1) SESSION + TASK SHELL-STAMP. Always Get-Date, never user message timestamps.
(2) 30-min hard stop. 29-min warning REQUIRED, shell-stamped.
(3) NO scope shrink. Every finding -> CLOSED-CP / TRACKED-Pxx / NEW-Pxx /
    WONT-DO-RATIONALE / RETRACTED. Zero silent drops.
(4) EDIT -> COMMIT -> PUSH -> TEST. Autonomous. No waiting for approval.
    Fix-loop on errors: write fix -> [FIX] commit -> push -> re-test.
(5) 100% pytest coverage (--cov-fail-under=100 in pyproject). Playwright
    100% on any UI work. Functional + negative + user-case + user-story
    all automated.
(6) BACKUP before edit. _backup/<filename>_YYYYMMDD-HHMM. If not, git
    commit + push first.
(7) context_log/ file BEFORE any other action. On-disk recovery for
    auto-compact / hallucination / amnesia.

==============================================================================
END OF STARTER PROMPT
==============================================================================
```

---

## Section 2: Verification commands

After the 6 mandatory actions:

```powershell
# Time stamp
powershell -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'"

# HEAD + working tree + remote sync (expect fd24031)
powershell -Command "cd C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa; git log --oneline -5; Write-Host '---status---'; git status --short; Write-Host '---remote---'; git ls-remote origin main"

# Test suite green in default mode (expect 848 passed, 26 PG-skipped)
powershell -Command "cd C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa; `$env:PATH = 'C:\Users\v_sen\AppData\Roaming\Python\Python314\Scripts;' + `$env:PATH; Remove-Item Env:FORENSA_TEST_DB_URL -ErrorAction SilentlyContinue; poetry run pytest -q 2>&1 | Select-Object -Last 3"

# Test suite green in PG mode (only if Postgres container is up; expect 874 = 848 + 26 ungated)
powershell -Command "cd C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa; `$env:PATH = 'C:\Users\v_sen\AppData\Roaming\Python\Python314\Scripts;' + `$env:PATH; `$env:FORENSA_TEST_DB_URL = 'postgresql+asyncpg://forensa:forensa@localhost:5433/forensa'; poetry run pytest -q --no-cov 2>&1 | Select-Object -Last 3"

# Lint + type-check + format
powershell -Command "cd C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa; `$env:PATH = 'C:\Users\v_sen\AppData\Roaming\Python\Python314\Scripts;' + `$env:PATH; poetry run ruff check . 2>&1 | Select-Object -Last 2; poetry run ruff format --check . 2>&1 | Select-Object -Last 2; poetry run mypy packages apps/api 2>&1 | Select-Object -Last 2"
```

---

## Section 3: Absolute paths to read in order

1. **Rules:** `C:\Users\v_sen\Documents\Projects\claude-memory\global\CLAUDE_RULES.md`
2. **This session's status doc:** `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\PHASES_REVIEW_BEFORE_AFTER_20260515_0748.md`
3. **This next-session prompt:** `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\NEXT_SESSION_PROMPT_20260515_0751.md`
4. **Roadmap:** `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md`
5. **Context log folder:** `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa\phases\context_log\` (read all in numeric order if recovering from compact)

---

## Section 4: BR scoreboard at HEAD `fd24031`

| BR | Status |
|---|---|
| BR-01 Cryptographic chain | IMPLEMENTED+TESTED |
| BR-02 Multi-party identity binding (dual signature) | IMPLEMENTED+TESTED |
| BR-03 Tenant signing keys | IMPLEMENTED+TESTED |
| BR-04 Ingest-time policy binding | IMPLEMENTED+TESTED |
| BR-05 Regulator-grade evidence pack (JSON-LD + PDF) | **IMPLEMENTED+TESTED** (flipped this session via CP9.21a + CP9.21b) |
| BR-06 RFC 3161 TSA daily anchoring | IMPLEMENTED+TESTED (+ CP9.22 customer-visible endpoint) |
| BR-07 LangGraph multi-agent provenance | STUB (no langgraph dep) |
| BR-08 Omniverse physical-action replay | STUB |
| BR-09 10K events/sec sustained (Kafka path) | PARTIAL (CP12.4 deferred) |
| BR-10 Gemini Flash investigator UI | IMPLEMENTED+TESTED |
| BR-11 Counterfactual narrative generation | IMPLEMENTED+TESTED |
| BR-12 Tabletop incident response mode | STUB |
| BR-13 M&A due diligence export | STUB |

**Score: 9/13 IMPLEMENTED+TESTED.** +1 this session.

---

**End of next-session prompt.**
**HEAD at write-time:** `fd24031`
**Author:** Claude, 2026-05-15 07:51 +01:00
