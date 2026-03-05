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
    original_detection_provider = settings.detection_provider
    storage_dir = "/tmp/smartpantry-test-storage"

    settings.storage_provider = "local"
    settings.local_storage_dir = storage_dir
    settings.max_upload_images = 3
    settings.max_image_size_mb = 5
    settings.detection_provider = "mock"

    Path(storage_dir).mkdir(parents=True, exist_ok=True)
    yield

    settings.storage_provider = original_provider
    settings.local_storage_dir = original_dir
    settings.max_upload_images = original_max
    settings.max_image_size_mb = original_max_size
    settings.detection_provider = original_detection_provider
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
        assert row["detection_session"]["status"] == "completed"
        assert row["detection_session"]["model_version"] == "mock-v0"


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


@pytest.mark.asyncio
async def test_list_images_returns_uploaded_items(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    files = [("files", ("pantry.jpg", b"abc123", "image/jpeg"))]

    upload_res = await client.post("/images", headers=headers, files=files)
    assert upload_res.status_code == 201

    list_res = await client.get("/images", headers=headers)
    assert list_res.status_code == 200
    rows = list_res.json()["results"]
    assert len(rows) >= 1
    assert rows[0]["storage_key"].startswith("users/")


@pytest.mark.asyncio
async def test_get_detection_session_returns_proposals(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    files = [("files", ("milk_carton.jpg", b"abc123", "image/jpeg"))]

    upload_res = await client.post("/images", headers=headers, files=files)
    assert upload_res.status_code == 201
    session_id = upload_res.json()["results"][0]["detection_session"]["id"]

    session_res = await client.get(f"/detections/{session_id}", headers=headers)
    assert session_res.status_code == 200
    payload = session_res.json()
    assert payload["session"]["status"] == "completed"
    assert len(payload["proposals"]) == 1
    assert payload["proposals"][0]["state"] == "pending"
    assert payload["proposals"][0]["bbox_x"] is not None
    assert payload["proposals"][0]["bbox_y"] is not None
    assert payload["proposals"][0]["bbox_w"] is not None
    assert payload["proposals"][0]["bbox_h"] is not None
    assert payload["proposals"][0]["category_suggested"] is not None
    assert payload["proposals"][0]["source"] == "auto"


@pytest.mark.asyncio
async def test_get_image_content_returns_bytes(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    files = [("files", ("shelf.jpg", b"abc123", "image/jpeg"))]

    upload_res = await client.post("/images", headers=headers, files=files)
    assert upload_res.status_code == 201
    image_id = upload_res.json()["results"][0]["image"]["id"]

    content_res = await client.get(f"/images/{image_id}/content", headers=headers)
    assert content_res.status_code == 200
    assert content_res.headers["content-type"].startswith("image/jpeg")
    assert content_res.content == b"abc123"


@pytest.mark.asyncio
async def test_create_manual_proposal(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    files = [("files", ("shelf.jpg", b"abc123", "image/jpeg"))]

    upload_res = await client.post("/images", headers=headers, files=files)
    assert upload_res.status_code == 201
    session_id = upload_res.json()["results"][0]["detection_session"]["id"]

    manual_res = await client.post(
        f"/detections/{session_id}/manual-proposals",
        headers=headers,
        json={"x": 0.6, "y": 0.4, "w": 0.2, "h": 0.2, "label_hint": "green apple"},
    )
    assert manual_res.status_code == 201
    proposal = manual_res.json()
    assert proposal["source"] == "manual"
    assert proposal["label_raw"] == "green apple"
    assert proposal["category_suggested"] == "Produce"


@pytest.mark.asyncio
async def test_update_detection_proposal(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    files = [("files", ("beans_can.jpg", b"abc123", "image/jpeg"))]

    upload_res = await client.post("/images", headers=headers, files=files)
    assert upload_res.status_code == 201
    session_id = upload_res.json()["results"][0]["detection_session"]["id"]

    session_res = await client.get(f"/detections/{session_id}", headers=headers)
    assert session_res.status_code == 200
    proposal_id = session_res.json()["proposals"][0]["id"]

    patch_res = await client.patch(
        f"/detections/{session_id}/proposals/{proposal_id}",
        headers=headers,
        json={
            "label_raw": "black beans can",
            "quantity_suggested": 2,
            "quantity_unit": "can",
            "category_suggested": "Pantry",
            "is_perishable_suggested": False,
            "state": "edited",
        },
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["label_raw"] == "black beans can"
    assert updated["quantity_suggested"] == 2
    assert updated["quantity_unit"] == "can"
    assert updated["category_suggested"] == "Pantry"
    assert updated["is_perishable_suggested"] is False
    assert updated["state"] == "edited"
