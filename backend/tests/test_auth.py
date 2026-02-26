import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import Base, engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    """
    Ensure database tables exist before any auth tests run.

    In production we rely on the FastAPI startup hook; in tests using
    ASGITransport we proactively create tables here to avoid relying
    on startup events.
    """
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def unique_email() -> str:
    return f"user_{uuid.uuid4().hex}@example.com"


@pytest.mark.asyncio
async def test_register_and_login_and_me(client: AsyncClient):
    email = unique_email()
    password = "testpassword123"

    # Register
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == email
    assert "id" in data

    # # Login
    # r = await client.post(
    #     "/auth/login",
    #     json={"email": email, "password": password},
    # )
    # Login (OAuth2 password flow: form data)
    r = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert r.status_code == 200
    token_data = r.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # Use token to call /auth/me
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    r = await client.get("/auth/me", headers=headers)
    assert r.status_code == 200
    me = r.json()
    assert me["email"] == email
