# LUCY-006 — Create Shared LucyAI Types Package

## Contract

| Field | Value |
|-------|-------|
| TASK_ID | LUCY-006 |
| TITLE | Create shared LucyAI types package |
| OWNER | Cloud |
| TYPE | Foundation |
| PRIORITY | P1 |
| STATUS | READY |
| BRANCH | feature/LUCY-006-shared-types |
| FILE_SCOPE | `lucyai/`, `backend/` |
| DEPENDENCIES | LUCY-001 |

## Objective

Create a `lucyai/` Python package with shared type definitions, enums, and
protocols that the backend, agent runtime, and tool system will use.

## Context

Currently the backend has no typed domain model for the LucyAI product.
Types are scattered across Peewee models that mix C2 and platform concerns.

## Implementation

1. Create `lucyai/__init__.py`, `lucyai/types.py`, `lucyai/protocols.py`.
2. Define core enums: `TaskStatus`, `TaskType`, `ToolScope`, `RiskLevel`,
   `AgentRunState`, `ModelSlot`.
3. Define core protocols: `Tool`, `ModelProvider`, `ContextProvider`.
4. Define shared Pydantic models for API contracts.
5. Add `lucyai/tests/` with type validation tests.

## Acceptance Criteria

- [ ] `import lucyai` works from backend
- [ ] All enums and protocols defined with docstrings
- [ ] Type tests pass
- [ ] No circular imports

## Tests

`python -m pytest lucyai/tests/ -v`

## Expected Output

A clean, importable types package that all LucyAI components can depend on.

## Handoff

Subsequent Cloud tasks (LUCY-020 tool contract, LUCY-040 model router)
build on these types.
