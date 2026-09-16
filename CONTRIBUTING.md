# Contributing to LucyAI

## Quick Start

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python main.py                # http://localhost:8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173 → proxies /api to :8000
```

## Branch Strategy

- **Never work directly on `v2`** (default branch)
- One branch per task: `feature/LUCY-NNN-short-description`
- Atomic commits with descriptive messages
- Tests must pass before merge

## Quality Gates

A task is **DONE** only when:

- [ ] Code compiles / imports cleanly
- [ ] Relevant backend tests pass; the blocking regression suite stays green
- [ ] The full backend suite is run and does not regress the documented baseline
- [ ] `cd frontend && npm run build` passes (includes `tsc`)
- [ ] `make lint` passes
- [ ] No accidental file modifications outside the task scope
- [ ] Documentation updated if the change is user-visible
- [ ] Diff inspected before commit
- [ ] Task Board updated

## Code Style

- **Python**: follow existing conventions (FastAPI patterns, Peewee models).
  Max line length 120.  Imports at the top of files.
- **TypeScript/React**: follow existing conventions (functional components,
  Zustand stores, TanStack Query hooks).  Use the project's Tailwind/daisyUI
  design tokens.
- **Rust**: `cargo fmt` + `cargo clippy` (lucy-desktop).

## Adding Dependencies

Before adding a dependency, check:
1. Is the functionality already in the codebase?
2. Is there an already-installed package that can do it?
3. Is the package mature, maintained, and well-adopted?
4. Prefer versions published ≥ 7 days ago (supply-chain safety).

## Security

- Never expose secrets in logs, commits, or model context.
- Never modify security policies to work around build failures.
- Use `$VARIABLE_NAME` syntax for secrets in configuration.
- The offensive / C2 surface is permanently excluded from LucyAI.
  Do not improve, port, or re-enable it.

## Testing

```bash
# Blocking backend regression suite
cd backend && python -m pytest tests/test_auth.py tests/test_agents.py tests/test_library.py tests/test_metrics.py -v --tb=short

# Full backend suite (compare against the baseline tracked in LUCY-007)
cd backend && python -m pytest tests/ -v --tb=short

# Frontend build (includes typecheck)
cd frontend && npm run build

# Lint and hooks
make lint
pre-commit run --all-files
```

## Documentation

Keep these files in sync with the codebase:
- `MASTER_BLUEPRINT.md` — product vision and migration boundary
- `ARCHITECTURE.md` — system architecture
- `AGENTS.md` — agent development guide
- `docs/tasks/TASK_BOARD.md` — task tracking
- `CONTRIBUTING.md` — this file
