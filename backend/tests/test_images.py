import shutil
import uuid
from pathlib import Path

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


@pytest.fixture(autouse=True)
def force_local_storage():
    settings = get_settings()
    original_provider = settings.storage_provider
    original_dir = settings.local_storage_dir
    original_max = settings.max_upload_images
    original_max_size = settings.max_image_size_mb
    storage_dir = "/tmp/smartpantry-test-storage"

    settings.storage_provider = "local"
    settings.local_storage_dir = storage_dir
    settings.max_upload_images = 3
    settings.max_image_size_mb = 5

    Path(storage_dir).mkdir(parents=True, exist_ok=True)
    yield

    settings.storage_provider = original_provider
    settings.local_storage_dir = original_dir
    settings.max_upload_images = original_max
    settings.max_image_size_mb = original_max_size
    shutil.rmtree(storage_dir, ignore_errors=True)


def unique_email() -> str:
    return f"user_{uuid.uuid4().hex}@example.com"


async def register_and_login(client: AsyncClient) -> str:
    email = unique_email()
    password = "testpassword123"
    register_res = await client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert register_res.status_code == 201

    login_res = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert login_res.status_code == 200
    return login_res.json()["access_token"]


@pytest.mark.asyncio
async def test_upload_images_success(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    files = [
        ("files", ("pantry1.jpg", b"abc123", "image/jpeg")),
        ("files", ("pantry2.png", b"def456", "image/png")),
    ]

    res = await client.post("/images", headers=headers, files=files)
    assert res.status_code == 201
    body = res.json()
    assert len(body["results"]) == 2

    for row in body["results"]:
        assert row["image"]["id"] > 0
        assert row["image"]["storage_key"].startswith("users/")
        assert row["detection_session"]["status"] == "pending"


@pytest.mark.asyncio
async def test_upload_images_requires_auth(client: AsyncClient):
    files = [("files", ("pantry.jpg", b"abc123", "image/jpeg"))]
    res = await client.post("/images", files=files)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_upload_images_rejects_too_many_files(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    files = [
        ("files", ("1.jpg", b"a", "image/jpeg")),
        ("files", ("2.jpg", b"a", "image/jpeg")),
        ("files", ("3.jpg", b"a", "image/jpeg")),
        ("files", ("4.jpg", b"a", "image/jpeg")),
    ]
    res = await client.post("/images", headers=headers, files=files)
    assert res.status_code == 400
    assert "Max 3 images" in res.json()["detail"]


@pytest.mark.asyncio
async def test_upload_images_rejects_invalid_content_type(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    files = [("files", ("notes.txt", b"not-an-image", "text/plain"))]
    res = await client.post("/images", headers=headers, files=files)
    assert res.status_code == 400
    assert "Unsupported content type" in res.json()["detail"]
