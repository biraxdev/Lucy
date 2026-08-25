# Pack 1 — Le Socle (Cerveau)

La station spatiale. Reçoit les données, les stocke, les affiche. C'est le moteur FastAPI qui tourne sur ton serveur.

## Contenu

- `backend/main.py` — Point d'entrée FastAPI (lifespan, routers, middleware, CORS, JWT)
- `backend/config.py` — Settings Pydantic (env vars, JWT secrets, DB, flags)
- `backend/middleware.py` — CORS, JWT Auth, RequestLogging
- `backend/dependencies.py` — FastAPI dependency injection (OperatorUser, get_db)
- `backend/database.py` — SQLite init + Peewee connection
- `backend/core/crypto.py` — ECDH + AES-256-GCM + HKDF
- `backend/core/ws_manager.py` — ConnectionManager singleton + heartbeat + queue
- `backend/core/module_manager.py` — Plugin registry + HMAC signing
- `backend/core/auth.py` — JWT création/vérification + bcrypt
- `backend/core/task_queue.py` — Dispatch + priority queue
- `backend/core/orchestrator.py` — Timeline execution engine
- `backend/core/group_manager.py` — Groupes statiques/dynamiques d'agents
- `backend/core/log_manager.py` — Logging centralisé batched
- `backend/core/heartbeat_buffer.py` — Buffer heartbeat agents
- `backend/core/result_buffer.py` — Buffer résultats agents
- `backend/core/chat_buffer.py` — Buffer messages chat
- `backend/core/celery_app.py` — Celery factory (optionnel)
- `backend/db/models.py` — Toutes les tables Peewee (Agent, Task, Module, Credential, etc.)
- `backend/db/migrations/001_initial.py` — Auto-migration startup
- `backend/api/` — REST + WebSocket endpoints (health, auth, ws, agents, tasks, modules, build, setup, groups, credentials, logs, files, monitor, chat, alerts, dashboard)
- `backend/modules/` — Modules serveur-side (shell, screenshot, keylog, browser, file_manager, wifi, webcam, process, persistence, geoip)

## Démarrage rapide

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

En mode portable, le backend sert aussi le frontend buildé depuis `../frontend/dist`.
