# LUCY-013 — Terminal UI Page (Replace C2 Broadcast Shell)

## Contract

| Field | Value |
|-------|-------|
| TASK_ID | LUCY-013 |
| TITLE | Terminal UI with xterm connected to PTY backend |
| OWNER | Local |
| TYPE | Frontend / IDE |
| PRIORITY | P1 |
| STATUS | BACKLOG |
| BRANCH | feature/LUCY-013-terminal-ui |
| FILE_SCOPE | `frontend/src/pages/Terminal.tsx`, `frontend/src/components/terminal/` |
| DEPENDENCIES | LUCY-012 (PTY backend) |

## Objective

Replace the existing C2 broadcast-shell Terminal page with a real
interactive terminal connected to the PTY backend via WebSocket.

## Context

- `@xterm/xterm` and `@xterm/addon-fit` are already in package.json
  but are **not used** anywhere in the codebase.
- `frontend/src/pages/Terminal.tsx` is currently a C2 command dispatch form.
- Cloud will provide a PTY backend (LUCY-012) with a WebSocket endpoint.

## Implementation

1. Create `frontend/src/components/terminal/TerminalPanel.tsx`:
   - Initialize xterm Terminal instance
   - Connect @xterm/addon-fit for auto-resize
   - Connect to PTY WebSocket endpoint
   - Handle input → WS send, WS receive → terminal.write()
2. Replace `frontend/src/pages/Terminal.tsx`:
   - Render TerminalPanel
   - Support multiple terminal tabs (later)
3. Add proper theme integration (use Lucy dark theme colors).

## Acceptance Criteria

- [ ] Interactive shell session in the browser
- [ ] Auto-resize on window/panel resize
- [ ] Copy/paste works
- [ ] `npm run build` passes

## Tests

- Frontend build passes
- Manual: type commands → see output → resize → still works

## Expected Output

A working terminal page at `/terminal` with real PTY interaction.

## Handoff

Cloud delivers the PTY WebSocket backend (LUCY-012) first.
Local builds the UI on top.
