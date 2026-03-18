from fastapi import FastAPI

from app.api import auth, detections, health, images, inventory, recipes
from app.db import Base, engine, ensure_sqlite_schema_compatibility

app = FastAPI(
    title="SmartPantry API",
    description="AI-powered kitchen inventory and recipe recommendations",
    version="0.1.0",
)


@app.on_event("startup")
def on_startup() -> None:
    """
    Ensure database tables exist.

    For the MVP we use simple auto-creation on startup against SQLite.
    Later this can be replaced by migrations when we move to Postgres.
    """
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema_compatibility()


app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
app.include_router(images.router, prefix="/images", tags=["images"])
app.include_router(detections.router, prefix="/detections", tags=["detections"])
app.include_router(recipes.router, prefix="/recipes", tags=["recipes"])


@app.get("/")
async def root():
    return {"service": "SmartPantry API", "docs": "/docs"}
