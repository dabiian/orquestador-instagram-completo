# Run from any directory on Windows: powershell -ExecutionPolicy Bypass -File .\verify-instagram-local.ps1
# Local checks only; never creates an execution or contacts production services.
param([switch]$SkipDependencyInstall)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$original = Get-Location

function Run-Checked([string]$program, [string[]]$arguments) {
    & $program @arguments
    if ($LASTEXITCODE -ne 0) { throw "$program failed (exit $LASTEXITCODE)" }
}

function Test-Python([string]$name, [string]$directory, [string[]]$requirements, [string[]]$tests) {
    $venv = Join-Path $env:TEMP "orquestador-instagram-$name-venv"
    $pythonExe = Join-Path $venv 'Scripts\python.exe'
    if (-not (Test-Path $pythonExe)) { Run-Checked 'python' @('-m', 'venv', $venv) }
    Set-Location (Join-Path $root $directory)
    if (-not $SkipDependencyInstall) { Run-Checked $pythonExe (@('-m', 'pip', 'install') + $requirements) }
    Run-Checked $pythonExe $tests
}

try {
    Test-Python 'rpa' 'rpa_orchestrator-master\rpa_orchestrator-master' @('-e', '.[dev]') @('-m', 'pytest', '-q', 'tests/unit')

    $env:DEBUG = 'True'
    $env:SECRET_KEY = 'local-test-only'
    $env:DATABASE_URL = 'sqlite:///:memory:'
    $env:DJANGO_SETTINGS_MODULE = 'back_redes_sociales.settings'
    Test-Python 'django' 'backend-redes-sociales-main\backend-redes-sociales-main' @('-r', 'requirements.txt', 'pytest', 'pytest-django') @('-m', 'pytest', '-q', 'dashboard/tests/test_orchestrator_instagram.py')

    $env:PYTHONPATH = Join-Path $root 'Bot-Instagram-\Bot-Instagram--master'
    Test-Python 'bot' 'Bot-Instagram-\Bot-Instagram--master' @('pytest', 'requests', 'python-dotenv') @('-m', 'pytest', '-q', 'tests/test_orchestrator_claim_fallback.py')

    Set-Location (Join-Path $root 'Fronted-Instagram-master\Fronted-Instagram-master')
    if (-not $SkipDependencyInstall) { Run-Checked 'npm' @('ci', '--no-audit', '--no-fund') }
    Run-Checked 'npm' @('run', 'build')
    Run-Checked 'node' @('--test', 'tests/orchestrator.test.js')
    Write-Host 'Local Instagram checks passed. No server execution was created.'
} finally {
    Set-Location $original
}
