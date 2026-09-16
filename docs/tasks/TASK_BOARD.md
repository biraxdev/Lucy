# LucyAI — Task Board

> Source of truth for development progress.  Updated after every task completion.

## Status Legend

| Status | Meaning |
|--------|---------|
| BACKLOG | Identified, not yet refined |
| READY | Refined, all dependencies met, can be started |
| IN_PROGRESS | Actively being worked on |
| BLOCKED | Waiting on a dependency or decision |
| REVIEW | Code complete, awaiting review |
| TESTING | Under test |
| DONE | All quality gates passed, merged |

---

## Phase 0 — Foundation

| ID | Task | Owner | Status | Priority | Dependencies | Branch | Tests |
|----|------|-------|--------|----------|-------------|--------|-------|
| LUCY-001 | Fix CI to target v2 branch, run regression + full baseline + lint | Cloud | REVIEW | P0 | — | feature/LUCY-001-foundation | 14 blocking tests pass; full baseline recorded |
| LUCY-002 | Clean tracked generated artifacts (.gitignore, git rm) | Cloud | REVIEW | P0 | — | feature/LUCY-001-foundation | 135 generated files removed from index |
| LUCY-003 | Fix broken Netlify config (portable paths, remove placeholder proxy) | Cloud | REVIEW | P0 | — | feature/LUCY-001-foundation | frontend build passes |
| LUCY-004 | Add pre-commit hooks (flake8, eslint, key detection) | Cloud | REVIEW | P0 | — | feature/LUCY-001-foundation | all hooks pass |
| LUCY-005 | Consolidate CI: merge ci.yml + deploy.yml | Cloud | READY | P0 | LUCY-001 | feature/LUCY-005-consolidate-ci | CI green |
| LUCY-006 | Create shared LucyAI types package (lucyai/) | Cloud | READY | P1 | LUCY-001 | feature/LUCY-006-shared-types | imports work |
| LUCY-007 | Stabilize the legacy full backend suite | Cloud | BACKLOG | P0 | LUCY-001 | — | eliminate 25 failures + 29 errors without extending retired C2 code |

## Phase 1 — IDE Core (Local-primary)

| ID | Task | Owner | Status | Priority | Dependencies | Branch | Tests |
|----|------|-------|--------|----------|-------------|--------|-------|
| LUCY-010 | Workspace/project model + file explorer API | Cloud | BACKLOG | P1 | LUCY-006 | — | API tests |
| LUCY-011 | Multi-tab Monaco editor integration | Local | BACKLOG | P1 | LUCY-010 | — | Opens/saves files |
| LUCY-012 | PTY terminal backend + xterm connection | Cloud | BACKLOG | P1 | LUCY-006 | — | Shell session works |
| LUCY-013 | Terminal UI page (replace C2 broadcast shell) | Local | BACKLOG | P1 | LUCY-012 | — | PTY streams |
| LUCY-014 | Git status/diff/commit UI | Local | BACKLOG | P2 | LUCY-010 | — | Git ops work |
| LUCY-015 | Consolidate 4 chat UIs into one assistant panel | Local | BACKLOG | P1 | — | — | Single chat works |
| LUCY-016 | Command palette: add IDE commands (open file, go to symbol) | Local | BACKLOG | P2 | LUCY-011 | — | Commands execute |

## Phase 2 — Agent Core

| ID | Task | Owner | Status | Priority | Dependencies | Branch | Tests |
|----|------|-------|--------|----------|-------------|--------|-------|
| LUCY-020 | Coding-agent tool contract + registry | Cloud | BACKLOG | P1 | LUCY-006 | — | Tool registration |
| LUCY-021 | Durable agent-run state machine (DB-persisted sessions) | Cloud | BACKLOG | P1 | LUCY-020 | — | Run lifecycle |
| LUCY-022 | Sandbox executor (fail-closed, per-run isolation) | Cloud | BACKLOG | P1 | LUCY-021 | — | Sandbox tests |
| LUCY-023 | File/shell/git tools (first tool implementations) | Cloud | BACKLOG | P1 | LUCY-020 | — | Tool tests |

## Phase 3 — Autonomous Coding

| ID | Task | Owner | Status | Priority | Dependencies | Branch | Tests |
|----|------|-------|--------|----------|-------------|--------|-------|
| LUCY-030 | Adapt ai_chat_engine reflect→plan→execute for coding tasks | Cloud | BACKLOG | P1 | LUCY-021 | — | Plan/execute loop |
| LUCY-031 | Test/debug/fix autonomous loop with safeguards | Cloud | BACKLOG | P1 | LUCY-030 | — | Loop terminates |
| LUCY-032 | Self-review + commit workflow | Cloud | BACKLOG | P2 | LUCY-031 | — | Clean commits |

## Phase 4 — Model Router

| ID | Task | Owner | Status | Priority | Dependencies | Branch | Tests |
|----|------|-------|--------|----------|-------------|--------|-------|
| LUCY-040 | Async multi-provider LLM abstraction (replace llm_bridge) | Cloud | BACKLOG | P1 | LUCY-006 | — | Provider tests |
| LUCY-041 | Streaming + cancellation + token accounting | Cloud | BACKLOG | P1 | LUCY-040 | — | Stream tests |
| LUCY-042 | Task-type routing (fast/code/reasoning/long-context/local) | Cloud | BACKLOG | P2 | LUCY-041 | — | Routing tests |

## Phase 5 — Context Engine

| ID | Task | Owner | Status | Priority | Dependencies | Branch | Tests |
|----|------|-------|--------|----------|-------------|--------|-------|
| LUCY-050 | Repository file indexing + symbol search | Cloud | BACKLOG | P1 | LUCY-010 | — | Index tests |
| LUCY-051 | Relevant-context selection algorithm | Cloud | BACKLOG | P1 | LUCY-050 | — | Context tests |
| LUCY-052 | Semantic search (embeddings + vector store) | Cloud | BACKLOG | P2 | LUCY-050 | — | Search tests |

## Phase 6 — Multi-Agent

| ID | Task | Owner | Status | Priority | Dependencies | Branch | Tests |
|----|------|-------|--------|----------|-------------|--------|-------|
| LUCY-060 | Orchestrator + task decomposition | Cloud | BACKLOG | P2 | LUCY-031 | — | Decompose tests |
| LUCY-061 | Parallel execution + dependency graph | Cloud | BACKLOG | P2 | LUCY-060 | — | Parallel tests |
| LUCY-062 | Adapt ReactFlow workflow canvas for agent orchestration | Local | BACKLOG | P2 | LUCY-060 | — | Canvas works |

---

_Last updated: 2026-09-16 — Foundation implementation in review; legacy test debt captured in LUCY-007._
