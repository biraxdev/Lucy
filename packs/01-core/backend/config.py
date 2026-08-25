import secrets
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "Lucy C2"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "sqlite:///./lucy.db"

    # JWT
    JWT_SECRET: str = secrets.token_hex(32)
    JWT_REFRESH_SECRET: str = secrets.token_hex(32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Master key for credential encryption (32-byte hex)
    MASTER_KEY: str = secrets.token_hex(32)

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Portable mode (no Docker, backend serves the built frontend)
    PORTABLE_MODE: bool = False
    FRONTEND_DIST_PATH: str = "../frontend/dist"

    # Rate limiting
    RATE_LIMIT_PER_IP: str = "100/minute"
    RATE_LIMIT_PER_APIKEY: str = "1000/minute"
    RATE_LIMIT_AUTH: str = "10/minute"

    # Admin seed user (created on first startup)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "changeme"

    # Agent settings
    AGENT_HEARTBEAT_TIMEOUT: int = 60
    AGENT_OFFLINE_THRESHOLD: int = 120

    # Chat settings
    CHAT_HISTORY_LIMIT: int = 500
    CHAT_LOCAL_LLM_URL: str | None = None
    CHAT_LLM_MODEL: str = "llama3.2"
    CHAT_LLM_SYSTEM_PROMPT: str = (
        "You are Lucy, an AI assistant for a Red Team C2 platform. "
        "You help operators manage agents, dispatch tasks, analyze results, and suggest next steps. "
        "Be concise, tactical, and security-focused. When uncertain, use the keyword-based fallback. "
        "Available intents: agent_status, run_task, run_timeline, build_agent, show_credentials, "
        "show_findings, show_tasks, self_destruct, create_campaign, run_playbook, file_operation, "
        "add_agent_note, map_technique, summarize, help."
    )

    # Stealth pack default for chat/agent builds
    STEALTH_PACK_DEFAULT: bool = False

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_PING_TIMEOUT: int = 10

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_ROTATION_DAYS: int = 7

    # Predictive alerting
    PREDICTIVE_ALERT_INTERVAL_SECONDS: int = 300
    PREDICTIVE_ALERT_MAX_STORED: int = 500


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
