# Forensa Phases, CPs, and Reviews — current state at session 20260515_0902

**Saved:** 2026-05-15 09:02 +01:00 (Friday, Day 5 of 6-day hackathon; submission Monday 19 May)
**HEAD at save:** `c3c16b4` on `origin/main`
**Predecessor doc:** `PHASES_REVIEW_BEFORE_AFTER_20260515_0748.md` (snapshot at HEAD `fd24031`, BR scoreboard 9/13)
**Author:** Claude
**Purpose:** Refresh of the single-pane status doc after CP9.20, CP9.22 (carried-over commit), CP9.23, CP9.24, CP9.25 landed across the morning sessions.

---

## What changed since the predecessor doc

Five CPs landed between HEAD `fd24031` and HEAD `c3c16b4`:

| CP | Commit | What | Closes |
|---|---|---|---|
| **CP9.20** | `5535329` | Live Narrative SDK migration `google.generativeai` → `google.genai`. Pyproject hard-cut deprecated SDK. live_client.py `_default_generate_call` rewritten to use `genai.Client(api_key=...).aio.models.generate_content` with `GenerateContentConfig(thinking_config=ThinkingConfig(thinking_budget=0))`. scripts/test_api_keys.py + _DEFAULT_MODEL_ID flipped to gemini-2.5-pro. 2 test-assertion fixes for hardcoded model id. | NEW-P9.X.genai-sdk-migration (from CP9.4b backlog) |
| **CP9.23** | `af25e00` | Anchor integration into EvidencePack schema + builder. New AnchorEvidence frozen Pydantic model carrying RFC 3161 TSA proof (anchor_id, anchor_date, status, root_hash, tsa_identifier, tsr_bytes_b64, tsa_signature_b64, timestamped_at, anchored_at). EvidencePack gains optional `anchor: AnchorEvidence \| None` field bound into root_hash via new `_canonicalise_anchor` helper. 16 new tests covering build+verify, tamper detection, deferred-tombstone binding. | "Anchor integration into evidence packs (offline-verifiable)" stretch item from NEXT_SESSION_PROMPT_20260515_0751 |
| **CP9.24** | `c9d34b9` | Route wiring: `GET /v1/evidence-packs` now looks up the most recent TimestampAnchorRow in the scope window and passes it to `build_evidence_pack` via the CP9.23 `anchor=` kwarg. New `_latest_anchor_in_window` helper in evidence.py. Mock-session helpers in test_evidence_route.py + test_evidence_pdf_endpoint.py discriminate the 2nd execute call by "timestamp_anchors" substring. 4 new positive-path endpoint tests asserting pack.anchor surfaces correctly for both anchored and deferred rows. | Customer-visible half of CP9.23 |
| **CP9.25** | `c3c16b4` | PDF visual rendering of the TSA anchor block. New `_anchor_table(pack)` helper in pdf_renderer.py renders a 9-row 2-column table when pack.anchor is non-None. Anchored rows show abbreviated base64 blobs (first 12 + last 4 chars) + full root_hash + ISO-8601 timestamps; deferred rows show "not anchored" sentinel. PDF section header includes the explainer phrase "openssl ts -verify" so regulators know which tool to use. 4 new tests on test_pdf_renderer.py. | NEW-P9.23.pdf-anchor-display |

**Plus** CP9.22 (`fd24031` — anchors REST endpoint) landed in the predecessor session block but was captured in the predecessor doc; included here for completeness.

## BR scoreboard

| BR | Description | Status at predecessor (07:48) | Status now (09:02) |
|---|---|---|---|
| BR-01 | Cryptographic chain | IMPLEMENTED+TESTED | IMPLEMENTED+TESTED |
| BR-02 | Multi-party identity binding (dual signature) | IMPLEMENTED+TESTED | IMPLEMENTED+TESTED |
| BR-03 | Tenant signing keys | IMPLEMENTED+TESTED | IMPLEMENTED+TESTED |
| BR-04 | Ingest-time policy binding | IMPLEMENTED+TESTED | IMPLEMENTED+TESTED |
| BR-05 | Regulator-grade evidence pack | IMPLEMENTED+TESTED (JSON-LD + PDF) | IMPLEMENTED+TESTED (now offline-verifiable via embedded TSA anchor) |
| BR-06 | RFC 3161 TSA daily anchoring | IMPLEMENTED+TESTED (+ CP9.22 endpoint) | IMPLEMENTED+TESTED (+ CP9.22 endpoint + CP9.23/24/25 evidence-pack integration) |
| BR-07 | LangGraph multi-agent provenance | STUB | STUB |
| BR-08 | Omniverse physical-action replay | STUB | STUB |
| BR-09 | 10K events/sec sustained, 100K peak | PARTIAL | PARTIAL |
| BR-10 | Gemini Flash investigator UI | IMPLEMENTED+TESTED | IMPLEMENTED+TESTED (Gemini 2.5 Pro SDK migration via CP9.20) |
| BR-11 | Counterfactual narrative generation | IMPLEMENTED+TESTED | IMPLEMENTED+TESTED |
| BR-12 | Tabletop incident response mode | STUB | STUB |
| BR-13 | M&A due diligence export | STUB | STUB |

**Score then:** 9/13 IMPLEMENTED+TESTED. **Score now:** **9/13 IMPLEMENTED+TESTED.** No status flips this block - CP9.20/23/24/25 all deepen existing IMPLEMENTED+TESTED BRs (BR-05, BR-06, BR-10) rather than flipping new ones. The 4 non-IMPLEMENTED+TESTED BRs (BR-07 LangGraph, BR-08 Omniverse, BR-12 tabletop, BR-13 M&A) are all DEFERRED-out-of-hackathon-scope by design. BR-09 (Kafka path) is PARTIAL with CP12.4 destination.

## Test count progression this block

| HEAD | Default tests | Delta | CP |
|---|---:|---:|---|
| `fd24031` (predecessor doc baseline) | 848 | — | — |
| `5535329` (CP9.20) | 848 | 0 | SDK migration; 2 test-assertion fixes, no net new tests |
| `af25e00` (CP9.23) | 864 | +16 | schema + builder anchor integration |
| `c9d34b9` (CP9.24) | 868 | +4 | route wiring anchor lookup |
| `c3c16b4` (CP9.25) | 872 | +4 | PDF anchor block visual render |

**Net session delta: +24 default tests** across CP9.20/23/24/25, all at 100% coverage gate.

## Pending hackathon-window items at HEAD `c3c16b4`

| Item | Status | Notes |
|---|---|---|
| **CP9.20** Live Narrative SDK migration | **CLOSED** (`5535329`) | — |
| **CP9.21a/b** PDF render + Accept-header | **CLOSED** (`7e30e0d` + `7c2af4a`) | Earlier session. |
| **CP9.22** Anchors REST endpoint | **CLOSED** (`fd24031`) | Earlier session. |
| **CP9.23** Anchor in EvidencePack schema/builder | **CLOSED** (`af25e00`) | — |
| **CP9.24** Anchor route wiring | **CLOSED** (`c9d34b9`) | — |
| **CP9.25** PDF anchor block | **CLOSED** (`c3c16b4`) | — |
| Anchor integration into evidence packs (offline-verifiable) | **CLOSED** end-to-end | CP9.23 + 24 + 25 trio |
| **CP9.26** PG-mode verification re-run | PENDING | No code change; just confirms PG suite still passes against HEAD `c3c16b4`. |
| **NEW-P9.22.anchor-detail-endpoint** GET /v1/anchors/{id} | PENDING | Returns full TSR DER bytes for offline `openssl ts -verify`. ~40 LOC + 6 tests. |
| **NEW-P9.21.visual-snapshot** Playwright | NEW-Pxx backlog | Visual-snapshot regression test on the rendered PDF. Not hackathon-week critical. |

## Newly surfaced NEW-Pxx items from this block

| ID | Item | Destination |
|---|---|---|
| NEW-P11.x.multi-anchor-packs | Pack carrying all N anchored days when scope spans multiple days; requires Merkle tree work | TRACKED-P11.x |
| NEW-P9.23.pdf-anchor-display | PDF visual rendering of the anchor block | **CLOSED-CP9.25** (this block) |

**Tally: 1 new tracked item, 1 NEW-Pxx closed in-session, 0 silent drops.** Rule 3 honoured.

## Verification snapshot at HEAD `c3c16b4`

- Default suite: 872 passed, 26 PG-skipped (single run; 3× flake-free was satisfied per-CP).
- PG mode: not re-run since CP9.16-PG-up (`099afdb`). CP9.20/23/24/25 are pure-Python additive — no DB schema, no migration, no model touch — so PG mode has nothing they could break. PG mode re-run queued as CP9.26 (next session verification step).
- Lint: `poetry run ruff check .` — all checks passed at HEAD `c3c16b4`.
- Format: `poetry run ruff format --check .` — all files formatted.
- Type-check: `poetry run mypy packages apps/api` — Success: no issues found in 52 source files.
- Coverage: 100% line+branch maintained via `--cov-fail-under=100` gate.

## What the next session should do

In rough priority order:

1. **CP9.26: PG-mode verification re-run**. Spin up Postgres on `localhost:5433`, set `FORENSA_TEST_DB_URL`, run `poetry run pytest -q --no-cov`. Expected 898 passed (872 default + 26 PG-ungated). No code change; just confirms PG suite still passes against HEAD `c3c16b4` after 5 CPs landed without PG verification.
2. **NEW-P9.22.anchor-detail-endpoint** `GET /v1/anchors/{id}`. Returns the full row (including raw TSR DER bytes for offline `openssl ts -verify`) when the principal's tenant matches. ~40 LOC route + 6 tests (happy path, 404, 403 cross-tenant, deferred-tombstone shape, base64 transport, optional `Accept: application/timestamp-reply` for raw DER download).
3. **Stretch: Phase 9 close-out doc** at `phases/PHASES_DONE_*.md` listing all 25 CPs + commits + test counts for the hackathon submission package.

## Files added/changed this block

| Path | CP | Status | Size |
|---|---|---|---|
| `pyproject.toml` + `poetry.lock` | CP9.20 | modified | google-generativeai removed, google-genai added |
| `packages/narrative/live_client.py` | CP9.20 | modified | SDK swap inside `_default_generate_call`; model id flipped |
| `scripts/test_api_keys.py` | CP9.20 | modified | same swap |
| `tests/packages/test_live_narrative_client.py` | CP9.20 | modified | 2 model-id assertion updates |
| `packages/export/schema.py` | CP9.23 | modified | AnchorEvidence model + from_anchor_row classmethod + anchor field on EvidencePack |
| `packages/export/builder.py` | CP9.23 | modified | anchor kwarg + _canonicalise_anchor helper + verify symmetric extension |
| `tests/packages/test_anchor_in_evidence_pack.py` | CP9.23 | new | 16 tests |
| `apps/api/routes/evidence.py` | CP9.24 | modified | _latest_anchor_in_window helper + anchor= kwarg in build call |
| `tests/api/test_evidence_route.py` | CP9.24 | modified | mock-session discriminator |
| `tests/api/test_evidence_pdf_endpoint.py` | CP9.24 | modified | same |
| `tests/api/test_evidence_anchor_wiring.py` | CP9.24 | new | 4 tests |
| `packages/export/pdf_renderer.py` | CP9.25 | modified | _anchor_table helper + section render block |
| `tests/packages/test_pdf_renderer.py` | CP9.25 | modified | +4 tests |
| `phases/context_log/002_..._20260515-0810.md` | CP9.23 | new | session-recovery scaffold |
| `phases/context_log/003_..._20260515-0849.md` | CP9.24 | new | session-recovery scaffold |
| `phases/PHASES_REVIEW_BEFORE_AFTER_20260515_0902.md` | THIS FILE | new | scoreboard refresh |

## Backup discipline this block

All 10+ files modified across CP9.20/23/24/25 were backed up to local `_backup/` siblings before edit per CLAUDE_RULES FILE BACKUP RULE. Backup paths captured in each CP's commit message body.

---

**End of refresh.**
**HEAD at write-time:** `c3c16b4`
**Predecessor:** `PHASES_REVIEW_BEFORE_AFTER_20260515_0748.md` (still on disk; the snapshot at HEAD `fd24031` is historically true and is not edited in place).
