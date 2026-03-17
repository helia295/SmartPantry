from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import InventoryItem, Recipe, RecipeIngredient, User


def normalize_term(value: str) -> str:
    return " ".join(value.strip().lower().split())


def parse_csv_terms(raw_value: Optional[str]) -> list[str]:
    if not raw_value:
        return []
    return [normalize_term(part) for part in raw_value.split(",") if normalize_term(part)]


def build_recipe_summary(recipe: Recipe) -> dict[str, Any]:
    try:
        dietary_tags = json.loads(recipe.dietary_tags_json or "[]")
    except json.JSONDecodeError:
        dietary_tags = []

    try:
        nutrition = json.loads(recipe.nutrition_json or "{}")
    except json.JSONDecodeError:
        nutrition = {}

    return {
        "id": recipe.id,
        "title": recipe.title,
        "slug": recipe.slug,
        "source_name": recipe.source_name,
        "source_url": recipe.source_url,
        "image_url": recipe.image_url,
        "rating": recipe.rating,
        "prep_minutes": recipe.prep_minutes,
        "cook_minutes": recipe.cook_minutes,
        "total_minutes": recipe.total_minutes,
        "servings": recipe.servings,
        "cuisine": recipe.cuisine,
        "dietary_tags": dietary_tags if isinstance(dietary_tags, list) else [],
        "nutrition": nutrition if isinstance(nutrition, dict) else {},
        "created_at": recipe.created_at,
    }


def get_recipe_detail(
    recipe_id: int,
    db: Session,
) -> Optional[dict[str, Any]]:
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if recipe is None:
        return None

    ingredients = (
        db.query(RecipeIngredient)
        .filter(RecipeIngredient.recipe_id == recipe.id)
        .order_by(RecipeIngredient.id.asc())
        .all()
    )

    detail = build_recipe_summary(recipe)
    detail["instructions_text"] = recipe.instructions_text
    detail["ingredients"] = [
        {
            "ingredient_raw": ingredient.ingredient_raw,
            "ingredient_normalized": ingredient.ingredient_normalized,
            "quantity_text": ingredient.quantity_text,
            "is_optional": ingredient.is_optional,
        }
        for ingredient in ingredients
    ]
    return detail


def recommend_recipes(
    *,
    db: Session,
    current_user: User,
    main_ingredients: Optional[str] = None,
    cuisine: Optional[str] = None,
    max_total_minutes: Optional[int] = None,
    dietary_tags: Optional[str] = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    normalized_main_ingredients = set(parse_csv_terms(main_ingredients))
    normalized_dietary_tags = set(parse_csv_terms(dietary_tags))
    normalized_cuisine = normalize_term(cuisine) if cuisine else None
    inventory_names = {
        normalize_term(item.normalized_name or item.name)
        for item in db.query(InventoryItem)
        .filter(InventoryItem.user_id == current_user.id)
        .all()
    }
    match_terms = inventory_names | normalized_main_ingredients

    candidate_recipe_ids: list[int]
    if match_terms:
        candidate_rows = (
            db.query(
                RecipeIngredient.recipe_id,
                func.count(RecipeIngredient.id).label("match_count"),
            )
            .filter(RecipeIngredient.ingredient_normalized.in_(match_terms))
            .group_by(RecipeIngredient.recipe_id)
            .order_by(func.count(RecipeIngredient.id).desc(), RecipeIngredient.recipe_id.asc())
            .limit(500)
            .all()
        )
        candidate_recipe_ids = [int(row.recipe_id) for row in candidate_rows]
        if not candidate_recipe_ids:
            return []
    else:
        candidate_recipe_ids = [
            row[0]
            for row in db.query(Recipe.id)
            .order_by(
                Recipe.total_minutes.asc().nulls_last(),
                Recipe.id.asc(),
            )
            .limit(250)
            .all()
        ]

    if not candidate_recipe_ids:
        return []

    recipes = (
        db.query(Recipe)
        .filter(Recipe.id.in_(candidate_recipe_ids))
        .order_by(Recipe.title.asc())
        .all()
    )
    ingredients = (
        db.query(RecipeIngredient)
        .filter(RecipeIngredient.recipe_id.in_(candidate_recipe_ids))
        .order_by(RecipeIngredient.recipe_id.asc(), RecipeIngredient.id.asc())
        .all()
    )

    ingredients_by_recipe: dict[int, list[RecipeIngredient]] = defaultdict(list)
    for ingredient in ingredients:
        ingredients_by_recipe[ingredient.recipe_id].append(ingredient)

    ranked_results: list[dict[str, Any]] = []
    for recipe in recipes:
        recipe_tags = build_recipe_summary(recipe)["dietary_tags"]
        normalized_recipe_tags = {normalize_term(tag) for tag in recipe_tags if isinstance(tag, str)}
        if normalized_dietary_tags and not normalized_dietary_tags.issubset(normalized_recipe_tags):
            continue

        recipe_cuisine = normalize_term(recipe.cuisine) if recipe.cuisine else None
        if normalized_cuisine and recipe_cuisine != normalized_cuisine:
            continue

        if max_total_minutes is not None and recipe.total_minutes is not None:
            if recipe.total_minutes > max_total_minutes:
                continue

        recipe_ingredients = ingredients_by_recipe.get(recipe.id, [])
        required_ingredients = [
            ingredient
            for ingredient in recipe_ingredients
            if not ingredient.is_optional and ingredient.ingredient_normalized
        ]
        required_names = [ingredient.ingredient_normalized for ingredient in required_ingredients]
        matched_ingredients = sorted({name for name in required_names if name in inventory_names})
        missing_ingredients = sorted({name for name in required_names if name not in inventory_names})

        required_count = len(required_names)
        match_count = len(matched_ingredients)
        match_ratio = (match_count / required_count) if required_count else 0.0

        main_ingredient_matches = len(
            [name for name in normalized_main_ingredients if name in matched_ingredients]
        )
        if normalized_main_ingredients:
            main_ingredient_bonus = 2.0 * (main_ingredient_matches / len(normalized_main_ingredients))
        else:
            main_ingredient_bonus = 0.0

        cuisine_bonus = 1.0 if normalized_cuisine and recipe_cuisine == normalized_cuisine else 0.0
        time_bonus = 0.75 if max_total_minutes is not None and recipe.total_minutes is not None else 0.0

        if not inventory_names:
            base_score = -float(required_count or 999)
            if recipe.total_minutes is not None:
                base_score -= recipe.total_minutes / 1000.0
        else:
            overlap_bonus = 3.0 if match_count > 0 else -6.0
            base_score = (
                6.0 * match_ratio
                - 1.25 * len(missing_ingredients)
                + main_ingredient_bonus
                + cuisine_bonus
                + time_bonus
                + overlap_bonus
            )

        ranked_results.append(
            {
                "recipe": build_recipe_summary(recipe),
                "score": round(base_score, 4),
                "inventory_match_count": match_count,
                "required_ingredient_count": required_count,
                "matched_ingredients": matched_ingredients,
                "missing_ingredients": missing_ingredients,
            }
        )

    ranked_results.sort(
        key=lambda row: (
            row["score"],
            row["inventory_match_count"],
            -(row["recipe"]["total_minutes"] if row["recipe"]["total_minutes"] is not None else 10**9),
            row["recipe"]["title"],
        ),
        reverse=True,
    )
    return ranked_results[: max(1, min(limit, 20))]
