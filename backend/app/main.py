from fastapi import FastAPI

from app.api import auth, health
from app.db import Base, engine

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


app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])


@app.get("/")
async def root():
    return {"service": "SmartPantry API", "docs": "/docs"}
