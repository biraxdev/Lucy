#!/usr/bin/env bash
set -euo pipefail

# Run the 14 targeted backend tests
pytest backend/tests/test_auth.py backend/tests/test_agents.py backend/tests/test_library.py backend/tests/test_metrics.py -v

# Build the frontend if npm is available
if command -v npm >/dev/null 2>&1; then
    cd frontend && npm run build
else
    echo "npm not found, skipping frontend build"
fi
