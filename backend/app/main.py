"""
SafeSite FastAPI application — entry point.
Mounts all routers, configures middleware, manages lifespan.
"""

import logging

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.v1.auth import router as auth_router
from app.api.v1.detect import router as detect_router
from app.api.v1.violations import jobs_router, router as violations_router
from app.core.cache import cache
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

if settings.SENTRY_DSN and settings.is_production:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.2)

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
    )

    # --- Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )

    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["yourdomain.com", "*.yourdomain.com"],
        )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # --- Lifespan ---
    @app.on_event("startup")
    async def startup() -> None:
        await cache.connect()
        logger.info("SafeSite API started — Redis connected")

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await cache.disconnect()

    # --- Routers ---
    app.include_router(auth_router,       prefix="/api/v1")
    app.include_router(detect_router,     prefix="/api/v1")
    app.include_router(violations_router, prefix="/api/v1")
    app.include_router(jobs_router,       prefix="/api/v1")

    @app.get("/health", tags=["health"], include_in_schema=False)
    async def health() -> dict:
        return {"status": "ok", "version": "1.0.0"}

    return app


app = create_app()
