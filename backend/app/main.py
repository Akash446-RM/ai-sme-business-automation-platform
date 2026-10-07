"""FastAPI application factory for the SME Business Automation Platform."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import check_database_connection
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Startup and shutdown hooks."""
    configure_logging()
    logger.info("Starting %s (%s)", settings.app_name, settings.environment)
    if check_database_connection():
        logger.info("Database connection verified: %s", settings.db_name)
    else:
        logger.error(
            "Database connection FAILED for '%s'. Run scripts/init_db.py and check .env",
            settings.db_name,
        )
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "Unified business automation platform for SMEs combining business "
            "management, analytics, machine learning forecasting and grounded AI agents."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["meta"], summary="Service metadata")
    def root() -> dict:
        return {
            "name": settings.app_name,
            "version": "1.0.0",
            "environment": settings.environment,
            "docs": "/docs",
            "api": settings.api_v1_prefix,
        }

    @app.get("/health", tags=["meta"], summary="Liveness and dependency health")
    def health() -> dict:
        database_ok = check_database_connection()
        return {
            "status": "ok" if database_ok else "degraded",
            "database": "ok" if database_ok else "unavailable",
            "environment": settings.environment,
        }

    return app


app = create_app()
