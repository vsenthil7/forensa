# Forensa Demo Video Creation pipeline
#
# Ported from C:\Users\v_sen\Documents\Projects\0001_Hack0014_Vertex_Swarm_Tashi\auditex\demovideo\creation\run-creation.ps1
# (sibling hackathon project). Modular pieces this wrapper coordinates:
#   1. Pre-flight: Docker Postgres up + alembic migrated
#   2. Seed demo data (TRUNCATE + reseed for a clean recording)
#   3. Run playwright captioned spec (DEMO=1)
#   4. Archive recorded video to demo/ + demo/_backup/
#   5. Pointer file for verification steps
#
# Usage:
#   pwsh ./demovideo/creation/run-creation.ps1
#
# Env overrides:
#   FORENSA_DB_URL    optional, defaults to local Docker pg on 5433
#   FORENSA_API_URL   optional, defaults to http://127.0.0.1:8000 (Playwright boots uvicorn)

$ErrorActionPreference = 'Stop'
# Ensure poetry is on PATH (Windows pip-installs to %APPDATA%\Python\PythonXY\Scripts)
if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
    $env:PATH = "$env:APPDATA\Python\Python314\Scripts;$env:PATH"
}
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent (Split-Path -Parent $here)
$demoDir = Join-Path $projectRoot 'demo'
$backupDir = Join-Path $demoDir '_backup'
$resultsDir = Join-Path (Split-Path -Parent $here) 'results\creation'
$frontendDir = Join-Path $projectRoot 'apps\console'
$specPath = 'tests-e2e/demo/end-to-end-demo.spec.ts'
$defaultDbUrl = 'postgresql+asyncpg://forensa:forensa@localhost:5433/forensa'

Write-Host '' -ForegroundColor Yellow
Write-Host '[creation] === Forensa Demo Video Creation === ' -ForegroundColor Yellow

# 1) Pre-flight: Postgres up + alembic at head
Write-Host '[creation] 1/5 pre-flight: docker postgres up?' -ForegroundColor Cyan
$dbUrl = if ($env:FORENSA_DB_URL) { $env:FORENSA_DB_URL } else { $defaultDbUrl }
Push-Location $projectRoot
try {
    $pgStatus = docker ps --filter 'name=forensa-pg' --format '{{.Names}}:{{.Status}}' 2>$null
    if (-not ($pgStatus -match 'forensa-pg.*Up')) {
        Write-Host '  forensa-pg container is not running - starting via docker compose...' -ForegroundColor Yellow
        docker compose up -d forensa-pg | Out-Null
        Start-Sleep -Seconds 4
    } else {
        Write-Host "  $pgStatus"
    }

    Write-Host '[creation] 1/5 pre-flight: alembic upgrade head' -ForegroundColor Cyan
    $env:FORENSA_DATABASE_URL = $dbUrl
    $env:FORENSA_DB_URL = $dbUrl
    poetry run alembic upgrade head | Out-Null
    Write-Host '  migrations OK'
} finally { Pop-Location }

# 2) Seed demo data (idempotent: re-running on a seeded DB re-mints the token)
Write-Host '[creation] 2/5 seeding demo data (mints FORENSA_TENANT_ID + FORENSA_TOKEN)' -ForegroundColor Cyan
Push-Location $projectRoot
try {
    $seedOut = poetry run python scripts/seed_demo_data.py 2>&1 | Out-String
    Write-Host $seedOut
    # Parse FORENSA_TENANT_ID and FORENSA_TOKEN out of the printed
    # PowerShell-style export lines that seed_demo_data.py emits.
    $tenantMatch = [regex]::Match($seedOut, "FORENSA_TENANT_ID\s*=\s*'([^']+)'")
    $tokenMatch = [regex]::Match($seedOut, 'FORENSA_TOKEN\s*=\s*"([^"]+)"')
    if (-not $tenantMatch.Success -or -not $tokenMatch.Success) {
        throw "Could not parse FORENSA_TENANT_ID + FORENSA_TOKEN from seed output"
    }
    $env:FORENSA_TENANT_ID = $tenantMatch.Groups[1].Value
    $env:FORENSA_TOKEN = $tokenMatch.Groups[1].Value
    $env:FORENSA_SCOPE_START = '2026-05-13T00:00:00+00:00'
    $env:FORENSA_SCOPE_END = '2026-05-14T23:59:59+00:00'
    # Auth-layer env vars so uvicorn (booted by Playwright) recognises the token.
    # Default HMAC secret derives deterministically from the demo slug.
    $env:FORENSA_HMAC_SECRET = '666f72656e73612d64656d6f666f72656e73612d64656d6f666f72656e73612d'
    $env:FORENSA_HMAC_TENANT_ID = $env:FORENSA_TENANT_ID
    # Next.js Console env vars. NEXT_PUBLIC_* vars are inlined into the
    # client bundle at build/dev time so the browser-side fetcher in
    # apps/console/src/lib/apiFetch.ts can send the Authorization header.
    $env:NEXT_PUBLIC_FORENSA_API_URL = 'http://localhost:8000'
    $env:NEXT_PUBLIC_FORENSA_TOKEN = $env:FORENSA_TOKEN
    $env:NEXT_PUBLIC_FORENSA_DEMO_TENANT_ID = $env:FORENSA_TENANT_ID
    Write-Host "  tenant_id: $($env:FORENSA_TENANT_ID)"
    Write-Host '  token + auth env wired (FastAPI + Console)'
} finally { Pop-Location }

# 3) Run the playwright spec in DEMO mode
Write-Host '[creation] 3/5 running playwright captioned spec (DEMO=1)' -ForegroundColor Cyan
Push-Location $frontendDir
try {
    $env:DEMO = '1'
    npx playwright test $specPath --headed --project=chromium --reporter=line
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[creation] playwright spec failed - aborting archive' -ForegroundColor Red
        exit $LASTEXITCODE
    }
} finally {
    Remove-Item Env:DEMO -ErrorAction SilentlyContinue
    Pop-Location
}

# 4) Archive the recorded video to demo/ + demo/_backup/
Write-Host '[creation] 4/5 archiving video to demo/ + demo/_backup/' -ForegroundColor Cyan
New-Item -Path $demoDir -ItemType Directory -Force | Out-Null
New-Item -Path $backupDir -ItemType Directory -Force | Out-Null
New-Item -Path $resultsDir -ItemType Directory -Force | Out-Null

$testResultsDir = Join-Path $frontendDir 'test-results'
$src = Get-ChildItem $testResultsDir -Recurse -Filter 'video.webm' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match 'end-to-end' } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $src) {
    Write-Host '[creation] no recorded video found in apps/console/test-results/ - did the spec run?' -ForegroundColor Red
    exit 1
}
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$dstName = "end-to-end-$stamp.webm"
$dstMain = Join-Path $demoDir $dstName
$dstBackup = Join-Path $backupDir $dstName
Copy-Item $src.FullName $dstMain -Force
Copy-Item $src.FullName $dstBackup -Force
Set-Content -Path (Join-Path $resultsDir 'latest.txt') -Value $dstMain -Encoding ASCII
Write-Host "  active : $dstMain"
Write-Host "  backup : $dstBackup"
Write-Host ("  size   : {0} MB" -f [math]::Round($src.Length / 1MB, 2))

# 5) Done
Write-Host '[creation] 5/5 complete' -ForegroundColor Green
Write-Host -NoNewline '  watch with: start '
Write-Host $dstMain
$global:LATEST_DEMO_VIDEO = $dstMain
