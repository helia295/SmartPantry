import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "smartpantry-api"


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    r = await client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["service"] == "SmartPantry API"


@pytest.mark.asyncio
async def test_health_check_includes_cors_headers_for_allowed_origin(client: AsyncClient):
    r = await client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"},
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_production_settings_emit_expected_deployment_warnings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "dev-secret-change-me")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./smartpantry.db")
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")

    settings = Settings()
    warnings = settings.deployment_warnings()

    assert any("JWT_SECRET" in warning for warning in warnings)
    assert any("SQLite" in warning for warning in warnings)
    assert any("STORAGE_PROVIDER" in warning for warning in warnings)
    assert any("CORS_ORIGINS" in warning for warning in warnings)
