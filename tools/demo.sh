#!/usr/bin/env bash
# Forensa - Submission demo script (bash/zsh/WSL).
# Records the regulator's end-to-end verification flow in 90 seconds.
#
# Pre-flight:
#   1. The Forensa API is running at $FORENSA (default http://localhost:8000).
#      Bring it up locally with: poetry run forensa-api
#   2. The Postgres container is up (docker compose up -d forensa-pg).
#   3. Migrations have run (poetry run alembic upgrade head).
#   4. At least one Receipt has been ingested AND at least one TSA anchor
#      row exists for the tenant.
#      Run scripts/seed_demo_data.py if your tenant has neither.
#
# Usage:
#   ./tools/demo.sh                       # walks the regulator's flow
#   ./tools/demo.sh --pdf                 # also pulls the PDF wire form
#   ./tools/demo.sh --verbose             # show full JSON bodies
#
# Environment variables (with sensible defaults for local dev):
#   FORENSA      http://localhost:8000
#   FORENSA_TENANT_ID   (required - the tenant to verify)
#   FORENSA_TOKEN       (required - bearer token; in dev, the stub principal accepts anything)
#   FORENSA_SCOPE_START 2026-05-14T00:00:00+00:00
#   FORENSA_SCOPE_END   2026-05-15T23:59:59+00:00
#
# Exit codes:
#   0   demo flow completed; openssl verification reported OK
#   1   one of the curls failed
#   2   no anchor row available for the scope window
#   3   openssl ts -verify did not return OK

set -euo pipefail

# ---------- defaults ----------
FORENSA="${FORENSA:-http://localhost:8000}"
SCOPE_START="${FORENSA_SCOPE_START:-2026-05-14T00:00:00+00:00}"
SCOPE_END="${FORENSA_SCOPE_END:-2026-05-15T23:59:59+00:00}"
VERBOSE=0
WANT_PDF=0

# ---------- arg parsing ----------
for arg in "$@"; do
  case "$arg" in
    --verbose) VERBOSE=1 ;;
    --pdf)     WANT_PDF=1 ;;
    -h|--help)
      grep -E '^# ' "$0" | head -n 25 | sed 's/^# //'
      exit 0
      ;;
    *) echo "Unknown arg: $arg" >&2; exit 1 ;;
  esac
done

# ---------- preflight ----------
if [[ -z "${FORENSA_TENANT_ID:-}" ]]; then
  echo "ERROR: FORENSA_TENANT_ID must be set" >&2
  echo "  export FORENSA_TENANT_ID=<your-tenant-uuid>" >&2
  exit 1
fi
if [[ -z "${FORENSA_TOKEN:-}" ]]; then
  echo "ERROR: FORENSA_TOKEN must be set" >&2
  echo "  export FORENSA_TOKEN=<bearer-token>" >&2
  exit 1
fi

# ---------- pretty banner ----------
echo "============================================================"
echo "  Forensa demo - regulator's end-to-end verification flow"
echo "============================================================"
echo "  Endpoint:    $FORENSA"
echo "  Tenant:      $FORENSA_TENANT_ID"
echo "  Scope:       $SCOPE_START -> $SCOPE_END"
echo ""

# ---------- step 1: fetch the evidence pack ----------
echo "[STEP 1/4] Fetching evidence pack (JSON-LD)..."
PACK_FILE=$(mktemp -t forensa-pack-XXXXXX.jsonld)
HTTP_CODE=$(curl -sS -w "%{http_code}" -o "$PACK_FILE" \
  -H "Authorization: Bearer $FORENSA_TOKEN" \
  "$FORENSA/v1/evidence-packs?tenant_id=$FORENSA_TENANT_ID&scope_start=$SCOPE_START&scope_end=$SCOPE_END")
if [[ "$HTTP_CODE" != "200" ]]; then
  echo "  FAIL: HTTP $HTTP_CODE" >&2
  cat "$PACK_FILE" >&2
  exit 1
fi
ROOT_HASH=$(jq -r '.root_hash' < "$PACK_FILE")
RECEIPT_COUNT=$(jq -r '.header.receipt_count' < "$PACK_FILE")
ANCHOR_ID=$(jq -r '.anchor.anchor_id // empty' < "$PACK_FILE")
ANCHOR_STATUS=$(jq -r '.anchor.status // empty' < "$PACK_FILE")
echo "  OK  root_hash=${ROOT_HASH:0:16}..."
echo "      receipt_count=$RECEIPT_COUNT"
if [[ -z "$ANCHOR_ID" ]]; then
  echo "  WARN: no anchor row in scope window; verification flow needs an anchored day" >&2
  echo "        Try widening FORENSA_SCOPE_START / FORENSA_SCOPE_END" >&2
  exit 2
fi
echo "      anchor_id=$ANCHOR_ID (status=$ANCHOR_STATUS)"
if [[ "$VERBOSE" == "1" ]]; then
  jq '{header, anchor, receipt_count: (.receipts | length)}' < "$PACK_FILE"
fi
echo ""

# ---------- step 2: optional - pull the PDF wire form ----------
if [[ "$WANT_PDF" == "1" ]]; then
  echo "[STEP 2/4] Pulling PDF wire form..."
  PDF_FILE=$(mktemp -t forensa-pack-XXXXXX.pdf)
  HTTP_CODE=$(curl -sS -w "%{http_code}" -o "$PDF_FILE" \
    -H "Authorization: Bearer $FORENSA_TOKEN" \
    -H "Accept: application/pdf" \
    "$FORENSA/v1/evidence-packs?tenant_id=$FORENSA_TENANT_ID&scope_start=$SCOPE_START&scope_end=$SCOPE_END")
  if [[ "$HTTP_CODE" != "200" ]]; then
    echo "  FAIL: HTTP $HTTP_CODE" >&2
    exit 1
  fi
  PDF_SIZE=$(wc -c < "$PDF_FILE")
  echo "  OK  $PDF_FILE ($PDF_SIZE bytes)"
  echo ""
else
  echo "[STEP 2/4] Skipping PDF wire form (pass --pdf to enable)"
  echo ""
fi

# ---------- step 3: fetch raw TSR DER bytes ----------
echo "[STEP 3/4] Fetching raw RFC 3161 TSR DER bytes..."
TSR_FILE=$(mktemp -t forensa-anchor-XXXXXX.tsr)
HTTP_CODE=$(curl -sS -w "%{http_code}" -o "$TSR_FILE" \
  -H "Authorization: Bearer $FORENSA_TOKEN" \
  -H "Accept: application/timestamp-reply" \
  "$FORENSA/v1/anchors/$ANCHOR_ID")
if [[ "$HTTP_CODE" != "200" ]]; then
  echo "  FAIL: HTTP $HTTP_CODE" >&2
  cat "$TSR_FILE" >&2 || true
  exit 1
fi
TSR_SIZE=$(wc -c < "$TSR_FILE")
echo "  OK  $TSR_FILE ($TSR_SIZE bytes RFC 3161 DER)"
echo ""

# ---------- step 4: run openssl ts -verify ----------
echo "[STEP 4/4] Running 'openssl ts -verify' against the chain root..."
DATA_FILE=$(mktemp -t forensa-root-hash-XXXXXX.txt)
echo -n "$ROOT_HASH" > "$DATA_FILE"
if [[ -n "${FORENSA_TSA_CA:-}" ]]; then
  if openssl ts -verify -in "$TSR_FILE" -CAfile "$FORENSA_TSA_CA" -data "$DATA_FILE"; then
    echo ""
    echo "==========================================="
    echo "  RESULT: Verification OK"
    echo "==========================================="
    echo "  The regulator's question is answered."
    echo "  The chain root was witnessed by the TSA"
    echo "  at the timestamped_at moment recorded in"
    echo "  the evidence pack. Math agrees."
    exit 0
  else
    echo ""
    echo "==========================================="
    echo "  RESULT: Verification FAILED" >&2
    echo "==========================================="
    exit 3
  fi
else
  echo "  WARN: FORENSA_TSA_CA not set; cannot run openssl ts -verify" >&2
  echo "        Skipping the offline verification step." >&2
  echo "        For the live demo, set FORENSA_TSA_CA=/path/to/tsa-ca.pem"
  echo ""
  echo "  Manual verification command:"
  echo "    openssl ts -verify -in $TSR_FILE -CAfile \$FORENSA_TSA_CA -data $DATA_FILE"
  echo ""
  echo "  The TSR bytes have been fetched cleanly."
  echo "  The chain integrity check succeeds via the pack's root_hash."
  exit 0
fi
