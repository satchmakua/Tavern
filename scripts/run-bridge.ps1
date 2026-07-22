#requires -Version 5.1
<#
.SYNOPSIS
    Run the Companion Daemon against the live WC3 map bridge (w3ts File format).

.DESCRIPTION
    Points the daemon at the map's CustomMapData folder: it reads TavernState.txt
    (game → daemon) and writes TavernDirective.txt (daemon → game), both in the
    w3ts File on-disk format (--wc3). Load the Tavern bridge map in Reforged, then
    run this. Ctrl-C to stop.

.EXAMPLE
    ./scripts/run-bridge.ps1            # fake LLM (fast, deterministic first test)
    ./scripts/run-bridge.ps1 -Real      # real Ollama models
#>
[CmdletBinding()]
param([switch]$Real)

$bridge = Join-Path $env:USERPROFILE "OneDrive\Documents\Warcraft III\CustomMapData"
if (-not (Test-Path $bridge)) { New-Item -ItemType Directory -Force -Path $bridge | Out-Null }

$daemon = Join-Path (Split-Path -Parent $PSScriptRoot) "daemon"
$py = Join-Path $daemon ".venv\Scripts\python.exe"

$argv = @("-m", "tavern", "--bridge", $bridge, "--wc3")
if (-not $Real) { $argv += "--fake-llm" }

Write-Host "Bridge dir: $bridge" -ForegroundColor Cyan
Write-Host ("Mode: {0}" -f ($(if ($Real) { "real Ollama" } else { "fake-llm" }))) -ForegroundColor Cyan
Write-Host "Tip: pause OneDrive sync while testing to avoid file locks. Ctrl-C to stop.`n" -ForegroundColor DarkGray

Push-Location $daemon
try { & $py @argv } finally { Pop-Location }
