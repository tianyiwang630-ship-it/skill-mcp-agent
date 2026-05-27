$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv was not found on PATH. Install uv first: https://docs.astral.sh/uv/getting-started/installation/" -ForegroundColor Red
    exit 1
}

function Invoke-NativeCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

$VenvDir = Join-Path $ProjectRoot ".venv"
$ScriptsDir = Join-Path $VenvDir "Scripts"
$PythonExe = Join-Path $ScriptsDir "python.exe"
$PipExe = Join-Path $ScriptsDir "pip.exe"
$PythonVersion = "3.12"

if (-not (Test-Path $PythonExe)) {
    Write-Host "Creating agent-alpha virtual environment with uv..." -ForegroundColor Cyan
    Invoke-NativeCommand uv @("venv", ".venv", "--python", $PythonVersion)
}

$ActualPythonVersion = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($ActualPythonVersion -ne $PythonVersion) {
    Write-Host "agent-alpha .venv is Python $ActualPythonVersion, but Python $PythonVersion is required." -ForegroundColor Red
    Write-Host "Remove .venv and run this script again to recreate it with Python $PythonVersion." -ForegroundColor Yellow
    exit 1
}

& $PythonExe -c "import tempfile"
if ($LASTEXITCODE -ne 0) {
    Write-Host "agent-alpha .venv Python is missing the standard library module 'tempfile'." -ForegroundColor Red
    Write-Host "This usually means the uv-managed Python installation is incomplete or corrupted." -ForegroundColor Yellow
    Write-Host "Remove .venv and reinstall uv's Python 3.12 runtime, then run this script again." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $PipExe)) {
    Write-Host "Bootstrapping pip inside agent-alpha .venv..." -ForegroundColor Cyan
    Invoke-NativeCommand $PythonExe @("-m", "ensurepip", "--upgrade")
}

$env:VIRTUAL_ENV = $VenvDir
$env:AGENT_ALPHA_PROJECT_ROOT = $ProjectRoot
$env:AGENT_ALPHA_PYTHON = $PythonExe
$env:PYTHONNOUSERSITE = "1"
$env:PATH = "$ScriptsDir;$env:PATH"

Write-Host "Installing/updating requirements..." -ForegroundColor Cyan
Invoke-NativeCommand uv @("pip", "install", "--python", $PythonExe, "-r", "requirements.txt")

Write-Host "Installing/updating agent-alpha in editable mode..." -ForegroundColor Cyan
Invoke-NativeCommand uv @("pip", "install", "--python", $PythonExe, "-e", ".")

$env:PIP_REQUIRE_VIRTUALENV = "true"

Write-Host "Starting agent-alpha..." -ForegroundColor Green
Invoke-NativeCommand $PythonExe @("-m", "agent.cli.main")
