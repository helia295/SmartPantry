import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import Base, engine, ensure_sqlite_schema_compatibility
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
    ensure_sqlite_schema_compatibility()
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
    display_name = "Pantry Pal"

    # Register
    r = await client.post(
        "/auth/register",
        json={"email": email, "display_name": display_name, "password": password},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == email
    assert data["display_name"] == display_name
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
    assert me["display_name"] == display_name
    assert me["timezone"] == "UTC"


@pytest.mark.asyncio
async def test_update_timezone(client: AsyncClient):
    email = unique_email()
    password = "testpassword123"
    display_name = "Timezone Tester"

    register_res = await client.post(
        "/auth/register",
        json={"email": email, "display_name": display_name, "password": password},
    )
    assert register_res.status_code == 201

    login_res = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    update_res = await client.patch(
        "/auth/me/timezone",
        headers=headers,
        json={"timezone": "America/New_York"},
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["timezone"] == "America/New_York"
    assert updated["display_name"] == display_name


@pytest.mark.asyncio
async def test_update_profile_details(client: AsyncClient):
    email = unique_email()
    password = "testpassword123"
    display_name = "Profile Tester"

    register_res = await client.post(
        "/auth/register",
        json={"email": email, "display_name": display_name, "password": password},
    )
    assert register_res.status_code == 201

    login_res = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    update_res = await client.patch(
        "/auth/me",
        headers=headers,
        json={
            "display_name": "Chef Helia",
            "email": unique_email(),
            "timezone": "America/Los_Angeles",
        },
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["display_name"] == "Chef Helia"
    assert updated["timezone"] == "America/Los_Angeles"


@pytest.mark.asyncio
async def test_refresh_token_returns_new_valid_access_token(client: AsyncClient):
    email = unique_email()
    password = "testpassword123"

    register_res = await client.post(
        "/auth/register",
        json={"email": email, "display_name": "Refresh Tester", "password": password},
    )
    assert register_res.status_code == 201

    login_res = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    refresh_res = await client.post(
        "/auth/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert refresh_res.status_code == 200
    refreshed = refresh_res.json()
    assert "access_token" in refreshed
    assert refreshed["token_type"] == "bearer"

    me_res = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {refreshed['access_token']}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["email"] == email


@pytest.mark.asyncio
async def test_update_password_requires_current_password_and_enables_new_login(client: AsyncClient):
    email = unique_email()
    password = "testpassword123"
    new_password = "newpassword456"

    register_res = await client.post(
        "/auth/register",
        json={"email": email, "display_name": "Password Tester", "password": password},
    )
    assert register_res.status_code == 201

    login_res = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    update_res = await client.patch(
        "/auth/me/password",
        headers=headers,
        json={"current_password": password, "new_password": new_password},
    )
    assert update_res.status_code == 204

    old_login_res = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert old_login_res.status_code == 401

    new_login_res = await client.post(
        "/auth/login",
        data={"username": email, "password": new_password},
    )
    assert new_login_res.status_code == 200
