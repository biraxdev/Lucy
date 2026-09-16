# LucyAI — Execution Directive

## Objective

Transform the Lucy platform into **LucyAI**: an AI-first IDE capable of
understanding projects, planning work, executing code, testing, correcting,
using tools, coordinating agents, and operating with Local + Cloud runtimes.

## Absolute Rules

1. **Audit before coding** — inspect the repo before making changes.
2. **REUSE > ADAPT > EXTEND > BUILD** — never rebuild what exists.
3. **No offensive capabilities** — do not port, improve, or re-enable
   any C2/implant/exploit/evasion functionality.
4. **Performance first** — speed, low latency, minimal tokens, parallelism.
5. **Simple architecture** — no premature abstractions or microservices.
6. **Git is the source of truth** — atomic commits, descriptive messages,
   branch per task, tests before merge.
7. **Documentation stays current** — update docs with every significant change.
8. **Autonomous problem-solving** — inspect, search, determine cause,
   implement, test, fix, retest.  Don't stop at the first failure.
   Don't loop infinitely either (budget + retry limits).
9. **Don't block for reversible technical decisions** — take the optimal
   choice, document it, let the human correct if needed.
10. **Parallelise what can be** — identify independent tasks and run them
    concurrently; keep dependent tasks sequential.

## Execution Order

### Per-Session Cycle

```
AUDIT repo state
→ UPDATE architecture docs if needed
→ CHECK TASK_BOARD for next READY task
→ IMPLEMENT the task
→ TEST (scoped, then full suite before PR)
→ LINT + TYPECHECK
→ COMMIT (atomic, descriptive)
→ PUSH branch
→ UPDATE TASK_BOARD
→ OPEN / UPDATE PR
→ PREPARE next tasks
```

### Cloud Responsibilities

Architecture, backend, orchestration, agent runtime, model routing,
context engine, memory, MCP, security, infrastructure, CI/CD, complex
debugging, optimization, long-running tasks.

### Local Responsibilities

Frontend, UI, IDE, editor, navigation, explorer, tabs, terminal UI,
panels, chat UI, task UI, settings, UX, integration frontend, targeted fixes.

### Handoff Protocol

At every handoff between Cloud and Local:
1. Commit + push
2. Update TASK_BOARD.md
3. Document files modified, tests run, problems found
4. Document the next task with full context
5. The repo is the source of truth — never assume the other agent knows
   what was done.

## Task Contract

Every task file must contain:

```
TASK_ID, TITLE, OWNER, TYPE, PRIORITY, STATUS, BRANCH, FILE_SCOPE,
DEPENDENCIES, OBJECTIVE, CONTEXT, IMPLEMENTATION, ACCEPTANCE_CRITERIA,
TESTS, EXPECTED_OUTPUT, HANDOFF
```

A task must be precise enough that another agent can execute it without
needing the full project history.

## Quality Gate

A task is DONE only when:
- Code compiles / type-checks
- Lint passes
- Tests pass
- Integration verified
- Diff inspected (no accidental changes)
- Documentation updated if needed
- Commit created on feature branch
- Task Board updated

## Performance Gate

On every significant feature, verify:
- CPU / memory impact
- Latency
- Number of model calls
- Context size sent to models
- Network calls
- Execution time
- Cache opportunities
- Parallelisation opportunities

Optimise critical paths.  Don't optimise insignificant details prematurely.
