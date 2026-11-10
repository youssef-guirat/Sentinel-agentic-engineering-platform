$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPython) {
    & $venvPython scripts/bootstrap.py @args
    exit $LASTEXITCODE
}

$launcher = Get-Command py -ErrorAction SilentlyContinue
if ($launcher) {
    & py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info[:3] == (3, 11, 9) else 1)" *> $null
    if ($LASTEXITCODE -eq 0) {
        & py -3.11 scripts/bootstrap.py @args
        exit $LASTEXITCODE
    }
}

$python311 = Get-Command python3.11 -ErrorAction SilentlyContinue
if ($python311) {
    & $python311.Source scripts/bootstrap.py @args
    exit $LASTEXITCODE
}

Write-Error "Sentinel requires Python 3.11.9. Install it, then rerun .\init.ps1."
