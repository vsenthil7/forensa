# Forensa - dev orchestration helper
#
# CP9.61 / CP9.61b - wraps `docker compose` with the canonical --env-file
# argument so callers don't have to remember it. Matches the MendoraCI
# ergonomic pattern (single entry point per dev op).
#
# Usage from repo root:
#   .\tools\dev.ps1 up         # bring stack up detached
#   .\tools\dev.ps1 down       # stop + remove containers (volume preserved)
#   .\tools\dev.ps1 down-v     # stop + remove containers AND named volume (DATA LOSS)
#   .\tools\dev.ps1 ps         # docker compose ps
#   .\tools\dev.ps1 logs       # tail all services
#   .\tools\dev.ps1 logs api   # tail one service
#   .\tools\dev.ps1 build      # rebuild images without cache
#   .\tools\dev.ps1 health     # poll /healthz + console root + authed /v1/anchors
#   .\tools\dev.ps1 psql       # interactive psql shell inside the postgres container
#   .\tools\dev.ps1 migrate    # re-run alembic upgrade head (idempotent)
#   .\tools\dev.ps1 status     # one-line status of all services + ports
#   .\tools\dev.ps1 token      # mint a Bearer token for the demo tenant (CP9.61b)
#   .\tools\dev.ps1 demo       # one-shot: mint token + curl every authed surface (CP9.61b)

[CmdletBinding()]
param(
  [Parameter(Position = 0, Mandatory = $true)]
  [ValidateSet("up","down","down-v","ps","logs","build","health","psql","migrate","status","restart","token","demo","help")]
  [string]$Action,
  [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
  [string[]]$Rest
)

# NOTE: NOT using $ErrorActionPreference = "Stop" globally because docker /
# Invoke-WebRequest emit non-terminating warnings that cascade into Catch.

# Resolve repo root from this script's location
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$EnvFile = ".env.compose"
if (-not (Test-Path $EnvFile)) {
  Write-Error "$EnvFile not found in repo root. CP9.61 expected this file."
  exit 1
}

# If .env.compose.local exists (gitignored override), layer it on
$EnvArgs = @("--env-file", $EnvFile)
if (Test-Path ".env.compose.local") {
  $EnvArgs += @("--env-file", ".env.compose.local")
}

function Get-Ports {
  $envText = Get-Content $EnvFile -Raw
  $ports = @{}
  foreach ($var in @("POSTGRES_HOST_PORT","API_HOST_PORT","CONSOLE_HOST_PORT")) {
    if ($envText -match "(?m)^${var}=(\S+)") { $ports[$var] = $matches[1] }
  }
  return $ports
}

function Get-DemoToken {
  # Mints inside the running forensa-api container using scripts/mint_demo_token.py.
  # PYTHONPATH=/app + cwd=/app makes `from apps.api.auth.token import ...` resolve.
  $output = docker exec -e PYTHONPATH=/app -w /app forensa-api python /app/scripts/mint_demo_token.py
  return $output
}

function Invoke-AuthedGet {
  param([string]$Url, [string]$Token)
  # Use a clean try/catch with Stop scoped to just this call so PowerShell's
  # default non-terminating-error noise from Invoke-WebRequest stays contained.
  $ErrorActionPreference = "Stop"
  try {
    $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 -Headers @{ "Authorization" = ("Bearer " + $Token) }
    return @{ ok = $true; status = $r.StatusCode; body = $r.Content }
  } catch {
    $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 0 }
    $body = if ($_.ErrorDetails) { $_.ErrorDetails.Message } else { $_.Exception.Message }
    return @{ ok = $false; status = $code; body = $body }
  }
}

switch ($Action) {
  "up" {
    Write-Host "[dev.ps1] docker compose $($EnvArgs -join ' ') up -d --build"
    & docker compose @EnvArgs up -d --build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & "$PSCommandPath" status
  }
  "down" {
    & docker compose @EnvArgs down
  }
  "down-v" {
    Write-Host "[dev.ps1] WARNING - this removes the forensa-pg-data volume." -ForegroundColor Yellow
    $confirm = Read-Host "Type 'yes' to confirm"
    if ($confirm -eq "yes") {
      & docker compose @EnvArgs down -v
    } else {
      Write-Host "Aborted."
    }
  }
  "ps" {
    & docker compose @EnvArgs ps
  }
  "logs" {
    if ($Rest) {
      & docker compose @EnvArgs logs -f --tail=100 $Rest
    } else {
      & docker compose @EnvArgs logs -f --tail=50
    }
  }
  "build" {
    & docker compose @EnvArgs build --no-cache
  }
  "health" {
    $ports = Get-Ports
    $apiPort = $ports.API_HOST_PORT
    $consolePort = $ports.CONSOLE_HOST_PORT
    Write-Host "[dev.ps1] api healthz (http://localhost:${apiPort}/healthz)"
    try { (Invoke-WebRequest -Uri "http://localhost:${apiPort}/healthz" -UseBasicParsing -TimeoutSec 5).Content }
    catch { Write-Host ("  ERROR: " + $_.Exception.Message) -ForegroundColor Red }
    Write-Host ""
    Write-Host "[dev.ps1] console root (http://localhost:${consolePort})"
    try {
      $r = Invoke-WebRequest -Uri "http://localhost:${consolePort}" -UseBasicParsing -TimeoutSec 5
      Write-Host ("  HTTP " + $r.StatusCode + " (" + $r.Content.Length + " bytes)")
    } catch { Write-Host ("  ERROR: " + $_.Exception.Message) -ForegroundColor Red }
    Write-Host ""
    Write-Host "[dev.ps1] authed /v1/anchors smoke (Bearer minted via scripts/mint_demo_token.py)"
    $token = Get-DemoToken
    $envText = Get-Content $EnvFile -Raw
    $tenant = if ($envText -match "(?m)^FORENSA_HMAC_TENANT_ID=(\S+)") { $matches[1] } else { "" }
    $result = Invoke-AuthedGet -Url ("http://localhost:" + $apiPort + "/v1/anchors?tenant_id=" + $tenant) -Token $token
    if ($result.ok) {
      Write-Host ("  HTTP " + $result.status + " :: " + $result.body)
    } else {
      Write-Host ("  HTTP " + $result.status + " :: " + $result.body) -ForegroundColor Red
    }
  }
  "psql" {
    $envText = Get-Content $EnvFile -Raw
    $pgUser = "forensa"
    $pgDb = "forensa"
    if ($envText -match "(?m)^POSTGRES_USER=(\S+)") { $pgUser = $matches[1] }
    if ($envText -match "(?m)^POSTGRES_DB=(\S+)")   { $pgDb   = $matches[1] }
    & docker exec -it forensa-postgres psql -U $pgUser -d $pgDb
  }
  "migrate" {
    & docker compose @EnvArgs run --rm api-migrate
  }
  "status" {
    $ports = Get-Ports
    Write-Host ""
    & docker compose @EnvArgs ps
    Write-Host ""
    Write-Host "[dev.ps1] URLs:" -ForegroundColor Cyan
    Write-Host ("  Console : http://localhost:" + $ports.CONSOLE_HOST_PORT)
    Write-Host ("  API     : http://localhost:" + $ports.API_HOST_PORT)
    Write-Host ("  Healthz : http://localhost:" + $ports.API_HOST_PORT + "/healthz")
    Write-Host ("  Postgres: localhost:" + $ports.POSTGRES_HOST_PORT)
    Write-Host ""
  }
  "restart" {
    if ($Rest) {
      & docker compose @EnvArgs restart $Rest
    } else {
      & docker compose @EnvArgs restart
    }
  }
  "token" {
    Write-Host (Get-DemoToken)
  }
  "demo" {
    $ports = Get-Ports
    $apiPort = $ports.API_HOST_PORT
    $envText = Get-Content $EnvFile -Raw
    $tenant = if ($envText -match "(?m)^FORENSA_HMAC_TENANT_ID=(\S+)") { $matches[1] } else { "" }
    $token = Get-DemoToken
    Write-Host ("[dev.ps1] minted token for tenant " + $tenant.Substring(0,8) + "...")
    Write-Host ""
    $surfaces = @("anchors","receipts","metrics")
    foreach ($s in $surfaces) {
      # Use string concat (NOT interpolation) so PowerShell doesn't try to
      # parse `$s?tenant_id` as a variable name with a ? in it.
      $url = "http://localhost:" + $apiPort + "/v1/" + $s + "?tenant_id=" + $tenant
      Write-Host ("=== GET /v1/" + $s + " ===") -ForegroundColor Cyan
      $result = Invoke-AuthedGet -Url $url -Token $token
      if ($result.ok) {
        Write-Host ("HTTP " + $result.status)
        Write-Host $result.body
      } else {
        Write-Host ("HTTP " + $result.status) -ForegroundColor Red
        Write-Host $result.body
      }
      Write-Host ""
    }
  }
  "help" {
    Get-Content $PSCommandPath | Select-String -Pattern '^# ' | ForEach-Object { $_.Line.Substring(2) }
  }
}
