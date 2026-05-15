# Forensa Phases, CPs, and Reviews — current state at session 20260515_0748

**Saved:** 2026-05-15 07:48 +01:00 (Friday, Day 5 of 6-day hackathon; submission Monday 19 May)
**HEAD at save:** `fd24031` on `origin/main`
**Predecessor doc:** `PHASES_REVIEW_BEFORE_AFTER_20260515_0604.md` (snapshot at HEAD `c750485`, BR scoreboard 8/13)
**Author:** Claude
**Purpose:** Refresh of the single-pane status doc after CP9.21a, CP9.21b, CP9.22 landed in this session.

---

## What changed since the predecessor doc

Three CPs landed between HEAD `c750485` and HEAD `fd24031`:

| CP | Commit | Time | What | Closes |
|---|---|---|---|---|
| **CP9.21a** | `7e30e0d` | 15 May 06:50 | PDF render module (`packages/export/pdf_renderer.py`, 330 LOC) + 24 unit tests at 100% line+branch coverage. Deterministic A4 PDF via reportlab 4.5.1, pinned CreationDate+ModDate for byte-identical reproduction, uncompressed content streams for forensic grep + cross-build determinism, header table + receipts table + PROV-O activities table + per-page footer. | Enterprise-Grade Review 3.17 #1 (No PDF rendering) + CP6.3 deferral from Phase 6 |
| **CP9.21b** | `7c2af4a` | 15 May 07:18 | Accept: application/pdf content negotiation on `GET /v1/evidence-packs` + 17 endpoint tests + BRD BR-05 row flip PARTIAL→IMPLEMENTED+TESTED. Conservative wildcard handling (`*/*` and `application/*` do NOT trigger PDF; explicit `application/pdf` token required). Filename includes first 12 chars of root_hash. Response carries X-Forensa-Root-Hash header for cross-check against JSON-LD form. | BR-05 second half (regulator-grade evidence pack now ships in both wire forms) |
| **CP9.22** | `fd24031` | 15 May 07:48 | `GET /v1/anchors` REST endpoint (`apps/api/routes/anchors.py`, 150 LOC) exposing TimestampAnchorRow surface from CP9.19 + 11 endpoint tests. Auth+tenant binding via get_principal. Window filter (since/until) + pagination (limit/offset). DESC ordering by anchor_date. Both anchored and deferred row types surfaced with full base64 transport for tsr_bytes + tsa_signature. Plus `phases/context_log/` scaffold (file 001 lands with this commit). | Customer-visible half of CP9.19 RFC 3161 TSA anchoring work |

## BR scoreboard

| BR | Description | Status at predecessor (06:04) | Status now (07:48) |
|---|---|---|---|
| BR-01 | Cryptographic chain | IMPLEMENTED+TESTED | IMPLEMENTED+TESTED |
| BR-02 | Multi-party identity binding (dual signature) | IMPLEMENTED+TESTED (CP9.18 trio) | IMPLEMENTED+TESTED |
| BR-03 | Tenant signing keys | IMPLEMENTED+TESTED | IMPLEMENTED+TESTED |
| BR-04 | Ingest-time policy binding | IMPLEMENTED+TESTED (CP9.14) | IMPLEMENTED+TESTED |
| BR-05 | Regulator-grade evidence pack | PARTIAL (JSON-LD done, PDF not) | **IMPLEMENTED+TESTED (CP9.21a + CP9.21b)** |
| BR-06 | RFC 3161 TSA daily anchoring | IMPLEMENTED+TESTED (CP9.19) | IMPLEMENTED+TESTED (+ CP9.22 customer-visible endpoint) |
| BR-07 | LangGraph multi-agent provenance | STUB | STUB (no langgraph dep yet) |
| BR-08 | Omniverse physical-action replay | STUB | STUB (no Omniverse) |
| BR-09 | 10K events/sec sustained, 100K peak | PARTIAL (no Kafka path yet) | PARTIAL |
| BR-10 | Gemini Flash investigator UI | IMPLEMENTED+TESTED (CP9.1+CP9.4) | IMPLEMENTED+TESTED |
| BR-11 | Counterfactual narrative generation | IMPLEMENTED+TESTED (CP9.1) | IMPLEMENTED+TESTED |
| BR-12 | Tabletop incident response mode | STUB | STUB |
| BR-13 | M&A due diligence export | STUB | STUB |

**Score then:** 8/13 IMPLEMENTED+TESTED. **Score now:** **9/13 IMPLEMENTED+TESTED.** +1 in this session (BR-05). The remaining 4 non-IMPLEMENTED+TESTED BRs split into 1 PARTIAL (BR-09 Kafka deferred to CP12.4) and 3 STUB (BR-07/BR-08/BR-12/BR-13, all DEFERRED out of hackathon scope by design — counts to 4, with BR-12/BR-13 both deferred).

## Test count progression this session

| HEAD | Default tests | New tests | New CP |
|---|---:|---:|---|
| `c750485` (session start) | 796 | — | — |
| `7e30e0d` (CP9.21a) | 820 | +24 | renderer module tests |
| `7c2af4a` (CP9.21b) | 837 | +17 | Accept-header endpoint tests |
| `fd24031` (CP9.22) | 848 | +11 | anchors-endpoint tests |

**Net session delta: +52 default tests at 100% coverage maintained throughout.** PG-mode count unchanged (no migration / no model touch / no schema change in any of the 3 CPs).

## Review fix scoreboard delta

Top-20 review items movement this session:

| # | Item | Predecessor status | Now |
|---|---|---|---|
| 12 | Detached pack signature | TRACKED-P11.6 | TRACKED-P11.6 (now blocks BOTH wire forms: JSON-LD + PDF) |

No other top-20 items moved this session; the work was BR-05 closure + CP9.19 enterprise-UX surfacing, both of which sit outside the top-20 review list.

## Pending hackathon-window items at HEAD `fd24031`

From the original Phase 9 close-out list in `NEXT_SESSION_PROMPT_20260515_0604.md`:

| Item | Status | Notes |
|---|---|---|
| **CP9.20** Live Narrative SDK migration `google.generativeai` → `google.genai` | PENDING | The largest remaining hackathon-window item. Code surface estimated ~80 LOC + ~12 tests. Live SDK is currently `google-generativeai >=0.8.3,<0.9` per pyproject; the migration target is the newer `google-genai` SDK. The mock client path is unaffected; LiveNarrativeClient swap is gated by `# pragma: no cover` already so the test surface is integration-only. |
| **CP9.21** PDF render | **CLOSED** | CP9.21a `7e30e0d` + CP9.21b `7c2af4a`. |
| **CP9.22** Anchors endpoint | **CLOSED** | `fd24031`. |
| Anchor integration into evidence packs (offline-verifiable) | PENDING | Tracked as NEW-P10.x. The JSON-LD evidence pack today carries the chain root via root_hash but does NOT embed the day's TimestampAnchorRow shape. Embedding would let an offline verifier check the TSA signature without an additional API call. Requires evidence pack schema bump (would change root_hash, which is intentional — anchor inclusion changes the pack's identity). |

## Newly surfaced NEW-Pxx items from this session

| ID | Item | Destination |
|---|---|---|
| NEW-P9.21.qr-code | QR code on the PDF linking to the JSON-LD endpoint | NEW-Pxx backlog (deferred from CP9.21b) |
| NEW-P9.21.visual-snapshot | Playwright visual-snapshot test of the rendered PDF | NEW-Pxx backlog |
| NEW-P9.22.pg-integration | PG-integration test of `GET /v1/anchors` against real Postgres | TRACKED-P10.x |
| NEW-P9.22.cursor-pagination | Cursor pagination by anchor_date for very deep lists | TRACKED-P12.x |
| NEW-P9.22.anchor-detail-endpoint | `GET /v1/anchors/{id}` returning full TSR DER bytes for offline `openssl ts -verify` | TRACKED-P10.x |
| NEW-P9.22.inclusion-proof | Inclusion-proof endpoint blocked by NEW-P11.X.merkle-tree | TRACKED-P11.x |

**Tally: 6 new tracked items, 0 silent drops.** Rule 3 honoured.

## Verification snapshot at HEAD `fd24031`

- Default suite: 848 passed, 26 PG-skipped (single run; 3× flake-free was satisfied per-CP during this session).
- PG mode: not re-run since CP9.16-PG-up (`099afdb`). CP9.21a/b and CP9.22 are pure-Python additive — no DB schema, no migration, no model touch — so PG mode has nothing they could break. PG mode re-run is queued for the next session as a verification step.
- Lint: `poetry run ruff check .` — all checks passed.
- Format: `poetry run ruff format --check .` — 125 files already formatted.
- Type-check: `poetry run mypy packages apps/api` — Success: no issues found in 52 source files.
- Coverage: 100% line+branch maintained via `--cov-fail-under=100` gate in pyproject.

## What the next session should do

In rough priority order:

1. **CP9.20: Live Narrative SDK migration**. Largest remaining hackathon-window item. Touch `packages/narrative/live_client.py` to use `google-genai` instead of `google-generativeai`. Add the new SDK to pyproject. Test surface is small because the live path is `# pragma: no cover` (integration-only).
2. **Anchor integration into evidence packs**. Embed the day's `TimestampAnchorRow` data into the JSON-LD evidence pack so an offline verifier can check the TSA signature without an API call. Requires schema bump on EvidencePack + a new bind field in root_hash. This is a customer-visible enterprise UX item.
3. **PG-mode re-run** as a verification step. No code change expected; just confirms PG suite (822 tests at HEAD `099afdb`) still passes against HEAD `fd24031`.
4. **NEW-P9.22.anchor-detail-endpoint** if there's time. ~40 LOC + 6 tests. Reuses the same auth + window + pagination pattern as the list endpoint.

## Files added/changed this session

| Path | Status | Size |
|---|---|---|
| `packages/export/pdf_renderer.py` | new | 332 LOC |
| `tests/packages/test_pdf_renderer.py` | new | 345 LOC, 24 tests |
| `apps/api/routes/evidence.py` | modified | +50 LOC (Accept-header branch) |
| `tests/api/test_evidence_pdf_endpoint.py` | new | 300 LOC, 17 tests |
| `docs/02_brd/BRD.md` | modified | BR-05 row + detail + headline + change log |
| `apps/api/routes/anchors.py` | new | 150 LOC |
| `apps/api/main.py` | modified | +2 lines (import + include_router) |
| `tests/api/test_anchors_route.py` | new | 220 LOC, 11 tests |
| `phases/context_log/001_session-start-cp9-22-closeout_20260515-0741.md` | new | session-recovery scaffold |
| `pyproject.toml` + `poetry.lock` | modified | reportlab >=4.2.5,<5 (+ pillow transitively) |
| `phases/PHASES_REVIEW_BEFORE_AFTER_20260515_0748.md` | THIS FILE | scoreboard refresh |

## Backup discipline this session

| Path | Backup destination |
|---|---|
| `pyproject.toml` | `_backup/pyproject.toml_20260515-0631` |
| `apps/api/routes/evidence.py` | `apps/api/routes/_backup/evidence.py_20260515-0704` |
| `docs/02_brd/BRD.md` | `docs/02_brd/_backup/BRD.md_20260515-0709` |
| `apps/api/main.py` | `apps/api/_backup/main.py_20260515-0726` |
| `apps/api/routes/anchors.py` | `apps/api/routes/_backup/anchors.py_20260515-0744` |
| `tests/api/test_anchors_route.py` | `tests/api/_backup/test_anchors_route.py_20260515-0744` |
| `phases/PHASES_REVIEW_BEFORE_AFTER_20260515_0604.md` | `phases/_backup/PHASES_REVIEW_BEFORE_AFTER_20260515_0604.md_20260515-0748` |

All per CLAUDE_RULES FILE BACKUP RULE.

---

**End of refresh.**
**HEAD at write-time:** `fd24031`
**Predecessor:** `PHASES_REVIEW_BEFORE_AFTER_20260515_0604.md` (still on disk; the snapshot at HEAD `c750485` is historically true and is not edited in place).
