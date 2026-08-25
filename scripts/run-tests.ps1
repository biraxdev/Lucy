Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Run the 14 targeted backend tests
& pytest backend/tests/test_auth.py backend/tests/test_agents.py backend/tests/test_library.py backend/tests/test_metrics.py -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Build the frontend if npm is available
$npm = Get-Command npm -ErrorAction SilentlyContinue
if ($npm) {
    cd frontend
    & npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "npm not found, skipping frontend build"
}
