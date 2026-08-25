import logging
from pathlib import Path

from peewee import SqliteDatabase

from config import settings

logger = logging.getLogger(__name__)

db_path = settings.DATABASE_URL.replace("sqlite:///", "")
database = SqliteDatabase(
    db_path,
    pragmas={
        "journal_mode": "wal",
        "cache_size": -1 * 256000,          # 256 MB page cache
        "mmap_size": 64_000_000,            # 64 MB memory-mapped I/O
        "temp_store": "memory",
        "foreign_keys": 1,
        "ignore_check_constraints": 0,
        "synchronous": "normal",            # WAL tolerates normal safely
        "wal_autocheckpoint": 1000,
        "busy_timeout": 5000,
    },
)


def initialize_database() -> None:
    """Create tables and run migrations."""
    from db.models import ALL_MODELS
    from db.migrations import run_migrations

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
