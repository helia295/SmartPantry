from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, detections, health, images, inventory, recipes
from app.core.config import get_settings
from app.db import Base, engine, ensure_sqlite_schema_compatibility


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    Ensure database tables exist.

    For the MVP we use simple auto-creation on startup against SQLite.
    Later this can be replaced by migrations when we move to Postgres.
    """
    settings = get_settings()

    for warning in settings.deployment_warnings():
        logger.warning("Deployment configuration warning: %s", warning)

    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema_compatibility()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="SmartPantry API",
        description="AI-powered kitchen inventory and recipe recommendations",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
    app.include_router(images.router, prefix="/images", tags=["images"])
    app.include_router(detections.router, prefix="/detections", tags=["detections"])
    app.include_router(recipes.router, prefix="/recipes", tags=["recipes"])

    @app.get("/")
    async def root():
        return {"service": "SmartPantry API", "docs": "/docs"}

    return app


app = create_app()
