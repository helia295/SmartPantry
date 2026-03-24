import io
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.db import Base, engine, ensure_sqlite_schema_compatibility
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema_compatibility()
    yield


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def unique_email() -> str:
    return f"rate_limit_{uuid.uuid4().hex}@example.com"


@pytest.mark.asyncio
async def test_login_rate_limit_returns_429(client: AsyncClient):
    settings = get_settings()
    original_limit = settings.auth_rate_limit_requests
    original_window = settings.auth_rate_limit_window_seconds
    settings.auth_rate_limit_requests = 2
    settings.auth_rate_limit_window_seconds = 60
    app.state.rate_limiter = app.state.rate_limiter.__class__(settings)

    try:
        email = unique_email()
        password = "testpassword123"
        register_res = await client.post(
            "/auth/register",
            json={"email": email, "display_name": "Rate Limit User", "password": password},
        )
        assert register_res.status_code == 201

        ok_1 = await client.post("/auth/login", data={"username": email, "password": password})
        ok_2 = await client.post("/auth/login", data={"username": email, "password": password})
        limited = await client.post("/auth/login", data={"username": email, "password": password})

        assert ok_1.status_code == 200
        assert ok_2.status_code == 200
        assert limited.status_code == 429
        assert "Retry-After" in limited.headers
    finally:
        settings.auth_rate_limit_requests = original_limit
        settings.auth_rate_limit_window_seconds = original_window
        app.state.rate_limiter = app.state.rate_limiter.__class__(settings)


@pytest.mark.asyncio
async def test_image_upload_rate_limit_returns_429(client: AsyncClient):
    settings = get_settings()
    original_limit = settings.image_upload_rate_limit_requests
    original_window = settings.image_upload_rate_limit_window_seconds
    settings.image_upload_rate_limit_requests = 1
    settings.image_upload_rate_limit_window_seconds = 60
    app.state.rate_limiter = app.state.rate_limiter.__class__(settings)

    try:
        email = unique_email()
        password = "testpassword123"
        register_res = await client.post(
            "/auth/register",
            json={"email": email, "display_name": "Upload Limit User", "password": password},
        )
        assert register_res.status_code == 201

        login_res = await client.post(
            "/auth/login",
            data={"username": email, "password": password},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        files = [
            ("files", ("test.png", io.BytesIO(b"fake-image"), "image/png")),
        ]
        first = await client.post("/images", headers=headers, files=files)
        second = await client.post("/images", headers=headers, files=files)

        assert first.status_code in {201, 500}
        assert second.status_code == 429
    finally:
        settings.image_upload_rate_limit_requests = original_limit
        settings.image_upload_rate_limit_window_seconds = original_window
        app.state.rate_limiter = app.state.rate_limiter.__class__(settings)
