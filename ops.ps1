# Forensa ops.ps1 - single dispatcher for repo development and demo operations
# Pattern ported from Verixa AT-Hack0017. Windows-only for hackathon environment.
# Linux equivalent: ops.sh (Year 2 production).
#
# Usage: .\ops.ps1 <action> [args]
# List all actions: .\ops.ps1 help

param(
    [Parameter(Position=0)]
    [string]$Action = 'help',
    [Parameter(ValueFromRemainingArguments=$true)]
    $Rest
)

$ErrorActionPreference = 'Stop'
$RepoRoot = $PSScriptRoot
$LogDir = Join-Path $RepoRoot 'logs'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

function Log-Action {
    param([string]$Msg)
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = '[' + $ts + '] ' + $Msg
    Write-Host $line -ForegroundColor Cyan
    Add-Content -Path (Join-Path $LogDir 'ops.log') -Value $line
}

function Stamp-Start { param([string]$Task) Log-Action ('TASK START: ' + $Task) }
function Stamp-End   { param([string]$Task) Log-Action ('TASK END:   ' + $Task) }

function Require-Tool {
    param([string]$Tool)
    if (-not (Get-Command $Tool -ErrorAction SilentlyContinue)) {
        Write-Error ('Required tool not found: ' + $Tool)
        exit 1
    }
}


# ===== HELP =====
function Action-Help {
    Write-Host 'Forensa ops.ps1 - 28 actions' -ForegroundColor Yellow
    Write-Host ''
    Write-Host 'REPO and GIT' -ForegroundColor Green
    Write-Host '  status               git status + branch + log oneline'
    Write-Host '  push                 git add -A; commit -m; push (interactive message)'
    Write-Host '  pull                 git pull --rebase'
    Write-Host '  commit-doc <n>       quick commit of docs/<n>_*/'
    Write-Host ''
    Write-Host 'BUILD' -ForegroundColor Green
    Write-Host '  build-api            poetry install + alembic upgrade head'
    Write-Host '  build-console        pnpm install + pnpm build'
    Write-Host '  build-docker         docker compose build'
    Write-Host '  build-all            build-api + build-console + build-docker'
    Write-Host ''
    Write-Host 'RUN' -ForegroundColor Green
    Write-Host '  run-api              start FastAPI dev server (uvicorn --reload)'
    Write-Host '  run-console          start Next.js dev server (pnpm dev)'
    Write-Host '  run-worker           start Celery worker'
    Write-Host '  run-all              run all three in parallel jobs'
    Write-Host ''
    Write-Host 'TEST' -ForegroundColor Green
    Write-Host '  test-python          pytest --cov=packages,apps/api --cov-fail-under=100'
    Write-Host '  test-typescript      pnpm vitest run --coverage'
    Write-Host '  test-e2e             Playwright on live dev servers'
    Write-Host '  test-load            Locust 10K sustained + 100K peak'
    Write-Host '  test-all             python + typescript + e2e in sequence'
    Write-Host ''
    Write-Host 'DEMO' -ForegroundColor Green
    Write-Host '  ingest-smoke         POST 100 synthetic events through /v1/events'
    Write-Host '  verify-chain         full-ledger chain verification'
    Write-Host '  evidence-pack        generate eu-ai-act-art12 pack for last 24h'
    Write-Host '  lobstertrap-pipe     start Lobster Trap verdict adapter in foreground'
    Write-Host '  tamper-demo          modify a Receipt, show chain verification fail'
    Write-Host '  gemini-narrative     run Gemini Pro narrative on a sample cohort'
    Write-Host '  generate-openapi     dump FastAPI app openapi -> docs/openapi.json'
    Write-Host ''
    Write-Host 'OPS' -ForegroundColor Green
    Write-Host '  db-migrate           alembic upgrade head'
    Write-Host '  db-rollback          alembic downgrade -1'
    Write-Host '  deploy-helm          helm upgrade --install forensa ./deploy/helm'
    Write-Host '  ci-local             run full CI suite locally (3 jobs parallel)'
    Write-Host '  backup-now           pg_dump tenant + S3 sync'
    Write-Host ''
    Write-Host 'META' -ForegroundColor Green
    Write-Host '  help                 this message'
    Write-Host '  version              show v0.x.x + commit SHA'
}


# ===== REPO and GIT =====
function Action-Status {
    Stamp-Start 'status'
    git status
    git branch --show-current
    git log --oneline -10
    Stamp-End 'status'
}

function Action-Push {
    Stamp-Start 'push'
    git add -A
    $msg = Read-Host 'Commit message'
    git commit -m $msg
    git push 2>&1 | Select-Object -Last 3
    Stamp-End 'push'
}

function Action-Pull {
    Stamp-Start 'pull'
    git pull --rebase 2>&1 | Select-Object -Last 3
    Stamp-End 'pull'
}

function Action-CommitDoc {
    param([string]$Num)
    Stamp-Start ('commit-doc ' + $Num)
    if (-not $Num) { Write-Error 'Provide doc number, e.g. .\ops.ps1 commit-doc 13'; return }
    $padded = $Num.PadLeft(2, '0')
    $folder = Get-ChildItem 'docs' -Directory | Where-Object { $_.Name -like ("$padded`_*") } | Select-Object -First 1
    if (-not $folder) { Write-Error ('No docs folder matches ' + $padded); return }
    git add (Join-Path 'docs' $folder.Name)
    $msg = Read-Host ('Commit message for DOC-' + $padded)
    git commit -m ('[DOC-' + $padded + '] ' + $msg)
    git push 2>&1 | Select-Object -Last 2
    Stamp-End ('commit-doc ' + $Num)
}

# ===== BUILD =====
function Action-BuildApi {
    Stamp-Start 'build-api'
    Push-Location $RepoRoot
    Require-Tool 'poetry'
    poetry install --with dev
    poetry run alembic upgrade head
    Pop-Location
    Stamp-End 'build-api'
}

function Action-BuildConsole {
    Stamp-Start 'build-console'
    Push-Location (Join-Path $RepoRoot 'apps/console')
    Require-Tool 'pnpm'
    pnpm install
    pnpm build
    Pop-Location
    Stamp-End 'build-console'
}

function Action-BuildDocker {
    Stamp-Start 'build-docker'
    Push-Location $RepoRoot
    Require-Tool 'docker'
    docker compose build
    Pop-Location
    Stamp-End 'build-docker'
}

function Action-BuildAll {
    Action-BuildApi
    Action-BuildConsole
    Action-BuildDocker
}


# ===== RUN =====
function Action-RunApi {
    Stamp-Start 'run-api'
    Push-Location $RepoRoot
    Require-Tool 'poetry'
    poetry run uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
    Pop-Location
    Stamp-End 'run-api'
}

function Action-RunConsole {
    Stamp-Start 'run-console'
    Push-Location (Join-Path $RepoRoot 'apps/console')
    pnpm dev
    Pop-Location
    Stamp-End 'run-console'
}

function Action-RunWorker {
    Stamp-Start 'run-worker'
    Push-Location $RepoRoot
    poetry run celery -A apps.worker.app worker --loglevel=info
    Pop-Location
    Stamp-End 'run-worker'
}

function Action-RunAll {
    Stamp-Start 'run-all'
    Write-Host 'Starting api, console, worker in 3 windows...'
    $cmdA = 'cd ' + $RepoRoot + '; .\ops.ps1 run-api'
    $cmdC = 'cd ' + $RepoRoot + '; .\ops.ps1 run-console'
    $cmdW = 'cd ' + $RepoRoot + '; .\ops.ps1 run-worker'
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $cmdA
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $cmdC
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $cmdW
    Stamp-End 'run-all'
}


# ===== TEST =====
function Action-TestPython {
    Stamp-Start 'test-python'
    Push-Location $RepoRoot
    poetry run pytest --cov=packages --cov=apps/api --cov-fail-under=100 --cov-report=term-missing
    $code = $LASTEXITCODE
    Pop-Location
    Stamp-End 'test-python'
    if ($code -ne 0) { exit $code }
}

function Action-TestTypescript {
    Stamp-Start 'test-typescript'
    Push-Location (Join-Path $RepoRoot 'apps/console')
    pnpm vitest run --coverage
    $code = $LASTEXITCODE
    Pop-Location
    Stamp-End 'test-typescript'
    if ($code -ne 0) { exit $code }
}

function Action-TestE2E {
    Stamp-Start 'test-e2e'
    Push-Location $RepoRoot
    pnpm exec playwright test
    $code = $LASTEXITCODE
    Pop-Location
    Stamp-End 'test-e2e'
    if ($code -ne 0) { exit $code }
}

function Action-TestLoad {
    Stamp-Start 'test-load'
    Push-Location (Join-Path $RepoRoot 'load-tests')
    Require-Tool 'locust'
    locust -f locustfile.py --headless --users 100 --spawn-rate 10 --run-time 2m
    Pop-Location
    Stamp-End 'test-load'
}

function Action-TestAll {
    Action-TestPython
    Action-TestTypescript
    Action-TestE2E
}

# ===== DEMO =====
function Action-IngestSmoke {
    Stamp-Start 'ingest-smoke'
    Push-Location $RepoRoot
    poetry run python tools/ingest_smoke.py --events 100 --endpoint http://localhost:8000/v1/events
    Pop-Location
    Stamp-End 'ingest-smoke'
}

function Action-VerifyChain {
    Stamp-Start 'verify-chain'
    Push-Location $RepoRoot
    poetry run python tools/verify_chain.py --tenant default --full
    Pop-Location
    Stamp-End 'verify-chain'
}

function Action-EvidencePack {
    Stamp-Start 'evidence-pack'
    Push-Location $RepoRoot
    poetry run python tools/evidence_pack.py --template eu-ai-act-art12 --since 24h --tenant default
    Pop-Location
    Stamp-End 'evidence-pack'
}

function Action-LobstertrapPipe {
    Stamp-Start 'lobstertrap-pipe'
    Push-Location $RepoRoot
    poetry run python tools/lobstertrap_pipe.py --foreground
    Pop-Location
    Stamp-End 'lobstertrap-pipe'
}

function Action-TamperDemo {
    Stamp-Start 'tamper-demo'
    Push-Location $RepoRoot
    Write-Host 'Step 1: Create chain of 100 receipts'
    poetry run python tools/tamper_demo.py --create-chain 100
    Write-Host 'Step 2: Verify chain (should pass)'
    poetry run python tools/verify_chain.py --tenant demo --expect pass
    Write-Host 'Step 3: Modify receipt at index 50'
    poetry run python tools/tamper_demo.py --modify-leaf 50
    Write-Host 'Step 4: Verify chain (should fail at 50)'
    poetry run python tools/verify_chain.py --tenant demo --expect fail-at 50
    Pop-Location
    Stamp-End 'tamper-demo'
}

function Action-GeminiNarrative {
    Stamp-Start 'gemini-narrative'
    Push-Location $RepoRoot
    poetry run python tools/gemini_narrative.py --cohort sample --template eu-ai-act-art12
    Pop-Location
    Stamp-End 'gemini-narrative'
}

function Action-GenerateOpenapi {
    Stamp-Start 'generate-openapi'
    Push-Location $RepoRoot
    poetry run python tools/dump_openapi.py --out docs/openapi.json
    Pop-Location
    Stamp-End 'generate-openapi'
}

# ===== OPS =====
function Action-DbMigrate {
    Stamp-Start 'db-migrate'
    Push-Location $RepoRoot
    poetry run alembic upgrade head
    Pop-Location
    Stamp-End 'db-migrate'
}

function Action-DbRollback {
    Stamp-Start 'db-rollback'
    Push-Location $RepoRoot
    poetry run alembic downgrade -1
    Pop-Location
    Stamp-End 'db-rollback'
}

function Action-DeployHelm {
    Stamp-Start 'deploy-helm'
    Require-Tool 'helm'
    helm upgrade --install forensa (Join-Path $RepoRoot 'deploy/helm') --values (Join-Path $RepoRoot 'deploy/helm/values.yaml')
    Stamp-End 'deploy-helm'
}

function Action-CiLocal {
    Stamp-Start 'ci-local'
    Write-Host 'Running CI suite locally (3 jobs in parallel)...'
    $jobs = @()
    $jobs += Start-Job -Name py    -ScriptBlock { Set-Location $using:RepoRoot; poetry run pytest --cov=packages --cov=apps/api --cov-fail-under=100 }
    $jobs += Start-Job -Name ts    -ScriptBlock { Set-Location (Join-Path $using:RepoRoot 'apps/console'); pnpm vitest run --coverage }
    $jobs += Start-Job -Name e2e   -ScriptBlock { Set-Location $using:RepoRoot; pnpm exec playwright test }
    $jobs | Wait-Job | Out-Null
    foreach ($j in $jobs) {
        Write-Host ('---- ' + $j.Name + ' ----') -ForegroundColor Yellow
        Receive-Job $j
        $j | Remove-Job
    }
    Stamp-End 'ci-local'
}

function Action-BackupNow {
    Stamp-Start 'backup-now'
    Push-Location $RepoRoot
    poetry run python tools/backup.py --pg-dump --s3-sync
    Pop-Location
    Stamp-End 'backup-now'
}

# ===== META =====
function Action-Version {
    $sha = git rev-parse --short HEAD
    Write-Host ('Forensa v0.1.0 (' + $sha + ')')
    Write-Host 'ops.ps1 dispatcher v1'
}

# ===== DISPATCHER =====
switch ($Action.ToLower()) {
    'help'             { Action-Help }
    'status'           { Action-Status }
    'push'             { Action-Push }
    'pull'             { Action-Pull }
    'commit-doc'       { Action-CommitDoc $Rest[0] }
    'build-api'        { Action-BuildApi }
    'build-console'    { Action-BuildConsole }
    'build-docker'     { Action-BuildDocker }
    'build-all'        { Action-BuildAll }
    'run-api'          { Action-RunApi }
    'run-console'      { Action-RunConsole }
    'run-worker'       { Action-RunWorker }
    'run-all'          { Action-RunAll }
    'test-python'      { Action-TestPython }
    'test-typescript'  { Action-TestTypescript }
    'test-e2e'         { Action-TestE2E }
    'test-load'        { Action-TestLoad }
    'test-all'         { Action-TestAll }
    'ingest-smoke'     { Action-IngestSmoke }
    'verify-chain'     { Action-VerifyChain }
    'evidence-pack'    { Action-EvidencePack }
    'lobstertrap-pipe' { Action-LobstertrapPipe }
    'tamper-demo'      { Action-TamperDemo }
    'gemini-narrative' { Action-GeminiNarrative }
    'generate-openapi' { Action-GenerateOpenapi }
    'db-migrate'       { Action-DbMigrate }
    'db-rollback'      { Action-DbRollback }
    'deploy-helm'      { Action-DeployHelm }
    'ci-local'         { Action-CiLocal }
    'backup-now'       { Action-BackupNow }
    'version'          { Action-Version }
    default {
        Write-Host ('Unknown action: ' + $Action) -ForegroundColor Red
        Write-Host ''
        Action-Help
        exit 1
    }
}

