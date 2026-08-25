# Project Lucy — Remote Agent Testing System (RATS)
## Architecture & Structure Documentation

---

## Table of Contents

1. [Overview](#1-overview)
2. [Tech Stack](#2-tech-stack)
3. [Directory Structure](#3-directory-structure)
4. [Entity-Relationship Diagrams](#4-entity-relationship-diagrams)
5. [Backend Modules](#5-backend-modules)
6. [Agent (Implant) Modules](#6-agent-implant-modules)
7. [Frontend Modules](#7-frontend-modules)
8. [Communication Architecture](#8-communication-architecture)
9. [Security Architecture](#9-security-architecture)
10. [Build & Deployment](#10-build--deployment)

---

## 1. Overview

**Lucy** is a modular Remote Agent Testing System (RATS) designed for authorized Red Team simulations. It provides:

- A centralized **C2 backend** (Command & Control) built on FastAPI
- A real-time **operator dashboard** (React/TypeScript)
- A **lightweight implant agent** (standalone Python, no external deps)
- An **encrypted plugin system** for dynamic capability extension
- A **task orchestration engine** with timelines and group targeting

> All activity is intended for authorized penetration testing and Red Team simulations only.

---

## 2. Tech Stack

| Layer      | Technology                                                      |
|------------|-----------------------------------------------------------------|
| Backend    | Python 3.12, FastAPI, Uvicorn, WebSockets, SQLite, Peewee ORM  |
| Frontend   | React 18, TypeScript, Vite, TailwindCSS, DaisyUI, Zustand      |
| Agent      | Python 3.x (stdlib only), fallback C via ctypes                |
| Queue      | Celery + Redis                                                  |
| Auth       | JWT (python-jose), bcrypt (passlib), API Key rotation          |
| Crypto     | AES-256-GCM, ECDH (P-256), HKDF, HMAC-SHA256                  |
| Build      | Docker Compose (backend + frontend), PyInstaller (agent)       |
| Extras     | Socket.IO, TanStack Query v5, Recharts, Leaflet, Monaco Editor |

---

## 3. Directory Structure

```
lucy/
│
├── backend/                        # FastAPI C2 server
│   ├── main.py                     # Application entry point (lifespan handler)
│   ├── config.py                   # Settings (env vars, JWT secrets, etc.)
│   ├── dependencies.py             # FastAPI dependency injection
│   ├── middleware.py               # CORS, Auth, Request logging
│   ├── requirements.txt
│   │
│   ├── core/                       # Business logic & services
│   │   ├── auth.py                 # JWT creation/verification, API key management
│   │   ├── crypto.py               # ECDH, AES-256-GCM, HKDF, HMAC
│   │   ├── ws_manager.py           # WebSocket connection manager (singleton)
│   │   ├── module_manager.py       # Plugin registry, HMAC verification
│   │   ├── task_queue.py           # Task dispatch, priority queue logic
│   │   ├── celery_app.py           # Celery application factory
│   │   ├── orchestrator.py         # Timeline execution engine
│   │   ├── group_manager.py        # Static/dynamic agent group resolution
│   │   ├── log_manager.py          # Centralized logging (singleton, batched)
│   │   ├── log_rotation.py         # Log archiving, gz compression
│   │   └── credential_manager.py   # Credential dedup, encryption, scoring
│   │
│   ├── db/                         # Data layer
│   │   ├── models.py               # Peewee ORM models (all tables)
│   │   └── migrations/
│   │       └── 001_initial.py      # Auto-migration on startup
│   │
│   ├── api/                        # REST + WebSocket endpoints
│   │   ├── auth.py                 # /api/v1/auth/*
│   │   ├── agents.py               # /api/v1/agents/*
│   │   ├── tasks.py                # /api/v1/tasks/*
│   │   ├── modules.py              # /api/v1/modules/*
│   │   ├── timelines.py            # /api/v1/timelines/*
│   │   ├── groups.py               # /api/v1/groups/*
│   │   ├── credentials.py          # /api/v1/credentials/*
│   │   ├── logs.py                 # /api/v1/logs/*
│   │   ├── build.py                # /api/v1/build/* (Agent Builder)
│   │   └── ws.py                   # WebSocket endpoint (/ws)
│   │
│   ├── modules/                    # Server-side module definitions
│   │   ├── screenshot.py
│   │   ├── keylog.py
│   │   ├── file_manager.py
│   │   ├── shell.py
│   │   ├── process.py
│   │   ├── wifi.py
│   │   ├── browser.py
│   │   ├── persistence.py
│   │   ├── geoip.py
│   │   └── webcam.py
│   │
│   ├── tasks/                      # Celery task definitions
│   │   ├── agent_task.py
│   │   ├── broadcast_task.py
│   │   ├── timeline_task.py
│   │   ├── cleanup_task.py
│   │   └── health_check.py
│   │
│   └── celery_worker.py            # Celery worker entry point
│
├── frontend/                       # React operator dashboard
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   │
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── routes.tsx
│       │
│       ├── api/
│       │   ├── client.ts           # Axios instance + JWT interceptors
│       │   ├── auth.ts             # login, refresh, me
│       │   ├── agents.ts           # agent CRUD
│       │   ├── tasks.ts            # task + timeline API calls
│       │   └── modules.ts          # module store API
│       │
│       ├── stores/
│       │   ├── authStore.ts        # User session (Zustand)
│       │   ├── agentStore.ts       # Agent list + selected agent
│       │   ├── taskStore.ts        # Active task queue
│       │   └── uiStore.ts          # Sidebar, theme, modals
│       │
│       ├── pages/
│       │   ├── Login.tsx
│       │   ├── Dashboard.tsx
│       │   ├── Agents.tsx
│       │   ├── AgentDetail.tsx
│       │   ├── ModuleStore.tsx
│       │   ├── TimelineBuilder.tsx
│       │   ├── AgentBuilder.tsx    # Noob-friendly agent compiler
│       │   └── Settings.tsx
│       │
│       ├── components/
│       │   ├── Layout.tsx
│       │   ├── Sidebar.tsx
│       │   ├── Navbar.tsx
│       │   ├── AgentCard.tsx
│       │   ├── AgentTable.tsx
│       │   ├── TaskTimeline.tsx
│       │   ├── TaskQueue.tsx
│       │   ├── LogViewer.tsx
│       │   ├── Terminal.tsx
│       │   ├── TerminalTabs.tsx
│       │   ├── BroadcastSelector.tsx
│       │   ├── MapView.tsx
│       │   ├── CodeEditor.tsx
│       │   ├── FileExplorer.tsx
│       │   ├── DataTable.tsx
│       │   ├── LogFeed.tsx
│       │   ├── ModuleCard.tsx
│       │   ├── ModuleDetail.tsx
│       │   ├── UploadForm.tsx
│       │   ├── BlockNode.tsx
│       │   ├── ConnectionLine.tsx
│       │   ├── ParamModal.tsx
│       │   ├── TimelinePreview.tsx
│       │   └── AgentSelector.tsx
│       │
│       ├── hooks/
│       │   ├── useWebSocket.ts
│       │   ├── useAgents.ts
│       │   └── useTasks.ts
│       │
│       ├── types/
│       │   ├── agent.ts
│       │   ├── task.ts
│       │   ├── module.ts
│       │   └── user.ts
│       │
│       └── styles/
│           └── globals.css
│
├── agent/                          # Standalone implant
│   ├── main.py                     # PyInstaller entry point
│   ├── agent.py                    # Main agent loop
│   ├── config.py                   # Baked build-time configuration (optional)
│   │
│   ├── core/
│   │   ├── crypto.py               # ECDH + AES-GCM (mirrors backend/core/crypto.py)
│   │   ├── loader.py               # Dynamic module loader (exec-based)
│   │   ├── pty_handler.py          # PTY abstraction (Windows/Linux/macOS)
│   │   ├── stealth.py              # Anti-sandbox / anti-analysis checks
│   │   └── offline_queue.py        # Buffer tasks when disconnected
│   │
│   ├── modules/
│   │   ├── builtin.py              # Built-in: shell, file, info
│   │   ├── keylog.py               # Keylogger (pynput + OS fallbacks)
│   │   ├── screenshot.py           # Screenshot (PIL + ctypes fallbacks)
│   │   ├── shell.py                # Reverse shell with PTY
│   │   └── browser/
│   │       ├── browser.py          # Browser stealer (dispatcher)
│   │       ├── chromium.py         # Chrome/Edge/Brave credential extraction
│   │       └── firefox.py          # Firefox/Thunderbird extraction
│   │
│   ├── payloads/
│   │   └── config_template.ini     # Fallback INI config template
│   │
│   └── build.bat / build.ps1       # One-click Windows build scripts
│
├── docker-compose.yml              # Backend + frontend + Redis + Celery
├── backend/Dockerfile
├── frontend/Dockerfile
├── tools/
│   └── portable/                   # One-click USB launcher
│       ├── start.bat               # Windows one-click open
│       └── start.sh                # Linux/macOS one-click open
├── Makefile
└── README.md
```

---

## 4. Entity-Relationship Diagrams

### 4.1 — Core ERD (All Tables)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              AGENT                                       │
├──────────────────┬──────────────────────────────────────────────────────┤
│ id               │ UUID PK                                               │
│ hostname         │ VARCHAR                                               │
│ os               │ VARCHAR (windows/linux/darwin)                        │
│ username         │ VARCHAR                                               │
│ ip_public        │ VARCHAR                                               │
│ ip_private       │ VARCHAR                                               │
│ architecture     │ VARCHAR (x86_64/arm64)                                │
│ processor        │ VARCHAR                                               │
│ ram_total        │ INTEGER (bytes)                                       │
│ ram_available    │ INTEGER (bytes)                                       │
│ first_seen       │ DATETIME                                              │
│ last_seen        │ DATETIME                                              │
│ status           │ ENUM (online/idle/offline/compromised)                │
│ public_key       │ TEXT (PEM — ECDH P-256)                               │
│ aes_key          │ TEXT (encrypted — stored AES-256-GCM)                 │
│ group_id         │ FK → AgentGroup.id (nullable)                         │
│ tags             │ JSON []                                               │
└──────────────────┴──────────────────────────────────────────────────────┘
         │                    │                       │
         │ 1:N                │ 1:N                   │ 1:N
         ▼                    ▼                       ▼
┌────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│     TASK       │  │   CREDENTIAL     │  │     FILE_EVENT       │
├────────────────┤  ├──────────────────┤  ├──────────────────────┤
│ id  UUID PK    │  │ id  UUID PK      │  │ id  UUID PK          │
│ agent_id FK    │  │ agent_id FK      │  │ agent_id FK          │
│ module VARCHAR │  │ url VARCHAR      │  │ path TEXT            │
│ action VARCHAR │  │ hostname VARCHAR │  │ action ENUM          │
│ params JSON    │  │ username VARCHAR │  │   (upload/download/  │
│ status ENUM    │  │ password TEXT    │  │    delete/modify)    │
│  (queued/      │  │   (AES encrypted)│  │ size INTEGER         │
│   running/     │  │ source ENUM      │  │ hash VARCHAR SHA256  │
│   completed/   │  │   (browser/wifi/ │  │ timestamp DATETIME   │
│   failed)      │  │    ssh/rdp)      │  └──────────────────────┘
│ result JSON    │  │ confidence ENUM  │
│ error TEXT     │  │   (high/med/low) │
│ created_at     │  │ tags JSON []     │
│ executed_at    │  │ captured_at      │
└────────────────┘  │ version INTEGER  │
                    └──────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                              MODULE                                      │
├──────────────────┬──────────────────────────────────────────────────────┤
│ id               │ UUID PK                                               │
│ name             │ VARCHAR (unique)                                      │
│ version          │ VARCHAR (semver)                                      │
│ description      │ TEXT                                                  │
│ author           │ VARCHAR                                               │
│ code             │ TEXT (Python source, downloaded by agent)             │
│ dependencies     │ JSON [] (pip packages with versions)                  │
│ os_compat        │ JSON [] (windows/linux/darwin)                        │
│ signature        │ VARCHAR (HMAC-SHA256 of code)                         │
│ enabled          │ BOOLEAN                                               │
└──────────────────┴──────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                                LOG                                       │
├──────────────────┬──────────────────────────────────────────────────────┤
│ id               │ UUID PK                                               │
│ agent_id         │ FK → Agent.id (nullable — system logs)                │
│ level            │ ENUM (DEBUG/INFO/WARN/ERROR/CRITICAL)                 │
│ module           │ VARCHAR (source module/component)                     │
│ message          │ TEXT                                                  │
│ timestamp        │ DATETIME                                              │
└──────────────────┴──────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                              USER                                        │
├──────────────────┬──────────────────────────────────────────────────────┤
│ id               │ UUID PK                                               │
│ username         │ VARCHAR (unique)                                      │
│ password_hash    │ VARCHAR (bcrypt)                                      │
│ role             │ ENUM (superadmin/admin/operator/viewer)               │
│ tenant_id        │ FK → Tenant.id (nullable, superadmin = null)         │
│ api_key          │ VARCHAR (rotatable)                                   │
│ totp_secret      │ VARCHAR (nullable)                                    │
│ totp_enabled     │ BOOLEAN (default false)                               │
│ last_login       │ DATETIME                                              │
│ created_at       │ DATETIME                                              │
└──────────────────┴──────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           TENANT                                         │
├──────────────────┬──────────────────────────────────────────────────────┤
│ id               │ UUID PK                                               │
│ name             │ VARCHAR (unique)                                      │
│ slug             │ VARCHAR (unique)                                      │
│ description      │ TEXT                                                  │
│ color            │ VARCHAR (default accent)                              │
│ active           │ BOOLEAN (default true)                                │
│ created_at       │ DATETIME                                              │
└──────────────────┴──────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           AGENT_GROUP                                    │
├──────────────────┬──────────────────────────────────────────────────────┤
│ id               │ UUID PK                                               │
│ name             │ VARCHAR                                               │
│ description      │ TEXT                                                  │
│ type             │ ENUM (static/dynamic)                                 │
│ dynamic_query    │ TEXT (SQL-like filter e.g. os='windows')              │
│ tenant_id        │ FK → Tenant.id                                        │
│ tags             │ JSON []                                               │
└──────────────────┴──────────────────────────────────────────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            TIMELINE                                      │
├──────────────────┬──────────────────────────────────────────────────────┤
│ id               │ UUID PK                                               │
│ name             │ VARCHAR                                               │
│ description      │ TEXT                                                  │
│ tenant_id        │ FK → Tenant.id                                        │
│ agent_group      │ JSON [] (group IDs or ["all"])                          │
│ steps            │ JSON [] (ordered TaskStep objects)                      │
│ trigger          │ ENUM (manual/on_connect/schedule)                     │
│ cron_expr        │ VARCHAR (nullable — cron string)                        │
│ loop             │ INTEGER (0=disabled, N=seconds interval)                │
│ status           │ ENUM (draft/active/completed/failed)                  │
│ created_by       │ FK → User.id (nullable)                               │
│ created_at       │ DATETIME                                              │
│ updated_at       │ DATETIME                                              │
└──────────────────┴──────────────────────────────────────────────────────┘
```

### 4.2 — Timeline Step Schema (JSON embedded)

```json
{
  "order": 1,
  "module": "info",
  "action": "run",
  "params": {},
  "delay": 0,
  "timeout": 60,
  "retry": 3,
  "on_failure": "continue | abort | skip"
}
```

### 4.3 — WebSocket Message Schema

```json
{
  "type": "heartbeat | task | result | log | module_request | error | stdin | stdout | resize",
  "agent_id": "uuid",
  "task_id": "uuid (optional)",
  "payload": {},
  "timestamp": "2024-01-01T00:00:00Z",
  "signature": "hmac-sha256-hex"
}
```

---

## 5. Backend Modules

### 5.1 — `backend/core/auth.py`
**Role:** JWT lifecycle management and API key validation.

- `create_access_token(user_id, role, scope)` — 30-minute JWT
- `create_refresh_token(user_id)` — 7-day JWT, stored in DB
- `verify_token(token)` — decode + validate claims
- `rotate_api_key(user_id)` — generates new 32-byte hex key, invalidates old
- `hash_password(plain)` / `verify_password(plain, hashed)` — bcrypt via passlib

---

### 5.2 — `backend/core/crypto.py`
**Role:** Cryptographic primitives shared by backend and agent.

| Function | Description |
|---|---|
| `generate_keypair()` | ECDH P-256 keypair → `(private_pem, public_pem)` |
| `derive_shared_secret(priv, pub)` | ECDH → raw 32-byte secret |
| `derive_aes_key(secret, salt)` | HKDF-SHA256 → 32-byte AES key |
| `encrypt(plaintext, aes_key)` | AES-256-GCM → `base64(nonce + cipher + tag)` |
| `decrypt(cipher_b64, aes_key)` | AES-256-GCM → plaintext bytes |
| `sign_message(payload, hmac_key)` | HMAC-SHA256 → hex string |
| `verify_signature(payload, sig, hmac_key)` | Constant-time compare |

> **Note:** `agent/core/crypto.py` mirrors this exactly using stdlib `cryptography` or `pycryptodome`.

---

### 5.3 — `backend/core/ws_manager.py`
**Role:** Central WebSocket broker managing all agent and frontend connections.

- `ConnectionManager` (singleton) — `{agent_id: AgentConnection}` registry
- `AgentConnection` — wraps WebSocket, tracks heartbeat timeout (30s), queues offline tasks
- `MessageRouter` — dispatches messages by `type` to registered handlers
- `broadcast(group_id, message)` — fan-out to all agents in a group
- `flush_offline_queue(agent_id)` — sends buffered tasks on reconnect

---

### 5.4 — `backend/core/module_manager.py`
**Role:** Plugin registry for uploadable/downloadable agent modules.

- `register_module(code, metadata)` — validates, signs with HMAC, stores
- `get_module(id)` — retrieves by ID with signature
- `verify_module_signature(code, signature)` — HMAC-SHA256 check
- `list_modules(filters)` — paginated listing with OS compat filter
- Module code is stored as plaintext in DB; signature prevents tampering during agent download

---

### 5.5 — `backend/core/orchestrator.py`
**Role:** Timeline execution engine — sequences task steps across agents.

- `execute_timeline(timeline_id, agent_ids)` — dispatches steps in order with delays
- `resolve_trigger(timeline)` — evaluates `on_connect`, `schedule`, `manual`
- Priority queue integration: each step pushed as a Celery task with priority mapping
- On each agent heartbeat: checks for active timelines targeting that agent's groups

---

### 5.6 — `backend/core/group_manager.py`
**Role:** Resolves which agents belong to a group at query time.

- `resolve_group(group_id)` → `[agent_id, ...]`
- **Static groups:** explicit membership table
- **Dynamic groups:** evaluates `dynamic_query` (SQL WHERE fragment) against Agent table
- Re-evaluated on: agent connect, heartbeat, timeline trigger

---

### 5.7 — `backend/core/task_queue.py`
**Role:** Task dispatch with priority levels and retry logic.

Priority levels:

| Level    | Delay  | Use Case                        |
|----------|--------|---------------------------------|
| CRITICAL | 0s     | Active shell session input      |
| HIGH     | 5s     | Screenshot, keylog flush        |
| NORMAL   | 30s    | Recon tasks, file ops           |
| LOW      | 120s   | Cleanup, passive scan           |

- Retry: max 3 attempts, backoff `[1, 3, 9]` minutes (exponential)
- Timeout: 60s default per task (configurable per module)

---

### 5.8 — `backend/core/log_manager.py`
**Role:** Centralized logging with in-memory buffering and batch writes.

- Singleton pattern with `asyncio.Queue` buffer
- Flush trigger: every 5 seconds OR 100 buffered entries (whichever first)
- Log types: `system`, `agent`, `task`, `module`, `security`
- `log_rotation.py` archives entries > 7 days to `.json.gz` files

---

### 5.9 — `backend/core/credential_manager.py`
**Role:** Credential ingestion, deduplication, and encrypted storage.

- `bulk_ingest(credentials, agent_id)` — validates, deduplicates by `SHA256(url+username)`
- **Versioning:** if password changed for existing hash → creates new version entry
- **Confidence scoring:** `high` (direct read), `medium` (parsed), `low` (regex)
- **Weak pattern detection:** flags credentials matching known weak patterns
- Passwords stored as `AES-256-GCM(password, master_key)`

---

### 5.10 — `backend/api/build.py` — Agent Builder

**Role:** Noob-friendly compilation endpoint for the standalone agent.

Flow:
1. Accept build request with target, modules, and 15+ packaging options.
2. Optional gate: if `BUILD_AUTH_TOKEN` is set, the UI must provide the exact token.
3. Every build is logged to `data/build_audit.log` with operator ID, options, and timestamp.
4. Generate `agent/config.py` with all values baked in plus watermark metadata (`build_id`, `operator_id`, `expires_at`).
5. **Windows:** package `agent/` sources + `build.bat`/`build.ps1` into a ZIP (PyInstaller must run on a Windows host).
6. **Linux/macOS:** run PyInstaller inside the container and emit the binary directly.
7. Background task updates `BUILDS[build_id]` with `queued → building → done/error`.
8. Frontend polls `/api/v1/build/{id}` and shows download button when ready.

Packaging options (frontend toggles):
- Hide console window, startup delay, single execution, self-destruct
- VM/debugger/sandbox checks, beacon jitter, max reconnections
- Registry Run key persistence, UAC bypass attempt
- TTL (agent stops working after N days), custom output name
- Obfuscate bytecode, anti-analysis, persistence

Frontend packs (one-click presets): Basic Recon, Full Featured, Stealth, Data Exfil, Recon Pro, Persistence, Cleanup, PrivEsc, Anti-Analysis, Full Red Team.

### 5.11 — API Endpoints Summary

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/health` | None | Health check |
| POST | `/api/v1/auth/login` | None | Login → JWT pair |
| POST | `/api/v1/auth/refresh` | Refresh | New access token |
| GET | `/api/v1/auth/me` | Bearer | Current user |
| GET/POST | `/api/v1/agents` | Bearer | List / register agent |
| GET/PATCH/DELETE | `/api/v1/agents/{id}` | Bearer | Agent CRUD |
| GET/POST | `/api/v1/tasks` | Bearer | List / create task |
| GET | `/api/v1/tasks/queue` | Bearer | Current queue state |
| DELETE | `/api/v1/tasks/{id}` | Bearer | Cancel queued task |
| GET/POST | `/api/v1/modules` | Bearer | List / upload module |
| GET | `/api/v1/modules/{id}/download` | Bearer | Signed module code |
| DELETE | `/api/v1/modules/{id}` | Admin | Remove module |
| GET/POST | `/api/v1/timelines` | Bearer | List / create timeline |
| POST | `/api/v1/timelines/{id}/execute` | Bearer | Run now |
| GET/POST | `/api/v1/groups` | Bearer | List / create group |
| GET | `/api/v1/groups/{id}/agents` | Bearer | Agents in group |
| POST | `/api/v1/credentials/bulk` | Agent | Batch credential insert |
| GET | `/api/v1/credentials` | Bearer | List credentials |
| GET | `/api/v1/credentials/export` | Admin | CSV/JSON export |
| GET | `/api/v1/logs` | Bearer | Paginated logs |
| GET | `/api/v1/logs/stream` | Bearer | SSE real-time stream |
| WS | `/ws?token=xxx` | JWT | Main agent/frontend WS |

---

## 6. Agent (Implant) Modules

### 6.1 — `agent/agent.py` — Main Loop

```
STARTUP
  ├── Parse config (.ini or hardcoded)
  ├── Anti-sandbox checks (RAM < 2GB, screen < 1024x768, debugger detect)
  ├── Collect system info (hostname, OS, username, IP, RAM, processes)
  └── ECDH handshake → derive AES session key

LOOP (every 15-30s jitter)
  ├── Send heartbeat {agent_id, cpu, ram, status}
  ├── Receive pending tasks from server
  └── For each task:
        ├── Load module (cache or download)
        ├── Execute in thread (60s timeout)
        └── Send result {task_id, status, data}
```

---

### 6.2 — `agent/core/crypto.py`
Mirrors `backend/core/crypto.py` exactly. Uses only stdlib-compatible imports (`cryptography` or `pycryptodome`). No disk writes. Key stored in process memory only.

---

### 6.3 — `agent/core/loader.py`
**Dynamic module loader:**

```python
module_cache: dict[str, ModuleNamespace] = {}

def load_module(name: str, code: str, version: str) -> ModuleNamespace:
    # exec(compile(code, '<module>', 'exec'), restricted_namespace)
    # cache by (name, version)
    # invalidate if version mismatch
```

- Restricted builtins: blocks `__import__`, `open`, `exec` in module scope (optional sandboxing)
- Each module runs in isolated namespace, communicates via return value only

---

### 6.4 — Built-in Modules (`agent/modules/builtin.py`)

| Module | Action | Description |
|--------|--------|-------------|
| `shell` | `exec` | `os.popen(cmd)` — stdout/stderr capture |
| `file` | `read/write/list/upload/download` | Filesystem operations |
| `info` | `run` | Full system info: CPU, RAM, disk, processes, installed software |

---

### 6.5 — `agent/modules/keylog.py`

- **Modes:** `live` (real-time WS), `buffer` (batch every N seconds), `on_demand`
- **Backend hierarchy:** pynput → Windows `ctypes GetAsyncKeyState` → Linux `/dev/input` → macOS `CGEvent`
- **Circular buffer** in memory (configurable size, default 5000 events)
- **Window tracking:** tags each keystroke with active window title
- Safe mode: avoids capturing from known password input contexts

---

### 6.6 — `agent/modules/screenshot.py`

- **Modes:** `single`, `interval` (stream), `region`, `active_window`
- **Capture hierarchy:** PIL.ImageGrab → `xwd` (X11) → `screencapture` (macOS) → `ctypes BitBlt` (Windows)
- **Progressive delivery:** thumbnail (320×240) first, then full resolution
- **Streaming:** WebSocket binary frames with 8-byte header (`timestamp[4] + frame_number[4]`)

---

### 6.7 — `agent/modules/shell.py` + `agent/core/pty_handler.py`

- **Windows:** Named pipe + `cmd.exe` / `powershell.exe` with redirected stdio
- **Linux/macOS:** `pty.openpty()` / `os.forkpty()` + `/bin/bash`
- WS frame types: `stdin`, `stdout`, `resize` (rows/cols), `exit`
- Inactivity timeout: 15 minutes; keepalive ping every 30s

---

### 6.8 — `agent/modules/browser/`

**Chromium extraction flow:**
```
1. Read "Local State" → extract "os_crypt.encrypted_key"
2. Decrypt master key:
   - Windows: DPAPI (CryptUnprotectData via ctypes)
   - macOS: Keychain (security CLI)
   - Linux: libsecret / kwallet
3. Open "Login Data" (SQLite copy — file is locked while Chrome runs)
4. Decrypt each password_value with AES-128-GCM (v10/v80+) or DES3 (legacy)
```

**Firefox extraction flow:**
```
1. Read profiles.ini → locate profile directory
2. Parse logins.json or logins.sqlite
3. If master password set → attempt blank + common passwords
4. Decrypt with NSS library (ctypes) or python-nss
```

---

### 6.9 — Server-side Module Catalog (`backend/modules/`)

| Module | Category | OS | Key Capability |
|--------|----------|----|----------------|
| `screenshot` | Recon | All | Screen capture, streaming |
| `keylog` | Exfiltration | All | Keystroke capture with window context |
| `file_manager` | Exfiltration | All | Tree, upload, download, delete |
| `shell` | Control | All | Interactive PTY shell |
| `process` | Recon | All | List, kill, inject |
| `wifi` | Exfiltration | Win/Lin | SSID + plaintext passwords |
| `browser` | Exfiltration | All | Passwords, cookies, history |
| `persistence` | Persistence | Win/Lin | Startup/cron installation |
| `geoip` | Recon | All | IP geolocation (ipinfo.io) |
| `webcam` | Recon | All | Camera capture (OpenCV) |

---

## 7. Frontend Modules

### 7.1 — State Management (Zustand stores)

| Store | State | Actions |
|-------|-------|---------|
| `authStore` | `user`, `token`, `isAuthenticated` | `login`, `logout`, `refreshToken` |
| `agentStore` | `agents[]`, `selectedAgent` | `setAgents`, `updateAgent`, `selectAgent` |
| `taskStore` | `tasks[]`, `activeQueue` | `addTask`, `updateTaskStatus`, `clearCompleted` |
| `uiStore` | `sidebarOpen`, `theme`, `activeModal` | `toggleSidebar`, `setTheme`, `openModal` |

---

### 7.2 — Pages

| Page | Route | Description |
|------|-------|-------------|
| `Login` | `/login` | JWT auth form |
| `Dashboard` | `/` | Stats, charts, map, live feed |
| `Agents` | `/agents` | Agent table with filters |
| `AgentDetail` | `/agents/:id` | Full agent view (tabs) |
| `ModuleStore` | `/modules` | Plugin marketplace + code editor |
| `TimelineBuilder` | `/timelines/:id` | Drag & drop attack chain builder |
| `Settings` | `/settings` | API keys, users, config |

---

### 7.3 — Key Components

| Component | Description |
|-----------|-------------|
| `Terminal.tsx` | xterm.js shell, single/broadcast/script modes |
| `MapView.tsx` | Leaflet map with agent markers + clustering |
| `CodeEditor.tsx` | Monaco Editor (Python syntax, HMAC-aware save) |
| `FileExplorer.tsx` | Tree-view file browser with upload/download |
| `LogViewer.tsx` | Real-time log feed (SSE/WS), filterable by level |
| `TaskTimeline.tsx` | Gantt-like visualization of timeline steps |
| `TimelineBuilder.tsx` | react-flow canvas + react-dnd palette |
| `DataTable.tsx` | Reusable paginated, sortable, filterable table |

---

### 7.4 — WebSocket Integration

```typescript
// hooks/useWebSocket.ts
// Connects to ws://backend/ws?token=<jwt>
// Dispatches messages to appropriate Zustand store actions

socket.on("heartbeat",  (msg) => agentStore.updateAgent(msg.agent_id, msg.payload))
socket.on("task",       (msg) => taskStore.addTask(msg.payload))
socket.on("result",     (msg) => taskStore.updateTaskStatus(msg.task_id, msg.payload))
socket.on("log",        (msg) => logBuffer.push(msg.payload))
socket.on("stdout",     (msg) => terminalRef.current?.write(msg.payload.data))
```

---

## 8. Communication Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        OPERATOR BROWSER                          │
│   React Dashboard ←──WebSocket + REST──→ FastAPI Backend        │
└──────────────────────────────────┬──────────────────────────────┘
                                   │ AES-256-GCM encrypted channel
                          ┌────────┴────────┐
                          │  FastAPI + WS   │
                          │   (C2 Server)   │
                          └────────┬────────┘
                                   │ ECDH → AES session key per agent
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
               ┌────────┐    ┌────────┐    ┌────────┐
               │ Agent  │    │ Agent  │    │ Agent  │
               │  Win   │    │ Linux  │    │ macOS  │
               └────────┘    └────────┘    └────────┘
```

### Message Flow — Task Execution

```
Operator clicks "Run screenshot"
  → POST /api/v1/tasks {agent_id, module: "screenshot", params}
    → Celery task_queue.enqueue(priority=HIGH)
      → WebSocket push to agent {type: "task", task_id, module, params}
        → Agent executes screenshot module
          → WebSocket result {type: "result", task_id, status, data}
            → Backend stores result in Task.result
              → WebSocket push to Frontend {type: "result", ...}
                → taskStore.updateTaskStatus() → UI update
```

### ECDH Handshake Sequence

```
Agent                                          Server
  │                                               │
  │── generate ECDH keypair ───────────────────►  │
  │── POST /register {pubkey, sysinfo} ─────────► │
  │                                               │── generate ECDH keypair
  │                                               │── derive shared_secret
  │                                               │── HKDF → aes_key
  │                                               │── encrypt nonce proof
  │ ◄──── {server_pubkey, nonce_encrypted} ───── │
  │── derive shared_secret ─────────────────────  │
  │── HKDF → aes_key ───────────────────────────  │
  │── decrypt + verify nonce ───────────────────  │
  │                                               │
  │  [session established — all comms AES-GCM]    │
```

---

## 9. Security Architecture

### 9.1 — Authentication Layers

```
Layer 1 — JWT Bearer (operator access)
  Header: Authorization: Bearer <access_token>
  Payload: {sub: user_id, role: admin|operator|viewer, scope, exp}

Layer 2 — API Key (automation / agent registration)
  Header: X-API-Key: <32-byte-hex>
  Rotatable per user, stored hashed in DB

Layer 3 — Agent Session Key (per-agent AES key)
  Derived via ECDH handshake
  Stored in memory only (never written to disk)
```

### 9.2 — Rate Limiting

| Scope | Limit |
|-------|-------|
| Per IP | 100 req/min |
| Per API Key | 1000 req/min |
| Auth endpoint | 10 req/min |

### 9.3 — Agent Anti-Detection (Basic)

- RAM check: aborts if < 2GB (likely sandbox)
- Screen resolution check: aborts if < 1024×768 (VM indicator)
- Debugger detection: `IsDebuggerPresent` (Windows) / `/proc/self/status` TracerPid (Linux)
- Jitter: random heartbeat interval 15–30s (prevents timing-based detection)
- Memory-only: no files written unless `file.write` task explicitly received

---

## 10. Build & Deployment

### 10.1 — Docker Compose

```yaml
# docker-compose.yml (summary)
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports: ["8000:8000"]
    env_file: [.env]
    volumes: [./data:/app/data]
    depends_on: { redis: { condition: service_healthy } }

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports: ["3001:80"]
    depends_on: { backend: { condition: service_healthy } }

  celery_worker:
    build:
      context: .
      dockerfile: backend/Dockerfile
    command: celery -A core.celery_app worker -l info -Q critical,high,normal,low -c 4
    env_file: [.env]
    depends_on: { backend: { condition: service_healthy } }

  celery_beat:
    build:
      context: .
      dockerfile: backend/Dockerfile
    command: celery -A core.celery_app beat -l info --scheduler celery.beat.PersistentScheduler
    env_file: [.env]
    depends_on: { backend: { condition: service_healthy } }
```

### 10.2 — Agent Builder Flow

1. Operator selects target OS / arch, modules, C2 URL, API key (auto-generated if empty).
2. Frontend `POST /api/v1/build` → backend returns `{build_id, status: "queued"}`.
3. Backend writes `agent/config.py` with all values baked in.
4. **Windows:** packages `agent/`, `core/`, `modules/`, `main.py`, `config.py`, `build.bat`, `build.ps1` into a ZIP.
5. **Linux/macOS:** runs `pyinstaller` inside the container and emits the binary directly.
6. Frontend polls `/api/v1/build/{id}` every 2s until `done` / `error`.
7. Download button serves the ZIP/binary.

### 10.3 — Manual Agent Build (PyInstaller)

```bash
pyinstaller agent/main.py \
  --onefile --noconsole \
  --name lucy_agent \
  --hidden-import agent \
  --hidden-import core.crypto \
  --hidden-import core.stealth \
  --hidden-import core.offline_queue \
  --hidden-import modules.builtin
```

Output: `dist/lucy_agent.exe` (Windows) / `dist/lucy_agent` (Linux/macOS)

### 10.4 — Portable USB Launcher

Drop the Lucy folder on a USB drive. No Docker required. On the target analysis machine:

**Windows:**
```batch
tools\portable\start.bat
```

**Linux/macOS:**
```bash
bash tools/portable/start.sh
```

What happens:
1. `tools/portable/launcher.py` ensures a Python 3.11+ interpreter is available (downloads the Windows embedded CPython archive if needed).
2. Creates a local virtual environment at `tools/portable/.venv` and installs backend requirements.
3. Builds the frontend once (`frontend/dist`).
4. Starts the backend on `http://127.0.0.1:8000` in `PORTABLE_MODE`.
5. The backend serves both the API and the built frontend from a single port.
6. Creates a Windows desktop shortcut named **Lucy C2** with the Lucy icon (`tools/portable/lucy.ico`).
7. Opens Lucy in its **own native desktop window** using `pywebview`.
8. Use `python tools/portable/launcher.py --browser` to open in the default browser instead.

Notes:
- Redis/Celery are optional in portable mode. If Redis is unavailable, tasks are queued locally and delivered when an agent reconnects via WebSocket.
- SQLite database is stored at `tools/portable/lucy.db` by default.
- The whole folder can be moved/copied to another machine or USB drive.

### 10.5 — Default Credentials

After first startup, log in with:

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `admin` |

You can change both the username and password from the in-app **Settings** page (`/settings`).

### 10.6 — Environment Variables

| Variable | Component | Description |
|----------|-----------|-------------|
| `JWT_SECRET` | Backend | HMAC key for JWT signing |
| `JWT_REFRESH_SECRET` | Backend | Separate key for refresh tokens |
| `DATABASE_URL` | Backend | SQLite path (`sqlite:///./lucy.db`) |
| `REDIS_URL` | Backend/Celery | `redis://redis:6379/0` |
| `MASTER_KEY` | Backend | AES key for credential encryption |
| `API_CORS_ORIGINS` | Backend | Allowed frontend origins |
| `VITE_API_URL` | Frontend | Backend base URL |
| `VITE_WS_URL` | Frontend | WebSocket URL |
| `BUILD_AUTH_TOKEN` | Backend | Optional gate for Agent Builder builds |
| `BUILD_AUDIT_PATH` | Backend | Path for build audit log (default `data/build_audit.log`) |
| `PORTABLE_MODE` | Backend | `true` to serve frontend static files from backend |
| `FRONTEND_DIST_PATH` | Backend | Path to built frontend (`frontend/dist`) |
| `AGENT_C2_URL` | Agent | Hardcoded or config: C2 server address |
| `AGENT_API_KEY` | Agent | Initial registration key |

---

*Generated for Project Lucy — RATS v1.0 — Authorized Red Team Use Only*
