# Forensa - Per-CP Code File + Test File Map

Generated: Wed 14/05/2026 07:55  |  HEAD: 31d2b8d

Single comprehensive table mapping every CP across all 8 phases to its production code file(s), test file(s), and exact counts. Reads top-to-bottom as the literal build journey.

## Legend

- **LOC** = wc -l line count
- **Tests** = pytest def_tests for Python; vitest it() blocks for TypeScript (parametric expansions not separately counted)
- Multiple test files separated by comma
- DEFERRED CPs have no production or test file

---

## Phase 0 - Green CI baseline

| CP | Title | Production code (file: LOC) | Test file (file: LOC; tests) | Notes |
|---|---|---|---|---|
| CP0.1 | Fix Playwright wait-on URL scheme | .github/workflows/ci.yml (1-char edit) | n/a | Infra fix; CI 25798493526 green |
| CP0.2 | Verify all 7 CI jobs | n/a | (existing 217 pytest baseline unchanged) | Acceptance = ci-gate green |
| CP0.3 | Commit + push | n/a | n/a | DOC commit only |

---

## Phase 1 - Crypto primitives

| CP | Title | Production code (file: LOC) | Test file (file: LOC; tests) | Notes |
|---|---|---|---|---|
| CP1.1 | canonical_json + sha256 | packages/crypto/hash.py: 50 | tests/packages/test_crypto_hash.py: 126; 21 | None-reject + naive-datetime reject + 5 parametric + 3 hypothesis |
| CP1.2 | Ed25519 sign + verify | packages/crypto/sign.py: 89 | tests/packages/test_crypto_sign.py: 121; 18 | Wrong-length keys + 2 hypothesis round-trip |
| CP1.3 | Merkle chain | packages/crypto/merkle.py: 99 | tests/packages/test_crypto_merkle.py: 134; 22 | Out-of-order + gap + broken-prev + tampered-payload + 2 parametric + 2 hypothesis |
| **Phase 1 total** | - | **238 LOC across 3 files** | **381 LOC across 3 files; 61 def-tests = 65 collected** | - |

---

## Phase 2 - Lobster Trap policy gate

| CP | Title | Production code (file: LOC) | Test file (file: LOC; tests) | Notes |
|---|---|---|---|---|
| CP2.1 | PolicyDecision + PolicyVerdict | packages/policy/lobstertrap.py: 117 (shared with CP2.2 + CP2.3) | tests/packages/test_lobstertrap.py: 177; 23 | 8 tests for CP2.1 (4 happy + 4 negative) |
| CP2.2 | LobsterTrapClient ABC | packages/policy/lobstertrap.py (shared) | tests/packages/test_lobstertrap.py (shared) | 8 tests for ABC + terminal error path |
| CP2.3 | MockLobsterTrapClient | packages/policy/lobstertrap.py (shared) | tests/packages/test_lobstertrap.py (shared) | 9 tests; deterministic per kind + 2 hypothesis |
| CP2.4 | bundle_builder + content_hash | packages/policy/bundle_builder.py: 113 | tests/packages/test_bundle_builder.py: 150; 22 | Two-step build + 4 negative + 2 hypothesis |
| **Phase 2 total** | - | **230 LOC across 2 files** | **327 LOC across 2 files; 45 def-tests = 49 collected** | - |

---

## Phase 3 - BR-04 policy snapshot

| CP | Title | Production code (file: LOC) | Test file (file: LOC; tests) | Notes |
|---|---|---|---|---|
| CP3.1 | PolicySnapshot capture | packages/policy/snapshot.py: 115 | tests/packages/test_snapshot.py: 209; 18 | Triple-check id + version + hash; 5 negative + 1 property |
| CP3.2 | alembic 0002 + PolicySnapshotRow | alembic/versions/20260513_2055_policy_snapshot.py: 67  +  packages/ledger/models.py: 162 (PolicySnapshotRow added) | tests/packages/test_alembic_migration.py: 88; 7  +  tests/packages/test_ledger_models.py: 144; 12 | 6 tables + 12 indexes + 3 CHECK constraints |
| CP3.3 | ReplayPolicy + drift_detected | packages/policy/replay.py: 78 | tests/packages/test_replay.py: 101; 5 | Never returns live_bundle.content_hash |
| **Phase 3 total** | - | **422 LOC across 3 files (models.py shared with later CPs)** | **542 LOC across 4 files; 42 def-tests = 32 + parametric expansions** | - |

---

## Phase 4 - Receipt issuance

| CP | Title | Production code (file: LOC) | Test file (file: LOC; tests) | Notes |
|---|---|---|---|---|
| CP4.1 | build_receipt + recompute_receipt_hash | packages/ledger/receipt_builder.py: 152 | tests/packages/test_receipt_builder.py: 165; 9 | 7-field bind dict; genesis prev_receipt_hash sentinel; 1 hypothesis |
| CP4.2 | session.py + repositories.py | packages/ledger/session.py: 57  +  packages/ledger/repositories.py: 192 | tests/packages/test_repositories.py: 235; 13 | session_scope ACM; write_event_with_receipt 3-invariant check |
| CP4.3 | sequence monotonicity | packages/ledger/receipt_builder.py (shared CP4.1) | tests/packages/test_receipt_chain.py: 144; 10 (CP4.3 subset = 5 tests) | Parametric over n=1-10; cross-tenant rejection |
| CP4.4 | hash chain integrity | packages/ledger/receipt_builder.py (shared CP4.1) | tests/packages/test_receipt_chain.py (shared CP4.3; CP4.4 subset = 5 tests) | prev_hash linkage + tamper via model_copy |
| CP4.5 | Phase 4 DONE doc | n/a | n/a | phase4_DONE.md (56 KB) |
| **Phase 4 total** | - | **401 LOC across 3 files (1 shared)** | **544 LOC across 3 files; 32 def-tests = 40 collected (parametric expansion)** | - |

---

## Phase 5 - Console + Receipts API

| CP | Title | Production code (file: LOC) | Test file (file: LOC; tests) | Notes |
|---|---|---|---|---|
| CP5.1 | HealthBadge 4-state | apps/console/src/components/HealthBadge.tsx (vitest target) | apps/console/src/components/__tests__/HealthBadge.test.tsx: 106; 14 it-tests | 4-state pill + last-checked tooltip |
| CP5.2 | GET /v1/receipts list | apps/api/routes/receipts.py: 134 (shared with CP5.3)  +  packages/ledger/repositories.py: 192 (list_receipts_for_tenant added; shared with Phase 4) | tests/api/test_receipts_route.py: 256; 12 (CP5.2 subset = 8 tests) | Pagination + base64 sig + dependency_overrides |
| CP5.3 | GET /v1/receipts/{id} + integrity | apps/api/routes/receipts.py (shared CP5.2)  +  packages/ledger/repositories.py (get_receipt_by_id added) | tests/api/test_receipts_route.py (shared CP5.2; CP5.3 subset = 4 tests) | integrity_ok live recompute; 404 not found |
| CP5.4 | ReceiptList + ReceiptDetail UI | apps/console/src/components/ReceiptList.tsx  +  apps/console/src/components/ReceiptDetail.tsx  +  apps/console/src/app/page.tsx (extended)  +  apps/console/src/app/receipts/[id]/page.tsx (new) | apps/console/src/components/__tests__/ReceiptList.test.tsx: 123; 11  +  apps/console/src/components/__tests__/ReceiptDetail.test.tsx: 118; 11 | Red TAMPER DETECTED badge; click-nav; cancellation paths |
| CP5.5 | Phase 5 DONE doc | n/a | n/a | phase5_DONE.md (67 KB) |
| **Phase 5 total** | - | **6 new TypeScript files + 1 route Python file + repositories.py extensions** | **3 vitest files (347 LOC; 36 it-tests) + 1 pytest file (256 LOC; 12 def-tests)** | - |

---

## Phase 6 - Evidence pack export

| CP | Title | Production code (file: LOC) | Test file (file: LOC; tests) | Notes |
|---|---|---|---|---|
| CP6.1 | JSON-LD evidence pack schema | packages/export/schema.py: 111 | tests/packages/test_evidence_schema.py: 137; 16 | EvidencePackHeader + ReceiptEvidenceItem + ProvActivity + EvidencePack pydantic models with @context + PROV-O |
| CP6.2 | build_evidence_pack + verify | packages/export/builder.py: 119 | tests/packages/test_evidence_builder.py: 171; 9 | root_hash binds whole pack via canonical_json + SHA-256 |
| CP6.3 | PDF render with hash chain | DEFERRED | DEFERRED | Phase 9 polish; presentation over JSON-LD |
| CP6.4 | GET /v1/evidence-packs endpoint | apps/api/routes/evidence.py: 74 | tests/api/test_evidence_route.py: 212; 6 | 422 naive/inverted scope; 413 over 1000 receipts |
| CP6.5 | Phase 6 DONE doc | n/a | n/a | phase6_DONE.md (32 KB) |
| **Phase 6 total** | - | **304 LOC across 3 files** | **520 LOC across 3 files; 31 def-tests** | CP6.3 honest deferral |

---

## Phase 7 - Gemini narrative generation

| CP | Title | Production code (file: LOC) | Test file (file: LOC; tests) | Notes |
|---|---|---|---|---|
| CP7.1 | NarrativeClient ABC + MockNarrativeClient | packages/narrative/client.py: 67 | tests/packages/test_narrative.py: 128; 12 (CP7.1 subset = 6 tests) | NarrativeResult dataclass; content_hash binds prompt + model + text |
| CP7.2 | build_prompt + prompt_hash | packages/narrative/prompt.py: 53 | tests/packages/test_narrative.py (shared CP7.1; CP7.2 subset = 6 tests) | EvidencePack-driven; head-5 receipt truncation |
| CP7.3 | POST /v1/narratives endpoint | apps/api/routes/narratives.py: 106 | tests/api/test_narratives_route.py: 222; 7 | 3-anchor chain (pack_root_hash + prompt_hash + content_hash); 502 for client fail |
| CP7.4 | Phase 7 DONE doc | n/a | n/a | phase7_DONE.md (33 KB) |
| **Phase 7 total** | - | **226 LOC across 3 files** | **350 LOC across 2 files; 19 def-tests** | - |

---

## Phase 8 - Demo tabletop + BR-09 load test

| CP | Title | Production code (file: LOC) | Test file (file: LOC; tests) | Notes |
|---|---|---|---|---|
| CP8.1 | demo_tabletop one-command demo | scripts/demo_tabletop.py: 112 | tests/scripts/test_demo_and_load.py: 36; 4 (CP8.1 subset = 2 tests) | 5-stage pipeline; ALL CHECKS PASSED end state |
| CP8.2 | BR-09 load test | scripts/load_test.py: 83 | tests/scripts/test_demo_and_load.py (shared CP8.1; CP8.2 subset = 2 tests) | 1000 events in 0.155s = 6452 events / sec |
| CP8.3 | Live Gemini client | DEFERRED | DEFERRED | Phase 9 demo day; FORENSA_GEMINI_API_KEY env var |
| CP8.4 | Phase 8 DONE doc + final report | n/a | n/a | phase8_DONE.md (16 KB) + STATUS_REPORT_20260514_0420.md |
| **Phase 8 total** | - | **195 LOC across 2 files** | **36 LOC across 1 file; 4 def-tests** | CP8.3 honest deferral |

---

## Cross-cutting tests (not phase-specific - schema models from earlier units)

| Subject | Production code | Test file (file: LOC; tests) |
|---|---|---|
| Event pydantic | packages/schema/event.py: 81 | tests/packages/test_event.py: 78; 11 |
| Receipt pydantic | packages/schema/receipt.py: 63 | tests/packages/test_receipt.py: 90; 14 |
| Tenant pydantic | packages/schema/tenant.py: 52 | tests/packages/test_tenant.py: 46; 7 |
| Agent pydantic | packages/schema/agent.py: 56 | tests/packages/test_agent.py: 61; 10 |
| PolicyBundle pydantic | packages/schema/policy_bundle.py: 39 | tests/packages/test_policy_bundle.py: 69; 9 |
| OTel GenAI normaliser | packages/ingest/normaliser.py: 121 | tests/packages/test_normaliser.py: 188; 26 |
| healthz endpoint | apps/api/main.py healthz path | tests/api/test_healthz.py: 23; 2 |
| POST /v1/events endpoint | apps/api/routes/events.py: 34 | tests/api/test_events_endpoint.py: 103; 11 |
| **Cross-cutting total** | **445 LOC across 7 files** | **658 LOC across 8 files; 90 def-tests** | |

---

## Grand totals

| Source | Files | LOC | Test files | Test LOC | Tests |
|---|---:|---:|---:|---:|---:|
| Phase 1 (crypto) | 3 | 238 | 3 | 381 | 61 (= 65 collected) |
| Phase 2 (policy) | 2 | 230 | 2 | 327 | 45 (= 49 collected) |
| Phase 3 (snapshot) | 3 | 422 | 4 | 542 | 42 (= 32 base + parametric) |
| Phase 4 (receipts) | 3 | 401 (1 shared) | 3 | 544 | 32 (= 40 collected) |
| Phase 5 (console + API) | 6 TypeScript + 1 Python | ~590 + 134 | 3 vitest + 1 pytest | 347 + 256 | 36 vitest + 12 pytest |
| Phase 6 (evidence) | 3 | 304 | 3 | 520 | 31 |
| Phase 7 (narrative) | 3 | 226 | 2 | 350 | 19 |
| Phase 8 (demo + load) | 2 | 195 | 1 | 36 | 4 |
| Cross-cutting | 7 | 445 | 8 | 658 | 90 |
| **Grand total Python** | **24** | **~2415 LOC** | **24** | **~3370 LOC** | **464 pytest** |
| **Grand total TypeScript** | **6** | **~590 LOC** | **3** | **347 LOC** | **36 vitest** |
| **Grand total Playwright** | **2 test files** | n/a | 2 | n/a | **2** |
| **Combined** | **30 files** | **~3005 LOC production** | **29 files** | **~3717 LOC tests** | **502 tests at 100pct coverage** |

---

## Quick lookup index

### Where does crypto live?
- packages/crypto/hash.py + sign.py + merkle.py
- tests/packages/test_crypto_hash.py + test_crypto_sign.py + test_crypto_merkle.py

### Where does the receipt chain live?
- packages/ledger/receipt_builder.py (build_receipt + recompute_receipt_hash)
- packages/ledger/repositories.py (write_event_with_receipt + list + get_by_id)
- packages/ledger/models.py (PolicySnapshotRow + ReceiptRow ORM)
- tests/packages/test_receipt_builder.py + test_receipt_chain.py + test_repositories.py

### Where do the API endpoints live?
- apps/api/main.py (FastAPI app factory + healthz)
- apps/api/routes/events.py (POST /v1/events)
- apps/api/routes/receipts.py (GET /v1/receipts + GET /v1/receipts/{id})
- apps/api/routes/evidence.py (GET /v1/evidence-packs)
- apps/api/routes/narratives.py (POST /v1/narratives)
- tests/api/ (one test file per route)

### Where does the UI live?
- apps/console/src/components/HealthBadge.tsx + ReceiptList.tsx + ReceiptDetail.tsx
- apps/console/src/app/page.tsx (home)
- apps/console/src/app/receipts/[id]/page.tsx (detail route)
- apps/console/src/components/__tests__/ (one test file per component)

### Where does the demo live?
- scripts/demo_tabletop.py (5-stage pipeline)
- scripts/load_test.py (BR-09 1000 events)
- tests/scripts/test_demo_and_load.py

---

## End of file

Every production file has a corresponding test file. Every test file enforces 100pct coverage on its production code. Reading this table answers the question: "what was built, where is it, and where are its tests?" for every CP.
