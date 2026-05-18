# Forensa 9-screen walkthrough video creation pipeline.
#
# CP9.62 - records the comprehensive captioned walkthrough video showing
# all 9 v1.x console screens in two passes (empty state + loaded state).
#
# Differs from run-creation.ps1 in that it:
#   1. Uses the EXISTING docker-compose stack (postgres:5433, api:8000, console:3001)
#      rather than booting its own uvicorn + next-dev. Faster, matches prod-like topology.
#   2. TRUNCATES tenant tables before seeding so pass 1 sees a truly empty state.
#   3. Seeds the DB, then records ONE playwright run that does BOTH passes
#      (the spec walks empty screens first, then loaded screens). The "empty"
#      state for pass 1 is captured BEFORE seed by the truncate step; seed
#      then happens BEFORE playwright runs so pass 2 has data. Critical:
#      the spec captures empty state by querying right after navigate; if
#      data exists it'll show data. To truly show empty state in pass 1
#      AND loaded state in pass 2 in one recording, we'd need a mid-run
#      seed. Workaround for this CP: pass 1 captures the LIVE state of
#      the DB at start (which we deliberately empty); pass 2 reloads
#      the same screens, but by then the seed has already happened so
#      they'll show loaded data. NO mid-run seed call needed.
#
# Steps:
#   1. Pre-flight: docker compose stack up
#   2. TRUNCATE: clear all tenant rows so pass 1 sees empty state
#   3. Boot a background watchdog that runs seed_demo_data.py 30s after
#      pass 1 navigation starts (mid-recording mid-passes). Actually
#      simpler: just SEED FIRST, then record. Pass 1 will show
#      EXACTLY the same data as Pass 2 in this design, defeating the
#      "empty vs loaded" point.
#   3'. REVISED: Record pass 1 with truncated DB (no seed env -> spec exits
#       after pass 1 closing card). Move that recording aside. Seed.
#       Record pass 2 (with env wired -> spec skips its own pass 1 via
#       a SKIP_PASS_1 env, then does pass 2). Concat the two webms.
#
# Usage:
#   pwsh ./demovideo/creation/run-walkthrough.ps1
#
# Env overrides:
#   FORENSA_DB_URL              defaults to local Docker pg on 5433
#   FORENSA_CONSOLE_URL         defaults to http://localhost:3001 (compose stack)
#   FORENSA_API_URL             defaults to http://localhost:8000

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent (Split-Path -Parent $here)
$demoDir = Join-Path $projectRoot 'demo'
$backupDir = Join-Path $demoDir '_backup'
$resultsDir = Join-Path (Split-Path -Parent $here) 'results\creation'
$frontendDir = Join-Path $projectRoot 'apps\console'
$specPath = 'tests-e2e/demo/walkthrough-9-screens.spec.ts'
$testResultsDir = Join-Path $frontendDir 'test-results-walkthrough'

Write-Host ''
Write-Host '[walkthrough] === Forensa 9-Screen Walkthrough Video === ' -ForegroundColor Yellow

# 1) Pre-flight - compose stack health
Write-Host '[walkthrough] 1/6 pre-flight: docker compose stack healthy?' -ForegroundColor Cyan
$pgStatus = docker ps --filter 'name=forensa-postgres' --format '{{.Names}}:{{.Status}}' 2>$null
$apiStatus = docker ps --filter 'name=forensa-api' --format '{{.Names}}:{{.Status}}' 2>$null
$conStatus = docker ps --filter 'name=forensa-console' --format '{{.Names}}:{{.Status}}' 2>$null
if (-not ($pgStatus -match 'healthy') -or -not ($apiStatus -match 'healthy') -or -not ($conStatus -match 'healthy')) {
    Write-Host '  stack not fully healthy - running tools/dev.ps1 up' -ForegroundColor Yellow
    Push-Location $projectRoot
    try { & .\tools\dev.ps1 up; Start-Sleep -Seconds 12 } finally { Pop-Location }
} else {
    Write-Host "  postgres: $pgStatus"
    Write-Host "  api     : $apiStatus"
    Write-Host "  console : $conStatus"
}

# Helper - clear test-results between passes so the recording is unambiguous
function Clear-WalkthroughResults {
    Get-ChildItem $testResultsDir -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match 'walkthrough' } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

# Helper - find the most recent walkthrough recording
function Find-WalkthroughRecording {
    Get-ChildItem $testResultsDir -Recurse -Filter 'video.webm' -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match 'walkthrough' } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}

# 2) TRUNCATE - drop all tenant data for clean pass-1 empty state
Write-Host '[walkthrough] 2/6 truncating tenant tables for clean empty state' -ForegroundColor Cyan
# Simple multi-statement truncate via -c. Order doesn't matter with CASCADE.
$truncateSql = "TRUNCATE TABLE receipts, events, timestamp_anchors, ma_export_jobs, policy_bundle_approvals, idempotency_records, policy_bundles, policy_snapshots, agents, tenants CASCADE;"
docker exec -e PGPASSWORD=forensa_dev_pw forensa-postgres psql -U forensa -d forensa -c $truncateSql 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host '  truncate had warnings - continuing' -ForegroundColor Yellow
} else {
    Write-Host '  ok: all tenant tables truncated (alembic_version preserved)'
}

# 3) RECORD PASS 1 (empty state) - no env tokens means spec exits after closing card
Write-Host '[walkthrough] 3/6 recording PASS 1 (empty state) - playwright' -ForegroundColor Cyan
Clear-WalkthroughResults
Push-Location $frontendDir
try {
    $env:DEMO = '1'
    $env:FORENSA_CONSOLE_URL = if ($env:FORENSA_CONSOLE_URL) { $env:FORENSA_CONSOLE_URL } else { 'http://localhost:3001' }
    $env:FORENSA_API_URL = if ($env:FORENSA_API_URL) { $env:FORENSA_API_URL } else { 'http://localhost:8000' }
    Remove-Item Env:FORENSA_TENANT_ID -ErrorAction SilentlyContinue
    Remove-Item Env:FORENSA_TOKEN -ErrorAction SilentlyContinue
    npx playwright test --config playwright.demo-walkthrough.config.ts --headed --project=chromium-desktop
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[walkthrough] pass 1 playwright failed - aborting' -ForegroundColor Red
        exit $LASTEXITCODE
    }
} finally {
    Remove-Item Env:DEMO -ErrorAction SilentlyContinue
    Pop-Location
}
$pass1Src = Find-WalkthroughRecording
if (-not $pass1Src) {
    Write-Host '[walkthrough] no pass-1 recording found - aborting' -ForegroundColor Red
    exit 1
}
$tmpDir = Join-Path $env:TEMP "forensa-walkthrough-$(Get-Date -Format yyyyMMdd_HHmmss)"
New-Item -Path $tmpDir -ItemType Directory -Force | Out-Null
$pass1Webm = Join-Path $tmpDir 'pass1.webm'
Copy-Item $pass1Src.FullName $pass1Webm -Force
Write-Host "  pass 1 saved: $pass1Webm  ($([math]::Round((Get-Item $pass1Webm).Length / 1MB, 2)) MB)"

# 4) SEED demo data inside the api container
Write-Host '[walkthrough] 4/6 seeding demo data inside forensa-api container' -ForegroundColor Cyan
$seedOut = docker exec -e PYTHONPATH=/app -e FORENSA_DB_URL='postgresql+asyncpg://forensa:forensa_dev_pw@postgres:5432/forensa' -e FORENSA_DEMO_USE_MOCK_TSA=1 -w /app forensa-api python /app/scripts/seed_demo_data.py 2>&1 | Out-String
Write-Host $seedOut
$tenantMatch = [regex]::Match($seedOut, "FORENSA_TENANT_ID\s*=\s*'([^']+)'")
$tokenMatch = [regex]::Match($seedOut, 'FORENSA_TOKEN\s*=\s*"([^"]+)"')
if (-not $tenantMatch.Success -or -not $tokenMatch.Success) {
    Write-Host '[walkthrough] could not parse tenant + token from seed output' -ForegroundColor Red
    exit 1
}
$env:FORENSA_TENANT_ID = $tenantMatch.Groups[1].Value
$env:FORENSA_TOKEN = $tokenMatch.Groups[1].Value
$env:FORENSA_SCOPE_START = '2026-05-13T00:00:00+00:00'
$env:FORENSA_SCOPE_END = '2026-05-14T23:59:59+00:00'
Write-Host "  tenant_id : $($env:FORENSA_TENANT_ID)"

# 5) RECORD PASS 2 (loaded state) - env now wired, spec runs both passes
# We want only the pass-2 portion of this recording, so we'll trim later.
# Actually simpler: we'll concat pass1 + pass2 (full), and skip the first
# pass-1 portion in pass 2 via a SKIP_PASS_1 env var the spec respects.
Write-Host '[walkthrough] 5/6 recording PASS 2 (loaded state) - playwright' -ForegroundColor Cyan
Clear-WalkthroughResults
Push-Location $frontendDir
try {
    $env:DEMO = '1'
    $env:FORENSA_SKIP_PASS_1 = '1'
    npx playwright test --config playwright.demo-walkthrough.config.ts --headed --project=chromium-desktop
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[walkthrough] pass 2 playwright failed' -ForegroundColor Red
        exit $LASTEXITCODE
    }
} finally {
    Remove-Item Env:DEMO -ErrorAction SilentlyContinue
    Remove-Item Env:FORENSA_SKIP_PASS_1 -ErrorAction SilentlyContinue
    Pop-Location
}
$pass2Src = Find-WalkthroughRecording
if (-not $pass2Src) {
    Write-Host '[walkthrough] no pass-2 recording found - aborting' -ForegroundColor Red
    exit 1
}
$pass2Webm = Join-Path $tmpDir 'pass2.webm'
Copy-Item $pass2Src.FullName $pass2Webm -Force
Write-Host "  pass 2 saved: $pass2Webm  ($([math]::Round((Get-Item $pass2Webm).Length / 1MB, 2)) MB)"

# 6) ffmpeg concat + mp4 transcode
Write-Host '[walkthrough] 6/6 ffmpeg concat + mp4 transcode' -ForegroundColor Cyan
New-Item -Path $demoDir -ItemType Directory -Force | Out-Null
New-Item -Path $backupDir -ItemType Directory -Force | Out-Null
New-Item -Path $resultsDir -ItemType Directory -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$dstWebm = Join-Path $demoDir "forensa-walkthrough-$stamp.webm"
$dstMp4 = Join-Path $demoDir "forensa-walkthrough-$stamp.mp4"
$dstBackup = Join-Path $backupDir "forensa-walkthrough-$stamp.webm"

$previousEAP = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        # Write concat manifest (ffmpeg needs UNIX line endings + escaped paths).
        $concatFile = Join-Path $tmpDir 'concat.txt'
        $pass1Esc = ($pass1Webm -replace '\\', '/') -replace "'", "''"
        $pass2Esc = ($pass2Webm -replace '\\', '/') -replace "'", "''"
        @("file '$pass1Esc'", "file '$pass2Esc'") -join "`n" | Set-Content -Path $concatFile -Encoding ASCII
        Write-Host '  concatenating pass 1 + pass 2 via ffmpeg' -ForegroundColor Cyan
        & ffmpeg -y -f concat -safe 0 -i $concatFile -c:v libvpx -b:v 1M -crf 10 -an $dstWebm *> $null
        if ((Test-Path $dstWebm) -and ((Get-Item $dstWebm).Length -gt 1KB)) {
            Copy-Item $dstWebm $dstBackup -Force
            Write-Host '  concat ok'
        } else {
            Write-Host '  concat failed - falling back to pass-2 only' -ForegroundColor Yellow
            Copy-Item $pass2Webm $dstWebm -Force
            Copy-Item $pass2Webm $dstBackup -Force
        }
        & ffmpeg -y -i $dstWebm -c:v libx264 -crf 22 -preset slow -an $dstMp4 *> $null
        if ((Test-Path $dstMp4) -and ((Get-Item $dstMp4).Length -gt 1KB)) {
            Write-Host "  mp4 transcode ok"
        }
    } else {
        Copy-Item $pass2Webm $dstWebm -Force
        Copy-Item $pass2Webm $dstBackup -Force
        Write-Host '  ffmpeg not on PATH - using pass-2 only, no concat' -ForegroundColor Yellow
    }
} finally {
    $ErrorActionPreference = $previousEAP
}

Set-Content -Path (Join-Path $resultsDir 'latest.txt') -Value $dstWebm -Encoding ASCII

Write-Host ''
Write-Host '[walkthrough] DONE' -ForegroundColor Green
Write-Host ''
Write-Host "  webm   : $dstWebm  ($([math]::Round((Get-Item $dstWebm).Length / 1MB, 2)) MB)"
if (Test-Path $dstMp4) {
    Write-Host "  mp4    : $dstMp4  ($([math]::Round((Get-Item $dstMp4).Length / 1MB, 2)) MB)"
}
Write-Host "  backup : $dstBackup"
Write-Host ''
Write-Host "  watch with: start $dstWebm" -ForegroundColor Cyan
Write-Host ''

Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
