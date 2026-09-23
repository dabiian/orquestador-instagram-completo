param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsToPass
)

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "No se encontró el Python de self_healer/.venv en $python"
    exit 1
}

& $python (Join-Path $PSScriptRoot "test_harness.py") @ArgsToPass
exit $LASTEXITCODE
