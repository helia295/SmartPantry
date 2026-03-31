from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import InventoryItem, User
from app.schemas.assistant import (
    RecipeAssistantSuggestionRead,
    RecipeAssistantUseUpRead,
    RecipeAssistantUseUpRequest,
)
from app.services.llm import generate_recipe_assistant_plan
from app.services.recipes import canonicalize_ingredient_phrase, get_recipe_detail, parse_csv_terms, recommend_recipes


def _normalize_iso_days(value: Optional[datetime]) -> int | None:
    if value is None:
        return None
    now = datetime.now(timezone.utc)
    current = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    delta = now - current
    return max(delta.days, 0)


def _serialize_inventory_item(item: InventoryItem) -> dict[str, Any]:
    return {
        "name": item.name,
        "normalized_name": item.normalized_name,
        "quantity": float(item.quantity),
        "unit": item.unit,
        "category": item.category,
        "is_perishable": bool(item.is_perishable),
        "days_in_pantry": _normalize_iso_days(item.created_at),
        "days_since_update": _normalize_iso_days(item.last_updated),
    }


def _normalize_prioritized_ingredients(
    *,
    prioritized_ingredients: list[str],
    pantry_items: list[InventoryItem],
) -> list[str]:
    available_names: dict[str, str] = {}
    for item in pantry_items:
        normalized = canonicalize_ingredient_phrase(item.normalized_name or item.name)
        if normalized:
            available_names.setdefault(normalized, item.name)

    cleaned: list[str] = []
    seen: set[str] = set()
    for raw_value in prioritized_ingredients:
        normalized = canonicalize_ingredient_phrase(raw_value)
        if not normalized or normalized in seen or normalized not in available_names:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned


def _build_effective_main_ingredients(
    *,
    request: RecipeAssistantUseUpRequest,
    prioritized_ingredients: list[str],
) -> str | None:
    merged_terms = list(dict.fromkeys(parse_csv_terms(request.main_ingredients) + prioritized_ingredients))
    if not merged_terms:
        return None
    return ",".join(merged_terms)


def _sort_pantry_items_for_assistant(
    *,
    pantry_items: list[InventoryItem],
    prioritized_ingredients: list[str],
    prioritize_oldest_items: bool,
) -> list[InventoryItem]:
    prioritized_index = {name: index for index, name in enumerate(prioritized_ingredients)}

    def sort_key(item: InventoryItem) -> tuple[int, int, int, str]:
        normalized = canonicalize_ingredient_phrase(item.normalized_name or item.name)
        selected_rank = prioritized_index.get(normalized, 999)
        perishable_rank = 0 if item.is_perishable else 1
        oldest_rank = (
            -(_normalize_iso_days(item.created_at) or 0)
            if prioritize_oldest_items and item.is_perishable
            else 0
        )
        return (
            selected_rank,
            perishable_rank,
            oldest_rank,
            item.name.lower(),
        )

    return sorted(pantry_items, key=sort_key)


def _build_empty_response(*, pantry_items_to_use_first: list[str]) -> RecipeAssistantUseUpRead:
    return RecipeAssistantUseUpRead(
        summary="I couldn't find strong pantry-based recipe matches yet.",
        strategy_note="Add a few more staple items or broaden your request, then try again.",
        pantry_items_to_use_first=pantry_items_to_use_first,
        recipes=[],
    )


def _build_prompt_payload(
    *,
    request: RecipeAssistantUseUpRequest,
    pantry_items: list[InventoryItem],
    candidate_results: list[dict[str, Any]],
) -> dict[str, Any]:
    settings = get_settings()
    prioritized_ingredients = _normalize_prioritized_ingredients(
        prioritized_ingredients=request.prioritized_ingredients,
        pantry_items=pantry_items,
    )
    sorted_pantry_items = _sort_pantry_items_for_assistant(
        pantry_items=pantry_items,
        prioritized_ingredients=prioritized_ingredients,
        prioritize_oldest_items=request.prioritize_oldest_items,
    )
    prioritized_pantry = sorted_pantry_items[: max(settings.openai_assistant_max_pantry_items, 1)]

    candidate_recipes: list[dict[str, Any]] = []
    for result in candidate_results[: max(settings.openai_assistant_max_recipes, 1)]:
        recipe = result["recipe"]
        detail = get_recipe_detail(recipe_id=recipe["id"], db=result["db"], current_user=result["current_user"])
        candidate_recipes.append(
            {
                "recipe_id": recipe["id"],
                "title": recipe["title"],
                "total_minutes": recipe.get("total_minutes"),
                "matched_ingredients": result.get("matched_ingredients", []),
                "missing_ingredients": result.get("missing_ingredients", []),
                "dietary_tags": recipe.get("dietary_tags", []),
                "cuisine": recipe.get("cuisine"),
                "ingredients": [
                    ingredient["ingredient_normalized"]
                    for ingredient in (detail or {}).get("ingredients", [])[:12]
                    if ingredient.get("ingredient_normalized")
                ],
            }
        )

    pantry_items_to_use_first = [item["name"] for item in map(_serialize_inventory_item, prioritized_pantry[:6])]
    prioritization_hint = (
        "Prefer recipes that use the user's selected pantry items and also favor older perishable items first."
        if request.prioritize_oldest_items and prioritized_ingredients
        else "Prefer recipes that use older perishable items first."
        if request.prioritize_oldest_items
        else "Prefer recipes that use the user's selected pantry items first and do not force age-based prioritization."
        if prioritized_ingredients
        else "Prioritize pantry fit and user request without forcing age-based prioritization."
    )

    return {
        "user_request": {
            "goal": (request.user_goal or "").strip() or None,
            "main_ingredients": (request.main_ingredients or "").strip() or None,
            "max_total_minutes": request.max_total_minutes,
            "prioritize_oldest_items": request.prioritize_oldest_items,
            "prioritized_ingredients": prioritized_ingredients,
        },
        "prioritization_hint": prioritization_hint,
        "pantry_items_to_use_first": pantry_items_to_use_first,
        "pantry_items": [_serialize_inventory_item(item) for item in prioritized_pantry],
        "candidate_recipes": candidate_recipes,
    }


def build_recipe_assistant_response(
    *,
    db: Session,
    current_user: User,
    payload: RecipeAssistantUseUpRequest,
) -> RecipeAssistantUseUpRead:
    settings = get_settings()
    pantry_items = (
        db.query(InventoryItem)
        .filter(InventoryItem.user_id == current_user.id)
        .order_by(InventoryItem.created_at.asc().nulls_last(), InventoryItem.id.asc())
        .all()
    )

    if not pantry_items:
        return RecipeAssistantUseUpRead(
            summary="Add a few pantry items first so I can suggest recipes that fit what you already have.",
            strategy_note="Once your inventory has a few staples, I can help you use older or perishable items first.",
            pantry_items_to_use_first=[],
            recipes=[],
        )

    prioritized_ingredients = _normalize_prioritized_ingredients(
        prioritized_ingredients=payload.prioritized_ingredients,
        pantry_items=pantry_items,
    )

    recommendation_payload = recommend_recipes(
        db=db,
        current_user=current_user,
        main_ingredients=_build_effective_main_ingredients(
            request=payload,
            prioritized_ingredients=prioritized_ingredients,
        ),
        max_total_minutes=payload.max_total_minutes,
        page=1,
        page_size=max(settings.openai_assistant_max_recipes, 3),
    )
    raw_results = recommendation_payload.get("results", [])

    prioritized_pantry = _sort_pantry_items_for_assistant(
        pantry_items=pantry_items,
        prioritized_ingredients=prioritized_ingredients,
        prioritize_oldest_items=payload.prioritize_oldest_items,
    )
    pantry_items_to_use_first = [item.name for item in prioritized_pantry[:6]]

    if not raw_results:
        return _build_empty_response(pantry_items_to_use_first=pantry_items_to_use_first)

    candidate_results = [
        {
            **result,
            "db": db,
            "current_user": current_user,
        }
        for result in raw_results
    ]
    prompt_payload = _build_prompt_payload(
        request=payload,
        pantry_items=pantry_items,
        candidate_results=candidate_results,
    )
    llm_response = generate_recipe_assistant_plan(prompt_payload=prompt_payload)

    allowed_recipe_ids = {result["recipe"]["id"] for result in raw_results}
    allowed_title_by_id = {result["recipe"]["id"]: result["recipe"]["title"] for result in raw_results}
    filtered_recipes: list[RecipeAssistantSuggestionRead] = []
    for recipe in llm_response.recipes:
        if recipe.recipe_id not in allowed_recipe_ids:
            continue
        filtered_recipes.append(
            RecipeAssistantSuggestionRead(
                recipe_id=recipe.recipe_id,
                title=allowed_title_by_id[recipe.recipe_id],
                reason=recipe.reason,
                uses_up=recipe.uses_up,
                missing_ingredients=recipe.missing_ingredients,
                substitution_ideas=recipe.substitution_ideas,
                time_note=recipe.time_note,
            )
        )

    if not filtered_recipes:
        return RecipeAssistantUseUpRead(
            summary="I found some promising recipes, but I couldn't finalize the assistant summary this time.",
            strategy_note="Try again in a moment or use the manual recipe finder below.",
            pantry_items_to_use_first=pantry_items_to_use_first,
            recipes=[],
        )

    return RecipeAssistantUseUpRead(
        summary=llm_response.summary,
        strategy_note=llm_response.strategy_note,
        pantry_items_to_use_first=pantry_items_to_use_first,
        recipes=filtered_recipes,
    )
