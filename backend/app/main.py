"""FastAPI application factory + lifespan."""

import os
import threading
import time
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.health import router as health_router
from app.api.router import api_router
from app.api.ws_events import router as ws_events_router
from app.api.ws_live import router as ws_live_router
from app.config import settings
from app.middleware.cors import setup_cors
from app.services.connection_manager import get_connection_manager
from app.utils.errors import register_exception_handlers
from app.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


# Paths that generate noise — skip logging entirely
_SILENT_PATHS = {"/health", "/api/v1/health", "/favicon.ico"}


class LoggingMiddleware(BaseHTTPMiddleware):
    """Production-grade HTTP request logger.

    * Health-check / favicon requests are silenced.
    * Successful (2xx) responses are logged at DEBUG.
    * Non-2xx responses are logged at WARNING with timing.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in _SILENT_PATHS:
            return await call_next(request)

        import time as _t

        start = _t.monotonic()
        response = await call_next(request)
        elapsed_ms = round((_t.monotonic() - start) * 1000, 1)

        log_kw = dict(
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=elapsed_ms,
        )
        if response.status_code >= 400:
            logger.warning("http", **log_kw)
        else:
            logger.debug("http", **log_kw)

        return response


def _force_exit_delayed() -> None:
    """Force-exit after 1.5 seconds to bypass the Python 3.14 + concurrent.futures hang."""
    time.sleep(1.5)
    os._exit(0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    setup_logging(settings.LOG_LEVEL)
    logger.info(
        "backend_starting",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )

    # Log active service backends for operational clarity
    logger.info(
        "service_backends",
        vertex_ai=settings.GOOGLE_GENAI_USE_VERTEXAI,
        agent_engine_sessions=settings.USE_AGENT_ENGINE_SESSIONS,
        agent_engine_memory=settings.USE_AGENT_ENGINE_MEMORY_BANK,
        agent_engine_code_exec=settings.USE_AGENT_ENGINE_CODE_EXECUTION,
        project=settings.GOOGLE_CLOUD_PROJECT or "(not set)",
        location=settings.GOOGLE_CLOUD_LOCATION,
    )

    # Eager validation: if Vertex AI is on, required config must be present
    if settings.GOOGLE_GENAI_USE_VERTEXAI and not settings.GOOGLE_CLOUD_PROJECT:
        raise RuntimeError(
            "GOOGLE_GENAI_USE_VERTEXAI=True but GOOGLE_CLOUD_PROJECT is not set. "
            "Set GOOGLE_CLOUD_PROJECT in .env or disable Vertex AI."
        )

    # Start the heartbeat reaper so stale WS connections are cleaned up
    mgr = get_connection_manager()
    mgr.start_reaper()

    # Start in-process cron runner. In development this is the primary
    # trigger mechanism. In production it stays off by default to avoid
    # double-trigger races with Cloud Scheduler, but can be enabled
    # explicitly for fallback behavior.
    _scheduler_svc = None
    try:
        from app.services.scheduler_service import get_scheduler_service

        _scheduler_svc = get_scheduler_service()
        should_run_local_cron = (
            not settings.is_production
            or settings.ENABLE_LOCAL_CRON_IN_PRODUCTION
        )
        if should_run_local_cron:
            poll = 60.0 if settings.is_production else 15.0
            await _scheduler_svc.start_local_cron(poll_interval=poll)
        else:
            logger.info("local_cron_disabled_in_production")
    except Exception:
        logger.warning("cron_runner_start_failed", exc_info=True)

    yield

    # Shutdown — stop local cron + reaper + close MCP/plugin connections
    if _scheduler_svc:
        with suppress(Exception):
            await _scheduler_svc.stop_local_cron()
    mgr.stop_reaper()
    try:
        from app.services.plugin_registry import get_plugin_registry

        await get_plugin_registry().shutdown()
    except Exception:
        pass
    try:
        from app.services.mcp_manager import get_mcp_manager

        await get_mcp_manager().shutdown()
    except Exception:
        pass
    try:
        from app.services.e2b_desktop_service import get_e2b_desktop_service

        await get_e2b_desktop_service().destroy_all()
    except Exception:
        pass
    logger.info("backend_shutting_down")
    # Launch a delayed suicide sequence to avoid hanging on Windows thread pool teardown
    threading.Thread(target=_force_exit_delayed, daemon=True).start()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # Trust proxy headers (X-Forwarded-Proto etc.) so redirects use https://
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

    # Add logging middleware first
    app.add_middleware(LoggingMiddleware)

    # Subscription billing middleware (runs after auth, before route handlers)
    # Registration order is reversed: last added = first executed.
    # Desired order: Auth → Subscription → UsageGate → Handler
    from app.middleware.usage_gate import UsageGateMiddleware
    from app.middleware.subscription_middleware import SubscriptionMiddleware
    from app.middleware.auth_middleware import AuthMiddleware
    app.add_middleware(UsageGateMiddleware)          # 4th in chain
    app.add_middleware(SubscriptionMiddleware)        # 3rd in chain
    app.add_middleware(AuthMiddleware)                # 2nd in chain (after CORS)

    # Middleware
    setup_cors(app)

    # Exception handlers
    register_exception_handlers(app)

    # Routes — root /health for Cloud Run probe
    app.include_router(health_router, tags=["health"])
    # All API routes under /api/v1
    app.include_router(api_router)

    # WebSocket routes under /ws
    app.include_router(ws_live_router, prefix="/ws", tags=["websocket"])
    app.include_router(ws_events_router, prefix="/ws", tags=["websocket"])

    return app


app = create_app()
