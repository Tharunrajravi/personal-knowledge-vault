"""
main.py — FastAPI application entry point

Startup sequence:
  1. Load config from SSM (or .env for local dev)
  2. Create DB tables + install search trigger
  3. Warm up Redis connection
  4. Register all routes
  5. Start serving

Health check at /health — used by ALB target group health checks.
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import init_db, close_db, get_redis

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup/shutdown) ───────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler.
    Everything before yield runs on startup.
    Everything after yield runs on shutdown.
    """
    settings = get_settings()
    logger.info(f"Starting PKV API [{settings.app_env}]")

    # Initialize database (create tables, install triggers)
    await init_db()
    logger.info("Database ready")

    # Warm up Redis connection
    redis = await get_redis()
    await redis.ping()
    logger.info("Redis ready")

    logger.info("PKV API ready to serve requests")
    yield

    # Shutdown
    logger.info("Shutting down PKV API...")
    await close_db()
    logger.info("Connections closed")


# ── App factory ───────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Personal Knowledge Vault API",
        version="1.0.0",
        description="Save, tag, search, and manage your knowledge links.",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request logging middleware ────────────────────────────────────────────
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"{request.method} {request.url.path} "
            f"→ {response.status_code} ({duration_ms:.1f}ms)"
        )
        return response

    # ── Rate limiting middleware ──────────────────────────────────────────────
    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        settings = get_settings()
        try:
            from app.database import CacheManager
            redis = await get_redis()
            cache = CacheManager(redis)

            # Use IP as rate limit key
            client_ip = request.client.host
            key = f"ratelimit:{client_ip}"
            count = await cache.increment(key, ttl=settings.rate_limit_window_seconds)

            if count > settings.rate_limit_requests:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many requests. Please slow down."},
                    headers={"Retry-After": str(settings.rate_limit_window_seconds)},
                )
        except Exception:
            pass  # Don't break requests if Redis is down

        return await call_next(request)

    # ── Routes ────────────────────────────────────────────────────────────────
    from app.routes.auth import router as auth_router
    from app.routes.links import router as links_router
    from app.routes.scraper import router as scraper_router
    from app.routes.extras import tags_router, dashboard_router, export_router

    app.include_router(auth_router,      prefix="/api")
    app.include_router(links_router,     prefix="/api")
    app.include_router(scraper_router,   prefix="/api")
    app.include_router(tags_router,      prefix="/api")
    app.include_router(dashboard_router, prefix="/api")
    app.include_router(export_router,    prefix="/api")

    # ── Health check ─────────────────────────────────────────────────────────
    # ALB calls this every 30 seconds. Must return 200 for the task to receive traffic.
    @app.get("/health", tags=["infrastructure"])
    async def health_check():
        checks = {"api": "ok", "database": "unknown", "cache": "unknown"}

        try:
            from app.database import get_engine
            from sqlalchemy import text
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {str(e)[:50]}"

        try:
            redis = await get_redis()
            await redis.ping()
            checks["cache"] = "ok"
        except Exception as e:
            checks["cache"] = f"error: {str(e)[:50]}"

        all_ok = all(v == "ok" for v in checks.values())
        return JSONResponse(
            content={"status": "healthy" if all_ok else "degraded", **checks},
            status_code=200,  # Always 200 so ALB doesn't kill the task
        )

    # ── Root ──────────────────────────────────────────────────────────────────
    @app.get("/", tags=["infrastructure"])
    async def root():
        return {
            "name": "Personal Knowledge Vault API",
            "version": "1.0.0",
            "docs": "/docs",
        }

    return app


# ── Entry point ───────────────────────────────────────────────────────────────
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
