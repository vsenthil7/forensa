"""CP9.60b - replace <pending> SHA placeholders in LIVE traceability matrix
with the actual commit SHAs landed in this session.

The LIVE matrix was authored by web Claude before the SHAs existed. This
script substitutes them in place. One pass, idempotent (if no <pending>
left, nothing to do).
"""

from pathlib import Path

LIVE = Path(
    r"C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google"
    r"\forensa\docs\17_traceability_matrix\TRACEABILITY_MATRIX_LIVE.md"
)

# Map each <pending> row to its real SHA based on CP id in the row.
# Order matters: most-recent-first matches the LIVE file's ordering.
substitutions = [
    # CP9.59 - 1 pending row
    ("`<pending>` | 2026-05-18 16:30 BST | **CP9.59**",
     "`321ceb7` | 2026-05-18 17:08 BST | **CP9.59**"),
    # CP9.53..58 are all in the single combined commit 'aefb18c'
    ("`<pending>` | 2026-05-18 15:21 BST | **CP9.58**",
     "`aefb18c` | 2026-05-18 17:05 BST | **CP9.58**"),
    ("`<pending>` | 2026-05-18 15:21 BST | **CP9.57**",
     "`aefb18c` | 2026-05-18 17:05 BST | **CP9.57**"),
    ("`<pending>` | 2026-05-18 15:21 BST | **CP9.56**",
     "`aefb18c` | 2026-05-18 17:05 BST | **CP9.56**"),
    ("`<pending>` | 2026-05-18 15:21 BST | **CP9.55**",
     "`aefb18c` | 2026-05-18 17:05 BST | **CP9.55**"),
    ("`<pending>` | 2026-05-18 15:21 BST | **CP9.53**",
     "`aefb18c` | 2026-05-18 17:05 BST | **CP9.53**"),
    # CP9.52 - 1 pending row
    ("`<pending>` | 2026-05-18 14:45 BST | **CP9.52a-g**",
     "`1b8a2f5` | 2026-05-18 17:02 BST | **CP9.52a-g**"),
]

text = LIVE.read_text(encoding="utf-8")
for old, new in substitutions:
    assert old in text, f"ANCHOR MISSING: {old}"
    text = text.replace(old, new, 1)
LIVE.write_text(text, encoding="utf-8")

# Append a CP9.60a + CP9.60b row at the top of the ledger for the
# docs v2.0 introduction + this very SHA sweep.
ledger_anchor = "Per Rule A.11 every row names the IDs the commit closed (or advanced).\n\n| Commit | Pushed | CP | IDs closed | What |\n|---|---|---|---|---|\n"
ledger_addition = (
    ledger_anchor
    + "| `<pending-cp960b>` | 2026-05-18 17:15 BST | **CP9.60b** | LIVE doc SHA sweep | "
    "Replace `<pending>` placeholders for CP9.52/9.53/9.55/9.56/9.57/9.58/9.59 with the actual landed SHAs "
    "(1b8a2f5, aefb18c, 321ceb7). LIVE matrix now grounded against `origin/main` HEAD. "
    "Per Rule A.11: this row is documentation reconciliation, not a code CP. |\n"
    "| `b7c78cb` | 2026-05-18 16:53 BST | **CP9.60a** | Rule A.11 introduction, "
    "supersession map (BR-02/06/10/11), BRD_IDENTIFIER_MAP.md, docs/21_traceability_workbook | "
    "Apply forensa_docs_v2.0_20260518.zip (nested): full elaborated doc pack v2.0 (BRD 135-486 LOC, "
    "USE_CASES 52-328 LOC, TRACEABILITY_MATRIX 80-241 LOC, LIVE companions for both, new 13-sheet "
    "workbook, archived v1.x snapshots). |\n"
)
assert ledger_anchor in text, "Ledger anchor missing - file shape may have shifted"
text = LIVE.read_text(encoding="utf-8")
text = text.replace(ledger_anchor, ledger_addition, 1)
LIVE.write_text(text, encoding="utf-8")
print("LIVE matrix updated.")
print(f"  Substituted {len(substitutions)} <pending> rows.")
print("  Added CP9.60a + CP9.60b ledger rows at top.")
