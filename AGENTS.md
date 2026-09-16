# LucyAI — Agent Development Guide

## Coding Agent Contract

Every coding agent (single or multi-agent) must expose these capabilities.
Not all are required immediately; implement only what the current phase needs.

```
plan()          → Produce a structured execution plan from a user request
inspect()       → Read files, symbols, dependencies in the workspace
search()        → Find relevant code / docs / knowledge
understand()    → Build context from inspection + search results
decompose()     → Split a plan into independent / dependent sub-tasks
execute()       → Run the plan: edit files, run commands, call tools
useTool()       → Invoke a registered tool (FS, terminal, git, browser, MCP…)
modify()        → Apply file edits (create, patch, delete)
run()           → Execute shell commands in the sandbox
test()          → Run the project's test suite (scoped or full)
debug()         → Analyze failures: error, stack trace, recent changes
fix()           → Attempt a correction when confidence is sufficient
review()        → Self-review changes before committing
commit()        → Create an atomic git commit with a descriptive message
report()        → Produce a structured result / status update
```

## Tool System

Tools are registered capabilities with strict contracts:

```python
class Tool(Protocol):
    name: str
    description: str
    input_schema: dict          # JSON Schema for parameters
    output_schema: dict         # JSON Schema for results
    scopes: set[str]            # {"read", "write", "network", "process"}
    risk: Literal["low", "medium", "high", "critical"]
    idempotent: bool
    timeout_seconds: int
```

**Priority for tool implementation:**

1. MCP / existing CLI / existing API / existing library
2. Thin wrapper around an existing tool
3. Custom implementation (last resort)

**Built-in tool categories (progressive):**

- Filesystem (read, write, list, search, watch)
- Terminal / Shell (PTY execution, streaming output)
- Git (status, diff, commit, branch, push, pull, log)
- Package manager (install, update, audit)
- Test runner (discover, run, parse results)
- Browser (fetch, search, screenshot)
- MCP (connect, list tools, call tool)
- Database (query, migrate)
- Deployment (build, push, health check)

## Autonomous Loop

```
PLAN → INSPECT → IMPLEMENT → RUN → TEST → ANALYZE → FIX → TEST → REVIEW → COMMIT → REPORT
```

On test failure, the agent **does not stop**.  It:
1. Analyzes: error message, file, stack trace, recent change, context
2. Determines confidence level for a fix
3. If confident: applies fix → re-tests
4. If not confident: reports the issue with analysis

**Loop safeguards (every loop must have):**
- Budget (max tokens / max cost)
- Timeout (wall-clock limit)
- Retry limit (max fix attempts, default 3)
- State tracking (which step, which attempt)
- Logs (every decision recorded)
- Reason for stopping

## Multi-Agent (Phase 6+)

When the base architecture works, the system can delegate to specialized agents:

| Role | Responsibility |
|------|---------------|
| Architect | High-level design decisions |
| Planner | Task decomposition and scheduling |
| Coder | File editing, code generation |
| Researcher | Documentation lookup, API exploration |
| Tester | Test writing and execution |
| Debugger | Failure analysis and fix proposals |
| Reviewer | Code quality, security, style review |
| Documenter | README, API docs, changelogs |

Independent tasks run in parallel; dependent tasks remain sequential.

## Memory (Phase 7+)

Progressively introduce:
- Project memory (repo structure, conventions, patterns)
- Architecture memory (decisions, constraints, trade-offs)
- Task memory (what was tried, what worked, what failed)
- Agent memory (per-session context, tool results)

Start simple (structured JSON / SQLite); add vector search only when needed.

## Cloud vs Local Execution

| Environment | Primary Responsibilities |
|-------------|------------------------|
| **Cloud** | Architecture, backend, orchestration, agent runtime, model routing, context engine, memory, MCP, security, CI/CD, complex problems, long tasks |
| **Local** | Frontend, UI, IDE, editor, terminal, navigation, tabs, panels, chat UI, task UI, settings, UX, targeted fixes |

This split is a guideline, not a hard boundary.  Reassign if one environment
is more efficient for a specific task.

## Handoff Protocol

At every Cloud ↔ Local handoff:
1. Commit and push all changes
2. Update `docs/tasks/TASK_BOARD.md`
3. Document: files modified, tests run, problems found, dependencies
4. Document the next task clearly
5. Never assume the other agent knows what was done — the repo and docs
   are the source of truth
