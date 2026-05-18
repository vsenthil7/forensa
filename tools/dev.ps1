# Forensa - dev orchestration helper
#
# CP9.61 - wraps `docker compose` with the canonical --env-file argument
# so callers don't have to remember it. Matches the MendoraCI ergonomic
# pattern (single entry point per dev op).
#
# Usage from repo root:
#   .\tools\dev.ps1 up         # bring stack up detached
#   .\tools\dev.ps1 down       # stop + remove containers (volume preserved)
#   .\tools\dev.ps1 down-v     # stop + remove containers AND named volume (DATA LOSS)
#   .\tools\dev.ps1 ps         # docker compose ps
#   .\tools\dev.ps1 logs       # tail all services
#   .\tools\dev.ps1 logs api   # tail one service
#   .\tools\dev.ps1 build      # rebuild images without cache
#   .\tools\dev.ps1 health     # poll /healthz + console root
#   .\tools\dev.ps1 psql       # interactive psql shell inside the postgres container
#   .\tools\dev.ps1 migrate    # re-run alembic upgrade head (idempotent)
#   .\tools\dev.ps1 status     # one-line status of all services + ports

[CmdletBinding()]
param(
  [Parameter(Position = 0, Mandatory = $true)]
  [ValidateSet("up","down","down-v","ps","logs","build","health","psql","migrate","status","restart","help")]
  [string]$Action,
  [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
  [string[]]$Rest
)

$ErrorActionPreference = "Stop"

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
    Write-Host "[dev.ps1] api healthz (http://localhost:$apiPort/healthz)"
    try { (Invoke-WebRequest -Uri "http://localhost:$apiPort/healthz" -UseBasicParsing -TimeoutSec 5).Content }
    catch { Write-Host ("  ERROR: " + $_.Exception.Message) -ForegroundColor Red }
    Write-Host ""
    Write-Host "[dev.ps1] console root (http://localhost:$consolePort)"
    try {
      $r = Invoke-WebRequest -Uri "http://localhost:$consolePort" -UseBasicParsing -TimeoutSec 5
      Write-Host ("  HTTP " + $r.StatusCode + " (" + $r.Content.Length + " bytes)")
    } catch { Write-Host ("  ERROR: " + $_.Exception.Message) -ForegroundColor Red }
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
  "help" {
    Get-Content $PSCommandPath | Select-String -Pattern '^# ' | ForEach-Object { $_.Line.Substring(2) }
  }
}
