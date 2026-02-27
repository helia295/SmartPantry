import uuid

import pytest
from httpx import ASGITransport, AsyncClient

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
    token = login_res.json()["access_token"]
    return token


@pytest.mark.asyncio
async def test_inventory_crud_flow(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_res = await client.post(
        "/inventory",
        headers=headers,
        json={"name": "Black Beans", "quantity": 2, "unit": "can", "is_perishable": False},
    )
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["name"] == "Black Beans"
    assert created["normalized_name"] == "black beans"
    assert created["created_at"] is not None
    item_id = created["id"]

    list_res = await client.get("/inventory", headers=headers)
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 1
    assert any(item["id"] == item_id for item in items)

    update_res = await client.patch(
        f"/inventory/{item_id}",
        headers=headers,
        json={"quantity": 3, "unit": "cans", "name": "Black Beans Organic"},
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["quantity"] == 3
    assert updated["unit"] == "cans"
    assert updated["normalized_name"] == "black beans organic"

    delete_res = await client.delete(f"/inventory/{item_id}", headers=headers)
    assert delete_res.status_code == 204

    post_delete_list = await client.get("/inventory", headers=headers)
    assert post_delete_list.status_code == 200
    assert all(item["id"] != item_id for item in post_delete_list.json())


@pytest.mark.asyncio
async def test_inventory_is_user_scoped(client: AsyncClient):
    user1_token = await register_and_login(client)
    user2_token = await register_and_login(client)
    user1_headers = {"Authorization": f"Bearer {user1_token}"}
    user2_headers = {"Authorization": f"Bearer {user2_token}"}

    create_res = await client.post(
        "/inventory",
        headers=user1_headers,
        json={"name": "Milk", "quantity": 1, "unit": "carton", "is_perishable": True},
    )
    assert create_res.status_code == 201
    item_id = create_res.json()["id"]

    user2_list = await client.get("/inventory", headers=user2_headers)
    assert user2_list.status_code == 200
    assert all(item["id"] != item_id for item in user2_list.json())

    user2_delete = await client.delete(f"/inventory/{item_id}", headers=user2_headers)
    assert user2_delete.status_code == 404
