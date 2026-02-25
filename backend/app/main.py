from fastapi import FastAPI

from app.api import health

app = FastAPI(
    title="SmartPantry API",
    description="AI-powered kitchen inventory and recipe recommendations",
    version="0.1.0",
)

app.include_router(health.router, prefix="/health", tags=["health"])


@app.get("/")
async def root():
    return {"service": "SmartPantry API", "docs": "/docs"}
