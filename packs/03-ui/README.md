# Pack 3 — L'Interface (Yeux)

Le centre de contrôle visuel. Dashboard React, chat, builder, terminal — tout ce que l'opérateur voit et touche.

## Contenu

- `frontend/package.json` — Dépendances React + Vite + Tailwind + DaisyUI
- `frontend/vite.config.ts` — Config build
- `frontend/tsconfig.json` — Types TypeScript
- `frontend/tailwind.config.js` — Theme Lucy
- `frontend/index.html` — Entry HTML
- `frontend/postcss.config.js` — PostCSS
- `frontend/src/main.tsx` — Montage React + QueryClient
- `frontend/src/App.tsx` — RouterProvider + OnboardingWizard
- `frontend/src/routes.tsx` — Toutes les routes (lazy loading)
- `frontend/src/api/client.ts` — Axios + intercepteur JWT
- `frontend/src/api/*.ts` — Endpoints API (auth, agents, tasks, modules, credentials, alerts, chat, strategy, tenants, groups, logs, reports)
- `frontend/src/stores/*.ts` — Zustand stores (auth, agent, task, chat, tenant, UI)
- `frontend/src/hooks/*.ts` — Hooks (useAgents, useTasks, useWebSocket)
- `frontend/src/types/*.ts` — Interfaces TypeScript (agent, task, module, chat, strategy, user)
- `frontend/src/lib/*.ts` — Utilitaires (feedTranslator, statusTheme)
- `frontend/src/pages/*.tsx` — 27 pages (Dashboard, Agents, Chat, Builder, Settings, Terminal, Map, Timeline, Strategy, Reports, etc.)
- `frontend/src/components/*.tsx` — Composants layout (Layout, Sidebar, Navbar, OnboardingWizard, ErrorBoundary, etc.)
- `frontend/src/components/ui/*.tsx` — Composants UI (Card, AgentCard, StatusBadge, TaskCard, HeatmapCard, etc.)
- `frontend/src/contexts/*.tsx` — Contextes (ToastContext)
- `frontend/src/styles/*.css` — Styles globaux

## Démarrage rapide

```bash
cd frontend
npm install
npm run dev
```

Build production :
```bash
npm run build
```
