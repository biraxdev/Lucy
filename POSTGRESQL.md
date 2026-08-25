# PostgreSQL backend support

Lucy can use PostgreSQL instead of the default SQLite file. SQLite remains the default for local development; PostgreSQL is useful for heavier workloads or concurrent access.

## Windows PostgreSQL installation

1. Download the installer from <https://www.postgresql.org/download/windows/> (EDB installer is the easiest on Windows).
2. Run the installer and accept the defaults. Note the port (default `5432`) and the `postgres` superuser password.
3. Make sure the PostgreSQL service is running (`Services` → `postgresql-x64-<version>` → Running).

## Create the `lucy` database and user

Open **pgAdmin** or `psql` and run:

```sql
CREATE USER lucy WITH PASSWORD 'password' CREATEDB;
CREATE DATABASE lucy OWNER lucy;
GRANT ALL PRIVILEGES ON DATABASE lucy TO lucy;
```

You can replace `password` with a stronger value. The `CREATEDB` right is only needed for the initial setup.

## Install the Python driver

From the repository root:

```powershell
cd backend
.venv\Scripts\python -m pip install psycopg2-binary==2.9.10
```

Or install everything in `requirements.txt` if you are setting the environment up from scratch.

## Point Lucy at PostgreSQL

Set the `DATABASE_URL` environment variable for the shell that will run the backend. Do not commit database credentials.

PowerShell:

```powershell
$env:DATABASE_URL = "postgresql://lucy:password@localhost:5432/lucy"
```

cmd:

```cmd
set DATABASE_URL=postgresql://lucy:password@localhost:5432/lucy
```

The default `DATABASE_URL` in `backend/.env` is left at `sqlite:///./lucy.db` so SQLite stays the default. The environment variable override takes precedence.

## Run migrations and seed

Migrations and the admin user seed run automatically when the FastAPI app starts. From `backend`:

```powershell
.venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Alternatively:

```powershell
.venv\Scripts\python main.py
```

Watch the logs for `Database tables created/verified ...` and the admin seed message.

## Switch back to SQLite

Stop the backend, then either:

- Remove the `DATABASE_URL` environment variable override, or
- Set `DATABASE_URL=sqlite:///./lucy.db` before starting.

The `backend/.env` file keeps `DATABASE_URL=sqlite:///./lucy.db`, so the default local dev behavior is unchanged.
