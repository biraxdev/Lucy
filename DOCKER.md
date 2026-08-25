# Lucy Docker Guide

This document covers running the Lucy backend and optional services with Docker.

## Quick Start

1. Copy the example environment file and set real values:

   ```powershell
   Copy-Item .env.example .env      # Windows
   # or
   cp .env.example .env             # Linux / macOS
   ```

2. Edit `.env` and replace all `CHANGE_ME_*` placeholders with strong, unique
   values. At minimum set:

   - `JWT_SECRET`
   - `JWT_REFRESH_SECRET`
   - `MASTER_KEY`
   - `ADMIN_USERNAME`
   - `ADMIN_PASSWORD`

   Do not commit `.env` to Git; it is already ignored by `.dockerignore`.

3. Build and start the stack:

   ```bash
   docker compose up --build -d
   ```

4. Open the health endpoint in a browser or with curl:

   ```bash
   curl http://localhost:8000/health
   ```

## Services

- `lucy-backend` — FastAPI backend built from `Dockerfile` in the project root.
  Exposes port `8000` and depends on Redis.
- `redis` — `redis:7-alpine` on port `6379`, used as the broker/result backend.
- `lucy-frontend` (optional) — Node 20 container that installs, builds, and
  serves the frontend on port `3000`. Start it with:

  ```bash
  docker compose --profile frontend up --build -d
  ```

## Volume Mapping

- `./data:/app/data` — persists the SQLite database and generated reports on the
  host so data survives container restarts.
- `./frontend:/app` — used only by the optional `lucy-frontend` service for live
  source mounting.

## Common Commands

```bash
# Start everything in the background
docker compose up -d

# Rebuild and start
docker compose up --build -d

# View backend logs
docker compose logs -f lucy-backend

# Restart only the backend
docker compose restart lucy-backend

# Stop all services but keep volumes
docker compose down

# Stop all services and remove named volumes
docker compose down -v

# Run a one-off shell in the backend container
docker compose exec lucy-backend sh
```

## Environment Notes

- The compose file sets `ENVIRONMENT=production` explicitly.
- `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` point to the
  `redis` service automatically; no manual Redis URL is required unless you run
  outside of Docker.
- `lucy-backend` waits for Redis to report healthy before it starts.
- The backend image exposes port `8000` and provides a `HEALTHCHECK` on
  `/health`.
