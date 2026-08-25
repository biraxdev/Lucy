# Portable Runtime for Project Lucy

Self-contained Python 3.12, Node.js 20, and Redis 5 binaries for local development. No system installation or admin rights required.

## What's included

| Tool | Version | Location |
|------|---------|----------|
| Python | 3.12.7 | `tools/python312/` |
| Node.js | 20.18.1 | `tools/node20/` |
| Redis | 5.0.14.1 | `tools/redis/` |

## Quick start

From PowerShell (in the project root):

```powershell
.\tools\activate.ps1
.\tools\start-redis.bat
```

From CMD (in the project root):

```cmd
tools\activate.bat
tools\start-redis.bat
```

After activation, `python`, `node`, `npm`, `redis-server`, `redis-cli`, and `pip` are available on `PATH` for the current shell.

## Install project dependencies

Once activated, or directly from the project root:

```cmd
tools\install-deps.bat
```

This installs backend Python requirements and frontend npm packages using the portable runtimes.

## Stop Redis

```cmd
tools\stop-redis.bat
```

## Notes

- Redis is provided by the community-maintained Windows port (5.0.14.1). It is fully compatible with the Celery broker/result backend used by Lucy, but it is not Redis 7. If you need Redis 7 features, use the Docker Compose stack (`make dev`).
- The entire `tools/` folder is relocatable; all helper scripts use relative paths based on their own location.
- To recreate the runtime from scratch, run `powershell -ExecutionPolicy Bypass -File tools\setup-portable.ps1`.
