import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from typing import Optional

from app.db import Base, SessionLocal, engine, ensure_sqlite_schema_compatibility
from app.main import app
from app.models import InventoryItem, Recipe, RecipeFeedback, RecipeIngredient


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
def clear_recipe_tables():
    with SessionLocal() as db:
        db.query(RecipeFeedback).delete()
        db.query(RecipeIngredient).delete()
        db.query(Recipe).delete()
        db.commit()
    yield
    with SessionLocal() as db:
        db.query(RecipeFeedback).delete()
        db.query(RecipeIngredient).delete()
        db.query(Recipe).delete()
        db.commit()


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


def seed_recipe(
    *,
    title: str,
    slug: str,
    # cuisine: str | None,
    cuisine: Optional[str] = None,
    # total_minutes: int | None,
    total_minutes: Optional[int] = None,
    # tags: list[str],
    tags: list[str] = [],
    ingredients: list[str] = [],
    # instructions_text: str | None = None,
    instructions_text: Optional[str] = None,
    # source_url: str | None = None,
    source_url: Optional[str] = None,
    # rating: float | None = None,
    rating: Optional[float] = None,
) -> int:
    with SessionLocal() as db:
        recipe = Recipe(
            title=title,
            slug=slug,
            cuisine=cuisine,
            total_minutes=total_minutes,
            dietary_tags_json=json.dumps(tags),
            nutrition_json=json.dumps({"calories": 100}),
            instructions_text=instructions_text,
            source_url=source_url,
            rating=rating,
            search_text=" ".join([title.lower(), *(ingredient.lower() for ingredient in ingredients)]),
        )
        db.add(recipe)
        db.flush()

        for ingredient in ingredients:
            db.add(
                RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_raw=ingredient,
                    ingredient_normalized=ingredient.strip().lower(),
                    quantity_text=None,
                    is_optional=False,
                )
            )
        db.commit()
        return recipe.id


def add_inventory_item(user_id: int, name: str) -> None:
    with SessionLocal() as db:
        db.add(
            InventoryItem(
                user_id=user_id,
                name=name,
                normalized_name=name.strip().lower(),
                quantity=1.0,
                unit="count",
            )
        )
        db.commit()


def get_user_id_from_token(token: str) -> int:
    from app.core.security import settings
    from jose import jwt

    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return int(payload["sub"])


@pytest.mark.asyncio
async def test_recommendations_rank_highest_inventory_overlap(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    user_id = get_user_id_from_token(token)

    add_inventory_item(user_id, "pasta")
    add_inventory_item(user_id, "tomato")
    add_inventory_item(user_id, "garlic")

    seed_recipe(
        title="Pasta Pomodoro",
        slug="pasta-pomodoro",
        cuisine="Italian",
        total_minutes=20,
        tags=["vegetarian"],
        ingredients=["pasta", "tomato", "garlic", "basil"],
    )
    seed_recipe(
        title="Chicken Tacos",
        slug="chicken-tacos",
        cuisine="Mexican",
        total_minutes=25,
        tags=["dinner"],
        ingredients=["chicken", "tortillas", "salsa"],
    )

    res = await client.get("/recipes/recommendations", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert body["total_results"] == 1
    assert len(body["results"]) == 1
    assert body["results"][0]["recipe"]["title"] == "Pasta Pomodoro"
    assert body["results"][0]["inventory_match_count"] == 3
    assert "basil" in body["results"][0]["missing_ingredients"]


@pytest.mark.asyncio
async def test_recommendations_return_empty_when_no_overlap_exists_for_inventory(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    user_id = get_user_id_from_token(token)

    add_inventory_item(user_id, "peach")
    add_inventory_item(user_id, "orange")
    add_inventory_item(user_id, "corn")

    seed_recipe(
        title="Beef Stew",
        slug="beef-stew",
        cuisine=None,
        total_minutes=60,
        tags=["dinner"],
        ingredients=["beef", "potato", "carrot"],
    )

    res = await client.get("/recipes/recommendations", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["total_results"] == 0
    assert body["results"] == []


@pytest.mark.asyncio
async def test_recommendations_respect_filters(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    user_id = get_user_id_from_token(token)

    add_inventory_item(user_id, "rice")
    add_inventory_item(user_id, "egg")

    seed_recipe(
        title="Quick Fried Rice",
        slug="quick-fried-rice",
        cuisine="Asian",
        total_minutes=15,
        tags=["quick", "gluten-free"],
        ingredients=["rice", "egg", "soy sauce"],
    )
    seed_recipe(
        title="Slow Pasta Bake",
        slug="slow-pasta-bake",
        cuisine="Italian",
        total_minutes=55,
        tags=["vegetarian"],
        ingredients=["pasta", "tomato", "cheese"],
    )

    res = await client.get(
        "/recipes/recommendations?cuisine=asian&max_total_minutes=20&dietary_tags=quick",
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["recipe"]["title"] == "Quick Fried Rice"


@pytest.mark.asyncio
async def test_main_ingredient_matches_are_prioritized_without_changing_total_matches(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    user_id = get_user_id_from_token(token)

    add_inventory_item(user_id, "corn")
    add_inventory_item(user_id, "orange")
    add_inventory_item(user_id, "peach")

    seed_recipe(
        title="Orange Breakfast Bake",
        slug="orange-breakfast-bake",
        cuisine=None,
        total_minutes=25,
        tags=["breakfast"],
        ingredients=["orange", "egg", "milk"],
    )
    seed_recipe(
        title="Skillet Corn Chowder",
        slug="skillet-corn-chowder",
        cuisine=None,
        total_minutes=30,
        tags=["dinner"],
        ingredients=["whole kernel corn", "milk", "onion"],
    )

    base_res = await client.get("/recipes/recommendations", headers=headers)
    assert base_res.status_code == 200
    base_body = base_res.json()
    assert base_body["total_results"] == 2

    focused_res = await client.get("/recipes/recommendations?main_ingredients=corn", headers=headers)
    assert focused_res.status_code == 200
    focused_body = focused_res.json()
    assert focused_body["total_results"] == 2
    assert focused_body["results"][0]["recipe"]["title"] == "Skillet Corn Chowder"


@pytest.mark.asyncio
async def test_recommendations_empty_inventory_fallback_prefers_simpler_recipes(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    seed_recipe(
        title="Three Ingredient Toast",
        slug="three-ingredient-toast",
        cuisine=None,
        total_minutes=5,
        tags=["breakfast"],
        ingredients=["bread", "butter", "jam"],
    )
    seed_recipe(
        title="Big Party Chili",
        slug="big-party-chili",
        cuisine=None,
        total_minutes=90,
        tags=["dinner"],
        ingredients=["beans", "tomato", "onion", "garlic", "chili powder", "beef"],
    )

    res = await client.get("/recipes/recommendations", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["results"][0]["recipe"]["title"] == "Three Ingredient Toast"


@pytest.mark.asyncio
async def test_read_recipe_detail_returns_ingredients_and_rating(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    recipe_id = seed_recipe(
        title="Open Recipe Salad",
        slug="open-recipe-salad",
        cuisine="American",
        total_minutes=10,
        tags=["vegetarian"],
        ingredients=["lettuce", "olive oil", "lemon juice"],
        instructions_text="Mix and serve.",
        source_url=None,
        rating=4.6,
    )

    res = await client.get(f"/recipes/{recipe_id}", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "Open Recipe Salad"
    assert body["source_url"] is None
    assert body["rating"] == 4.6
    assert body["current_feedback"] is None
    assert len(body["ingredients"]) == 3
    assert body["ingredients"][0]["ingredient_normalized"] == "lettuce"


@pytest.mark.asyncio
async def test_recipe_feedback_updates_detail_and_book(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    recipe_id = seed_recipe(
        title="Liked Pasta",
        slug="liked-pasta",
        cuisine="Italian",
        total_minutes=20,
        tags=["dinner"],
        ingredients=["pasta", "tomato"],
    )

    feedback_res = await client.post(
        f"/recipes/{recipe_id}/feedback",
        headers=headers,
        json={"feedback_type": "like"},
    )
    assert feedback_res.status_code == 200
    assert feedback_res.json()["feedback_type"] == "like"

    detail_res = await client.get(f"/recipes/{recipe_id}", headers=headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["current_feedback"] == "like"

    book_res = await client.get("/recipes/book", headers=headers)
    assert book_res.status_code == 200
    book_body = book_res.json()
    assert len(book_body["results"]) == 1
    assert book_body["results"][0]["title"] == "Liked Pasta"
    assert book_body["results"][0]["current_feedback"] == "like"


@pytest.mark.asyncio
async def test_disliked_recipes_are_excluded_from_recommendations(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    user_id = get_user_id_from_token(token)

    add_inventory_item(user_id, "rice")
    add_inventory_item(user_id, "egg")

    liked_recipe_id = seed_recipe(
        title="Rice Bowl",
        slug="rice-bowl",
        cuisine="Asian",
        total_minutes=15,
        tags=["quick"],
        ingredients=["rice", "egg", "soy sauce"],
    )
    disliked_recipe_id = seed_recipe(
        title="Rice Omelet",
        slug="rice-omelet",
        cuisine="Asian",
        total_minutes=18,
        tags=["quick"],
        ingredients=["rice", "egg", "butter"],
    )

    dislike_res = await client.post(
        f"/recipes/{disliked_recipe_id}/feedback",
        headers=headers,
        json={"feedback_type": "dislike"},
    )
    assert dislike_res.status_code == 200

    rec_res = await client.get("/recipes/recommendations", headers=headers)
    assert rec_res.status_code == 200
    body = rec_res.json()
    titles = [row["recipe"]["title"] for row in body["results"]]
    assert "Rice Omelet" not in titles
    assert "Rice Bowl" in titles
    assert body["results"][0]["recipe"]["current_feedback"] in (None, "like")


@pytest.mark.asyncio
async def test_recommendations_are_paginated_in_pages_of_ten(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    user_id = get_user_id_from_token(token)

    add_inventory_item(user_id, "tomato")

    for index in range(12):
        seed_recipe(
            title=f"Tomato Recipe {index + 1}",
            slug=f"tomato-recipe-{index + 1}",
            cuisine=None,
            total_minutes=10 + index,
            tags=["dinner"],
            ingredients=["tomato", f"ingredient-{index + 1}"],
        )

    first_page = await client.get("/recipes/recommendations?page=1&page_size=10", headers=headers)
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert first_body["page"] == 1
    assert first_body["page_size"] == 10
    assert first_body["total_results"] == 12
    assert first_body["total_pages"] == 2
    assert len(first_body["results"]) == 10

    second_page = await client.get("/recipes/recommendations?page=2&page_size=10", headers=headers)
    assert second_page.status_code == 200
    second_body = second_page.json()
    assert second_body["page"] == 2
    assert len(second_body["results"]) == 2
