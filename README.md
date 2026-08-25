<div align="center">

# Lucy

### Advanced Red Team & Security Resilience Platform

**Autonomous C2 · AI Architect · Visual Scripting · Module Arsenal · Defense Telemetry**

</div>

---

## Overview

**Lucy** is a full-stack, self-contained platform for authorized red-team
operations, offensive security research, and resilience testing. It unifies a
high-performance FastAPI backend, a modern React frontend, a standalone Python
agent, and an integrated AI architect capable of generating modules, endpoints,
and UI components from natural-language instructions.

> **Authorized use only.** Deploy Lucy solely against systems you own or have
> explicit written permission to test. Unauthorized use is illegal and against
> the terms of this software.

---

## Key Capabilities

| Domain | Feature | Description |
|--------|---------|-------------|
| **AI Architect** | `/ai-chat` | Conversational interface with reflection, clarification, planning, and autonomous code generation. Generates Python modules, FastAPI endpoints, and React components. |
| **AI Agent** | `/ai-agent` | Technical orchestration API: threat analysis, script generation, sandboxed execution, MITRE ATT&CK suggestions. |
| **Visual Scripting** | `/script-builder` | Drag-and-drop timeline builder (ReactFlow) with live WebSocket execution tracking. |
| **Agent Builder** | `/builder` | Compile standalone agents (PyInstaller or quick-bundle) with module selection, stealth options, and code signing. |
| **Module Arsenal** | 48 modules | Screenshot, keylog, shell, browser, file ops, persistence, port scan, webcam, clipboard, credential dump, EDR evasion, lateral movement, and more. |
| **Defense Center** | `/defense` | SIEM-style event ingestion, detection rules, alerting, MITRE mapping, and local scanners. |
| **Operations** | `/tasks`, `/terminal` | Task dispatch, broadcast shell, real-time result streaming. |
| **Intelligence** | `/findings`, `/credentials`, `/alerts` | Findings management, encrypted credential store, alert queue. |
| **Strategy** | `/strategy`, `/mission` | ATT&CK tactics/techniques, campaigns, playbooks, agent notes. |
| **Administration** | `/rbac`, `/setup`, `/logs` | Role-based access control, tenant setup, audit trail. |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12 · FastAPI · WebSockets · Peewee ORM · SQLite |
| **Task Queue** | Celery 5 · Redis 7 (with automatic in-memory fallback) |
| **Frontend** | React 18 · TypeScript · Vite · TailwindCSS · DaisyUI · Zustand · TanStack Query · ReactFlow |
| **Agent** | Python 3.12 standalone · PyInstaller binary · WebSocket + HTTP transports |
| **AI** | Ollama (local LLM) · DeepSeek Coder · No external API calls |
| **Infrastructure** | Docker Compose · Kali Linux sandbox · Portable mode (no Docker required) |
| **Cryptography** | AES-256-GCM · ECDH P-256 + HKDF · HMAC-SHA256 · JWT (30 min access / 7 day refresh) |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         OPERATOR (Browser)                        │
│                                                                   │
│   Dashboard · Script Builder · AI Architect · AI Chat · Defense   │
│   Agent Builder · Terminal · Tasks · Credentials · Settings       │
│                                                                   │
│                        REST API + WebSocket                       │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────┼───────────────────────────────────┐
│                         BACKEND (FastAPI)                        │
│                                                                   │
│   Module Manager · Timeline Orchestrator · AI Engine · Chat       │
│   Auth (JWT) · Crypto (AES-256) · Task Queue · WS Manager         │
│   Defense Engine · Predictive Alerting · Auto-Recon              │
│                                                                   │
│                    SQLite (Peewee ORM · 25 tables)               │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────┼───────────────────────────────────┐
│                      INFRASTRUCTURE (Docker)                     │
│                                                                   │
│   Redis (broker) · Celery (worker + beat) · Ollama (LLM)         │
│   Kali Sandbox (4 GB / 2 CPU · seccomp unconfined)               │
└──────────────────────────────┼───────────────────────────────────┘
                               │
┌──────────────────────────────┼───────────────────────────────────┐
│                          AGENT (Python)                          │
│                                                                   │
│   WebSocket + HTTP polling · Offline queue · Stealth controller   │
│   48 local modules · Dynamic module download · Heartbeat          │
└───────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Option A — Docker Compose (full stack)

```bash
git clone <repo>
cd lucy

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env — change all secrets

# Launch all services
docker compose up -d

# Pull the LLM model
docker exec -it lucy-ollama-1 ollama pull deepseek-coder-v2:lite
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3001 |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Ollama | http://localhost:11434 |
| Sandbox shell | `docker exec -it lucy-sandbox bash` |

**Default credentials:** `admin` / `admin` (change immediately in Settings).

### Option B — Local development

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
python main.py                  # Starts on 0.0.0.0:8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                     # Vite dev server with /api proxy to :8000
```

### Option C — Portable mode (no Docker, no Redis)

```bash
cd tools/portable
python launcher.py              # SQLite at tools/portable/lucy.db
```

Portable mode uses the in-memory task worker automatically when Redis is
unavailable. No Docker, no Redis, no external dependencies.

---

## Module Arsenal

48 modules are auto-discovered at startup from `backend/modules/` with rich
metadata (actions, params schema, MITRE category, OS compatibility).

| Category | Modules |
|----------|---------|
| **Recon** | info, port_scan, wifi, geoip, process |
| **Execution** | shell, bof, injection, exec_kit |
| **File** | file (read/write/list/delete/exfil), file_manager |
| **Surveillance** | screenshot, screen_stream, keylog, webcam, clipboard |
| **Credentials** | browser, credential_dump, mfa_harvest, secret_hunter, token, pth, kerberoast, brute_local |
| **Persistence** | persistence, persistence_adv, persist_kit |
| **Evasion** | stealth, anti_analysis, anti_debug, anti_vm, edr_evasion, sleep_mask, syscalls, stack_spoof, uac_bypass, tls_fingerprint |
| **Lateral** | lateral, pivoting, remote_control |
| **Transport** | beacon_kit, stager, domain_fronting, traffic_shaper, covert_store |
| **Other** | builtin, macos, syscall_kit, inject_kit, browser_harvest |

Module descriptors are defined in `backend/modules/descriptors.json`. Each
descriptor specifies the module's actions, parameter schema, category, tags,
and expected duration. The Script Builder reads these actions to populate the
UI; the agent dispatches them via `run(action, **params)`.

---

## API Reference

All endpoints require `Authorization: Bearer <JWT>` unless noted.

### Core Resources

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/login` | Obtain JWT access + refresh tokens |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `GET` | `/api/v1/auth/me` | Current authenticated user |
| `POST` | `/api/v1/auth/change-password` | Change operator password |
| `POST` | `/api/v1/auth/rotate-key` | Rotate API key |
| `GET` | `/api/v1/agents` | List registered agents |
| `POST` | `/api/v1/agents/register` | Register a new agent |
| `POST` | `/api/v1/agents/{id}/heartbeat` | Agent heartbeat (returns pending tasks) |
| `GET` | `/api/v1/tasks` | List tasks (filter by agent, status, priority) |
| `POST` | `/api/v1/tasks` | Create and dispatch a task |
| `GET` | `/api/v1/tasks/{id}` | Task detail with result |
| `DELETE` | `/api/v1/tasks/{id}` | Cancel a task |
| `POST` | `/api/v1/tasks/{id}/result` | Submit task result (agent) |
| `GET` | `/api/v1/modules` | List all modules with actions + schema |
| `GET` | `/api/v1/timelines` | List timelines |
| `POST` | `/api/v1/timelines` | Create a timeline |
| `POST` | `/api/v1/timelines/{id}/execute` | Execute a timeline |
| `POST` | `/api/v1/build` | Queue an agent build |
| `GET` | `/api/v1/build/{id}` | Build status + progress |
| `GET` | `/api/v1/build/{id}/download` | Download build artifact |
| `GET` | `/api/v1/credentials` | List harvested credentials |
| `POST` | `/api/v1/credentials/{id}/reveal` | Decrypt and reveal a credential |
| `GET` | `/api/v1/findings` | List security findings |
| `GET` | `/api/v1/alerts` | List alerts |
| `GET` | `/api/v1/defense/status` | Defense engine status |
| `GET` | `/api/v1/defense/alerts` | Defense alerts |
| `POST` | `/api/v1/defense/scanners/run` | Run a local scanner |
| `GET` | `/api/v1/rbac/roles` | List RBAC roles + permissions |
| `PUT` | `/api/v1/rbac/users/{id}` | Update user role |
| `GET` | `/api/v1/monitor` | Server health (CPU, RAM, WS, DB size) |
| `POST` | `/api/v1/chat/command` | Natural-language command |
| `GET` | `/api/v1/chat/history` | Chat history (paginated) |
| `POST` | `/api/v1/ai-chat/send` | Send message to AI Architect |
| `POST` | `/api/v1/ai-agent/analyze-threat` | Threat analysis |
| `POST` | `/api/v1/ai-agent/generate-script` | Script generation |
| `POST` | `/api/v1/ai-agent/sandbox/execute` | Sandboxed command execution |

### WebSocket Channels

| Channel | Purpose |
|---------|---------|
| `ws://host/ws?token=<JWT>` | Frontend real-time feed (tasks, results, alerts, chat) |
| `ws://host/ws/agent/{id}?api_key=<key>` | Agent connection (task dispatch + result streaming) |

---

## Agent Builder

The Agent Builder (`/builder`) compiles standalone agents with two modes:

| Mode | Output | Use case |
|------|--------|----------|
| **Standard** | Native binary (PyInstaller) | No Python required on target. Code-signed on Windows to bypass SmartScreen. |
| **Quick** | Python zip bundle | Sub-30s packaging. Run with `pip install -r requirements.txt && python run.py`. |

**Build options:**
- OS target: Windows, Linux, macOS
- Module selection (drag-and-drop)
- Stealth pack: anti-analysis, hide window, beacon jitter, self-destruct
- EDR evasion: AMSI patch, ETW patch, NTDLL unhook, sleep mask
- Transport: WebSocket, HTTP, DNS, SMB, TCP
- TLS fingerprint spoofing (Chrome, Firefox, Safari, Edge, IE11)
- Dormant mode: periodic wake with disk persistence
- TTL expiry and build authorization token

---

## Defense Center

The Defense Center (`/defense`) provides blue-team visibility within the same
platform:

- **Event ingestion** — `POST /api/v1/defense/events` accepts structured
  security events from agents or external sensors.
- **Detection rules** — 11 built-in rules with MITRE ATT&CK mapping. Rules
  evaluate events and generate alerts by severity (critical/high/medium/low).
- **Alert queue** — Unread alert tracking, mark-as-read, bulk acknowledge.
- **MITRE map** — `GET /api/v1/defense/mitre-map` returns technique-to-rule
  mapping for ATT&CK Navigator integration.
- **Local scanners** — Run scanners locally or dispatch to agents via
  `POST /api/v1/defense/scanners/dispatch`.

---

## RBAC

Four roles with granular permissions:

| Role | Scope |
|------|-------|
| **superadmin** | Full access — all tenants, all operations |
| **admin** | Tenant admin — manage users, agents, all operations |
| **operator** | Red team operator — execute operations, manage agents |
| **viewer** | Read-only — observe operations, view data |

Manage roles at `/rbac`. Permissions cover agents, tasks, credentials,
findings, alerts, reports, builds, timelines, and operator management.

---

## Project Structure

```
lucy/
├── README.md                         This file
├── Makefile                          Docker + test shortcuts
├── docker-compose.yml                Full stack (redis, celery, ollama, sandbox)
├── .roorules                         AI agent operational SOP
│
├── backend/
│   ├── main.py                       FastAPI entry point
│   ├── config.py                     Centralized configuration
│   ├── database.py                   SQLite + migration runner
│   ├── middleware.py                 Auth, CORS, request logging
│   ├── requirements.txt              Python dependencies
│   ├── api/                          REST + WS routes (249 endpoints)
│   │   ├── ai_agent.py               AI Agent API
│   │   ├── ai_chat.py                AI Chat API
│   │   ├── agents.py                 Agent management + heartbeat
│   │   ├── tasks.py                  Task CRUD + results
│   │   ├── timelines.py              Timeline CRUD + execution
│   │   ├── build.py                  Agent build pipeline
│   │   ├── defense.py                Defense center API
│   │   ├── rbac.py                   RBAC API
│   │   └── ...
│   ├── core/                         Business logic
│   │   ├── ai_agent.py               AI agent orchestration
│   │   ├── ai_chat_engine.py         Reflect/clarify/plan/execute engine
│   │   ├── llm_bridge.py             Ollama LLM bridge
│   │   ├── module_manager.py         Module discovery + seeding
│   │   ├── orchestrator.py           Timeline orchestrator
│   │   ├── task_queue.py             Task dispatch (WS → Celery → in-memory)
│   │   ├── ws_manager.py             WebSocket connection manager
│   │   ├── crypto.py                 AES-256-GCM + ECDH
│   │   └── ...
│   ├── db/
│   │   ├── models.py                 Peewee models (25 tables)
│   │   └── migrations/               Schema migrations
│   ├── modules/                      48 Python modules + descriptors.json
│   ├── defense/                      Detection rules + scanners
│   ├── templates/                    Report templates
│   ├── data/                         Seed data (PoCs, build packs)
│   └── tests/                        186 pytest tests
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts                Dev proxy /api → :8000
│   └── src/
│       ├── routes.tsx                28 routes
│       ├── api/                      Axios API clients
│       ├── types/                    TypeScript contracts
│       ├── pages/                    React pages
│       ├── components/               UI components + script-builder
│       ├── stores/                   Zustand stores
│       ├── hooks/                    React hooks (agents, tasks, WebSocket)
│       └── lib/                      Utilities (feed translator, etc.)
│
├── agent/
│   ├── agent.py                      Main agent loop (WS + HTTP)
│   ├── core/                         Crypto, stealth, offline queue, loader
│   ├── modules/                      30+ agent-side modules
│   └── tests/                        Agent unit tests
│
├── tools/
│   ├── portable/                     No-Docker launcher
│   ├── arsenal/                      Offensive tooling
│   ├── redis/                        Redis binaries (Windows)
│   ├── python312/                    Embedded Python
│   └── node20/                       Embedded Node.js
│
├── packs/                            Extension packs
│   ├── 01-core/                      Core platform
│   ├── 02-agent/                     Agent extensions
│   ├── 03-ui/                        UI extensions
│   ├── 04-extensions/                Backend extensions
│   └── 05-arsenal/                   Arsenal extensions
│
└── docs/
    ├── README.md                     Technical API reference
    └── defense/                      Defense documentation
```

---

## Testing

```bash
# Backend (186 tests)
cd backend
python -m pytest tests/ -v

# Frontend
cd frontend
npm run build          # tsc + vite build (type-check + production build)
```

---

## Security

- **Authentication** — JWT access (30 min) + refresh (7 day) tokens. API keys
  stored as SHA-256 hashes.
- **Encryption** — AES-256-GCM for credentials at rest. ECDH P-256 key
  exchange per agent session (no static shared key).
- **Transport** — WebSocket and HTTP polling with API key authentication.
- **Sandbox** — Kali Linux container with 4 GB RAM / 2 CPU limits, seccomp
  unconfined for ptrace-based tooling.
- **Audit** — All AI actions, builds, and operator commands are logged.
- **Rate limiting** — 100 req/min per IP, 1000/min per API key.
- **LLM** — Ollama runs locally; no data is sent to external LLM APIs.

---

## Operational Rules

The `.roorules` file defines the AI agent's standard operating procedure:

- All execution strictly within the `lucy-sandbox` container
- Generated code must be structured (CLI, logic, structured logging)
- Auto-debug: on failure, analyze stdout/stderr, refactor, retry
- Output format: structured JSON in `/workspace/logs/`
- Destructive operations require explicit operator approval
- No credential exfiltration outside the sandbox
- No production system modification
- Maintain operator audit trails at all times

---

## Configuration

Key environment variables (see `backend/.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_USERNAME` | `admin` | Initial admin username |
| `ADMIN_PASSWORD` | `admin` | Initial admin password (change immediately) |
| `JWT_SECRET` | — | JWT signing secret (32+ hex bytes) |
| `MASTER_KEY` | — | AES-256 master key for credential encryption |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis broker URL |
| `PORTABLE_MODE` | `false` | Force in-memory task worker (no Redis) |
| `BUILD_AUTH_TOKEN` | — | Optional build authorization token |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Make Commands

```bash
make dev          # Start full stack (foreground)
make dev-bg       # Start full stack (background)
make stop         # Stop all services
make reset        # Stop + remove volumes + delete DB
make logs         # Tail all logs
make test         # Run backend tests
make lint         # Flake8 + ESLint
make install      # Install backend + frontend dependencies
make agent-build  # Build agent binary with PyInstaller
```

---

## License

Internal use only. For authorized penetration testing engagements and security
research.

> *Building defenses requires understanding attacks. Lucy is the workshop
> where that understanding is forged.*
