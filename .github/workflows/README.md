# Workflows

This directory contains GitHub Actions workflows for Lucy.

- `ci.yml` — Continuous Integration.
  - **Trigger:** `push` and `pull_request` on `main` and `master`.
  - **`backend-test` job:** Check out the repository, set up Python 3.12, install dependencies from `backend/requirements.txt`, and run the targeted backend tests with `pytest`.
  - **`frontend-build` job:** Check out the repository, set up Node 20, run `npm ci` in `frontend`, and build the frontend with `npm run build`.
