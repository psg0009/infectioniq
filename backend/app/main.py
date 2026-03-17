"""
InfectionIQ Backend API
Main FastAPI application entry point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import select
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
import logging

from app.config import settings, validate_production_config
from app.core.database import init_db, close_db
from app.core.redis import init_redis, close_redis
from app.core.audit import AuditMiddleware
from app.core.rate_limit import RateLimitMiddleware
from app.core.security_controls import SecurityHeadersMiddleware
from app.core.tenant import TenantMiddleware
from app.core.metrics_middleware import MetricsMiddleware
from app.services.scheduler import scheduler
from app.api.v1.router import api_router
from app.api.websocket import websocket_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting InfectionIQ API...")

    # Validate production configuration
    config_warnings = validate_production_config(settings)
    for w in config_warnings:
        logger.warning(f"Config issue: {w}")
    if config_warnings and settings.ENVIRONMENT == "production":
        raise RuntimeError(
            f"Production config validation failed: {'; '.join(config_warnings)}"
        )

    await init_db()
    await init_redis()
    await scheduler.start()
    logger.info("InfectionIQ API started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down InfectionIQ API...")
    await scheduler.stop()
    await close_db()
    await close_redis()
    logger.info("InfectionIQ API shut down complete")


# Create FastAPI application
app = FastAPI(
    title="InfectionIQ API",
    description="AI-Powered Surgical Infection Prevention System",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    default_response_class=ORJSONResponse,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Audit trail middleware (logs mutating requests)
app.add_middleware(AuditMiddleware)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware, requests_per_minute=120)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Tenant isolation middleware
app.add_middleware(TenantMiddleware)

# Prometheus HTTP metrics middleware
app.add_middleware(MetricsMiddleware)

# Include routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(websocket_router, prefix="/ws")


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API health check"""
    return {
        "status": "healthy",
        "service": "InfectionIQ API",
        "version": settings.APP_VERSION
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check endpoint with component-level breakdown"""
    import time
    from app.core.database import async_session_maker
    from app.core.redis import get_redis
    from app.api.v1.cameras import _camera_registry

    components = {}
    overall = "healthy"

    # Database check
    try:
        async with async_session_maker() as session:
            await session.execute(select(1))
        components["database"] = {"status": "connected"}
    except Exception as e:
        components["database"] = {"status": "error", "detail": str(e)}
        overall = "degraded"

    # Redis check
    try:
        redis = await get_redis()
        await redis.ping()
        components["redis"] = {"status": "connected"}
    except Exception as e:
        components["redis"] = {"status": "error", "detail": str(e)}
        overall = "degraded"

    # Scheduler status
    components["scheduler"] = {"tasks": scheduler.get_status()}

    # Camera summary
    total_cams = len(_camera_registry)
    online_cams = sum(1 for c in _camera_registry.values() if c.status == "ONLINE")
    offline_cams = sum(1 for c in _camera_registry.values() if c.status == "OFFLINE")
    components["cameras"] = {
        "total": total_cams,
        "online": online_cams,
        "offline": offline_cams,
        "health_percent": (online_cams / total_cams * 100) if total_cams > 0 else 0,
    }

    return {
        "status": overall,
        "version": settings.APP_VERSION,
        "timestamp": time.time(),
        "components": components,
    }


@app.get("/metrics", tags=["Monitoring"], include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint"""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from fastapi.responses import Response
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
