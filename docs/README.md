# Lucy — Technical Documentation

> **For authorized Red Team simulations only.**
> Do not deploy against systems you do not own or have explicit written
> permission to test.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Setup](#setup)
3. [API Reference](#api-reference)
4. [WebSocket Channels](#websocket-channels)
5. [Module Development](#module-development)
6. [Agent Builder](#agent-builder)
7. [Defense Center](#defense-center)
8. [Security](#security-considerations)
9. [Testing](#testing)

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    OPERATOR (Browser)                     │
│   Dashboard · Script Builder · AI Chat · Defense · RBAC  │
│                        REST + WS                          │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────┐
│                   BACKEND (FastAPI)                       │
│   249 endpoints · 25 DB tables · 48 modules · 11 rules   │
│   Task Queue (WS → Celery → in-memory fallback)          │
│   SQLite (Peewee ORM)                                    │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────┐
│                 INFRASTRUCTURE (Docker)                   │
│   Redis · Celery (worker + beat) · Ollama · Kali sandbox │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────┐
│                    AGENT (Python)                         │
│   WS + HTTP · Offline queue · 30+ local modules          │
└──────────────────────────────────────────────────────────┘
```

### Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 · FastAPI · WebSockets · Peewee ORM · SQLite |
| Task Queue | Celery 5 · Redis 7 (with in-memory fallback when Redis is down) |
| Frontend | React 18 · TypeScript · Vite · TailwindCSS · DaisyUI · Zustand · TanStack Query · ReactFlow |
| Agent | Python 3.12 standalone · PyInstaller binary · WebSocket + HTTP |
| AI | Ollama (local LLM) · DeepSeek Coder |
| Build | Docker Compose · PyInstaller · Code signing (Windows) |

---

## Setup

### Prerequisites

- Docker + Docker Compose v2 (for full stack)
- Python 3.12 (for local dev / agent builds)
- Node.js 20 (for local frontend dev)

### Quick Start (Docker)

```bash
cp backend/.env.example backend/.env
# Edit .env — change all secrets

docker compose up -d

# Pull the LLM model
docker exec -it lucy-ollama-1 ollama pull deepseek-coder-v2:lite
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3001 |
| Backend | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| Ollama | http://localhost:11434 |

**Default login:** `admin` / `admin` — change immediately in Settings.

### Local Development

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
python main.py

# Frontend
cd frontend
npm install
npm run dev
```

### Portable Mode (no Docker, no Redis)

```bash
cd tools/portable
python launcher.py
```

---

## API Reference

All endpoints require `Authorization: Bearer <JWT>` unless noted.

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | Get JWT tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Current user |
| POST | `/api/v1/auth/logout` | Revoke refresh token |
| POST | `/api/v1/auth/change-password` | Change password |
| POST | `/api/v1/auth/change-username` | Change username |
| POST | `/api/v1/auth/rotate-key` | Rotate API key |

### Agents

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/agents` | List all agents |
| GET | `/api/v1/agents/{id}` | Agent detail |
| POST | `/api/v1/agents/register` | Register new agent |
| POST | `/api/v1/agents/{id}/heartbeat` | Agent heartbeat (returns pending tasks) |
| POST | `/api/v1/agents/{id}/result` | Submit task result |
| DELETE | `/api/v1/agents/{id}` | Remove agent |

### Tasks

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/tasks` | List tasks (filter: agent_id, status, priority) |
| POST | `/api/v1/tasks` | Create and dispatch a task |
| GET | `/api/v1/tasks/{id}` | Task detail with result |
| PATCH | `/api/v1/tasks/{id}` | Update task status |
| DELETE | `/api/v1/tasks/{id}` | Cancel task |
| POST | `/api/v1/tasks/{id}/result` | Submit task result (agent) |
| GET | `/api/v1/tasks/agent/{id}/pending` | Pending tasks for an agent |

### Modules

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/modules` | List all modules with actions + schema |
| POST | `/api/v1/modules` | Upload a module |
| GET | `/api/v1/modules/{id}/download` | Download module code |
| DELETE | `/api/v1/modules/{id}` | Remove module |

### Timelines

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/timelines` | List timelines |
| POST | `/api/v1/timelines` | Create a timeline |
| POST | `/api/v1/timelines/{id}/execute` | Execute a timeline |
| GET | `/api/v1/timelines/{id}/tasks` | Tasks for a timeline |

### Build

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/build` | Queue an agent build |
| GET | `/api/v1/build/{id}` | Build status + progress |
| GET | `/api/v1/build/{id}/download` | Download build artifact |

### Credentials

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/credentials` | List credentials (search) |
| POST | `/api/v1/credentials/{id}/reveal` | Decrypt and reveal password |

### Defense

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/defense/status` | Defense engine status |
| GET | `/api/v1/defense/events` | List defense events |
| POST | `/api/v1/defense/events` | Ingest a defense event |
| GET | `/api/v1/defense/alerts` | List defense alerts |
| POST | `/api/v1/defense/alerts/{id}/read` | Mark alert as read |
| POST | `/api/v1/defense/alerts/read-all` | Mark all alerts as read |
| GET | `/api/v1/defense/rules` | List detection rules |
| GET | `/api/v1/defense/mitre-map` | MITRE ATT&CK technique mapping |
| GET | `/api/v1/defense/scanners` | List available scanners |
| POST | `/api/v1/defense/scanners/run` | Run a local scanner |
| POST | `/api/v1/defense/scanners/dispatch` | Dispatch scanner to an agent |

### RBAC

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/rbac/roles` | List roles + permissions |
| GET | `/api/v1/rbac/matrix` | Permission matrix |
| GET | `/api/v1/rbac/users` | List users |
| PUT | `/api/v1/rbac/users/{id}` | Update user role |
| GET | `/api/v1/rbac/me` | Current user's permissions |

### Chat & AI

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/chat/command` | Natural-language command |
| GET | `/api/v1/chat/history` | Chat history (paginated) |
| POST | `/api/v1/ai-chat/send` | Send message to AI Architect |
| GET | `/api/v1/ai-chat/status` | AI Chat engine status |
| POST | `/api/v1/ai-agent/analyze-threat` | Threat analysis |
| POST | `/api/v1/ai-agent/generate-script` | Script generation |
| POST | `/api/v1/ai-agent/sandbox/execute` | Sandboxed command execution |
| POST | `/api/v1/ai-agent/sandbox/write-file` | Write file in sandbox |
| POST | `/api/v1/ai-agent/sandbox/run-script` | Run script in sandbox |
| POST | `/api/v1/ai-agent/suggest-steps` | MITRE ATT&CK suggestions |
| GET | `/api/v1/ai-agent/context` | Full Lucy resource snapshot |

### Strategy

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/v1/strategy/tactics` | ATT&CK tactics |
| GET/POST | `/api/v1/strategy/techniques` | ATT&CK techniques |
| GET/POST | `/api/v1/strategy/campaigns` | Engagement campaigns |
| GET/POST | `/api/v1/strategy/playbooks` | Reusable step sequences |
| GET/POST | `/api/v1/strategy/notes` | Agent observations |

### Reports

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/reports` | Generate report |
| GET | `/api/v1/reports/{id}/download` | Download report |

### Monitor

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/monitor` | Server health (CPU, RAM, WS, DB, uptime) |

---

## WebSocket Channels

| Channel | Purpose |
|---------|---------|
| `ws://host/ws?token=<JWT>` | Frontend real-time feed (tasks, results, alerts, chat, agent events) |
| `ws://host/ws/agent/{id}?api_key=<key>` | Agent connection (task dispatch + result streaming) |

### Frontend events

| Type | Payload |
|------|---------|
| `task` | Task created or dispatched |
| `result` | Task result from agent |
| `chat` | Chat message (translated event) |
| `alert` | Defense alert |
| `agent_update` | Agent status change |

---

## Module Development

Modules are Python files with a top-level `run()` function. Each module is
auto-discovered from `backend/modules/` at startup.

### Descriptor format

Module metadata is defined in `backend/modules/descriptors.json`:

```json
{
  "screenshot": {
    "category": "surveillance",
    "actions": ["capture", "stream_start", "stream_stop"],
    "tags": ["visual", "screen"],
    "expected_duration": 20,
    "params_schema": {
      "type": "object",
      "properties": {
        "quality": { "type": "integer", "default": 70 },
        "width": { "type": "integer" },
        "height": { "type": "integer" }
      }
    }
  }
}
```

### Agent-side module

```python
# agent/modules/my_module.py

def run(action: str = "default", **kwargs) -> dict:
    if action == "scan":
        return {"status": "completed", "data": {"result": "ok"}}
    return {"status": "error", "error": f"Unknown action: {action}"}
```

### Backend-side module (for seeding)

```python
# backend/modules/my_module.py
NAME = "my_module"
VERSION = "1.0.0"
DESCRIPTION = "Example module"
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]
```

The backend module file is used only for metadata extraction (static AST
parsing). The agent-side module contains the actual `run()` implementation.

### Dispatch convention

- **Builtin modules** (`shell`, `file`, `info`, `builtin`): `run(action, params_dict)`
- **Local modules** (in `agent/modules/`): `run(action, **params)`
- **Downloaded modules**: `run(action, params_dict)`

The agent dispatcher handles each convention automatically based on the
module's registration path.

---

## Agent Builder

Two build modes:

| Mode | Output | Time | Target requirement |
|------|--------|------|-------------------|
| Standard | Native binary (PyInstaller) | 2-5 min | No Python needed |
| Quick | Python zip bundle | <30s | Python + pip on target |

### Build options

- **OS**: Windows, Linux, macOS
- **Modules**: drag-and-drop selection from 48 modules
- **Stealth pack**: anti-analysis, hide window, beacon jitter, self-destruct
- **EDR evasion**: AMSI patch, ETW patch, NTDLL unhook, sleep mask
- **Transport**: WebSocket, HTTP, DNS, SMB, TCP
- **TLS fingerprint**: Chrome, Firefox, Safari, Edge, IE11
- **Dormant mode**: periodic wake with disk persistence
- **Code signing**: self-signed Authenticode (Windows) to bypass SmartScreen
- **TTL expiry**: agent self-terminates after N days
- **Build authorization token**: optional shared secret for build requests

---

## Defense Center

The Defense Center provides blue-team visibility within the Lucy platform.

### Detection rules

11 built-in rules with MITRE ATT&CK mapping:

- Suspicious process execution (T1059)
- Credential dumping patterns (T1003)
- Lateral movement indicators (T1021)
- Persistence mechanisms (T1547)
- Defense evasion techniques (T1562)
- And more...

Rules evaluate ingested events and generate alerts by severity (critical,
high, medium, low, info).

### Scanners

Local scanners can be run on the backend or dispatched to agents:

- `POST /api/v1/defense/scanners/run` — run locally
- `POST /api/v1/defense/scanners/dispatch` — dispatch to agent

---

## Security Considerations

- Change all default secrets in `backend/.env` before any deployment
- JWT access tokens expire in 30 minutes; refresh tokens in 7 days
- All agent ↔ server communication uses API key authentication
- Credentials are AES-256-GCM encrypted at rest with the master key
- ECDH P-256 key exchange per agent session (no static shared key)
- API keys are stored as SHA-256 hashes
- Rate limiting: 100 req/min per IP, 1000/min per API key
- Ollama runs locally — no data sent to external LLM APIs
- All AI actions, builds, and operator commands are audit-logged

---

## Testing

```bash
# Backend (186 tests)
cd backend
python -m pytest tests/ -v

# Frontend
cd frontend
npm run build    # tsc type-check + vite production build
```
