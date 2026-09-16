# LUCY-001 — Foundation: CI, Repo Hygiene, Pre-commit Hooks

## Contract

| Field | Value |
|-------|-------|
| TASK_ID | LUCY-001 |
| TITLE | Fix CI, clean tracked artifacts, add pre-commit hooks |
| OWNER | Cloud |
| TYPE | Infrastructure |
| PRIORITY | P0 |
| STATUS | REVIEW |
| BRANCH | feature/LUCY-001-foundation |
| FILE_SCOPE | `.github/workflows/`, `.gitignore`, `.pre-commit-config.yaml`, `.netlify/`, root files |
| DEPENDENCIES | None |

## Objective

Make the repo buildable and testable on the actual default branch (`v2`),
enforce quality gates, and clean up tracked generated artifacts.

## Context

- CI workflows target `main`/`master` but the default branch is `v2`.
- `ci.yml` runs only 4 of 21 backend test files.
- No lint or typecheck gate in CI.
- 133 generated files tracked under `backend/data/`.
- Celerybeat schedule files tracked.
- Root `package-lock.json` is an empty stub.
- `.netlify/netlify.toml` has machine-specific Windows paths.
- No `.pre-commit-config.yaml` or `.husky/`.

## Implementation

1. **Fix CI branch triggers**: add `v2` to push/pull_request branches in
   both `ci.yml` and `deploy.yml`.
2. **Run backend tests in CI**: keep the 14-test regression set blocking and
   run the full 186-test legacy suite as a visible non-blocking baseline until
   LUCY-007 stabilizes it.
3. **Add lint gate to CI**: add safe flake8 checks + eslint parsing/warnings.
4. **Clean .gitignore**: add `backend/data/reports/`, `backend/data/*.db*`,
   `celerybeat-schedule*`, `backend/data/.setup_complete`,
   `backend/data/build_audit.log`.
5. **git rm --cached** the tracked generated files.
6. **Delete** empty root `package-lock.json`.
7. **Fix .netlify/netlify.toml**: replace machine-specific paths with
   `base = "frontend"` and `publish = "dist"`; remove the non-functional
   placeholder backend proxy until a real deployment endpoint is configured.
8. **Add .pre-commit-config.yaml** with: trailing-whitespace, end-of-file,
   check-yaml, detect-private-key, flake8, eslint.
9. **Update governance docs** created in this PR.

## Acceptance Criteria

- [x] CI triggers on `v2` branch
- [x] Full backend test suite runs in CI with its legacy baseline visible
- [x] Blocking backend regression suite passes
- [x] Lint gates present
- [x] Generated runtime files removed from the index and ignored
- [x] `.pre-commit-config.yaml` present and working
- [x] `.netlify/netlify.toml` uses portable paths

## Tests

- Blocking backend regression: 14 passed
- Full backend suite: 132 passed, 25 failed, 29 errors (identical on `origin/v2`)
- Frontend eslint: passes with 98 legacy warnings
- Frontend typecheck/build: passes
- Safe flake8 gate: passes
- `pre-commit run --all-files`: passes

## Expected Output

Green blocking CI on `v2`, with the complete legacy-suite result still
reported and tracked for repair in LUCY-007.

## Handoff

After merge, Local can start IDE UI tasks (LUCY-011+) on a clean foundation.
