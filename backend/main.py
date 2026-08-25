import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.types import Receive, Scope, Send

from config import settings
from dependencies import limiter

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("lucy")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle handler."""
    logger.info("=== Lucy Defense Platform starting up ===")

    from database import initialize_database, seed_admin_user

    initialize_database()
    seed_admin_user()

    from core.log_manager import LogManager
    from core.ws_manager import ConnectionManager
    from core.heartbeat_buffer import HeartbeatBuffer
    from core.result_buffer import ResultBuffer
    from core.chat_buffer import ChatBuffer

    log_manager = LogManager()
    await log_manager.start()

    ws_manager = ConnectionManager()
    await ws_manager.start_keepalive()

    heartbeat_buffer = HeartbeatBuffer()
    result_buffer = ResultBuffer()
    chat_buffer = ChatBuffer()
    await heartbeat_buffer.start()
    await result_buffer.start()
    await chat_buffer.start()

    app.state.ws_manager = ws_manager
    app.state.log_manager = log_manager
    app.state.heartbeat_buffer = heartbeat_buffer
    app.state.result_buffer = result_buffer
    app.state.chat_buffer = chat_buffer

    from core.alert_manager import AlertManager
    alert_manager = AlertManager()
    alert_manager.load_webhooks_from_db()
    app.state.alert_manager = alert_manager

    from core.orchestrator import Orchestrator
    orchestrator = Orchestrator()
    await orchestrator.start_scheduler()
    app.state.orchestrator = orchestrator

    from core.predictive_alerting import PredictiveAlertEngine
    predictive_engine = PredictiveAlertEngine()
    await predictive_engine.start()
    app.state.predictive_engine = predictive_engine

    try:
        from core.auto_recon import AutoReconEngine
        auto_recon = AutoReconEngine()
        await auto_recon.start()
        app.state.auto_recon = auto_recon

        # Wire auto-recon to trigger on new agent connections
        async def _on_agent_connect(agent_id: str, msg: dict) -> None:
            if auto_recon.is_auto_enabled():
                logger.info("Auto-recon triggered for agent %s", agent_id)
                await auto_recon.trigger_recon(agent_id)

        ws_manager.register_handler("heartbeat", _on_agent_connect)
    except ImportError:
        logger.debug("auto_recon not available — skipping.")

    # Start in-memory task worker in portable mode (no Redis/Celery)
    try:
        from core.task_queue import in_memory_worker, PORTABLE_MODE
        if PORTABLE_MODE:
            in_memory_worker.start()
            app.state.in_memory_worker = in_memory_worker
    except Exception as exc:
        logger.debug("In-memory task worker not started: %s", exc)

    # Seed built-in modules from backend/modules/ directory
    try:
        from core.module_manager import ModuleManager
        import pathlib
        modules_dir = str(pathlib.Path(__file__).resolve().parent / "modules")
        mm = ModuleManager()
        count = mm.seed_from_directory(modules_dir)
        if count > 0:
            logger.info("Auto-seeded %d modules from %s.", count, modules_dir)
    except Exception as exc:
        logger.debug("Module auto-seed skipped: %s", exc)

    # Seed PoC templates and build packs from data files
    try:
        from core.poc_library import seed_poc_templates
        seed_poc_templates()
    except Exception as exc:
        logger.debug("PoC library seed skipped: %s", exc)

    try:
        from core.build_packs import seed_build_packs
        seed_build_packs()
    except Exception as exc:
        logger.debug("Build packs seed skipped: %s", exc)

    # Seed MITRE ATT&CK strategy data, playbooks, campaigns, findings
    try:
        from core.seed_demo import seed_strategy_data
        seed_strategy_data()
    except Exception as exc:
        logger.debug("Strategy demo seed skipped: %s", exc)

    # Sync existing entities into the Resource Library index
    try:
        from core.library.sync import sync_existing_resources
        from core.library import registry
        registry.load_all_providers()
        sync_counts = sync_existing_resources()
        logger.info("Resource Library synced: %d resources.", sum(sync_counts.values()))
    except Exception as exc:
        logger.warning("Library sync skipped: %s", exc)

    logger.info("Lucy Defense Platform ready. Listening on %s:%d", settings.HOST, settings.PORT)

    yield

    logger.info("=== Lucy Defense Platform shutting down ===")
    await ws_manager.stop_keepalive()
    await log_manager.stop()
    await heartbeat_buffer.stop()
    await result_buffer.stop()
    await chat_buffer.stop()
    await predictive_engine.stop()
    if hasattr(app.state, "auto_recon"):
        await app.state.auto_recon.stop()
    if hasattr(app.state, "in_memory_worker"):
        app.state.in_memory_worker.stop()
    try:
        from core.screenshot_scheduler import ScreenshotScheduler
        await ScreenshotScheduler().stop()
    except Exception:
        pass
    logger.info("Shutdown complete.")


class WebSocketSafeStaticFiles(StaticFiles):
    """StaticFiles mount that refuses non-HTTP scopes instead of raising."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1000})
            return
        if scope["type"] != "http":
            return
        await super().__call__(scope, receive, send)


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Lucy — Defensive Security Monitoring Platform",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS or ["http://localhost:3000"],
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Requested-With",
            "Accept",
            "Origin",
            "Referer",
            "User-Agent",
            "X-CSRF-Token",
        ],
    )

    from middleware import JWTAuthMiddleware, PrometheusMiddleware, RBACMiddleware, RequestLoggingMiddleware

    # Order: Prometheus first (capture all traffic), then auth, then logging.
    app.add_middleware(PrometheusMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RBACMiddleware)
    app.add_middleware(JWTAuthMiddleware)

    _register_routers(app)

    if settings.PORTABLE_MODE:
        dist_path = (Path(__file__).resolve().parent / settings.FRONTEND_DIST_PATH).resolve()
        if dist_path.exists() and dist_path.is_dir():
            from starlette.responses import FileResponse

            assets_path = dist_path / "assets"
            if assets_path.exists() and assets_path.is_dir():
                app.mount(
                    "/assets",
                    WebSocketSafeStaticFiles(directory=str(assets_path)),
                    name="frontend-assets",
                )

            @app.get("/{path:path}")
            async def serve_spa(path: str) -> FileResponse:
                file_path = dist_path / path
                if file_path.exists() and file_path.is_file():
                    return FileResponse(str(file_path))
                return FileResponse(str(dist_path / "index.html"))

            logger.info("Serving frontend from %s", dist_path)
        else:
            logger.warning("Portable mode enabled but frontend dist not found at %s", dist_path)

    return app


def _register_routers(app: FastAPI) -> None:
    from api.health import router as health_router
    from api.ws import router as ws_router

    app.include_router(health_router)
    app.include_router(ws_router)

    try:
        from api.metrics import router as metrics_router

        app.include_router(metrics_router)
    except ImportError:
        logger.debug("api.metrics not yet implemented — skipping.")

    try:
        from api.auth import router as auth_router

        app.include_router(auth_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.auth not yet implemented — skipping.")

    try:
        from api.agents import router as agents_router

        app.include_router(agents_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.agents not yet implemented — skipping.")

    try:
        from api.tasks import router as tasks_router

        app.include_router(tasks_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.tasks not yet implemented — skipping.")

    try:
        from api.modules import router as modules_router

        app.include_router(modules_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.modules not yet implemented — skipping.")

    try:
        from api.timelines import router as timelines_router, pocs_router

        app.include_router(timelines_router, prefix="/api/v1")
        app.include_router(pocs_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.timelines not yet implemented — skipping.")

    try:
        from api.groups import router as groups_router

        app.include_router(groups_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.groups not yet implemented — skipping.")

    try:
        from api.credentials import router as credentials_router

        app.include_router(credentials_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.credentials not yet implemented — skipping.")

    try:
        from api.logs import router as logs_router

        app.include_router(logs_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.logs not yet implemented — skipping.")

    try:
        from api.monitor import router as monitor_router

        app.include_router(monitor_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.monitor not yet implemented — skipping.")

    try:
        from api.build import router as build_router

        app.include_router(build_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.build not yet implemented — skipping.")

    try:
        from api.build_packs import router as build_packs_router

        app.include_router(build_packs_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.build_packs not yet implemented — skipping.")

    try:
        from api.reports import router as reports_router

        app.include_router(reports_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.reports not yet implemented — skipping.")

    try:
        from api.alerts import router as alerts_router

        app.include_router(alerts_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.alerts not yet implemented — skipping.")

    try:
        from api.findings import router as findings_router

        app.include_router(findings_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.findings not yet implemented — skipping.")

    try:
        from api.setup import router as setup_router

        app.include_router(setup_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.setup not yet implemented — skipping.")

    try:
        from api.files import router as files_router

        app.include_router(files_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.files not yet implemented — skipping.")

    try:
        from api.tenants import router as tenants_router

        app.include_router(tenants_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.tenants not yet implemented — skipping.")

    try:
        from api.graphql import router as graphql_router

        app.include_router(graphql_router)
    except ImportError:
        logger.debug("api.graphql not yet implemented — skipping.")

    try:
        from api.audit import router as audit_router

        app.include_router(audit_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.audit not yet implemented — skipping.")

    try:
        from api.search import router as search_router

        app.include_router(search_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.search not yet implemented — skipping.")

    try:
        from api.ai_agent import router as ai_agent_router

        app.include_router(ai_agent_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.ai_agent not yet implemented — skipping.")

    try:
        from api.ai_chat import router as ai_chat_router

        app.include_router(ai_chat_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.ai_chat not yet implemented — skipping.")

    try:
        from api.dashboard import router as dashboard_router

        app.include_router(dashboard_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.dashboard not yet implemented — skipping.")

    try:
        from api.chat import router as chat_router

        app.include_router(chat_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.chat not yet implemented — skipping.")

    try:
        from api.strategy import router as strategy_router

        app.include_router(strategy_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.strategy not yet implemented — skipping.")

    try:
        from api.config import router as config_router

        app.include_router(config_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.config not yet implemented — skipping.")

    try:
        from api.c2_profiles import router as c2_profiles_router

        app.include_router(c2_profiles_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.c2_profiles not yet implemented — skipping.")

    try:
        from api.redirectors import router as redirectors_router

        app.include_router(redirectors_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.redirectors not yet implemented — skipping.")

    # --- New Tier 1-3 routers ---
    try:
        from api.operators import router as operators_router
        app.include_router(operators_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.operators not yet implemented — skipping.")

    try:
        from api.rbac import router as rbac_router
        app.include_router(rbac_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.rbac not yet implemented — skipping.")

    try:
        from api.auto_recon import router as auto_recon_router
        app.include_router(auto_recon_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.auto_recon not yet implemented — skipping.")

    try:
        from api.screenshot_scheduler import router as screenshot_scheduler_router
        app.include_router(screenshot_scheduler_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.screenshot_scheduler not yet implemented — skipping.")

    # --- Defensive security router ---
    try:
        from api.defense import router as defense_router
        app.include_router(defense_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.defense not yet implemented — skipping.")

    # --- Threat intelligence router (CVE/NVD) ---
    try:
        from api.threat_intel import router as threat_intel_router
        app.include_router(threat_intel_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.threat_intel not yet implemented — skipping.")

    # --- Resource Library router ---
    try:
        from api.library import router as library_router
        app.include_router(library_router, prefix="/api/v1")
    except ImportError:
        logger.debug("api.library not yet implemented — skipping.")


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
