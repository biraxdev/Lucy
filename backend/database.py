import logging
from pathlib import Path
from urllib.parse import urlparse

from peewee import PostgresqlDatabase, SqliteDatabase

from config import settings

logger = logging.getLogger(__name__)

_SQLITE_PRAGMAS = {
    "journal_mode": "wal",
    "cache_size": -1 * 256000,          # 256 MB page cache
    "mmap_size": 64_000_000,            # 64 MB memory-mapped I/O
    "temp_store": "memory",
    "foreign_keys": 1,
    "ignore_check_constraints": 0,
    "synchronous": "normal",            # WAL tolerates normal safely
    "wal_autocheckpoint": 1000,
    "busy_timeout": 5000,
}


def _sqlite_database(url: str) -> tuple[SqliteDatabase, str]:
    """Return a SqliteDatabase plus its filesystem path."""
    db_path = url.replace("sqlite:///", "")
    return SqliteDatabase(db_path, pragmas=_SQLITE_PRAGMAS), db_path


def _postgresql_database(url: str) -> PostgresqlDatabase:
    """Return a PostgresqlDatabase from a postgresql:// URL."""
    parsed = urlparse(url)
    dbname = parsed.path.lstrip("/") if parsed.path else "lucy"
    return PostgresqlDatabase(
        dbname,
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname,
        port=parsed.port or 5432,
        autorollback=True,
    )


def create_database() -> tuple[SqliteDatabase | PostgresqlDatabase, str | None]:
    """Factory returning the correct Peewee database for DATABASE_URL."""
    url = settings.DATABASE_URL
    scheme = url.split("://", 1)[0].lower()

    if scheme == "sqlite":
        return _sqlite_database(url)
    if scheme == "postgresql":
        return _postgresql_database(url), None

    raise ValueError(
        f"Unsupported DATABASE_URL scheme '{scheme}'. "
        "Use sqlite:///path/to/db or postgresql://user:pass@host:port/db."
    )


database, db_path = create_database()


def initialize_database() -> None:
    """Create tables and run migrations."""
    from db.models import ALL_MODELS
    from db.migrations import run_migrations

    if db_path is not None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    with database:
        database.create_tables(ALL_MODELS, safe=True)
    logger.info("Database tables created/verified (%d models).", len(ALL_MODELS))
    run_migrations()


def seed_admin_user() -> None:
    """Create default admin user or sync its password from the environment."""
    import secrets
    import time

    import bcrypt
    import peewee

    from core.auth import verify_password
    from db.models import User

    for attempt in range(5):
        try:
            with database.atomic():
                user = User.get_or_none(User.username == settings.ADMIN_USERNAME)
                if user is None:
                    if User.select().count() == 0:
                        user = User.create(
                            username=settings.ADMIN_USERNAME,
                            password_hash=bcrypt.hashpw(
                                settings.ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt()
                            ).decode("utf-8"),
                            role="admin",
                            api_key=secrets.token_hex(32),
                        )
                        logger.info(
                            "Admin user '%s' created.",
                            settings.ADMIN_USERNAME,
                        )
                    else:
                        logger.debug("Admin seed skipped — users already exist.")
                elif not verify_password(settings.ADMIN_PASSWORD, user.password_hash):
                    # Keep admin password in sync with .env unless the user explicitly changed it.
                    user.password_hash = bcrypt.hashpw(
                        settings.ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt()
                    ).decode("utf-8")
                    user.save()
                    logger.info("Admin password synced from environment.")
                else:
                    logger.debug("Admin password already matches environment.")
            return
        except peewee.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < 4:
                wait = 0.2 * (attempt + 1)
                logger.warning("DB locked during seed, retrying in %.1fs...", wait)
                time.sleep(wait)
                continue
            logger.warning("Admin seed operational error: %s", exc)
            return
