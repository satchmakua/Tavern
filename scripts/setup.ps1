#requires -Version 5.1
<#
.SYNOPSIS
    Tavern M0 environment setup — Ollama models.

.DESCRIPTION
    Confirms Ollama is installed, ensures its server is reachable at :11434
    (starting it if needed), pulls the LLM models the Companion Daemon depends
    on, and verifies they registered. Idempotent — safe to re-run.

.EXAMPLE
    ./scripts/setup.ps1

.EXAMPLE
    ./scripts/setup.ps1 -Models "llama3.1:8b","qwen2.5:7b"
#>
[CmdletBinding()]
param(
    [string]   $OllamaHost = "http://localhost:11434",
    [string[]] $Models     = @("llama3.1:8b-instruct", "qwen2.5:7b-instruct")
)

$ErrorActionPreference = "Stop"

function Write-Step { param($m) Write-Host "==> $m" -ForegroundColor Cyan }
function Write-Good { param($m) Write-Host "    OK  $m" -ForegroundColor Green }
function Write-Note { param($m) Write-Host "    !!  $m" -ForegroundColor Yellow }

function Test-Ollama {
    try { Invoke-RestMethod -Uri "$OllamaHost/api/tags" -TimeoutSec 5 | Out-Null; return $true }
    catch { return $false }
}

# 1. Ollama installed?
Write-Step "Checking for Ollama on PATH..."
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Note "Ollama not found. Install from https://ollama.com/download then re-run."
    exit 1
}
Write-Good "Found $($ollama.Source)"

# 2. Server reachable? Start it if not.
Write-Step "Checking Ollama server at $OllamaHost ..."
if (-not (Test-Ollama)) {
    Write-Note "Server not responding; starting 'ollama serve' in the background..."
    Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds(30)
    while (-not (Test-Ollama) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 1 }
    if (-not (Test-Ollama)) {
        Write-Note "Still unreachable at $OllamaHost. Start 'ollama serve' manually and re-run."
        exit 1
    }
}
Write-Good "Server is up at $OllamaHost"

# 3. Pull models.
foreach ($model in $Models) {
    Write-Step "Pulling $model (first run can take a while)..."
    & $ollama.Source pull $model
    if ($LASTEXITCODE -ne 0) {
        Write-Note "Failed to pull $model (exit $LASTEXITCODE). Check the tag at https://ollama.com/library."
        exit 1
    }
    Write-Good "$model pulled"
}

# 4. Verify the server lists them.
Write-Step "Verifying registered models..."
$installed = (Invoke-RestMethod -Uri "$OllamaHost/api/tags").models | ForEach-Object { $_.name }
$missing = @()
foreach ($model in $Models) {
    if ($installed | Where-Object { $_ -eq $model -or $_ -like "$model*" }) {
        Write-Good "$model present"
    } else {
        Write-Note "$model not listed by the server."
        $missing += $model
    }
}
if ($missing.Count -gt 0) { exit 1 }

Write-Host ""
Write-Host "Ollama setup complete." -ForegroundColor Green
Write-Host "Next (M0): install whisper.cpp (base.en) and Piper. See roadmap.md." -ForegroundColor Gray
