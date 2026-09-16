# LucyAI — Master Blueprint

## Product Identity

**LucyAI** is an AI-first IDE, autonomous coding agent, and (future)
multi-agent development system.  It is built on the reusable platform core of
the Lucy project and does **not** inherit, extend, or improve any offensive /
C2 / implant capabilities.

## Guiding Principle

    REUSE  >  ADAPT  >  EXTEND  >  BUILD

Before implementing anything, search the existing codebase, installed
dependencies, open-source libraries, MCP tools, and available CLI/APIs.  Only
build what cannot be obtained any other way.

## Current State (post-audit, v2 branch)

| Layer | Technology | Verdict |
|-------|-----------|---------|
| Backend | Python 3.12, FastAPI, Peewee, SQLite/PostgreSQL, WebSockets, Celery/Redis | **REUSE** (auth, RBAC, audit, config, DB, library registry, WS transport) |
| Frontend | React 18, TypeScript 5.6, Vite 5, TailwindCSS, daisyUI, Zustand, TanStack Query, ReactFlow, Monaco (dep only) | **REUSE** (shell, stores, client, CommandPalette, ReactFlow, streaming) |
| AI / LLM | Ollama-only via urllib, blocking calls, reflect→plan→execute loop, in-memory state | **ADAPT** (loop mechanics → coding agent; replace transport, add providers, persistence, streaming) |
| Library / Registry | ResourceProvider Protocol + singleton registry, ~22 providers | **ADAPT** (→ IDE resource catalog: repos, files, symbols, tools, knowledge) |
| Desktop | Rust egui 0.29, read-only SQLite dashboard | **ISOLATE** — not reusable as IDE shell; evaluate Tauri wrapper later |
| Offensive surface | C2 implant, 48 modules, agent builder, packs/05-arsenal | **RETIRE** — permanently excluded from LucyAI |

## Migration Boundary

### RETIRE — do not port into LucyAI

- `agent/` (C2 implant, multi-transport beacon, stealth controller)
- `agent/modules/` (keylog, credential_dump, injection, lateral, etc.)
- `backend/modules/` (48 offensive modules + descriptors.json)
- `packs/05-arsenal/`
- C2 control-plane APIs: `backend/api/agents.py` (implant registration),
  `backend/api/build.py` (agent builder), c2_profiles, redirectors
- Security-domain engines: threat_intel, poc_library, predictive_alerting,
  auto_recon, finding_engine, credential_manager, defense/*
- Offensive docs: `MASTER_PROMPT.md` (red-team RATS prompt),
  `LUCY_C2_SYSTEM_SUMMARY.txt`, `smoke_arsenal.py`, `test_offensive.py`
- System prompts in `backend/config.py` referencing offensive personas

### REUSE — domain-neutral platform core

- FastAPI factory, typed settings, route organization, DI, middleware
- Auth (JWT access/refresh), RBAC, TOTP, audit trail, crypto (at-rest)
- Peewee + SQLite WAL + PostgreSQL factory, migration runner
- ResourceProvider Protocol + LibraryRegistry
- WebSocket manager (event delivery pattern, heartbeat, buffers)
- Task records, priorities, statuses, retries, orchestration concepts
- React shell (Layout, Sidebar, Navbar), Zustand stores, TanStack Query
- axios client with silent token refresh + tenant header
- CommandPalette, ToastContext, AgentEventToaster
- SSE async-generator streaming (copilot.ts)
- ReactFlow node-graph (ScriptBuilder + script-builder/*)
- CopilotDrawer + ChatPanel scaffolding

### ADAPT — change domain semantics, keep mechanics

- `Agent` → coding worker / session
- `Task` → code / test / review job
- `Module` → typed development tool / plugin
- `Timeline` → coding workflow
- `Resource` → workspace knowledge / artifact
- LLM bridge → async multi-provider inference adapter
- ai_chat_engine reflect→plan→execute → general coding-agent loop
- ws_manager → token/event streaming transport (drop C2 semantics)
- search_engine keyword scorer → code/workspace search foundation

## Architecture Target (phases)

| Phase | Name | Scope |
|-------|------|-------|
| 0 | Foundation | Repo hygiene, CI on v2, shared types, framework-core isolation, CONTRIBUTING |
| 1 | IDE Core | Editor (Monaco), file explorer, tabs, real terminal (xterm+PTY), git UI |
| 2 | Agent Core | Coding-agent contract, tool system, durable run state, sandbox |
| 3 | Autonomous Coding | Planner, execution loop, test/debug/fix loop, review |
| 4 | Model Router | Multi-provider abstraction, streaming, fallback, cost/latency |
| 5 | Context Engine | Repo indexing, symbol search, semantic search, context selection |
| 6 | Multi-Agent | Orchestrator, decomposition, parallel execution, dependency graph |
| 7 | Memory | Project memory, decisions, task history, useful patterns |
| 8 | Self-Improvement | Metrics, failed-task analysis, pattern detection |

## Performance Priorities

1. Speed / low latency
2. Minimal token usage (context selection > full-repo dump)
3. Parallelization where independent
4. Cache aggressively
5. Local execution when pertinent, cloud when pertinent
6. Minimal cost

## Decision Rule

Choose the option maximizing **performance + simplicity + reliability +
reuse + evolvability** while minimizing **complexity + cost + latency +
maintenance**.

## Anti-Patterns

- Do not build microservices where a single process suffices.
- Do not build abstractions without a concrete consumer.
- Do not send the entire repo to the model; select relevant context.
- Do not block the event loop with synchronous calls.
- Do not improve, port, or re-enable any offensive / C2 functionality.
