# Pack 4 — Les Extensions (Muscles)

Modules secondaires groupés par thématique. Activables/désactivables via `ENABLED_EXTENSIONS` dans `.env`.

## Sous-Packs

### 4a — Gestion (RBAC / Multi-tenant)
- `backend/api/rbac.py` — Rôles & permissions
- `backend/api/operators.py` — Gestion opérateurs
- `backend/api/tenants.py` — Isolation multi-client
- `frontend/pages/RBAC.tsx` — UI gestion rôles
- `frontend/pages/Tenants.tsx` — UI tenants

### 4b — Analyse (Rapports / Findings)
- `backend/api/reports.py` — Génération rapports PDF
- `backend/api/findings.py` — Findings découvertes
- `backend/api/audit.py` — Audit logs
- `frontend/pages/Reports.tsx` — Visualisation rapports
- `frontend/pages/Findings.tsx` — Findings dashboard

### 4c — Stratégie (MITRE / Playbooks / Timelines)
- `backend/api/strategy.py` — TTPs MITRE, campagnes, playbooks
- `backend/api/timelines.py` — Scénarios séquentiels
- `backend/core/orchestrator.py` — Moteur d'exécution timeline
- `frontend/pages/Strategy.tsx` — MITRE mapping visuel
- `frontend/pages/TimelineBuilder.tsx` — Builder drag-drop
- `frontend/pages/Mission.tsx` — Vue mission
- `frontend/pages/GanttView.tsx` — Vue Gantt

### 4d — Réseau (C2 / Redirectors / Transports)
- `backend/api/c2_profiles.py` — Profiles malleables
- `backend/api/redirectors.py` — Redirecteurs fronting
- `backend/core/auto_recon.py` — Recon auto à la connexion
- `backend/core/screenshot_scheduler.py` — Screenshots périodiques
- `frontend/pages/C2Profiles.tsx` — UI profiles
- `frontend/pages/MapPage.tsx` — Carte agents

## Activation

Dans `.env` :
```env
ENABLED_EXTENSIONS=rbac,operators,tenants,reports,findings,strategy,timelines,c2_profiles,redirectors
```
