"""Shared pytest fixtures for the Lucy backend Phase 1 test suite."""
import atexit
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TESTS_DIR.parent
TEST_DB = TESTS_DIR / "test.db"

# Make sure backend imports work from the tests directory.
sys.path.insert(0, str(BACKEND_DIR))

# Force a temporary SQLite database and strong test-only secrets.
# The real .env is intentionally not used for test credentials.
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["JWT_SECRET"] = "test_jwt_secret_value_32_bytes_long_xxxxxxxx"
os.environ["JWT_REFRESH_SECRET"] = "test_jwt_refresh_value_32_bytes_long_xxxxx"
os.environ["MASTER_KEY"] = "test_master_key_value_32_bytes_long_xxxxxxxxx"
os.environ["ADMIN_USERNAME"] = "lucy_test_admin"
os.environ["ADMIN_PASSWORD"] = "T3stP@ssw0rd!2024"

from database import database, initialize_database, seed_admin_user  # noqa: E402
from dependencies import limiter  # noqa: E402
from main import app  # noqa: E402


def _remove_db_files() -> None:
    for suffix in ("", "-wal", "-shm"):
        path = TESTS_DIR / f"test.db{suffix}"
        try:
            path.unlink(missing_ok=True)
        except PermissionError:
            pass


atexit.register(_remove_db_files)


@pytest.fixture(autouse=True)
def setup_db():
    """Create a fresh temp database and seed the admin user before every test."""
    _remove_db_files()
    limiter.reset()
    initialize_database()
    seed_admin_user()
    yield
    try:
        database.close()
    except Exception:
        pass
    _remove_db_files()


@pytest.fixture
def client(setup_db):
    """Synchronous FastAPI TestClient."""
    c = TestClient(app)
    yield c
    c.close()
