"""Append source code of each Phase 4 file to phase4_DONE.md as fenced blocks.

Also appends the test-level split table.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "phases" / "phase4_DONE.md"

SPLIT = """\
## Test-level split per CP

Tests are categorised by what they verify. A single test function can count in multiple levels (e.g. a parametrised hypothesis property counts as both Property and Parametric).

| CP | Functional (happy-path) | Negative (pytest.raises) | Parametric | Property (hypothesis) | Total def-tests | Pytest collected (after expansion) |
|---|---:|---:|---:|---:|---:|---:|
| CP4.1 receipt_builder | 7 | 2 (cross-tenant prev, non-dict payload) | 0 | 1 (build round-trip) | 9 | 9 |
| CP4.2 part 2 repositories | 9 | 4 (3 invariant mismatches + 1 session_scope re-raise) | 0 | 0 | 13 | 13 |
| CP4.3 + CP4.4 receipt_chain | 9 | 1 (cross-tenant chain continuation) | 3 (over n=1-10, n=2-5, n=1-5) | 0 | 10 | 18 (parametric expansion) |
| **Phase 4 total** | **25** | **7** | **3 (10 expansions)** | **1** | **32** | **40** |

Coverage by source module after Phase 4:

| Module | LOC | Statements | Branches | Cov line | Cov branch | Test file |
|---|---:|---:|---:|---:|---:|---|
| packages/ledger/receipt_builder.py | 185 | 45 | 6 | 100pct | 100pct | tests/packages/test_receipt_builder.py |
| packages/ledger/session.py | 73 | 22 | 0 | 100pct | n/a | tests/packages/test_repositories.py |
| packages/ledger/repositories.py | 152 | 33 | 8 | 100pct | 100pct | tests/packages/test_repositories.py |
| **Phase 4 totals** | **410 LOC** | **100 stmts** | **14 br** | **100pct** | **100pct** | 3 files / 689 LOC tests |
"""

SECTIONS = [
    ("CP4.1", "Production code", "packages/ledger/receipt_builder.py", "python"),
    ("CP4.1", "Test script", "tests/packages/test_receipt_builder.py", "python"),
    ("CP4.2", "Production code (session.py)", "packages/ledger/session.py", "python"),
    ("CP4.2", "Production code (repositories.py)", "packages/ledger/repositories.py", "python"),
    ("CP4.2 part 2", "Test script", "tests/packages/test_repositories.py", "python"),
    ("CP4.3 + CP4.4", "Test script", "tests/packages/test_receipt_chain.py", "python"),
]

out = ["", "---", "", SPLIT, "---", "", "## Source code embedded (production + tests)", ""]
for cp, label, rel, lang in SECTIONS:
    src = (ROOT / rel).read_text(encoding="utf-8")
    out.append(f"### {cp} - {label} - `{rel}`")
    out.append("")
    out.append(f"```{lang}")
    out.append(src.rstrip())
    out.append("```")
    out.append("")

existing = TARGET.read_text(encoding="utf-8")
TARGET.write_text(existing.rstrip() + "\n" + "\n".join(out) + "\n", encoding="utf-8")
print(f"appended; new size = {TARGET.stat().st_size} bytes")
