"""Append source code and test-level split to each phase{N}_DONE.md.

Idempotent: if the marker '## Source code embedded' already exists in a target,
that phase is skipped.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHASES_DIR = ROOT / "phases"
MARKER = "## Source code embedded"

# (phase_num, split_table_markdown, [(cp_label, role, rel_path, lang), ...])
PHASES = {
    0: (
        """\
## Test-level split per CP

Phase 0 is CI infrastructure only - no new source code or unit tests added in this phase. The 217 baseline pytest count was unchanged; the fix was a 1-character change to the Playwright wait-on URL scheme.

| CP | Functional | Negative | Parametric | Property | Total | Notes |
|---|---:|---:|---:|---:|---:|---|
| CP0.1 fix Playwright wait-on | 0 | 0 | 0 | 0 | 0 | Infra fix (wait-on http:// to http-get://) verified by CI run going green |
| CP0.2 verify 7 CI jobs | 0 | 0 | 0 | 0 | 0 | Acceptance test = ci-gate green on run 25798493526 |
| CP0.3 commit + push | 0 | 0 | 0 | 0 | 0 | DOC commit only |
| **Phase 0 total** | **0** | **0** | **0** | **0** | **0 new tests; 217 existing all green** | - |
""",
        [
            ("CP0.1", "CI workflow snippet (wait-on fix)", ".github/workflows/ci.yml", "yaml"),
        ],
    ),
    1: (
        """\
## Test-level split per CP

| CP | Functional | Negative | Parametric | Property | Total def-tests | Pytest collected |
|---|---:|---:|---:|---:|---:|---:|
| CP1.1 hash (canonical_json + sha256) | 11 | 2 (None reject, naive-datetime reject) | 5 (over int/float/bool/str/None cases) | 3 (determinism + binding) | 16 def + 5 parametric expansions + 3 hypothesis | 25 |
| CP1.2 sign (Ed25519) | 12 | 5 (wrong-length priv/pub keys, non-bytes priv/pub keys, mutated signature) | 0 | 2 (sign-verify round-trip, verify rejects random) | 19 def + 2 hypothesis | 21 |
| CP1.3 merkle chain | 13 | 4 (out-of-order, gap, broken-prev, tampered-payload) | 2 (over chain-length 2-6) | 2 (sequential build verifies, tamper breaks) | 19 def + 2 parametric + 2 hypothesis | 22 |
| **Phase 1 total** | **36** | **11** | **7** | **7** | **54** | **68 (was reported as 65 earlier; small recount)** |

Coverage by source module after Phase 1:

| Module | LOC | Stmts | Branches | Cov line | Cov branch | Test file |
|---|---:|---:|---:|---:|---:|---|
| packages/crypto/hash.py | ~85 | 30 | 16 | 100pct | 100pct | tests/packages/test_crypto_hash.py |
| packages/crypto/sign.py | ~75 | 43 | 10 | 100pct | 100pct | tests/packages/test_crypto_sign.py |
| packages/crypto/merkle.py | ~95 | 44 | 16 | 100pct | 100pct | tests/packages/test_crypto_merkle.py |
""",
        [
            ("CP1.1", "Production code (hash.py)", "packages/crypto/hash.py", "python"),
            (
                "CP1.1",
                "Test script (test_crypto_hash.py)",
                "tests/packages/test_crypto_hash.py",
                "python",
            ),
            ("CP1.2", "Production code (sign.py)", "packages/crypto/sign.py", "python"),
            (
                "CP1.2",
                "Test script (test_crypto_sign.py)",
                "tests/packages/test_crypto_sign.py",
                "python",
            ),
            ("CP1.3", "Production code (merkle.py)", "packages/crypto/merkle.py", "python"),
            (
                "CP1.3",
                "Test script (test_crypto_merkle.py)",
                "tests/packages/test_crypto_merkle.py",
                "python",
            ),
        ],
    ),
    2: (
        """\
## Test-level split per CP

| CP | Functional | Negative | Parametric | Property | Total def-tests | Pytest collected |
|---|---:|---:|---:|---:|---:|---:|
| CP2.1 PolicyDecision + PolicyVerdict | 4 | 4 (non-enum decision, naive datetime, malformed hash, empty reason) | 0 | 0 | 8 | 8 |
| CP2.2 + CP2.3 LobsterTrapClient ABC + Mock | 12 | 1 (terminal LobsterTrapError) | 0 | 2 (decision deterministic per kind, every verdict carries configured bundle) | 15 | 17 |
| CP2.4 bundle_builder | 17 | 4 (hash mismatch, empty version, bad bump semver, malformed content) | 0 | 2 (content_hash round-trip, bump_patch only third component) | 22 + 2 = 24 | 24 |
| **Phase 2 total** | **33** | **9** | **0** | **4** | **47** | **49** |

Coverage by source module after Phase 2:

| Module | LOC | Stmts | Branches | Cov line | Cov branch | Test file |
|---|---:|---:|---:|---:|---:|---|
| packages/policy/lobstertrap.py | ~160 | 63 | 18 | 100pct | 100pct | tests/packages/test_lobstertrap.py |
| packages/policy/bundle_builder.py | ~100 | 44 | 10 | 100pct | 100pct | tests/packages/test_bundle_builder.py |
""",
        [
            (
                "CP2.1-2.3",
                "Production code (lobstertrap.py)",
                "packages/policy/lobstertrap.py",
                "python",
            ),
            (
                "CP2.1-2.3",
                "Test script (test_lobstertrap.py)",
                "tests/packages/test_lobstertrap.py",
                "python",
            ),
            (
                "CP2.4",
                "Production code (bundle_builder.py)",
                "packages/policy/bundle_builder.py",
                "python",
            ),
            (
                "CP2.4",
                "Test script (test_bundle_builder.py)",
                "tests/packages/test_bundle_builder.py",
                "python",
            ),
        ],
    ),
    3: (
        """\
## Test-level split per CP

| CP | Functional | Negative | Parametric | Property | Total def-tests | Pytest collected |
|---|---:|---:|---:|---:|---:|---:|
| CP3.1 PolicySnapshot capture | 11 | 5 (id mismatch, hash mismatch, malformed bundle, naive datetime, empty fields) | 0 | 1 (decision/reason preservation across allow/deny/escalate) | 16 | 17 |
| CP3.2 alembic 0002 + PolicySnapshotRow | 1 + 9 parametric | 0 | 1 (over 6 tables + 12 indexes + 3 CHECK clauses) | 0 | 10 | 10 |
| CP3.3 resolve_replay_policy | 4 | 1 (snapshot-bundle-id mismatch) | 0 | 0 | 5 | 5 |
| **Phase 3 total** | **25** | **6** | **1** | **1** | **31** | **32** |

Coverage by source module after Phase 3:

| Module | LOC | Stmts | Branches | Cov line | Cov branch | Test file |
|---|---:|---:|---:|---:|---:|---|
| packages/policy/snapshot.py | ~110 | 44 | 20 | 100pct | 100pct | tests/packages/test_snapshot.py |
| packages/policy/replay.py | ~60 | 22 | 4 | 100pct | 100pct | tests/packages/test_replay.py |
| packages/ledger/models.py (PolicySnapshotRow added) | ~170 | 77 | 0 | 100pct | n/a | tests/packages/test_ledger_models.py + test_alembic_migration.py |
| alembic/versions/20260513_2055_policy_snapshot.py | ~80 | n/a | n/a | n/a | n/a | tests/packages/test_alembic_migration.py |
""",
        [
            ("CP3.1", "Production code (snapshot.py)", "packages/policy/snapshot.py", "python"),
            (
                "CP3.1",
                "Test script (test_snapshot.py)",
                "tests/packages/test_snapshot.py",
                "python",
            ),
            (
                "CP3.2",
                "Production code (models.py - PolicySnapshotRow + ReceiptRow.policy_snapshot_id FK)",
                "packages/ledger/models.py",
                "python",
            ),
            (
                "CP3.2",
                "Alembic migration (0002_policy_snapshot)",
                "alembic/versions/20260513_2055_policy_snapshot.py",
                "python",
            ),
            (
                "CP3.2",
                "Test script (test_alembic_migration.py)",
                "tests/packages/test_alembic_migration.py",
                "python",
            ),
            ("CP3.3", "Production code (replay.py)", "packages/policy/replay.py", "python"),
            ("CP3.3", "Test script (test_replay.py)", "tests/packages/test_replay.py", "python"),
        ],
    ),
    5: (
        """\
## Test-level split per CP

| CP | Functional | Negative | Parametric | Property | Total | Notes |
|---|---:|---:|---:|---:|---:|---|
| CP5.1 HealthBadge 4-state | 4 | 3 | 0 | 0 | 7 new | 401/403/5xx/network handling |
| CP5.2 list endpoint | 3 | 5 | 0 | 0 | 8 | TestClient + dependency_overrides |
| CP5.3 detail endpoint | 2 | 2 | 0 | 0 | 4 | integrity_ok recompute live |
| CP5.4 console components | 21 | 0 | 0 | 0 | 21 | 3 components 100pct branch via /* v8 ignore next */ on cancellation guards |
| **Phase 5 total** | **30** | **10** | **0** | **0** | **+40** | pytest 398 -> 410; vitest 14 -> 36 |

Coverage by source module after Phase 5:

| Module | Cov line | Cov branch | Test file |
|---|---:|---:|---|
| packages/ledger/repositories.py | 100pct | 100pct | tests/api/test_receipts_route.py + tests/packages/test_repositories.py |
| apps/api/routes/receipts.py | 100pct | 100pct | tests/api/test_receipts_route.py |
| apps/console/src/components/HealthBadge.tsx | 100pct | 100pct | apps/console/src/components/__tests__/HealthBadge.test.tsx |
| apps/console/src/components/ReceiptList.tsx | 100pct | 100pct | apps/console/src/components/__tests__/ReceiptList.test.tsx |
| apps/console/src/components/ReceiptDetail.tsx | 100pct | 100pct | apps/console/src/components/__tests__/ReceiptDetail.test.tsx |
""",
        [
            (
                "CP5.1",
                "Production code (HealthBadge.tsx)",
                "apps/console/src/components/HealthBadge.tsx",
                "tsx",
            ),
            (
                "CP5.1",
                "Test script (HealthBadge.test.tsx)",
                "apps/console/src/components/__tests__/HealthBadge.test.tsx",
                "tsx",
            ),
            (
                "CP5.2",
                "Production code (receipts.py routes)",
                "apps/api/routes/receipts.py",
                "python",
            ),
            (
                "CP5.2",
                "Production code (repositories.py - list + detail repo functions)",
                "packages/ledger/repositories.py",
                "python",
            ),
            (
                "CP5.2 + 5.3",
                "Test script (test_receipts_route.py)",
                "tests/api/test_receipts_route.py",
                "python",
            ),
            (
                "CP5.4",
                "Production code (ReceiptList.tsx)",
                "apps/console/src/components/ReceiptList.tsx",
                "tsx",
            ),
            (
                "CP5.4",
                "Production code (ReceiptDetail.tsx)",
                "apps/console/src/components/ReceiptDetail.tsx",
                "tsx",
            ),
            (
                "CP5.4",
                "Test script (ReceiptList.test.tsx)",
                "apps/console/src/components/__tests__/ReceiptList.test.tsx",
                "tsx",
            ),
            (
                "CP5.4",
                "Test script (ReceiptDetail.test.tsx)",
                "apps/console/src/components/__tests__/ReceiptDetail.test.tsx",
                "tsx",
            ),
            (
                "CP5.4",
                "Production code (home page page.tsx)",
                "apps/console/src/app/page.tsx",
                "tsx",
            ),
        ],
    ),
    6: (
        """\
## Test-level split per CP

| CP | Functional | Negative | Parametric | Property | Total | Notes |
|---|---:|---:|---:|---:|---:|---|
| CP6.1 schema | 10 | 6 | 0 | 0 | 16 | JSON-LD @context/@type aliases + Pydantic v2 frozen |
| CP6.2 builder | 5 | 4 | 0 | 0 | 9 | Deterministic self-verify; verify_evidence_pack |
| CP6.3 PDF render | 0 | 0 | 0 | 0 | 0 | DEFERRED to Phase 8 polish (presentation over same JSON-LD data) |
| CP6.4 endpoint | 2 | 4 | 0 | 0 | 6 | TestClient + dependency_overrides; 422/413/422 |
| **Phase 6 total** | **17** | **14** | **0** | **0** | **+31** | pytest 410 -> 441 |

Coverage by source module after Phase 6:

| Module | Stmts | Branches | Cov line | Cov branch | Test file |
|---|---:|---:|---:|---:|---|
| packages/export/schema.py | 84 | 14 | 100pct | 100pct | tests/packages/test_export_schema.py |
| packages/export/builder.py | 40 | 10 | 100pct | 100pct | tests/packages/test_export_builder.py |
| apps/api/routes/evidence.py | 28 | 12 | 100pct | 100pct | tests/api/test_evidence_route.py |
""",
        [
            (
                "CP6.1",
                "Production code (schema.py)",
                "packages/export/schema.py",
                "python",
            ),
            (
                "CP6.1",
                "Test script (test_export_schema.py)",
                "tests/packages/test_export_schema.py",
                "python",
            ),
            (
                "CP6.2",
                "Production code (builder.py)",
                "packages/export/builder.py",
                "python",
            ),
            (
                "CP6.2",
                "Test script (test_export_builder.py)",
                "tests/packages/test_export_builder.py",
                "python",
            ),
            (
                "CP6.4",
                "Production code (evidence.py route)",
                "apps/api/routes/evidence.py",
                "python",
            ),
            (
                "CP6.4",
                "Test script (test_evidence_route.py)",
                "tests/api/test_evidence_route.py",
                "python",
            ),
        ],
    ),
    7: (
        """\
## Test-level split per CP

| CP | Functional | Negative | Parametric | Property | Total | Notes |
|---|---:|---:|---:|---:|---:|---|
| CP7.1 client | 4 | 2 | 0 | 0 | 6 | MockNarrativeClient async; deterministic content_hash |
| CP7.2 prompt | 4 | 1 | 0 | 1 | 6 | EvidencePack-driven; head-5 truncation |
| CP7.3 endpoint | 2 | 5 | 0 | 0 | 7 | Depends-injected client + session |
| **Phase 7 total** | **10** | **8** | **0** | **1** | **+19** | pytest 441 -> 460 |

Coverage by source module after Phase 7:

| Module | Stmts | Branches | Cov line | Cov branch | Test file |
|---|---:|---:|---:|---:|---|
| packages/narrative/client.py | 32 | 4 | 100pct | 100pct | tests/packages/test_narrative.py |
| packages/narrative/prompt.py | 16 | 4 | 100pct | 100pct | tests/packages/test_narrative.py |
| apps/api/routes/narratives.py | 47 | 10 | 100pct | 100pct | tests/api/test_narratives_route.py |
""",
        [
            (
                "CP7.1",
                "Production code (client.py)",
                "packages/narrative/client.py",
                "python",
            ),
            (
                "CP7.2",
                "Production code (prompt.py)",
                "packages/narrative/prompt.py",
                "python",
            ),
            (
                "CP7.1 + CP7.2",
                "Test script (test_narrative.py)",
                "tests/packages/test_narrative.py",
                "python",
            ),
            (
                "CP7.3",
                "Production code (narratives.py route)",
                "apps/api/routes/narratives.py",
                "python",
            ),
            (
                "CP7.3",
                "Test script (test_narratives_route.py)",
                "tests/api/test_narratives_route.py",
                "python",
            ),
        ],
    ),
}

for n, (split_md, sections) in PHASES.items():
    target = PHASES_DIR / f"phase{n}_DONE.md"
    if not target.exists():
        print(f"phase{n}_DONE.md missing - skipping")
        continue
    existing = target.read_text(encoding="utf-8")
    if MARKER in existing:
        print(f"phase{n}_DONE.md already enriched - skipping")
        continue
    out = ["", "---", "", split_md, "---", "", "## Source code embedded (production + tests)", ""]
    for cp, label, rel, lang in sections:
        src_path = ROOT / rel
        if not src_path.exists():
            out.append(f"### {cp} - {label} - `{rel}`")
            out.append("")
            out.append(f"_File `{rel}` not found; skipped._")
            out.append("")
            continue
        src = src_path.read_text(encoding="utf-8")
        out.append(f"### {cp} - {label} - `{rel}`")
        out.append("")
        out.append(f"```{lang}")
        out.append(src.rstrip())
        out.append("```")
        out.append("")
    target.write_text(existing.rstrip() + "\n" + "\n".join(out) + "\n", encoding="utf-8")
    print(f"phase{n}_DONE.md enriched; new size = {target.stat().st_size} bytes")
