#requires -Version 5.1
<#
.SYNOPSIS
    Tavern environment setup — Ollama (LLM) + Piper (TTS) + whisper.cpp (STT).

.DESCRIPTION
    Reproduces the full local toolchain the Companion Daemon and Voice Frontend
    depend on. Idempotent — safe to re-run; existing pieces are skipped.

      1. Install Ollama (via winget) if missing; ensure the server is up at :11434.
      2. Pull the LLM models and verify they registered.
      3. Download Piper + whisper.cpp binaries and models into <repo>/tools.

.EXAMPLE
    ./scripts/setup.ps1

.EXAMPLE
    ./scripts/setup.ps1 -SkipVoice            # LLM only
    ./scripts/setup.ps1 -Models "llama3.1:8b" # custom model set
#>
[CmdletBinding()]
param(
    [string]   $OllamaHost = "http://localhost:11434",
    [string[]] $Models     = @("llama3.1:8b", "qwen2.5:7b-instruct"),
    [switch]   $SkipVoice
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ToolsDir = Join-Path $RepoRoot "tools"

function Write-Step { param($m) Write-Host "==> $m" -ForegroundColor Cyan }
function Write-Good { param($m) Write-Host "    OK  $m" -ForegroundColor Green }
function Write-Note { param($m) Write-Host "    !!  $m" -ForegroundColor Yellow }

function Test-Ollama {
    try { Invoke-RestMethod -Uri "$OllamaHost/api/tags" -TimeoutSec 5 | Out-Null; return $true }
    catch { return $false }
}

function Get-File($url, $out) {
    if (Test-Path $out) { Write-Good "have $(Split-Path $out -Leaf)"; return }
    New-Item -ItemType Directory -Force -Path (Split-Path $out -Parent) | Out-Null
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $out
    Write-Good ("got {0} ({1:N1} MB)" -f (Split-Path $out -Leaf), ((Get-Item $out).Length / 1MB))
}

# --------------------------------------------------------------------------- #
# 1. Ollama
# --------------------------------------------------------------------------- #
Write-Step "Checking for Ollama..."
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    $local = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path $local) {
        $ollama = Get-Item $local
    } else {
        Write-Note "Ollama not found; installing via winget..."
        winget install --id Ollama.Ollama -e --silent --accept-source-agreements --accept-package-agreements
        if (-not (Test-Path $local)) { Write-Note "winget install did not produce $local. Install manually from https://ollama.com/download."; exit 1 }
        $ollama = Get-Item $local
    }
}
Write-Good "Found $($ollama.Source)"

Write-Step "Checking Ollama server at $OllamaHost ..."
if (-not (Test-Ollama)) {
    Write-Note "Server not responding; starting 'ollama serve' in the background..."
    Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds(30)
    while (-not (Test-Ollama) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 1 }
    if (-not (Test-Ollama)) { Write-Note "Still unreachable. Start 'ollama serve' manually and re-run."; exit 1 }
}
Write-Good "Server is up at $OllamaHost"

# --------------------------------------------------------------------------- #
# 2. Models
# --------------------------------------------------------------------------- #
foreach ($model in $Models) {
    Write-Step "Pulling $model (first run can take a while)..."
    & $ollama.Source pull $model
    if ($LASTEXITCODE -ne 0) { Write-Note "Failed to pull $model. Check the tag at https://ollama.com/library."; exit 1 }
    Write-Good "$model ready"
}

Write-Step "Verifying registered models..."
$installed = (Invoke-RestMethod -Uri "$OllamaHost/api/tags").models | ForEach-Object { $_.name }
foreach ($model in $Models) {
    if ($installed | Where-Object { $_ -eq $model -or $_ -like "$model*" }) { Write-Good "$model present" }
    else { Write-Note "$model not listed by the server."; exit 1 }
}

# --------------------------------------------------------------------------- #
# 3. Voice tooling (Piper TTS + whisper.cpp STT) -> <repo>/tools
# --------------------------------------------------------------------------- #
if (-not $SkipVoice) {
    Write-Step "Installing voice tools into $ToolsDir ..."
    $tmp = Join-Path $env:TEMP "tavern-setup"
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null

    # Piper binary
    if (-not (Test-Path "$ToolsDir\piper\piper.exe")) {
        Get-File "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip" "$tmp\piper.zip"
        Expand-Archive "$tmp\piper.zip" -DestinationPath $ToolsDir -Force
    }
    Write-Good "piper.exe ready"

    # whisper.cpp binary (CPU x64 — base.en is near-realtime on CPU)
    if (-not (Test-Path "$ToolsDir\whisper\Release\whisper-cli.exe")) {
        Get-File "https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.1/whisper-bin-x64.zip" "$tmp\whisper.zip"
        Expand-Archive "$tmp\whisper.zip" -DestinationPath "$ToolsDir\whisper" -Force
    }
    Write-Good "whisper-cli.exe ready"

    # Models / voices
    Get-File "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin" "$ToolsDir\whisper\models\ggml-base.en.bin"
    $vbase = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US"
    Get-File "$vbase/lessac/medium/en_US-lessac-medium.onnx"      "$ToolsDir\piper\voices\en_US-lessac-medium.onnx"
    Get-File "$vbase/lessac/medium/en_US-lessac-medium.onnx.json" "$ToolsDir\piper\voices\en_US-lessac-medium.onnx.json"
    Get-File "$vbase/ryan/medium/en_US-ryan-medium.onnx"          "$ToolsDir\piper\voices\en_US-ryan-medium.onnx"
    Get-File "$vbase/ryan/medium/en_US-ryan-medium.onnx.json"     "$ToolsDir\piper\voices\en_US-ryan-medium.onnx.json"
}

Write-Host ""
Write-Host "Tavern setup complete." -ForegroundColor Green
Write-Host "Try the brain:  cd daemon; .\.venv\Scripts\python.exe -m tavern --persona Dakkar" -ForegroundColor Gray
