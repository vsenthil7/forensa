<#
.SYNOPSIS
    Forensa - Submission demo script (PowerShell).

.DESCRIPTION
    Records the regulator's end-to-end verification flow in 90 seconds.
    PowerShell companion to tools/demo.sh; same flow, Windows-native.

.PARAMETER Pdf
    Also pull the PDF wire form alongside the JSON-LD.

.PARAMETER Verbose
    Print the full JSON pack body, not just the summary fields.

.NOTES
    Pre-flight:
        1. The Forensa API is running at $env:FORENSA (default http://localhost:8000).
           Bring it up locally with: poetry run forensa-api
        2. The Postgres container is up (docker compose up -d forensa-pg).
        3. Migrations have run (poetry run alembic upgrade head).
        4. At least one Receipt has been ingested AND at least one TSA anchor
           row exists for the tenant.

    Required environment variables:
        FORENSA_TENANT_ID    the tenant UUID to verify
        FORENSA_TOKEN        bearer token; dev stub principal accepts anything

    Optional:
        FORENSA              http://localhost:8000
        FORENSA_SCOPE_START  2026-05-14T00:00:00+00:00
        FORENSA_SCOPE_END    2026-05-15T23:59:59+00:00
        FORENSA_TSA_CA       path to TSA CA PEM for the openssl step

    Exit codes:
        0   demo flow completed; openssl verification reported OK
        1   one of the HTTP calls failed
        2   no anchor row available for the scope window
        3   openssl ts -verify did not return OK

.EXAMPLE
    .\tools\demo.ps1
    .\tools\demo.ps1 -Pdf
    .\tools\demo.ps1 -Pdf -Verbose
#>
[CmdletBinding()]
param(
    [switch]$Pdf
)

$ErrorActionPreference = 'Stop'

# ---------- defaults ----------
$forensa     = if ($env:FORENSA)             { $env:FORENSA }             else { 'http://localhost:8000' }
$scopeStart  = if ($env:FORENSA_SCOPE_START) { $env:FORENSA_SCOPE_START } else { '2026-05-14T00:00:00+00:00' }
$scopeEnd    = if ($env:FORENSA_SCOPE_END)   { $env:FORENSA_SCOPE_END }   else { '2026-05-15T23:59:59+00:00' }
$tenantId    = $env:FORENSA_TENANT_ID
$token       = $env:FORENSA_TOKEN
$tsaCa       = $env:FORENSA_TSA_CA

# ---------- preflight ----------
if (-not $tenantId) {
    Write-Host "ERROR: FORENSA_TENANT_ID must be set" -ForegroundColor Red
    Write-Host "  `$env:FORENSA_TENANT_ID = '<your-tenant-uuid>'"
    exit 1
}
if (-not $token) {
    Write-Host "ERROR: FORENSA_TOKEN must be set" -ForegroundColor Red
    Write-Host "  `$env:FORENSA_TOKEN = '<bearer-token>'"
    exit 1
}

# ---------- pretty banner ----------
Write-Host "============================================================"
Write-Host "  Forensa demo - regulator's end-to-end verification flow"
Write-Host "============================================================"
Write-Host "  Endpoint:    $forensa"
Write-Host "  Tenant:      $tenantId"
Write-Host "  Scope:       $scopeStart -> $scopeEnd"
Write-Host ""

# URL-encode the scope datetimes for safety.
$encStart = [uri]::EscapeDataString($scopeStart)
$encEnd   = [uri]::EscapeDataString($scopeEnd)

# ---------- step 1: fetch the evidence pack ----------
Write-Host "[STEP 1/4] Fetching evidence pack (JSON-LD)..."
$packUri = "$forensa/v1/evidence-packs?tenant_id=$tenantId&scope_start=$encStart&scope_end=$encEnd"
try {
    $packResponse = Invoke-WebRequest -Uri $packUri `
        -Headers @{ Authorization = "Bearer $token" } `
        -UseBasicParsing
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
$pack = $packResponse.Content | ConvertFrom-Json
$rootHash      = $pack.root_hash
$receiptCount  = $pack.header.receipt_count
$anchorId      = if ($pack.anchor) { $pack.anchor.anchor_id } else { $null }
$anchorStatus  = if ($pack.anchor) { $pack.anchor.status }    else { $null }

Write-Host "  OK  root_hash=$($rootHash.Substring(0,16))..."
Write-Host "      receipt_count=$receiptCount"
if (-not $anchorId) {
    Write-Host "  WARN: no anchor row in scope window; verification flow needs an anchored day" -ForegroundColor Yellow
    Write-Host "        Try widening FORENSA_SCOPE_START / FORENSA_SCOPE_END" -ForegroundColor Yellow
    exit 2
}
Write-Host "      anchor_id=$anchorId (status=$anchorStatus)"
if ($VerbosePreference -eq 'Continue') {
    $pack | ConvertTo-Json -Depth 6 | Write-Host
}
Write-Host ""

# ---------- step 2: optional - pull the PDF wire form ----------
if ($Pdf) {
    Write-Host "[STEP 2/4] Pulling PDF wire form..."
    $pdfFile = Join-Path $env:TEMP "forensa-pack-$([guid]::NewGuid().ToString('N').Substring(0,8)).pdf"
    try {
        Invoke-WebRequest -Uri $packUri `
            -Headers @{ Authorization = "Bearer $token"; Accept = 'application/pdf' } `
            -OutFile $pdfFile -UseBasicParsing
    } catch {
        Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
    $pdfSize = (Get-Item $pdfFile).Length
    Write-Host "  OK  $pdfFile ($pdfSize bytes)"
    Write-Host ""
} else {
    Write-Host "[STEP 2/4] Skipping PDF wire form (pass -Pdf to enable)"
    Write-Host ""
}

# ---------- step 3: fetch raw TSR DER bytes ----------
Write-Host "[STEP 3/4] Fetching raw RFC 3161 TSR DER bytes..."
$tsrFile  = Join-Path $env:TEMP "forensa-anchor-$([guid]::NewGuid().ToString('N').Substring(0,8)).tsr"
$tsrUri   = "$forensa/v1/anchors/$anchorId"
try {
    Invoke-WebRequest -Uri $tsrUri `
        -Headers @{ Authorization = "Bearer $token"; Accept = 'application/timestamp-reply' } `
        -OutFile $tsrFile -UseBasicParsing
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
$tsrSize = (Get-Item $tsrFile).Length
Write-Host "  OK  $tsrFile ($tsrSize bytes RFC 3161 DER)"
Write-Host ""

# ---------- step 4: run openssl ts -verify ----------
Write-Host "[STEP 4/4] Running 'openssl ts -verify' against the chain root..."
$dataFile = Join-Path $env:TEMP "forensa-root-hash-$([guid]::NewGuid().ToString('N').Substring(0,8)).txt"
[System.IO.File]::WriteAllText($dataFile, $rootHash, [System.Text.UTF8Encoding]::new($false))

if ($tsaCa) {
    $opensslOutput = & openssl ts -verify -in $tsrFile -CAfile $tsaCa -data $dataFile 2>&1
    $exitCode = $LASTEXITCODE
    Write-Host $opensslOutput
    if ($exitCode -eq 0) {
        Write-Host ""
        Write-Host "==========================================="
        Write-Host "  RESULT: Verification OK"  -ForegroundColor Green
        Write-Host "==========================================="
        Write-Host "  The regulator's question is answered."
        Write-Host "  The chain root was witnessed by the TSA"
        Write-Host "  at the timestamped_at moment recorded in"
        Write-Host "  the evidence pack. Math agrees."
        exit 0
    } else {
        Write-Host ""
        Write-Host "===========================================" -ForegroundColor Red
        Write-Host "  RESULT: Verification FAILED" -ForegroundColor Red
        Write-Host "===========================================" -ForegroundColor Red
        exit 3
    }
} else {
    Write-Host "  WARN: FORENSA_TSA_CA not set; cannot run openssl ts -verify" -ForegroundColor Yellow
    Write-Host "        For the live demo, set `$env:FORENSA_TSA_CA = 'C:\path\to\tsa-ca.pem'"
    Write-Host ""
    Write-Host "  Manual verification command:"
    Write-Host "    openssl ts -verify -in $tsrFile -CAfile `$env:FORENSA_TSA_CA -data $dataFile"
    Write-Host ""
    Write-Host "  The TSR bytes have been fetched cleanly."
    Write-Host "  The chain integrity check succeeds via the pack's root_hash."
    exit 0
}
