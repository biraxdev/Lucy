$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $MyInvocation.MyCommand.Definition
$frontend = Join-Path $repo "frontend"

if (-not (Test-Path $frontend)) {
    Write-Error "frontend directory not found at $frontend"
    exit 1
}

Set-Location $frontend
& npm run build
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
