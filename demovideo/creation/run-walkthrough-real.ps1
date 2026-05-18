# Forensa CP9.62 v2 - real-user-action walkthrough video pipeline.
#
# Mirrors auditex/demovideo/creation/run-creation.ps1 in shape.
# Single pass (no empty-state half this time - the auditex pattern shows the
# real journey end-to-end on a seeded DB).
#
# Steps:
#   1. Pre-flight  : compose stack healthy (postgres + api + console)
#   2. Wire Gemini : ensure .env.compose.local has the real key, restart api
#   3. Truncate    : drop tenant rows so the seed starts from a known state
#   4. Seed        : run scripts/seed_demo_data.py with REAL FreeTSA TSA
#                    (not mock) so TC-3 download captures real DER bytes
#                    -> parse tenant_id, token, AND bundle_id
#   5. Record      : playwright spec walkthrough-real.spec.ts
#   6. Archive     : ffmpeg trim leading frame + transcode mp4
#
# Usage:
#   pwsh ./demovideo/creation/run-walkthrough-real.ps1

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent (Split-Path -Parent $here)
$demoDir = Join-Path $projectRoot 'demo'
$backupDir = Join-Path $demoDir '_backup'
$resultsDir = Join-Path (Split-Path -Parent $here) 'results\creation'
$frontendDir = Join-Path $projectRoot 'apps\console'
$testResultsDir = Join-Path $frontendDir 'test-results-walkthrough-real'

Write-Host ''
Write-Host '[walkthrough-real] === Forensa real-user-action demo === ' -ForegroundColor Yellow

# 1) Pre-flight - compose stack
Write-Host '[walkthrough-real] 1/6 pre-flight: docker compose stack healthy?' -ForegroundColor Cyan
$pgStatus = docker ps --filter 'name=forensa-postgres' --format '{{.Names}}:{{.Status}}' 2>$null
$apiStatus = docker ps --filter 'name=forensa-api' --format '{{.Names}}:{{.Status}}' 2>$null
$conStatus = docker ps --filter 'name=forensa-console' --format '{{.Names}}:{{.Status}}' 2>$null
if (-not ($pgStatus -match 'healthy') -or -not ($apiStatus -match 'healthy') -or -not ($conStatus -match 'healthy')) {
    Write-Host '  stack not fully healthy - bringing up via tools/dev.ps1 up' -ForegroundColor Yellow
    Push-Location $projectRoot
    try { & .\tools\dev.ps1 up; Start-Sleep -Seconds 12 } finally { Pop-Location }
} else {
    Write-Host "  postgres: $pgStatus"
    Write-Host "  api     : $apiStatus"
    Write-Host "  console : $conStatus"
}

# 2) Verify Gemini key reaches the api container
Write-Host '[walkthrough-real] 2/6 verify Gemini wired into api container' -ForegroundColor Cyan
$geminiCheck = docker exec forensa-api sh -c 'echo ${#FORENSA_GEMINI_API_KEY}' 2>$null
$geminiKeyLen = [int]$geminiCheck
if ($geminiKeyLen -lt 30) {
    Write-Host "  Gemini key NOT in api container (len=$geminiKeyLen). Restarting with .env.compose.local..." -ForegroundColor Yellow
    Push-Location $projectRoot
    try {
        docker compose --env-file .env.compose --env-file .env.compose.local up -d api | Out-Null
        Start-Sleep -Seconds 10
    } finally { Pop-Location }
    $geminiKeyLen = [int](docker exec forensa-api sh -c 'echo ${#FORENSA_GEMINI_API_KEY}' 2>$null)
}
Write-Host "  Gemini key in api container: $geminiKeyLen chars"

# 3) Truncate tenant tables
Write-Host '[walkthrough-real] 3/6 truncating tenant tables' -ForegroundColor Cyan
$truncateSql = "TRUNCATE TABLE receipts, events, timestamp_anchors, ma_export_jobs, policy_bundle_approvals, idempotency_records, policy_bundles, policy_snapshots, agents, tenants CASCADE;"
docker exec -e PGPASSWORD=forensa_dev_pw forensa-postgres psql -U forensa -d forensa -c $truncateSql 2>&1 | Out-Null
Write-Host '  ok'

# 4) Seed - use REAL FreeTSA (not mock) so TC-3 has real DER bytes
Write-Host '[walkthrough-real] 4/6 seeding demo data (real FreeTSA TSA)' -ForegroundColor Cyan
$seedOut = docker exec `
    -e PYTHONPATH=/app `
    -e FORENSA_DB_URL='postgresql+asyncpg://forensa:forensa_dev_pw@postgres:5432/forensa' `
    -w /app forensa-api python /app/scripts/seed_demo_data.py 2>&1 | Out-String
Write-Host $seedOut

$tenantMatch = [regex]::Match($seedOut, "FORENSA_TENANT_ID\s*=\s*'([^']+)'")
$tokenMatch  = [regex]::Match($seedOut, 'FORENSA_TOKEN\s*=\s*"([^"]+)"')
$bundleMatch = [regex]::Match($seedOut, 'bundle_id=([0-9a-f-]+)')
if (-not $tenantMatch.Success -or -not $tokenMatch.Success) {
    Write-Host '[walkthrough-real] FAIL: could not parse tenant + token from seed output' -ForegroundColor Red
    exit 1
}
$env:FORENSA_TENANT_ID = $tenantMatch.Groups[1].Value
$env:FORENSA_TOKEN     = $tokenMatch.Groups[1].Value
$env:FORENSA_DEMO_BUNDLE_ID = if ($bundleMatch.Success) { $bundleMatch.Groups[1].Value } else { '' }
$env:FORENSA_SCOPE_START   = '2026-05-13T00:00:00+00:00'
$env:FORENSA_SCOPE_END     = '2026-05-14T23:59:59+00:00'
$env:FORENSA_CONSOLE_URL   = if ($env:FORENSA_CONSOLE_URL) { $env:FORENSA_CONSOLE_URL } else { 'http://localhost:3001' }
$env:FORENSA_API_URL       = if ($env:FORENSA_API_URL) { $env:FORENSA_API_URL } else { 'http://localhost:8000' }
Write-Host "  tenant_id  : $($env:FORENSA_TENANT_ID)"
Write-Host "  bundle_id  : $($env:FORENSA_DEMO_BUNDLE_ID)"

# 5) Record - single playwright run, single video
Write-Host '[walkthrough-real] 5/6 recording playwright walkthrough-real spec' -ForegroundColor Cyan
# Clean previous test-results
Get-ChildItem $testResultsDir -Directory -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Push-Location $frontendDir
try {
    $env:DEMO = '1'
    npx playwright test --config playwright.demo-walkthrough-real.config.ts --headed --project=chromium-desktop
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[walkthrough-real] playwright failed - aborting' -ForegroundColor Red
        exit $LASTEXITCODE
    }
} finally {
    Remove-Item Env:DEMO -ErrorAction SilentlyContinue
    Pop-Location
}

# 6) Locate + archive
Write-Host '[walkthrough-real] 6/6 archiving video' -ForegroundColor Cyan
$src = Get-ChildItem $testResultsDir -Recurse -Filter 'video.webm' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $src) {
    Write-Host '[walkthrough-real] no recording found' -ForegroundColor Red
    exit 1
}

New-Item -Path $demoDir -ItemType Directory -Force | Out-Null
New-Item -Path $backupDir -ItemType Directory -Force | Out-Null
New-Item -Path $resultsDir -ItemType Directory -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$dstWebm = Join-Path $demoDir "forensa-walkthrough-real-$stamp.webm"
$dstMp4  = Join-Path $demoDir "forensa-walkthrough-real-$stamp.mp4"
$dstBackup = Join-Path $backupDir "forensa-walkthrough-real-$stamp.webm"

$previousEAP = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        & ffmpeg -y -ss 1.0 -i $src.FullName -c:v libvpx -b:v 1M -crf 10 -an $dstWebm *> $null
        if ((Test-Path $dstWebm) -and ((Get-Item $dstWebm).Length -gt 1KB)) {
            Copy-Item $dstWebm $dstBackup -Force
            Write-Host '  webm trim ok'
        } else {
            Copy-Item $src.FullName $dstWebm -Force
            Copy-Item $src.FullName $dstBackup -Force
            Write-Host '  webm copy fallback' -ForegroundColor Yellow
        }
        & ffmpeg -y -i $dstWebm -c:v libx264 -crf 22 -preset slow -an $dstMp4 *> $null
        if ((Test-Path $dstMp4) -and ((Get-Item $dstMp4).Length -gt 1KB)) {
            Write-Host '  mp4 transcode ok'
        }
    } else {
        Copy-Item $src.FullName $dstWebm -Force
        Copy-Item $src.FullName $dstBackup -Force
        Write-Host '  ffmpeg not on PATH - raw copy' -ForegroundColor Yellow
    }
} finally {
    $ErrorActionPreference = $previousEAP
}

Set-Content -Path (Join-Path $resultsDir 'latest.txt') -Value $dstWebm -Encoding ASCII

Write-Host ''
Write-Host '[walkthrough-real] DONE' -ForegroundColor Green
Write-Host ''
Write-Host "  webm : $dstWebm  ($([math]::Round((Get-Item $dstWebm).Length / 1MB, 2)) MB)" -ForegroundColor White
if (Test-Path $dstMp4) {
    Write-Host "  mp4  : $dstMp4  ($([math]::Round((Get-Item $dstMp4).Length / 1MB, 2)) MB)" -ForegroundColor White
}
Write-Host ''
Write-Host "  watch: start $dstWebm" -ForegroundColor Cyan
