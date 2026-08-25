# Lucy — Deployment Guide

## Requirements

- Windows 10/11 or Windows Server 2019+
- Python 3.11 or newer
- Node.js 18 or newer
- Optional: Redis 7.x and/or PostgreSQL 15+

## 1. Backend Setup

### Install Python dependencies

Open a terminal in the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

### Create the environment file

Copy the example file to the project root or the `backend/` directory (the same directory from which `main.py` is launched):

```powershell
copy backend\.env.example .\.env
```

Generate strong secrets and replace all `CHANGE_ME_*` placeholders before starting:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Required values:

- `JWT_SECRET` — 64-character hex string
- `JWT_REFRESH_SECRET` — 64-character hex string, different from `JWT_SECRET`
- `MASTER_KEY` — 64-character hex string for credential encryption
- `ADMIN_USERNAME` — must not be `admin`
- `ADMIN_PASSWORD` — strong, unique password

Example `.env` fragment:

```dotenv
APP_NAME=Lucy C2
DEBUG=false
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000
DATABASE_URL=sqlite:///./lucy.db
JWT_SECRET=<64-char-hex>
JWT_REFRESH_SECRET=<64-char-hex>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
MASTER_KEY=<64-char-hex>
CORS_ORIGINS=["http://localhost:3000"]
ADMIN_USERNAME=lucy_admin
ADMIN_PASSWORD=<strong-password>
LOG_LEVEL=INFO
```

### Start the backend

From the `backend/` directory:

```powershell
cd backend
python main.py
```

Or from the project root:

```powershell
python backend\main.py
```

The SQLite database (`lucy.db`) is created on first startup and the seed admin user is provisioned.

## 2. Frontend Setup

Open a new terminal in the project root and install the Node dependencies:

```powershell
cd frontend
npm install
```

### Development mode

```powershell
npm run dev
```

The Vite dev server starts and points to the backend at the configured `CORS_ORIGINS` and API base URL.

### Production build

```powershell
npm run build
```

The static assets are written to `frontend/dist/`. Set `PORTABLE_MODE=true` in the backend `.env` to have the FastAPI app serve the built frontend from `frontend/dist/`.

### Preview the production build locally

```powershell
npm run preview
```

## 3. Optional: Redis and PostgreSQL

### Redis

Redis is used for Celery task queuing and result storage when `PORTABLE_MODE=false`:

```dotenv
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

Start Redis on `localhost:6379` and restart the backend.

### PostgreSQL

To move from SQLite to PostgreSQL, update the connection string and install the appropriate driver:

```powershell
python -m pip install psycopg2-binary
```

```dotenv
DATABASE_URL=postgresql://user:password@localhost:5432/lucy
```

## 4. Agent Install

The Python agent can be run directly from `agent/agent.py`:

```powershell
python agent\agent.py
```

Configure the agent by creating `agent/agent.ini` or by editing the defaults in `agent/agent.py` (`DEFAULT_CONFIG`):

```ini
[agent]
c2_url = http://127.0.0.1:8000
ws_url = ws://127.0.0.1:8000
api_key = <agent-api-key-from-server>
transport = websocket
heartbeat_min = 15
heartbeat_max = 30
task_timeout = 60
```

Available transports: `websocket`, `http`, `dns`, `smb`, `tcp`.

After starting the agent, it registers with the backend, appears under `/api/v1/agents/`, and begins accepting tasks over the configured transport.

## 5. Prometheus Metrics

Lucy exposes a Prometheus-compatible `/metrics` endpoint on the backend (public, no auth required).

```text
http://127.0.0.1:8000/metrics
```

Available metric families:

- `http_requests_total` — counter with `method`, `path`, `status` labels
- `http_request_duration_seconds` — histogram with `method`, `path` labels
- `lucy_agents_total` — gauge with `status` label (`online`, `offline`, `idle`, `unknown`)
- `lucy_tasks_total` — gauge with `status` label (`queued`, `running`, `completed`, `failed`, `cancelled`)
- `lucy_library_resources_total` — gauge with `resource_type` label

Example Prometheus scrape configuration:

```yaml
scrape_configs:
  - job_name: 'lucy'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

## 6. First Login

1. Start the backend and frontend.
2. Open the frontend URL (default: `http://localhost:3000`).
3. Log in with the credentials set in `ADMIN_USERNAME` and `ADMIN_PASSWORD`.
4. Register the first agent and test connectivity with a simple `heartbeat` or `screenshot` task.
