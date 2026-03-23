import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, detections, health, images, inventory, recipes
from app.core.config import get_settings
from app.db import Base, engine, ensure_sqlite_schema_compatibility
from app.services.detection import preload_detection_backend
from app.services.images import cleanup_expired_images_with_own_session


logger = logging.getLogger(__name__)


async def image_retention_worker(interval_seconds: int, batch_limit: int, stop_event: asyncio.Event):
    while True:
        deleted_count = await asyncio.to_thread(
            cleanup_expired_images_with_own_session,
            limit=batch_limit,
        )
        if deleted_count:
            logger.info("Image retention cleanup removed %s expired image(s).", deleted_count)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            break
        except TimeoutError:
            continue


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
    cleanup_expired_images_with_own_session(limit=settings.image_cleanup_batch_limit)
    try:
        await asyncio.to_thread(preload_detection_backend)
    except Exception:
        logger.exception("Detection backend warmup failed; first detection request may be slower.")

    stop_event = asyncio.Event()
    worker_task: asyncio.Task[None] | None = None
    if settings.image_cleanup_interval_minutes > 0:
        worker_task = asyncio.create_task(
            image_retention_worker(
                interval_seconds=max(settings.image_cleanup_interval_minutes, 1) * 60,
                batch_limit=max(settings.image_cleanup_batch_limit, 1),
                stop_event=stop_event,
            )
        )

    try:
        yield
    finally:
        if worker_task is not None:
            stop_event.set()
            await worker_task


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
