# LUCY-011 — Multi-Tab Monaco Editor Integration

## Contract

| Field | Value |
|-------|-------|
| TASK_ID | LUCY-011 |
| TITLE | Multi-tab Monaco editor with file open/save |
| OWNER | Local |
| TYPE | Frontend / IDE |
| PRIORITY | P1 |
| STATUS | BACKLOG |
| BRANCH | feature/LUCY-011-monaco-editor |
| FILE_SCOPE | `frontend/src/pages/Editor.tsx`, `frontend/src/components/editor/`, `frontend/src/stores/editorStore.ts` |
| DEPENDENCIES | LUCY-010 (workspace/file API) |

## Objective

Replace the read-only Monaco diff viewer with a full multi-tab code editor
that can open, edit, and save files from the workspace.

## Context

- `@monaco-editor/react` is already installed (frontend/package.json).
- Currently used only in `frontend/src/components/library/VersionHistory.tsx`
  for read-only diffs.
- No file explorer or workspace concept exists yet (LUCY-010 dependency).
- The normalized Zustand store pattern (agentStore) can be reused for
  editor buffers/tabs.

## Implementation

1. Create `frontend/src/stores/editorStore.ts` (Zustand):
   - `tabs: Tab[]` (id, filePath, language, content, dirty, cursorPosition)
   - `activeTabId: string | null`
   - Actions: openFile, closeTab, setActiveTab, updateContent, saveFile
2. Create `frontend/src/components/editor/EditorTabs.tsx`:
   - Tab bar with close buttons, dirty indicators, drag-to-reorder
3. Create `frontend/src/components/editor/CodeEditor.tsx`:
   - Wrap `@monaco-editor/react` with language detection, theme, keybindings
   - Wire onChange to editorStore.updateContent
   - Wire Ctrl+S to editorStore.saveFile (calls workspace API)
4. Create `frontend/src/pages/Editor.tsx`:
   - Layout: EditorTabs + CodeEditor (split panes later)
5. Add route `/editor` in routes.tsx.
6. Wire file explorer double-click to editorStore.openFile (when LUCY-010 lands).

## Acceptance Criteria

- [ ] Can open multiple files in tabs
- [ ] Syntax highlighting for common languages (TS, Python, Rust, JSON, MD)
- [ ] Dirty indicator on unsaved tabs
- [ ] Ctrl+S saves to workspace API
- [ ] Close tab with confirmation if dirty
- [ ] `npm run build` passes

## Tests

- Frontend build passes (`tsc && vite build`)
- Manual: open file → edit → save → reload → content persisted

## Expected Output

A working multi-tab code editor page at `/editor`.

## Handoff

Cloud provides the workspace/file API (LUCY-010).  Local builds the editor
UI on top of it.  After LUCY-011, work on LUCY-014 (git UI) and LUCY-016
(command palette file commands) can begin.
