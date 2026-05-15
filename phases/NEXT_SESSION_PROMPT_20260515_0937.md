# NEXT SESSION PROMPT — Forensa, written 2026-05-15 09:37 +01:00

You are Claude. You are working on the Forensa hackathon project. The hackathon submission deadline is Monday 19 May 2026 (3 days from now).

**Operating directory:** `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa`
**Repo:** `github.com/vsenthil7/forensa`
**Branch:** `main`
**HEAD at this prompt's write-time:** `1c656e0` on `origin/main`
**Rules:** `C:\Users\v_sen\Documents\Projects\claude-memory\global\CLAUDE_RULES.md` — READ FIRST, state all 14 as a numbered checklist before any other action.

---

## TL;DR for the next instance of Claude

**Phase 9 is CLOSED.** The hackathon-functional product is on `origin/main` at HEAD `1c656e0`. BR scoreboard: **9/13 IMPLEMENTED+TESTED** with all 4 non-IMPLEMENTED items DEFERRED out-of-hackathon by design. Default test suite: 878 passed. PG-mode: 904 passed. Coverage gate: 100%. The submission package doc is at `phases/PHASES_DONE_PHASE9_fe8e394_20260515-0933.md`.

**Two options for the next session:**
1. **Pre-submission polish work** — demo script, recorded MP4, judge handout, pitch rehearsal, slide deck. None of this is more code; it's submission-package work. The hackathon goes Monday 19 May.
2. **Phase 10 (post-submission)** — start picking up TRACKED-P10.x items: real auth provider (CP10.1), KMS adapter (CP10.2), PostgreSQL RLS (CP10.3). These are not hackathon-window items.

**Recommendation:** the next session should ASK the user before code work. The product side of Phase 9 is done. The remaining hackathon-window work is the pitch + the demo, not more features.

---

## Mandatory first 6 actions (in order, before any code work)

1. **Write context_log file 006** at `phases/context_log/006_<slug>_YYYYMMDD-HHMM.md` BEFORE any other action.
2. **Read CLAUDE_RULES.md** and state the 14 rules as a numbered checklist.
3. **Shell-stamp SESSION_START** via `Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'`.
4. **Stamp repo state**:
   ```powershell
   cd C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa
   git log --oneline -5
   git status --short
   git ls-remote origin main
   ```
   Expected: HEAD `1c656e0`, clean working tree, remote matches local.
5. **Read** `phases/PHASES_DONE_PHASE9_fe8e394_20260515-0933.md` to load the full Phase 9 closure picture (BR scoreboard + CP table + suite progression + headline architecture decisions + open TRACKED-Pxx items).
6. **Read** `phases/ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md` to load Phase 10-13 enterprise-roadmap context if the user decides on post-submission work.

---

## Current state snapshot at HEAD `1c656e0`

- **Default suite:** 878 passed, 26 PG-skipped, 100% coverage gate held.
- **PG-mode suite (verified CP9.26):** 904 passed.
- **BR scoreboard:** **9/13 IMPLEMENTED+TESTED**. BR-01/02/03/04/05/06/10/11 + 1 more. BR-07/08/12/13 STUB DEFERRED out-of-hackathon. BR-09 PARTIAL → CP12.4.
- **Lint/format/types:** all green (ruff check + ruff format --check + mypy strict on 52 packages/apps source files + bandit + pip-audit).
- **Last 5 commits:**
  - `1c656e0` [DOCS] PHASES_DONE_PHASE9_fe8e394_20260515-0933.md - Phase 9 close-out submission package
  - `fe8e394` [VERIFY] CP9.26 PG-mode verification re-run at HEAD 67b6bca - all green
  - `67b6bca` [FEAT] CP9.27 NEW-P9.22.anchor-detail-endpoint - GET /v1/anchors/{anchor_id} with raw TSR DER bytes
  - `f0c7dd3` [DOCS] phases/NEXT_SESSION_PROMPT_20260515_0904.md (now superseded by this one)
  - `d57492c` [DOCS] phases/ session refresh 2026-05-15 09:02

---

## Operating rules (compressed)

1. Session start/end shell-stamped via `Get-Date` (never user message timestamps, never prose-narrated).
2. Every task start/end shell-stamped; 30-min hard stop per task; 29-min warning REQUIRED via shell. **Each new user prompt = new 30-min budget**, not cumulative.
3. NO scope shrinking — every finding → CLOSED-CPx / TRACKED-Pxx / NEW-Pxx / WONT-DO / RETRACTED.
4. EDIT → COMMIT → PUSH → TEST → fix-loop autonomous; no per-CP approval needed.
5. 100% pytest coverage (`--cov-fail-under=100`), Playwright UI 100% when UI work touched.
6. BACKUP files to `_backup/<file>_YYYYMMDD-HHMM` BEFORE edit (net-new files don't need backup).
7. Context_log file on disk BEFORE any other action.

**Commit messages** go to `C:\Users\v_sen\Documents\Projects\claude-memory\global\commit_messages\YYYY-MM-DD_<slug>.txt` then `git commit -F <path>`. Always.

**Path prefix for poetry runs** (PowerShell):
```powershell
$env:PATH = 'C:\Users\v_sen\AppData\Roaming\Python\Python314\Scripts;' + $env:PATH
```

**Default-mode tests:**
```powershell
Remove-Item Env:FORENSA_TEST_DB_URL -ErrorAction SilentlyContinue
poetry run pytest -q
```

**PG-mode tests:**
```powershell
$env:FORENSA_TEST_DB_URL = 'postgresql+asyncpg://forensa:forensa@localhost:5433/forensa'
poetry run pytest -q --no-cov
```

(Postgres container `forensa-pg` should be UP on port 5433. Verify with `docker ps`.)

---

## Priority work for this session (ASK USER FIRST)

The next instance of Claude should NOT autonomously pick a priority. The product side of Phase 9 is done. Ask the user:

**A) Submission-week priorities (hackathon ends Monday 19 May):**
- Demo recording (MP4 walkthrough of the end-to-end flow: ingest → Receipt → TSA anchor → evidence pack JSON-LD + PDF → openssl ts -verify → Gemini narrative)
- Pitch slide deck (5-minute submission video script)
- Judge handout (1-pager PDF covering BR scoreboard + suite stats + architectural highlights)
- Readme polish (the repo's top-level README.md as the first thing judges see when they open github.com/vsenthil7/forensa)

**B) Phase 10 (post-submission):**
- CP10.1 Real auth provider integration (Auth0/Okta)
- CP10.2 KMS adapter for tenant signing keys
- CP10.3 PostgreSQL Row-Level Security policies
- Any of the 25 TRACKED-Pxx items named in PHASES_DONE_PHASE9_*.md

**C) Small remaining Phase 9 stretch items if user wants more product polish:**
- NEW-P9.21.qr-code (QR code on PDF linking to evidence-pack hash)
- NEW-P9.21.visual-snapshot (Playwright PDF visual regression)
- Multi-anchor packs (NEW-P11.x; requires Merkle tree work)

If the user just says "continue" without choosing, default behaviour: write a fresh status doc + offer the menu. Do not silently pick.

---

## Open TRACKED-Pxx items (NO silent drops)

From `PHASES_DONE_PHASE9_fe8e394_20260515-0933.md` NEW-Pxx tally section. The big-picture roadmap:

**TRACKED-P10.x (security/auth deepen):**
- KMS adapter, RLS policies, real Veea HTTP client, payload-size limit, OTel traceparent prop, FastAPI rate-limiter (6 items)

**TRACKED-P11.x (crypto hardening):**
- HSM bring-your-own-key, key rotation, post-quantum migration, real Merkle tree (vs current chain), multi-anchor packs (5 items)
- TRACKED-P11.6 detached platform signature on JSON-LD + PDF

**TRACKED-P12.x (observability/scale):**
- Kafka ingest queue (BR-09), async-job evidence packs, OTel auto-instrumentation, multi-region, chain-head concurrency, cursor pagination on anchors (6 items)

**TRACKED-P13.x (compliance/SaaS):**
- SOC 2 Type II, GDPR Article 17 × append-only ledger tension, EU AI Act Article 12 mapping, admin console, billing, SDK, customer success runbooks, pen test cadence (8 items)

Full roadmap in `phases/ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md`.

---

## Path inventory (verbatim, all live on origin/main at `1c656e0`)

**Production code surface:**
- `apps/api/main.py` — FastAPI factory + healthz + narrative-provider exposure
- `apps/api/auth/` — Principal + TokenVerifier + get_principal
- `apps/api/routes/events.py` — POST /v1/events (idempotency-key, agent signature, persistence)
- `apps/api/routes/receipts.py` — GET /v1/receipts (cursor pagination, signed_at window)
- `apps/api/routes/evidence.py` — GET /v1/evidence-packs (JSON-LD + PDF + anchor embed)
- `apps/api/routes/narratives.py` — POST /v1/narratives (Gemini live + 4-layer defence)
- `apps/api/routes/anchors.py` — GET /v1/anchors (list) + GET /v1/anchors/{id} (detail + raw DER)
- `apps/api/narrative_selector.py` — live-by-default Gemini selector
- `apps/api/ingest_service.py` — bundle provider + signing-key provider + enforcement bridge
- `packages/crypto/` — hash + merkle (actually chain; tree TRACKED-P11.x) + sign + tsa
- `packages/ledger/` — models + receipt_builder + bundle_repository + bundle_workflow + tsa_anchor + repositories + session
- `packages/policy/` — enforcement (canonical ABC) + lobstertrap (legacy alias) + snapshot + bundle_builder + replay
- `packages/ingest/normaliser.py` — OTel → Event (SpanKind=INTERNAL rejection, reasoning vs output disambiguation)
- `packages/export/` — schema (AnchorEvidence + EvidencePack) + builder (anchor binding) + pdf_renderer (anchor block)
- `packages/narrative/` — client (mock) + live_client (Gemini) + prompt (3-anchor bind)
- `packages/schema/` — pydantic frozen models (Event, Receipt, Tenant, Agent, PolicyBundle)

**Documentation surface (governance):**
- `docs/02_brd/BRD.md` — 13 BRs with status column
- `docs/11_threat_model/THREAT_MODEL.md` — 15 STRIDE threats
- All other 20 docs in `docs/00_executive_brief/` through `docs/22_sbom/`

**phases/ status-doc series (newest at top):**
- `phases/PHASES_DONE_PHASE9_fe8e394_20260515-0933.md` (close-out, HEAD `1c656e0`, 9/13)
- `phases/PHASES_REVIEW_BEFORE_AFTER_20260515_0902.md` (HEAD `d57492c`, 9/13)
- `phases/PHASES_REVIEW_BEFORE_AFTER_20260515_0748.md` (HEAD `fd24031`, 9/13)
- `phases/PHASES_REVIEW_BEFORE_AFTER_20260515_0604.md` (HEAD `c750485`, 8/13)
- `phases/NEXT_SESSION_PROMPT_20260515_0937.md` (this file)
- `phases/ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md` (Phase 10-13 roadmap)

**Context-log audit trail:**
- `phases/context_log/001_session-start-cp9-22-closeout_20260515-0741.md`
- `phases/context_log/002_cp9-20-closed-anchor-integration-next_20260515-0810.md`
- `phases/context_log/003_cp9-24-route-wiring-commit_20260515-0849.md`
- `phases/context_log/004_cp9-27-anchor-detail-endpoint_20260515-0926.md`
- `phases/context_log/005_cp9-26-pg-mode-verification_20260515-0929.md`
- Next: `phases/context_log/006_<slug>_<stamp>.md`

---

## Notes carried forward

- PowerShell wraps git stderr as "RemoteException" — push success is indicated by the `OLDHEAD..NEWHEAD  main -> main` line in the stderr block, NOT by exit code.
- Mock-session discriminator pattern for tests that hit a route running 2 selects: substring-match on `str(stmt).lower()` against the SQLAlchemy table name.
- canonical_json bans `None`; deferred-anchor rows replace 4 None fields with empty-string sentinels in `_canonicalise_anchor` before binding into root_hash.
- ReportLab embeds CreationDate/ModDate timestamps by default; `_pin_pdf_timestamps` post-processes the bytes to pin them to `pack.header.generated_at` for byte-deterministic output.
- The `# pragma: no cover` seam around `_default_generate_call` in `live_client.py` is why the CP9.20 SDK swap was painless.
- BR scoreboard flips only happen when a fresh BR moves from STUB/PARTIAL to IMPLEMENTED+TESTED; deepening an already-flipped BR does NOT count as a flip.
- Each new user prompt resets the 30-min task budget. Don't cumulate against the prior block's start time.
- Tool-use limits can interrupt mid-CP — always commit early if a CP can be split, and always note the working-tree state in the response so the next turn can resume cleanly.

**End of next-session prompt.**
