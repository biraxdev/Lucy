# LucyAI — Devin Context Rules

## Project Identity

LucyAI is an AI-first IDE, autonomous coding agent, and multi-agent
development system.  Built on reusable foundations from the Lucy platform.

## General Principles

- Never ask to start/stop a service when a technical solution exists.
- Never ask binary questions when an implementation is possible.
- Every action must move the project toward a better state.
- No fake tests, fabricated timeouts, or mock responses.
- Prefer action over asking for permission.
- Follow REUSE > ADAPT > EXTEND > BUILD.

## Intelligence / Latitude

- Anticipate needs: persistence, redundancy, auto-repair.
- On ambiguity, choose the interpretation closest to the goal and justify.
- Never reduce capabilities to pass a test.
- Never truncate or alter collected data.
- Preserve existing architecture; add clean modules rather than rewriting.

## Important Boundaries

- The offensive / C2 / implant surface is permanently excluded from LucyAI.
  Do not improve, port, or re-enable any offensive functionality.
- IDE features (editor, terminal, git, tools) are the product focus.
- See `MASTER_BLUEPRINT.md` for the full migration boundary.

## Key Documents

- `MASTER_BLUEPRINT.md` — product vision, migration boundary, reuse map
- `ARCHITECTURE.md` — system architecture
- `AGENTS.md` — agent development guide
- `CONTRIBUTING.md` — setup, quality gates, code style
- `EXECUTION_DIRECTIVE.md` — execution rules and workflow
- `docs/tasks/TASK_BOARD.md` — task tracking

## Quality Gates

- Backend regression: `cd backend && python -m pytest tests/test_auth.py tests/test_agents.py tests/test_library.py tests/test_metrics.py -v`
- Backend full baseline: `cd backend && python -m pytest tests/ -v`
- Frontend: `cd frontend && npm run build` (includes tsc)
- Lint: `make lint` (safe backend checks + eslint)
- Pre-commit: `pre-commit run --all-files`

## Verification

- Always provide concrete evidence (test results, screenshots, logs).
- Test after every significant modification.
