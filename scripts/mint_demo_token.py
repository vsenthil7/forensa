"""scripts/mint_demo_token.py — mint a Bearer token for the local-dev demo tenant.

CP9.61b. Reads FORENSA_HMAC_SECRET + FORENSA_HMAC_TENANT_ID from env and
emits a signed HMAC token to stdout. Useful for curl / httpie one-liners
against the local stack.

Usage (host):
    docker exec -e PYTHONPATH=/app -w /app forensa-api python /app/scripts/mint_demo_token.py

Usage (inside container):
    cd /app && python scripts/mint_demo_token.py

The minted token grants the read scopes for the four authenticated console
surfaces (receipts, anchors, evidence, narratives) plus metrics:read. For
write operations (events:write etc.) re-run with additional scopes.

Production token issuance (CP10.1) replaces this with an OIDC auth service.
"""

from __future__ import annotations

import os
import sys
from uuid import UUID

from apps.api.auth.token import mint_hmac_token


def main() -> int:
    secret_hex = os.environ.get("FORENSA_HMAC_SECRET")
    tenant_raw = os.environ.get("FORENSA_HMAC_TENANT_ID")
    if not secret_hex or not tenant_raw:
        print(
            "ERROR: FORENSA_HMAC_SECRET and FORENSA_HMAC_TENANT_ID must be set",
            file=sys.stderr,
        )
        return 1

    token = mint_hmac_token(
        tenant_id=UUID(tenant_raw),
        agent_id=UUID("00000000-0000-0000-0000-000000000001"),
        agent_slug="demo-agent",
        secret=bytes.fromhex(secret_hex),
        scopes=[
            "receipts:read",
            "anchors:read",
            "evidence:read",
            "narratives:read",
            "metrics:read",
            "tabletop:simulate",
            "ma-diligence:export",
        ],
    )
    print(token, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
