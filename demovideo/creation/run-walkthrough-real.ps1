# Forensa CP9.62 v2 - real-user-action walkthrough video pipeline.
#
# Hybrid topology (Option 2 from CP9.62 design):
#   - Postgres + API remain in docker-compose (forensa-postgres :5433, forensa-api :8000)
#     with the Gemini key wired via .env.compose.local
#   - Console runs on the HOST via `npm run dev` on port 3000, with
#     NEXT_PUBLIC_FORENSA_TOKEN baked in at dev-server start so apiFetch
#     attaches Authorization on every browser-side call
#
# Why hybrid: the compose console bundle has empty NEXT_PUBLIC_FORENSA_TOKEN
# baked in at build time. Rebuilding the container per recording takes ~90s.
# A host `npm run dev` reads the env at process start, so we pass the freshly-
# minted token and the console "just works" - identical to how auditex's
# demo pipeline drives its frontend.
#
# Steps:
#   1. Pre-flight  : compose postgres + api healthy (console-compose left up
#                    but unused for the recording)
#   2. Verify Gemini in api container
#   3. Truncate    : drop tenant rows for clean seed
#   4. Seed        : run scripts/seed_demo_data.py with REAL FreeTSA TSA
#                    -> parse tenant_id, token, bundle_id
#   5. Boot host Next.js dev on :3000 with token wired
#   6. Record      : playwright spec walkthrough-real.spec.ts
#   7. Stop dev    : kill the npm process
#   8. Archive     : ffmpeg trim + mp4 transcode
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

# 1) Pre-flight - compose postgres + api
Write-Host '[walkthrough-real] 1/8 pre-flight: compose postgres + api healthy?' -ForegroundColor Cyan
$pgStatus = docker ps --filter 'name=forensa-postgres' --format '{{.Names}}:{{.Status}}' 2>$null
$apiStatus = docker ps --filter 'name=forensa-api' --format '{{.Names}}:{{.Status}}' 2>$null
if (-not ($pgStatus -match 'healthy') -or -not ($apiStatus -match 'healthy')) {
    Write-Host '  bringing up via tools/dev.ps1 up' -ForegroundColor Yellow
    Push-Location $projectRoot
    try { & .\tools\dev.ps1 up; Start-Sleep -Seconds 12 } finally { Pop-Location }
} else {
    Write-Host "  postgres: $pgStatus"
    Write-Host "  api     : $apiStatus"
}

# 2) Verify Gemini key in api container (for TC-5 narratives upstream, even though
#    the spec doesn't drive /narratives in the 5-TC plan)
Write-Host '[walkthrough-real] 2/8 verify Gemini wired into api container' -ForegroundColor Cyan
$geminiKeyLen = [int](docker exec forensa-api sh -c 'echo ${#FORENSA_GEMINI_API_KEY}' 2>$null)
if ($geminiKeyLen -lt 30) {
    Write-Host "  Gemini key NOT wired (len=$geminiKeyLen). Restarting api with .env.compose.local..." -ForegroundColor Yellow
    Push-Location $projectRoot
    try {
        docker compose --env-file .env.compose --env-file .env.compose.local up -d api | Out-Null
        Start-Sleep -Seconds 10
    } finally { Pop-Location }
    $geminiKeyLen = [int](docker exec forensa-api sh -c 'echo ${#FORENSA_GEMINI_API_KEY}' 2>$null)
}
Write-Host "  Gemini key in api container: $geminiKeyLen chars"

# 3) Truncate
Write-Host '[walkthrough-real] 3/8 truncating tenant tables' -ForegroundColor Cyan
$truncateSql = "TRUNCATE TABLE receipts, events, timestamp_anchors, ma_export_jobs, policy_bundle_approvals, idempotency_records, policy_bundles, policy_snapshots, agents, tenants CASCADE;"
docker exec -e PGPASSWORD=forensa_dev_pw forensa-postgres psql -U forensa -d forensa -c $truncateSql 2>&1 | Out-Null
Write-Host '  ok'

# 4) Seed with real FreeTSA
Write-Host '[walkthrough-real] 4/8 seeding demo data (real FreeTSA TSA)' -ForegroundColor Cyan
$seedOut = docker exec `
    -e PYTHONPATH=/app `
    -e FORENSA_DB_URL='postgresql+asyncpg://forensa:forensa_dev_pw@postgres:5432/forensa' `
    -w /app forensa-api python /app/scripts/seed_demo_data.py 2>&1 | Out-String
Write-Host $seedOut

$tenantMatch = [regex]::Match($seedOut, "FORENSA_TENANT_ID\s*=\s*'([^']+)'")
$tokenMatch  = [regex]::Match($seedOut, 'FORENSA_TOKEN\s*=\s*"([^"]+)"')
$bundleMatch = [regex]::Match($seedOut, 'bundle_id=([0-9a-f-]+)')
if (-not $tenantMatch.Success -or -not $tokenMatch.Success) {
    Write-Host '[walkthrough-real] FAIL: parse error on seed output' -ForegroundColor Red
    exit 1
}
$env:FORENSA_TENANT_ID = $tenantMatch.Groups[1].Value
$env:FORENSA_TOKEN     = $tokenMatch.Groups[1].Value
$env:FORENSA_DEMO_BUNDLE_ID = if ($bundleMatch.Success) { $bundleMatch.Groups[1].Value } else { '' }
$env:FORENSA_SCOPE_START = '2026-05-13T00:00:00+00:00'
$env:FORENSA_SCOPE_END   = '2026-05-14T23:59:59+00:00'
$env:FORENSA_CONSOLE_URL = 'http://localhost:3000'  # host dev port
$env:FORENSA_API_URL     = 'http://localhost:8000'
# NEXT_PUBLIC_* vars are baked into the dev-server's client bundle at start time
$env:NEXT_PUBLIC_FORENSA_API_URL = 'http://localhost:8000'
$env:NEXT_PUBLIC_FORENSA_TOKEN = $env:FORENSA_TOKEN
$env:NEXT_PUBLIC_FORENSA_DEMO_TENANT_ID = $env:FORENSA_TENANT_ID
Write-Host "  tenant_id  : $($env:FORENSA_TENANT_ID)"
Write-Host "  bundle_id  : $($env:FORENSA_DEMO_BUNDLE_ID)"

# 5) Boot host Next.js dev on :3000 (background)
Write-Host '[walkthrough-real] 5/8 booting host Next.js dev on :3000' -ForegroundColor Cyan

# Free port 3000 if anything is on it
$pidsOn3000 = (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue).OwningProcess
if ($pidsOn3000) {
    Write-Host "  killing process(es) on port 3000: $pidsOn3000" -ForegroundColor Yellow
    $pidsOn3000 | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

# Write seeded token + tenant + API into apps/console/.env.local so Next.js
# bakes them into the client bundle when the dev server starts. This file is
# already gitignored (.gitignore line 78). We always overwrite to keep it
# in sync with the freshly-seeded token.
$envLocalPath = Join-Path $frontendDir '.env.local'
$envLocalLines = @(
    "# Auto-generated by run-walkthrough-real.ps1 - DO NOT COMMIT.",
    "NEXT_PUBLIC_FORENSA_API_URL=$($env:NEXT_PUBLIC_FORENSA_API_URL)",
    "NEXT_PUBLIC_FORENSA_TOKEN=$($env:NEXT_PUBLIC_FORENSA_TOKEN)",
    "NEXT_PUBLIC_FORENSA_DEMO_TENANT_ID=$($env:NEXT_PUBLIC_FORENSA_DEMO_TENANT_ID)"
)
Set-Content -Path $envLocalPath -Value ($envLocalLines -join "`r`n") -Encoding ASCII
Write-Host "  wrote $envLocalPath (token len $($env:NEXT_PUBLIC_FORENSA_TOKEN.Length))"

# Start npm run dev. It auto-loads .env.local at startup.
$devLog = Join-Path $env:TEMP "forensa-walkthrough-dev-$(Get-Date -Format yyyyMMdd_HHmmss).log"
$devCmd = "Set-Location '$frontendDir'; `$env:PORT='3000'; npm run dev"
$devProcess = Start-Process -FilePath 'powershell' -ArgumentList '-NoProfile','-Command',$devCmd -RedirectStandardOutput $devLog -RedirectStandardError "$devLog.err" -PassThru -WindowStyle Hidden
Write-Host "  npm run dev PID $($devProcess.Id), log $devLog"
Write-Host '  waiting for :3000 to respond (up to 90s)...' -NoNewline
$ready = $false
for ($i = 0; $i -lt 45; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri 'http://localhost:3000' -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { $ready = $true; break }
    } catch {}
    Write-Host -NoNewline '.'
}
Write-Host ''
if (-not $ready) {
    Write-Host '  dev server failed to start - log tail:' -ForegroundColor Red
    if (Test-Path $devLog) { Get-Content $devLog -Tail 30 }
    if (Test-Path "$devLog.err") { Write-Host '--- stderr ---'; Get-Content "$devLog.err" -Tail 30 }
    Stop-Process -Id $devProcess.Id -Force -ErrorAction SilentlyContinue
    exit 1
}
Write-Host '  dev server ready'

# 6) Record
Write-Host '[walkthrough-real] 6/8 recording playwright walkthrough-real spec' -ForegroundColor Cyan
Get-ChildItem $testResultsDir -Directory -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Push-Location $frontendDir
$specExit = 0
try {
    $env:DEMO = '1'
    npx playwright test --config playwright.demo-walkthrough-real.config.ts --headed --project=chromium-desktop
    $specExit = $LASTEXITCODE
} finally {
    Remove-Item Env:DEMO -ErrorAction SilentlyContinue
    Pop-Location
}

# 7) Stop dev + clean .env.local
Write-Host '[walkthrough-real] 7/8 stopping host Next.js dev' -ForegroundColor Cyan
$pidsOn3000 = (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue).OwningProcess
if ($pidsOn3000) {
    $pidsOn3000 | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
}
Stop-Process -Id $devProcess.Id -Force -ErrorAction SilentlyContinue
# Don't delete .env.local - keep it for next run + leaving it gives the dev
# the ability to refresh manually. .gitignore covers it.
Write-Host '  ok'

if ($specExit -ne 0) {
    Write-Host '[walkthrough-real] playwright spec failed - aborting archive' -ForegroundColor Red
    exit $specExit
}

# 8) Archive
Write-Host '[walkthrough-real] 8/8 archiving video' -ForegroundColor Cyan
$src = Get-ChildItem $testResultsDir -Recurse -Filter 'video.webm' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $src) { Write-Host '  no recording found' -ForegroundColor Red; exit 1 }

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
        }
        & ffmpeg -y -i $dstWebm -c:v libx264 -crf 22 -preset slow -an $dstMp4 *> $null
        if ((Test-Path $dstMp4) -and ((Get-Item $dstMp4).Length -gt 1KB)) { Write-Host '  mp4 transcode ok' }
    } else {
        Copy-Item $src.FullName $dstWebm -Force
        Copy-Item $src.FullName $dstBackup -Force
    }
} finally {
    $ErrorActionPreference = $previousEAP
}

Set-Content -Path (Join-Path $resultsDir 'latest.txt') -Value $dstWebm -Encoding ASCII

Write-Host ''
Write-Host '[walkthrough-real] DONE' -ForegroundColor Green
Write-Host ''
Write-Host "  webm : $dstWebm  ($([math]::Round((Get-Item $dstWebm).Length / 1MB, 2)) MB)"
if (Test-Path $dstMp4) {
    Write-Host "  mp4  : $dstMp4  ($([math]::Round((Get-Item $dstMp4).Length / 1MB, 2)) MB)"
}
Write-Host ''
Write-Host "  watch: start $dstWebm" -ForegroundColor Cyan
