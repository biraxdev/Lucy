# Lucy — System Architecture

## Overview

Lucy is a defensive security monitoring and authorized red-team operations platform. It is split into three main runtime components:

- **Backend** (`backend/main.py`) — FastAPI application exposing REST APIs and WebSocket channels.
- **Frontend** (`frontend/`) — React 18 single-page application built with Vite.
- **Agent** (`agent/agent.py`) — Lightweight Python endpoint implant that communicates with the C2 server over multiple transports.

The platform uses a relational datastore accessed through the Peewee ORM, with SQLite in WAL mode by default and a migration path to PostgreSQL.

## Backend

The backend is a FastAPI application (`backend/main.py`) that loads settings from a `.env` file through `backend/config.py`.

- **Runtime** — `python main.py` initializes the ORM, seeds the admin user, starts WebSocket keepalives, in-memory task workers (portable mode), the alert manager, the orchestrator, and the predictive alert engine.
- **ORM** — Peewee models are defined under `backend/models/`. Migrations are handled through the model layer.
- **Database** — SQLite (`sqlite:///./lucy.db`) is used in WAL mode by default. PostgreSQL is supported by changing `DATABASE_URL`.
- **API routing** — Core routes are mounted under `/api/v1/`, including:
  - `/api/v1/auth/login`
  - `/api/v1/agents`
  - `/api/v1/tasks`
  - `/api/v1/library`
- **Middleware stack** — request logging, CORS, JWT/API-key authentication, RBAC, and rate limiting.

## Frontend

The frontend is a React 18 + TypeScript application bundled with Vite.

- **Dev server** — `npm run dev` (`vite`)
- **Production build** — `npm run build` (`tsc && vite build`)
- **Preview server** — `npm run preview`
- **State / UI** — React Query, Zustand, Tailwind CSS, DaisyUI, React Flow, and xterm for the terminal view.
- **Build output** — `frontend/dist/`, which can be served directly by the backend when `PORTABLE_MODE=true`.

## WebSocket Broker

Real-time agent control is provided through the WebSocket broker in `backend/core/ws_manager.py`.

- **Agent route** — `/ws/agent/:id` authenticates the agent, opens a persistent channel, and adds the socket to the connection registry.
- **Keepalive** — `ConnectionManager.start_keepalive()` sends periodic heartbeats (`WS_HEARTBEAT_INTERVAL`) and enforces ping timeouts.
- **Buffers** — Incoming heartbeats, task results, and operator chat messages are staged through `HeartbeatBuffer`, `ResultBuffer`, and `ChatBuffer` before being committed to the database.
- **Push model** — Tasks and commands are pushed to agents over the WebSocket; agents respond with results on the same channel.

## Agent Transport

The Python agent in `agent/agent.py` is designed to operate with minimal dependencies and supports several transports:

- `websocket` — primary, low-latency channel
- `http` — long-polling fallback
- `dns`, `smb`, `tcp` — alternative beacon channels

Configuration is read from an INI file or the embedded `DEFAULT_CONFIG`. Tunables include `c2_url`, `ws_url`, `api_key`, heartbeat jitter, task timeout, TLS options, and stealth features.

## Library System

The library is a pluggable module registry for offensive and defensive tools.

- `backend/core/library/registry.py` — central registry that tracks available modules and providers.
- `backend/core/library/providers/` — provider implementations that fetch or generate modules.
- `backend/api/library.py` — REST endpoints for listing, searching, uploading, and downloading library entries.
- Agents can fetch modules at runtime from `/api/v1/modules/{module_id}/download`.

## Threat Intelligence

Threat-intel capabilities are integrated with the library and alerting pipelines:

- Alert ingestion, correlation, and enrichment are handled by `backend/core/alert_manager.py`.
- Predictive alerting is performed by `backend/core/predictive_alerting.py`.
- Indicators and MITRE mappings can be queried through the chat and library APIs.

## C2 / Agent Model

```
Operator  ->  Frontend  ->  REST API  ->  WebSocket Broker  ->  Agent
Agent     ->  WebSocket  ->  Result buffer  ->  Database  ->  Frontend
```

1. Operators log in through `/api/v1/auth/login` and receive a JWT.
2. Operators register or select an agent and dispatch a task.
3. The task is queued and pushed to the agent over its WebSocket connection.
4. The agent executes the task and returns a result.
5. The result is buffered, stored, and surfaced in the frontend.

All sensitive C2 traffic is encrypted. See `SECURITY.md` for details on ECDH key exchange and AES payload encryption.
