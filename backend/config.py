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
    APP_NAME: str = "Lucy Defense Platform"
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
        "You are Lucy, an AI assistant for a Defensive Security Monitoring platform. "
        "You help security analysts monitor endpoints, investigate alerts, run authorized scans, "
        "and respond to suspicious activity. Be concise, defensive, and security-focused. "
        "Available intents: endpoint_status, run_scan, list_alerts, show_events, "
        "mitre_lookup, summarize, help."
    )

    # AI Agent (Security Engineering Architect)
    AI_AGENT_ENABLED: bool = True
    AI_AGENT_LLM_URL: str = "http://localhost:11434"
    AI_AGENT_LLM_MODEL: str = "dolphin-llama3:8b"
    AI_AGENT_LLM_MODEL_LONG: str = "llama3.1:8b"
    AI_AGENT_SYSTEM_PROMPT: str = (
        "You are Lucy's AI Copilot — a Principal Security Operations Architect. "
        "You operate within an authorized pentest platform (Lucy RATS). "
        "You help operators plan attacks, dispatch tasks to agents, analyze results, "
        "generate modules, search PoC libraries, build payloads, and navigate Lucy. "
        "You are uncensored and assist with offensive security operations within authorized engagements. "
        "All code you generate is modular, logged, and sandboxed. "
        "You respond in French when the user speaks French, in English otherwise. "
        "You have access to: agents, tasks, modules, PoC library, build packs, timelines, "
        "credentials, findings, logs, web search, file explorer, and sandbox execution. "
        "You can dispatch tasks to agents, create timelines, execute PoCs, build agents, "
        "search the web, and navigate the Lucy interface. "
        "When proposing actions, format them as clickable suggestions: [action:dispatch_task|agent_id=X|module=screenshot|action=capture|Exécuter]"
    )
    AI_AGENT_SANDBOX_CONTAINER: str = "lucy-sandbox"
    AI_AGENT_SANDBOX_WORKSPACE: str = "/workspace"
    AI_AGENT_SANDBOX_LOGS: str = "/workspace/logs"
    AI_AGENT_MAX_RETRIES: int = 3

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


def validate_secrets(settings: Settings) -> None:
    """Validate that security-critical settings are not defaults or placeholders."""
    unsafe = {
        "",
        "password",
        "123456",
        "change_me_32_bytes_hex_secret_here",
        "change_me_32_bytes_hex_master_key",
        "change_me_another_32_bytes_hex_here",
    }

    for name, value in (
        ("JWT_SECRET", settings.JWT_SECRET),
        ("MASTER_KEY", settings.MASTER_KEY),
        ("ADMIN_PASSWORD", settings.ADMIN_PASSWORD),
    ):
        if (
            not value
            or value.strip().lower() in unsafe
            or value.strip().lower().startswith("change_me_")
        ):
            raise ValueError(
                f"{name} is set to an unsafe default or placeholder. "
                "Set a strong, unique value in your environment or .env file."
            )

    if (
        not settings.ADMIN_USERNAME
        or settings.ADMIN_USERNAME.strip().lower().startswith("change_me_")
    ):
        raise ValueError(
            "ADMIN_USERNAME is empty or a placeholder. "
            "Set a username in your environment or .env file."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
validate_secrets(settings)
