# LucyAI — System Architecture

## Overview

LucyAI is an AI-first IDE and autonomous coding agent built on a
reusable platform core extracted from the Lucy project.

The system is split into runtime layers that communicate through typed
interfaces:

```
USER
 ↓
LUCY UI  (React 18, Vite, Monaco, xterm, ReactFlow)
 ↓
API GATEWAY  (FastAPI, WebSocket, SSE)
 ↓
TASK MANAGER  (jobs: code / test / review / build)
 ↓
PLANNER  (reflect → plan → execute loop)
 ↓
MODEL ROUTER  (provider abstraction: Ollama / OpenAI / Anthropic / local)
 ↓
AGENT RUNTIME  (tool calls, sandbox, approval gates, durable state)
 ↓
TOOL SYSTEM  (filesystem, terminal, git, browser, tests, MCP, …)
 ↓
EXECUTION → TEST → DEBUG → FIX → RETEST → REVIEW → GIT → VALIDATION
```

Future multi-agent topology (Phase 6+):

```
USER
 ↓
ORCHESTRATOR
 ├── Agent Architect
 ├── Agent Planner
 ├── Agent Coder
 ├── Agent Researcher
 ├── Agent Tester
 ├── Agent Debugger
 ├── Agent Reviewer
 └── Agent Documentation
```

Agents may run in parallel when tasks are independent; dependent tasks
remain sequential.

## Backend

- **Runtime**: Python 3.12, FastAPI, Uvicorn, async
- **Persistence**: Peewee ORM, SQLite WAL (default), PostgreSQL optional
- **Auth**: JWT (30 min access / 7 day refresh), RBAC, TOTP, API keys
- **Task queue**: Celery + Redis (with in-memory fallback for portable mode)
- **Real-time**: WebSocket event delivery, SSE for streaming AI output
- **Library**: ResourceProvider Protocol + singleton registry (extensible
  for repos, files, symbols, tools, knowledge)

## Frontend

- **Stack**: React 18, TypeScript 5.6, Vite 5, TailwindCSS 3.4, daisyUI 4
- **State**: Zustand 5 (normalized entity stores), TanStack Query 5
- **Editor**: @monaco-editor/react (to be extended into full workspace editor)
- **Terminal**: @xterm/xterm (to be connected to a PTY backend)
- **Workflow**: ReactFlow node graph (adapt from ScriptBuilder)
- **AI**: CopilotDrawer / ChatPanel / SSE streaming
- **Navigation**: CommandPalette (Ctrl+K), react-router-dom v7 lazy routes

## Desktop

- `lucy-desktop/` is a Rust egui 0.29 native app reading a local SQLite
  snapshot (Dashboard / Agents / Tasks / Logs / Chat / Settings).
- It is **not** reusable as an IDE shell.  A Tauri or Electron wrapper
  around the web app will be evaluated when desktop distribution is needed.

## IDE Primitives (to build)

| Primitive | Status | Notes |
|-----------|--------|-------|
| File explorer + workspace model | **Missing** | No FS/project abstraction exists |
| Multi-tab Monaco editor | **Missing** | Monaco dep present, only used in diff viewer |
| PTY terminal | **Missing** | xterm dep present, page is C2 broadcast shell |
| Git status / diff / commit UI | **Missing** | No git integration |
| LSP / IntelliSense | **Missing** | No language server infrastructure |
| Build / Run / Debug panel | **Missing** | — |
| Problems / Diagnostics view | **Missing** | — |
| Settings | **Partial** | Setup page exists, needs IDE-oriented settings |

## Model Router (to build)

Simple abstraction selecting models by task type:

| Slot | Example | Selection criteria |
|------|---------|-------------------|
| FAST_MODEL | GPT-4o-mini, local | Low latency, cheap, simple tasks |
| CODE_MODEL | Claude Sonnet, DeepSeek Coder | Code generation, editing |
| REASONING_MODEL | o1, Claude Opus | Complex planning, debugging |
| LONG_CONTEXT_MODEL | Gemini 1.5 | Large file analysis |
| LOCAL_MODEL | Ollama | Privacy, offline, zero cost |

The router must be evolvable without rewriting the agent runtime.

## Context Engine (to build)

- Repository indexing (file list, symbols, dependency graph)
- Relevant-context selection (not full-repo dump)
- Semantic search (embeddings / vector store)
- Context compression and caching
- Incremental updates on file changes

Goal: maximum relevant information with minimum tokens.

## Security Model

- **Least privilege** for every agent and tool
- Sandbox execution (ephemeral container per run, fail-closed)
- Approval gates for destructive operations
- Filesystem boundaries (workspace root enforcement)
- Secret isolation (never in logs or model context)
- Audit trail for all tool calls and file changes

## Conventions

- Branch naming: `feature/LUCY-NNN-short-description`
- Commits: atomic, descriptive messages
- Tests before merge; lint + typecheck pass required
- Documentation updated with every significant change
