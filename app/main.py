"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import api_router
from app.core.config import AppConfig, Settings, get_app_config, get_settings
from app.core.exceptions import AppError
from app.core.logging import setup_logging
from app.core.paths import expand
from app.core.security import redact
from app.database.migrate import upgrade_database
from app.database.session import Database
from app.services.job_service import JobRunner

logger = logging.getLogger(__name__)

# Defends against DNS-rebinding: the API only answers to loopback host names.
LOCAL_HOSTS = ["127.0.0.1", "localhost", "[::1]", "testserver"]


def create_app(settings: Settings | None = None, config: AppConfig | None = None) -> FastAPI:
    settings = settings or get_settings()
    config = config or get_app_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        setup_logging(config.logging.level, expand(config.logging.directory))
        upgrade_database(settings.resolved_database_url)
        db = Database(settings.resolved_database_url)
        runner = JobRunner(db, config)
        recovered = runner.recover_interrupted()
        if recovered:
            logger.warning("Marked %d interrupted job(s) as failed.", recovered)
        app.state.db, app.state.job_runner = db, runner
        if not settings.is_localhost_bind:
            logger.warning(
                "API is bound to %s, not localhost. Anyone who can reach this port can read "
                "your projects. See docs/security.md.",
                settings.app_host,
            )
        try:
            yield
        finally:
            runner.shutdown()
            db.dispose()

    app = FastAPI(
        title="AI Social Media Handler",
        version=__version__,
        description="Local-first, AI-assisted video production and publishing API.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.config = config

    if settings.is_localhost_bind:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=LOCAL_HOSTS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.app.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": redact(exc.message), "details": exc.details}},
        )

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Internal server error.", "details": {}}},
        )

    app.include_router(api_router)
    return app
