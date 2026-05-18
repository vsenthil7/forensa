"""CP9.61 LIVE matrix sweep — add row to §1 commit ledger and update header.

Closes NFR-deployment-local per Rule A.11. Row references the 11 commits
landed between e52481a (CP9.60 close) and aec3de6 (CP9.61b dev.ps1 fix).
"""
from pathlib import Path

p = Path(
    r"C:\Users\v_sen\Documents\Projects\0007_AT_Hack0018_Forensa_TechEx_Veea_Google"
    r"\forensa\docs\17_traceability_matrix\TRACEABILITY_MATRIX_LIVE.md"
)
text = p.read_text(encoding="utf-8")

# 1. Update header lines: "Date stamp" + "Last sweep"
old_header = "**Doc:** 17b of 22 | **Companion to:** `TRACEABILITY_MATRIX.md` (canonical) | **Date stamp:** 2026-05-18 16:30 BST\n**Status:** LIVE — updated after every dev commit before the next mini-sprint starts\n**Last sweep:** 2026-05-18 16:30 BST after CP9.59 (API-F15 metrics endpoint + `/status` MetricsPanel)"
new_header = "**Doc:** 17b of 22 | **Companion to:** `TRACEABILITY_MATRIX.md` (canonical) | **Date stamp:** 2026-05-18 19:34 BST\n**Status:** LIVE — updated after every dev commit before the next mini-sprint starts\n**Last sweep:** 2026-05-18 19:34 BST after CP9.61 (enterprise-grade docker-compose stack + HMAC auth wiring)"
assert old_header in text, "header anchor missing"
text = text.replace(old_header, new_header, 1)

# 2. Insert CP9.61 row at top of commit ledger (after the table header line)
old_ledger_anchor = "Per Rule A.11 every row names the IDs the commit closed (or advanced).\n\n| Commit | Pushed | CP | IDs closed | What |\n|---|---|---|---|---|\n"
addition = (
    old_ledger_anchor
    + "| `aec3de6` | 2026-05-18 19:33 BST | **CP9.61 / CP9.61b** | **NFR-deployment-local close, BR-02 wiring** | "
    "Enterprise-grade local-dev orchestration: docker-compose stack with 4 services "
    "(postgres + api-migrate + api + console) matching MendoraCI pattern (`restart: unless-stopped`, "
    "healthchecks on every persistent service, `depends_on` with conditions, named volume "
    "`forensa-pg-data`, env-file `.env.compose` committed safe-default + `.env.compose.local` "
    "gitignored override). Ports chosen to avoid MendoraCI clash: postgres 5433, api 8000, console 3001. "
    "HMAC bearer auth (BR-02 / CP9.18b) wired through `FORENSA_HMAC_SECRET` + `FORENSA_HMAC_TENANT_ID` so "
    "`/v1/anchors`, `/v1/receipts`, `/v1/metrics` etc. return HTTP 200 out of the box. "
    "`tools/dev.ps1` helper with 14 actions (up/down/down-v/ps/logs/build/health/psql/migrate/status/restart/token/demo/help). "
    "`scripts/mint_demo_token.py` mints a Bearer token for the demo tenant. "
    "Six pre-existing latent bugs found and fixed: pnpm workspace symlinks with host absolute paths leaking into the image; "
    "alembic `FORENSA_DATABASE_URL` vs API `FORENSA_DB_URL` env-var mismatch; poetry venv absolute-path shebang in `/build/.venv`; "
    "PowerShell parser eating `$s?tenant_id`; `scripts/` not COPYed into the API runtime image; "
    "console Dockerfile's multi-stage standalone build never worked end-to-end. "
    "**11 commits in this CP**, all pushed to `origin/main`. End-to-end smoke test passes: "
    "all 3 services healthy, console serves 4 routes at 200, 3 authed API surfaces return 200. |\n"
)
assert old_ledger_anchor in text, "ledger anchor missing"
text = text.replace(old_ledger_anchor, addition, 1)

# 3. Append a §6 change log entry
old_changelog_anchor = "## 6. Change log\n\n| Date | Change |\n|---|---|\n"
changelog_addition = (
    old_changelog_anchor
    + "| 2026-05-18 19:34 BST | **CP9.61 sweep.** §1 commit ledger: row added for CP9.61 (enterprise-grade docker-compose stack + HMAC wiring). "
    "Header `Last sweep` flipped CP9.59 → CP9.61. "
    "Closes NFR-deployment-local. Test gate: all 4 services healthy, 4 console routes serve 200, 3 authed API surfaces return 200 with valid Bearer. "
    "Six latent bugs found and fixed during compose-up (documented in CP9.61_CLOSEOUT). |\n"
)
assert old_changelog_anchor in text, "changelog anchor missing"
text = text.replace(old_changelog_anchor, changelog_addition, 1)

p.write_text(text, encoding="utf-8")
print("LIVE matrix updated.")
print(f"  Header date stamp + Last sweep flipped to CP9.61.")
print(f"  §1 commit ledger: CP9.61 row added at top.")
print(f"  §6 change log: CP9.61 entry added at top.")
