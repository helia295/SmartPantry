import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from typing import Optional

import app.api.recipes as recipe_routes
import app.services.recipe_assistant as recipe_assistant_service
from app.db import Base, SessionLocal, engine, ensure_sqlite_schema_compatibility
from app.main import app
from app.models import (
    InventoryChangeLog,
    InventoryItem,
    Recipe,
    RecipeFeedback,
    RecipeIngredient,
    RecipeTag,
    RecipeTagLink,
)
from app.schemas import RecipeAssistantUseUpRead
from app.services.llm import RecipeAssistantUpstreamError
from app.services.recipe_assistant import build_recipe_assistant_response
from app.schemas.assistant import RecipeAssistantUseUpRequest


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
        db.query(RecipeTagLink).delete()
        db.query(RecipeTag).delete()
        db.query(RecipeFeedback).delete()
        db.query(RecipeIngredient).delete()
        db.query(Recipe).delete()
        db.commit()
    yield
    with SessionLocal() as db:
        db.query(RecipeTagLink).delete()
        db.query(RecipeTag).delete()
        db.query(RecipeFeedback).delete()
        db.query(RecipeIngredient).delete()
        db.query(Recipe).delete()
        db.commit()


def unique_email() -> str:
    return f"user_{uuid.uuid4().hex}@example.com"


async def register_and_login(client: AsyncClient) -> str:
    email = unique_email()
    password = "testpassword123"
    display_name = "Recipe Tester"

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


def add_inventory_item_with_metadata(
    user_id: int,
    name: str,
    *,
    is_perishable: bool = False,
    created_at: Optional[datetime] = None,
) -> None:
    with SessionLocal() as db:
        db.add(
            InventoryItem(
                user_id=user_id,
                name=name,
                normalized_name=name.strip().lower(),
                quantity=1.0,
                unit="count",
                is_perishable=is_perishable,
                created_at=created_at,
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
async def test_recipe_feedback_can_be_removed(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    recipe_id = seed_recipe(
        title="Orange Salad",
        slug="orange-salad",
        ingredients=["orange", "mint"],
        rating=4.2,
    )

    feedback_res = await client.post(
        f"/recipes/{recipe_id}/feedback",
        headers=headers,
        json={"feedback_type": "like"},
    )
    assert feedback_res.status_code == 200

    delete_res = await client.delete(f"/recipes/{recipe_id}/feedback", headers=headers)
    assert delete_res.status_code == 204

    detail_res = await client.get(f"/recipes/{recipe_id}", headers=headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["current_feedback"] is None

    book_res = await client.get("/recipes/book", headers=headers)
    assert book_res.status_code == 200
    assert book_res.json()["results"] == []


@pytest.mark.asyncio
async def test_favorite_recipe_tags_can_be_saved_and_listed(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    recipe_id = seed_recipe(
        title="Tagged Oatmeal",
        slug="tagged-oatmeal",
        ingredients=["oats", "milk"],
    )

    like_res = await client.post(
        f"/recipes/{recipe_id}/feedback",
        headers=headers,
        json={"feedback_type": "like"},
    )
    assert like_res.status_code == 200

    tags_res = await client.put(
        f"/recipes/{recipe_id}/tags",
        headers=headers,
        json={"tags": ["#breakfast", "quick", "Breakfast"]},
    )
    assert tags_res.status_code == 200
    assert tags_res.json()["tags"] == ["breakfast", "quick"]

    book_res = await client.get("/recipes/book", headers=headers)
    assert book_res.status_code == 200
    body = book_res.json()
    assert body["available_tags"] == ["breakfast", "quick"]
    assert body["results"][0]["favorite_tags"] == ["breakfast", "quick"]


@pytest.mark.asyncio
async def test_recipe_tags_are_removed_when_recipe_is_unfavorited(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    recipe_id = seed_recipe(
        title="Tagged Pasta",
        slug="tagged-pasta",
        ingredients=["pasta", "butter"],
    )

    like_res = await client.post(
        f"/recipes/{recipe_id}/feedback",
        headers=headers,
        json={"feedback_type": "like"},
    )
    assert like_res.status_code == 200

    tags_res = await client.put(
        f"/recipes/{recipe_id}/tags",
        headers=headers,
        json={"tags": ["dinner", "comfort-food"]},
    )
    assert tags_res.status_code == 200

    delete_res = await client.delete(f"/recipes/{recipe_id}/feedback", headers=headers)
    assert delete_res.status_code == 204

    book_res = await client.get("/recipes/book", headers=headers)
    assert book_res.status_code == 200
    body = book_res.json()
    assert body["results"] == []
    assert body["available_tags"] == []


@pytest.mark.asyncio
async def test_recipe_cook_preview_returns_matches_and_inventory_options(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    user_id = get_user_id_from_token(token)

    add_inventory_item(user_id, "egg")
    add_inventory_item(user_id, "milk")

    with SessionLocal() as db:
        recipe = Recipe(
            title="Breakfast Scramble",
            slug="breakfast-scramble",
            dietary_tags_json=json.dumps([]),
            nutrition_json=json.dumps({}),
            search_text="breakfast scramble egg milk salt",
        )
        db.add(recipe)
        db.flush()
        db.add(
            RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_raw="2 eggs",
                ingredient_normalized="egg",
                quantity_text=None,
                is_optional=False,
            )
        )
        db.add(
            RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_raw="200 ml milk",
                ingredient_normalized="milk",
                quantity_text=None,
                is_optional=False,
            )
        )
        db.add(
            RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_raw="1 pinch salt",
                ingredient_normalized="salt",
                quantity_text=None,
                is_optional=False,
            )
        )
        db.commit()
        recipe_id = recipe.id

    preview_res = await client.post(
        f"/recipes/{recipe_id}/cook-preview",
        headers=headers,
        json={"multiplier": 1},
    )
    assert preview_res.status_code == 200
    body = preview_res.json()
    assert body["recipe_id"] == recipe_id
    assert len(body["inventory_options"]) == 2
    egg_row = next(row for row in body["items"] if row["ingredient_normalized"] == "egg")
    assert egg_row["selected_inventory_item_name"] == "egg"
    assert egg_row["match_status"] in {"matched", "needs_review"}


@pytest.mark.asyncio
async def test_recipe_cook_apply_updates_inventory_and_logs_change(client: AsyncClient):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    user_id = get_user_id_from_token(token)

    with SessionLocal() as db:
        item = InventoryItem(
            user_id=user_id,
            name="Eggs",
            normalized_name="egg",
            quantity=8,
            unit="count",
            category="Dairy & Eggs",
            is_perishable=True,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        item_id = item.id

    with SessionLocal() as db:
        recipe = Recipe(
            title="Egg Toast",
            slug="egg-toast",
            dietary_tags_json=json.dumps([]),
            nutrition_json=json.dumps({}),
            search_text="egg toast egg bread",
        )
        db.add(recipe)
        db.flush()
        db.add(
            RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_raw="2 eggs",
                ingredient_normalized="egg",
                quantity_text=None,
                is_optional=False,
            )
        )
        db.add(
            RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_raw="2 slices bread",
                ingredient_normalized="bread",
                quantity_text=None,
                is_optional=False,
            )
        )
        db.commit()
        recipe_id = recipe.id

    apply_res = await client.post(
        f"/recipes/{recipe_id}/cook-apply",
        headers=headers,
        json={
            "multiplier": 1,
            "actions": [
                {
                    "ingredient_key": f"{recipe_id}:0",
                    "ingredient_raw": "2 eggs",
                    "ingredient_normalized": "egg",
                    "inventory_item_id": item_id,
                    "decision": "update",
                    "new_quantity": 6,
                },
                {
                    "ingredient_key": f"{recipe_id}:1",
                    "ingredient_raw": "2 slices bread",
                    "ingredient_normalized": "bread",
                    "decision": "ignore",
                },
            ],
        },
    )
    assert apply_res.status_code == 200
    body = apply_res.json()
    assert body["updated"] == 1
    assert body["ignored"] == 1

    with SessionLocal() as db:
        updated_item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        assert updated_item is not None
        assert updated_item.quantity == 6
        log = (
            db.query(InventoryChangeLog)
            .filter(
                InventoryChangeLog.inventory_item_id == item_id,
                InventoryChangeLog.change_type == "recipe_cooked_update",
            )
            .first()
        )
        assert log is not None


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


@pytest.mark.asyncio
async def test_use_up_my_pantry_assistant_requires_auth(client: AsyncClient):
    res = await client.post("/recipes/assistant/use-up", json={})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_use_up_my_pantry_assistant_returns_structured_response(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    def fake_assistant_response(**_: object) -> RecipeAssistantUseUpRead:
        return RecipeAssistantUseUpRead(
            summary="Start with the soup and the stir fry to use older produce first.",
            strategy_note="Lean on quick recipes when produce is getting old.",
            pantry_items_to_use_first=["spinach", "mushroom"],
            recipes=[
                {
                    "recipe_id": 7,
                    "title": "Mushroom Spinach Soup",
                    "reason": "It uses your oldest greens and cooks quickly.",
                    "uses_up": ["spinach", "mushroom"],
                    "missing_ingredients": ["broth"],
                    "substitution_ideas": ["Use water plus seasoning if broth is missing."],
                    "time_note": "About 20 minutes total.",
                }
            ],
        )

    monkeypatch.setattr(recipe_routes, "build_recipe_assistant_response", fake_assistant_response)

    res = await client.post(
        "/recipes/assistant/use-up",
        headers=headers,
        json={"user_goal": "quick dinner", "max_total_minutes": 30},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["summary"].startswith("Start with the soup")
    assert body["pantry_items_to_use_first"] == ["spinach", "mushroom"]
    assert body["recipes"][0]["recipe_id"] == 7
    assert body["recipes"][0]["uses_up"] == ["spinach", "mushroom"]


@pytest.mark.asyncio
async def test_use_up_my_pantry_assistant_handles_upstream_failure(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    def fake_failure(**_: object) -> RecipeAssistantUseUpRead:
        raise RecipeAssistantUpstreamError("The pantry assistant request failed.")

    monkeypatch.setattr(recipe_routes, "build_recipe_assistant_response", fake_failure)

    res = await client.post("/recipes/assistant/use-up", headers=headers, json={})
    assert res.status_code == 502
    assert res.json()["detail"] == "The pantry assistant request failed."


def test_recipe_assistant_returns_inventory_guidance_without_llm_when_pantry_is_empty():
    class DummyUser:
        id = 999

    with SessionLocal() as db:
        result = build_recipe_assistant_response(
            db=db,
            current_user=DummyUser(),
            payload=RecipeAssistantUseUpRequest(user_goal="easy dinner"),
        )
    assert result.recipes == []
    assert "Add a few pantry items first" in result.summary


def test_recipe_assistant_can_prioritize_selected_ingredients_without_oldest_bias(monkeypatch: pytest.MonkeyPatch):
    class DummyUser:
        id = 777

    add_inventory_item_with_metadata(DummyUser.id, "apple", is_perishable=False)
    add_inventory_item_with_metadata(DummyUser.id, "spinach", is_perishable=True)

    apple_recipe_id = seed_recipe(
        title="Apple Oat Bowl",
        slug="apple-oat-bowl",
        total_minutes=10,
        ingredients=["apple", "oats"],
    )
    seed_recipe(
        title="Spinach Eggs",
        slug="spinach-eggs",
        total_minutes=12,
        ingredients=["spinach", "egg"],
    )

    def fake_generate_recipe_assistant_plan(*, prompt_payload):
        assert prompt_payload["user_request"]["prioritize_oldest_items"] is False
        assert prompt_payload["user_request"]["prioritized_ingredients"] == ["apple"]
        assert prompt_payload["pantry_items_to_use_first"][0].lower() == "apple"
        return RecipeAssistantUseUpRead(
            summary="Start with the apple bowl.",
            strategy_note="You asked to prioritize apple specifically.",
            pantry_items_to_use_first=prompt_payload["pantry_items_to_use_first"],
            recipes=[
                {
                    "recipe_id": apple_recipe_id,
                    "title": "Apple Oat Bowl",
                    "reason": "It directly uses the ingredient you selected.",
                    "uses_up": ["apple"],
                    "missing_ingredients": [],
                    "substitution_ideas": [],
                    "time_note": "About 10 minutes total.",
                }
            ],
        )

    monkeypatch.setattr(
        recipe_assistant_service,
        "generate_recipe_assistant_plan",
        fake_generate_recipe_assistant_plan,
    )

    with SessionLocal() as db:
        result = build_recipe_assistant_response(
            db=db,
            current_user=DummyUser(),
            payload=RecipeAssistantUseUpRequest(
                user_goal="quick breakfast",
                prioritize_oldest_items=False,
                prioritized_ingredients=["apple"],
            ),
        )

    assert result.pantry_items_to_use_first[0].lower() == "apple"
    assert result.summary == "Start with the apple bowl."


def test_recipe_assistant_oldest_toggle_only_reorders_perishables(monkeypatch: pytest.MonkeyPatch):
    class DummyUser:
        id = 778

    now = datetime.now(timezone.utc)
    add_inventory_item_with_metadata(
        DummyUser.id,
        "rice",
        is_perishable=False,
        created_at=now - timedelta(days=30),
    )
    add_inventory_item_with_metadata(
        DummyUser.id,
        "spinach",
        is_perishable=True,
        created_at=now - timedelta(days=2),
    )
    add_inventory_item_with_metadata(
        DummyUser.id,
        "berries",
        is_perishable=True,
        created_at=now - timedelta(days=6),
    )

    recipe_id = seed_recipe(
        title="Berry Spinach Bowl",
        slug="berry-spinach-bowl",
        total_minutes=12,
        ingredients=["berries", "spinach", "yogurt"],
    )

    def fake_generate_recipe_assistant_plan(*, prompt_payload):
        assert prompt_payload["pantry_items_to_use_first"][:3] == ["berries", "spinach", "rice"]
        return RecipeAssistantUseUpRead(
            summary="Use the older berries first.",
            strategy_note="Perishable items should rise above shelf-stable pantry goods.",
            pantry_items_to_use_first=prompt_payload["pantry_items_to_use_first"],
            recipes=[
                {
                    "recipe_id": recipe_id,
                    "title": "Berry Spinach Bowl",
                    "reason": "It uses the older perishables first.",
                    "uses_up": ["berries", "spinach"],
                    "missing_ingredients": ["yogurt"],
                    "substitution_ideas": [],
                    "time_note": "About 12 minutes total.",
                }
            ],
        )

    monkeypatch.setattr(
        recipe_assistant_service,
        "generate_recipe_assistant_plan",
        fake_generate_recipe_assistant_plan,
    )

    with SessionLocal() as db:
        result = build_recipe_assistant_response(
            db=db,
            current_user=DummyUser(),
            payload=RecipeAssistantUseUpRequest(
                user_goal="light breakfast",
                prioritize_oldest_items=True,
            ),
        )

    assert result.pantry_items_to_use_first[:3] == ["berries", "spinach", "rice"]
