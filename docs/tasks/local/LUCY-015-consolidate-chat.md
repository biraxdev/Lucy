# LUCY-015 — Consolidate 4 Chat UIs into One Assistant Panel

## Contract

| Field | Value |
|-------|-------|
| TASK_ID | LUCY-015 |
| TITLE | Consolidate chat UIs into a single assistant panel |
| OWNER | Local |
| TYPE | Frontend / UX |
| PRIORITY | P1 |
| STATUS | BACKLOG |
| BRANCH | feature/LUCY-015-consolidate-chat |
| FILE_SCOPE | `frontend/src/pages/`, `frontend/src/components/copilot/`, `frontend/src/api/`, `frontend/src/stores/` |
| DEPENDENCIES | None |

## Objective

Merge the 4 separate chat implementations into one unified AI assistant
panel, derived from the strongest foundation (CopilotDrawer/ChatPanel).

## Context

There are currently 4 divergent chat UIs:
1. `Chat.tsx` + `api/chat.ts` ("Shannon" persona)
2. `AIChat.tsx` + `api/ai_chat.ts`
3. `AIAgent.tsx` + `api/ai_agent.ts`
4. `CopilotDrawer.tsx` + `ChatPanel.tsx` + `api/copilot.ts`

Each has its own message types, API modules, and state management.
CopilotDrawer/ChatPanel is the most complete (tabs, context awareness,
SSE streaming, markdown rendering).

## Implementation

1. Define a single `api/assistant.ts` module combining the best of
   chat, ai_chat, ai_agent, and copilot APIs.
2. Merge chatStore + copilotStore into a single `assistantStore.ts`.
3. Evolve CopilotDrawer/ChatPanel into the single assistant panel.
4. Remove Chat.tsx, AIChat.tsx, AIAgent.tsx and their dedicated API modules.
5. Update routes.tsx to remove duplicate chat routes.
6. Clean up dead French/English quick-action strings.

## Acceptance Criteria

- [ ] Single chat/assistant panel accessible from sidebar + Copilot FAB
- [ ] SSE streaming works
- [ ] Markdown + syntax highlighting renders
- [ ] No duplicate chat pages remain
- [ ] `npm run build` passes

## Tests

- Frontend build passes
- Manual: open assistant → send message → see streamed response

## Expected Output

One clean, unified assistant panel replacing 4 fragmented implementations.

## Handoff

Independent task — can start immediately.  Cleans the UI surface before
IDE features are layered on top.
