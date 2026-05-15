# NEXT SESSION PROMPT — Forensa, written 2026-05-15 09:04 +01:00

You are Claude. You are working on the Forensa hackathon project. The hackathon submission deadline is Monday 19 May 2026 (4 days from now).

**Operating directory:** `C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa`
**Repo:** `github.com/vsenthil7/forensa`
**Branch:** `main`
**HEAD at this prompt's write-time:** `d57492c` on `origin/main`
**Rules:** `C:\Users\v_sen\Documents\Projects\claude-memory\global\CLAUDE_RULES.md` — READ FIRST, state all 14 as a numbered checklist before any other action.

---

## Mandatory first 6 actions (in order, before any code work)

1. **Write context_log file 004** at `phases/context_log/004_<slug>_YYYYMMDD-HHMM.md` BEFORE any other action. The slug should describe the day's intent (e.g. `cp9-26-pg-verification-and-anchor-detail-endpoint`).
2. **Read CLAUDE_RULES.md** and state the 14 rules as a numbered checklist.
3. **Shell-stamp SESSION_START** via `Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'` — never use the user-message timestamp, never narrate the time in prose without the shell call.
4. **Stamp repo state**:
   ```powershell
   cd C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google\forensa
   git log --oneline -5
   git status --short
   git ls-remote origin main
   ```
   Expected: HEAD `d57492c`, clean working tree, remote matches local.
5. **Read** `phases/PHASES_REVIEW_BEFORE_AFTER_20260515_0902.md` to load the full BR scoreboard + CP history + pending list.
6. **Read** `phases/ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md` to load the longer-horizon Phase 10-13 enterprise items so nothing gets silently dropped (Rule 3).

---

## Current state snapshot

- **Default suite at HEAD `d57492c`:** 872 passed, 26 PG-skipped, 100% coverage gate held.
- **BR scoreboard:** 9/13 IMPLEMENTED+TESTED. (BR-01/02/03/04/05/06/10/11 + 1 more; BR-07/08/12/13 STUB DEFERRED out-of-hackathon; BR-09 PARTIAL → CP12.4.)
- **Lint/format/types at HEAD `d57492c`:** all green (ruff check + ruff format --check + mypy strict on 52 packages/apps source files).
- **PG mode:** last verified at HEAD `099afdb` (CP9.16-PG-up). 5 subsequent CPs (CP9.20/22/23/24/25) are pure-Python additive — no DB schema, no migration, no model touch — so PG mode has nothing they could break, but a fresh verification re-run is queued as CP9.26.

---

## Operating rules (compressed)

1. Session start/end shell-stamped via `Get-Date` (never user message timestamps, never prose-narrated).
2. Every task start/end shell-stamped; 30-min hard stop per task; 29-min warning REQUIRED via shell. **Each new user prompt = new 30-min budget**, not cumulative.
3. NO scope shrinking — every finding → CLOSED-CPx / TRACKED-Pxx / NEW-Pxx / WONT-DO / RETRACTED.
4. EDIT → COMMIT → PUSH → TEST → fix-loop autonomous; no per-CP approval needed.
5. 100% pytest coverage (`--cov-fail-under=100`), Playwright UI 100% when UI work touched.
6. BACKUP files to `_backup/<file>_YYYYMMDD-HHMM` BEFORE edit (net-new files don't need backup).
7. context_log file on disk BEFORE any other action.

**Commit messages** go to `C:\Users\v_sen\Documents\Projects\claude-memory\global\commit_messages\YYYY-MM-DD_<slug>.txt` then `git commit -F <path>`. Always.

**Path prefix for poetry runs** (PowerShell):
```powershell
$env:PATH = 'C:\Users\v_sen\AppData\Roaming\Python\Python314\Scripts;' + $env:PATH
```

**Default-mode tests** (most common):
```powershell
Remove-Item Env:FORENSA_TEST_DB_URL -ErrorAction SilentlyContinue
poetry run pytest -q
```

**PG-mode tests:**
```powershell
$env:FORENSA_TEST_DB_URL = 'postgresql+asyncpg://forensa:forensa@localhost:5433/forensa'
poetry run pytest -q --no-cov
```

---

## Priority work for this session

### Priority 1 — CP9.26: PG-mode verification re-run

**No code change.** Spin up Postgres on `localhost:5433` (Docker compose file in repo root), set `FORENSA_TEST_DB_URL`, run `poetry run pytest -q --no-cov`. Expected ~898 passed (872 default + 26 PG-ungated). Confirms PG suite still passes against HEAD `d57492c` after 5 CPs landed without PG verification.

If anything red surfaces, that's an honest finding — log it as CP9.26.fix and resolve before moving on. Most likely outcome: green, since nothing in CP9.20/22/23/24/25 touched DB schema, models, or migrations.

Commit message body should include the actual pytest output line count + duration so the verification is auditable.

### Priority 2 — NEW-P9.22.anchor-detail-endpoint: GET /v1/anchors/{id}

**~40 LOC route + 6 tests.** This is the customer-visible companion to the GET /v1/anchors list endpoint (CP9.22) and the EvidencePack-embedded anchor data (CP9.23/24/25). Returns the FULL TimestampAnchorRow including raw TSR DER bytes (base64-encoded in the JSON body, or with `Accept: application/timestamp-reply` returns the raw DER as binary for direct `openssl ts -verify` pipe).

**Schema (the JSON body for anchored rows):**
```json
{
  "id": "<uuid>",
  "tenant_id": "<uuid>",
  "anchor_date": "2026-05-15T00:00:00+00:00",
  "status": "anchored",
  "root_hash": "<64-hex>",
  "tsa_identifier": "<url-or-id>",
  "tsr_bytes_b64": "<base64>",
  "tsa_signature_b64": "<base64>",
  "timestamped_at": "2026-05-15T06:00:00+00:00",
  "anchored_at": "2026-05-15T06:05:00+00:00"
}
```

Deferred rows return the same shape with `tsr_bytes_b64`, `tsa_signature_b64`, `timestamped_at`, and `root_hash` all `null`.

**Endpoint behaviour:**
- `GET /v1/anchors/{anchor_id}` → 200 with body above when authenticated principal's tenant_id matches the row's tenant_id.
- 404 when anchor_id does not exist.
- 403 when anchor_id belongs to a different tenant.
- 401 when no Authorization header.

**Required tests (6):**
1. Happy-path anchored row returns full JSON body with all fields populated.
2. Deferred-tombstone row returns same shape with null signature fields.
3. 404 when anchor_id is not found.
4. 403 cross-tenant: principal tenant ≠ row tenant_id.
5. 401 when Authorization header missing.
6. `Accept: application/timestamp-reply` header returns raw DER bytes (Content-Type: application/timestamp-reply, body is base64-decoded `tsr_bytes`).

**Files:** add a new handler to `apps/api/routes/anchors.py` (extends the list endpoint already there). Tests go in `tests/api/test_anchors_route.py` (extends the existing 11 tests).

**Coverage:** the new helper must hit 100% line+branch; the new tests must cover all 4 status codes and both anchored/deferred shapes.

### Priority 3 (stretch) — Phase 9 close-out doc

Create `phases/PHASES_DONE_PHASE9_<HEAD>_YYYYMMDD-HHMM.md` listing all 25 CPs that landed in Phase 9 with their commits, test count deltas, and BR-status impacts. This is the **hackathon submission package** — a one-page-glance "what shipped in Phase 9" deliverable for the judging panel. Pull from the commit history (`git log --oneline phases/...` or full `git log --oneline c5e9c4f..HEAD` once the Phase 9 start commit is identified) + the existing PHASES_REVIEW_BEFORE_AFTER_* snapshot series.

Headers: Title + dates + final BR scoreboard + CP table (CP id | commit | what | tests added | BR impact) + suite progression line chart in markdown + list of NEW-Pxx items deferred to Phase 10+ with destinations.

---

## Open NEW-Pxx items tracked (NO silent drops)

- `NEW-P9.21.qr-code` — QR code on PDF (links to evidence-pack hash on JSON-LD endpoint) — backlog
- `NEW-P9.21.visual-snapshot` — Playwright PDF visual-snapshot regression — backlog
- `NEW-P9.22.pg-integration` — anchors endpoint live against PG (not just mocks) — TRACKED-P10.x
- `NEW-P9.22.cursor-pagination` — anchors endpoint cursor-pagination (currently offset DESC) — TRACKED-P12.x
- `NEW-P9.22.anchor-detail-endpoint` — **Priority 2 of this session**
- `NEW-P9.22.inclusion-proof` — Merkle inclusion proof on anchor — TRACKED-P11.x (blocked on real Merkle tree)
- `NEW-P11.x.multi-anchor-packs` — pack carrying all N anchored days when scope spans multiple — TRACKED-P11.x
- `TRACKED-P11.6` — detached platform signature on JSON-LD + PDF
- `NEW-P11.X.merkle-tree` — real Merkle tree vs current chain — TRACKED-P11.x
- `BR-09 Kafka path` — CP12.4
- All Phase 10-13 enterprise items per `ROADMAP_PHASE9_AND_ENTERPRISE_20260514_0823.md`

---

## Path inventory (verbatim, all live on origin/main at `d57492c`)

**Anchor integration surface (CP9.23/24/25):**
- `packages/export/schema.py` — `AnchorEvidence` model + `from_anchor_row` classmethod + `EvidencePack.anchor` optional field
- `packages/export/builder.py` — `build_evidence_pack(anchor=...)`, `verify_evidence_pack`, `_canonicalise_anchor`
- `packages/export/pdf_renderer.py` — `_anchor_table` helper + section render in `render_evidence_pack_pdf`
- `apps/api/routes/evidence.py` — `_latest_anchor_in_window` helper + `anchor=` kwarg in build call

**Anchors REST surface (CP9.22):**
- `apps/api/routes/anchors.py` — `GET /v1/anchors` (list endpoint, paginated DESC by anchor_date)
- `apps/api/main.py` — registers all 5 routers (events, receipts, evidence, narratives, anchors)

**Narrative SDK surface (CP9.20):**
- `packages/narrative/live_client.py` — `LiveNarrativeClient` using `google.genai`
- `scripts/test_api_keys.py` — manual Gemini smoke test (google.genai)

**Tests touched / added this morning:**
- `tests/packages/test_pdf_renderer.py` — 28 tests (CP9.25 added 4)
- `tests/packages/test_anchor_in_evidence_pack.py` — 16 tests (CP9.23)
- `tests/api/test_evidence_route.py` — 6 tests + CP9.24 mock discriminator
- `tests/api/test_evidence_pdf_endpoint.py` — 17 tests + CP9.24 mock discriminator
- `tests/api/test_evidence_anchor_wiring.py` — 4 tests (CP9.24 positive path)
- `tests/api/test_anchors_route.py` — 11 tests (CP9.22)
- `tests/packages/test_live_narrative_client.py` — 29 tests (CP9.20 assertions updated)

**Context logs (audit trail):**
- `phases/context_log/001_session-start-cp9-22-closeout_20260515-0741.md`
- `phases/context_log/002_cp9-20-closed-anchor-integration-next_20260515-0810.md`
- `phases/context_log/003_cp9-24-route-wiring-commit_20260515-0849.md`
- Next: `phases/context_log/004_<slug>_<stamp>.md`

**Status doc series (newest at top):**
- `phases/PHASES_REVIEW_BEFORE_AFTER_20260515_0902.md` (current, HEAD `d57492c`, 9/13)
- `phases/PHASES_REVIEW_BEFORE_AFTER_20260515_0748.md` (HEAD `fd24031`, 9/13)
- `phases/PHASES_REVIEW_BEFORE_AFTER_20260515_0604.md` (HEAD `c750485`, 8/13)

---

## Notes from the prior session worth carrying forward

- PowerShell wraps git stderr as "RemoteException" — push success is indicated by the `OLDHEAD..NEWHEAD  main -> main` line in the stderr block, NOT by exit code.
- Mock-session discriminator pattern for tests that hit a route running 2 selects: substring-match on the SQL `str(stmt).lower()` against the SQLAlchemy table name (e.g. `"timestamp_anchors"`).
- canonical_json bans `None`; deferred-anchor rows replace 4 None fields with empty-string sentinels in `_canonicalise_anchor` before binding into root_hash.
- ReportLab embeds CreationDate/ModDate timestamps by default; `_pin_pdf_timestamps` post-processes the bytes to pin them to `pack.header.generated_at` for byte-deterministic output.
- The `# pragma: no cover` seam around `_default_generate_call` in `live_client.py` is why the CP9.20 SDK swap was painless — the SDK call site was already test-blind by construction (CP9.1's `generate_call=` constructor injection paid the dividend).
- BR scoreboard flips only happen when a fresh BR moves from STUB/PARTIAL to IMPLEMENTED+TESTED; deepening an already-flipped BR (e.g. CP9.20/23/24/25 all deepen BR-05/06/10) does NOT count as a flip.

**End of next-session prompt.**
