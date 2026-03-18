from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import InventoryItem, Recipe, RecipeFeedback, RecipeIngredient, User


INGREDIENT_ALIASES = {
    "ap flour": "all-purpose flour",
    "all purpose flour": "all-purpose flour",
    "plain flour": "all-purpose flour",
    "garbanzo bean": "chickpea",
    "garbanzo beans": "chickpea",
    "chickpeas": "chickpea",
    "scallions": "green onion",
    "spring onions": "green onion",
    "green onions": "green onion",
    "capsicum": "bell pepper",
    "capsicums": "bell pepper",
    "bell peppers": "bell pepper",
    "sweet corn": "corn",
    "corn kernels": "corn",
    "kernel corn": "corn",
    "whole kernel corn": "corn",
    "cream-style corn": "corn",
    "peaches": "peach",
    "oranges": "orange",
    "eggs": "egg",
    "tomatoes": "tomato",
}


def normalize_term(value: str) -> str:
    return " ".join(value.strip().lower().split())


def canonicalize_ingredient_phrase(value: str) -> str:
    normalized = normalize_term(value)
    if not normalized:
        return ""

    normalized = normalized.replace("_", " ").replace("&", " and ")
    alias_match = INGREDIENT_ALIASES.get(normalized)
    if alias_match:
        return alias_match

    tokens = normalized.split()
    canonical_tokens = [INGREDIENT_ALIASES.get(token, token) for token in tokens]
    canonical = " ".join(canonical_tokens).strip()
    return INGREDIENT_ALIASES.get(canonical, canonical)


def parse_csv_terms(raw_value: Optional[str]) -> list[str]:
    if not raw_value:
        return []
    return [canonicalize_ingredient_phrase(part) for part in raw_value.split(",") if canonicalize_ingredient_phrase(part)]


def ingredient_matches_term(ingredient_name: str, term: str) -> bool:
    normalized_ingredient = canonicalize_ingredient_phrase(ingredient_name)
    normalized_term = canonicalize_ingredient_phrase(term)
    if not normalized_ingredient or not normalized_term:
        return False
    return normalized_ingredient == normalized_term or normalized_term in normalized_ingredient.split()


def ingredient_matches_any_term(ingredient_name: str, terms: set[str]) -> bool:
    return any(ingredient_matches_term(ingredient_name, term) for term in terms)


def build_recipe_summary(
    recipe: Recipe,
    *,
    current_feedback: Optional[str] = None,
) -> dict[str, Any]:
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
        "current_feedback": current_feedback,
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
    *,
    current_user: Optional[User] = None,
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

    feedback_type: Optional[str] = None
    if current_user is not None:
        feedback_type = (
            db.query(RecipeFeedback.feedback_type)
            .filter(
                RecipeFeedback.user_id == current_user.id,
                RecipeFeedback.recipe_id == recipe.id,
            )
            .scalar()
        )

    detail = build_recipe_summary(recipe, current_feedback=feedback_type)
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
    page: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    normalized_main_ingredients = set(parse_csv_terms(main_ingredients))
    normalized_dietary_tags = set(parse_csv_terms(dietary_tags))
    normalized_cuisine = normalize_term(cuisine) if cuisine else None
    inventory_names = {
        canonicalize_ingredient_phrase(item.normalized_name or item.name)
        for item in db.query(InventoryItem)
        .filter(InventoryItem.user_id == current_user.id)
        .all()
    }
    match_terms = inventory_names | normalized_main_ingredients
    feedback_rows = (
        db.query(RecipeFeedback.recipe_id, RecipeFeedback.feedback_type)
        .filter(RecipeFeedback.user_id == current_user.id)
        .all()
    )
    feedback_by_recipe_id = {int(row.recipe_id): row.feedback_type for row in feedback_rows}
    disliked_recipe_ids = {
        recipe_id for recipe_id, feedback_type in feedback_by_recipe_id.items() if feedback_type == "dislike"
    }

    candidate_recipe_ids: list[int]
    if match_terms:
        candidate_filter = or_(
            *[
                or_(
                    RecipeIngredient.ingredient_normalized == term,
                    RecipeIngredient.ingredient_normalized.like(f"%{term}%"),
                )
                for term in sorted(match_terms)
            ]
        )
        candidate_rows = (
            db.query(
                RecipeIngredient.recipe_id,
                func.count(RecipeIngredient.id).label("match_count"),
            )
            .filter(candidate_filter)
            .group_by(RecipeIngredient.recipe_id)
            .order_by(func.count(RecipeIngredient.id).desc(), RecipeIngredient.recipe_id.asc())
            .all()
        )
        candidate_recipe_ids = [
            int(row.recipe_id) for row in candidate_rows if int(row.recipe_id) not in disliked_recipe_ids
        ]
        if not candidate_recipe_ids:
            return {
                "page": page,
                "page_size": page_size,
                "total_results": 0,
                "total_pages": 0,
                "results": [],
            }
    else:
        candidate_recipe_ids = [
            row[0]
            for row in db.query(Recipe.id)
            .filter(~Recipe.id.in_(disliked_recipe_ids) if disliked_recipe_ids else True)
            .order_by(
                Recipe.total_minutes.asc().nulls_last(),
                Recipe.id.asc(),
            )
            .all()
        ]

    if not candidate_recipe_ids:
        return {
            "page": page,
            "page_size": page_size,
            "total_results": 0,
            "total_pages": 0,
            "results": [],
        }

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
        if recipe.id in disliked_recipe_ids:
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
        matched_ingredients = sorted(
            {name for name in required_names if ingredient_matches_any_term(name, inventory_names)}
        )
        missing_ingredients = sorted(
            {name for name in required_names if not ingredient_matches_any_term(name, inventory_names)}
        )

        required_count = len(required_names)
        match_count = len(matched_ingredients)
        match_ratio = (match_count / required_count) if required_count else 0.0

        main_ingredient_matches = len(
            [
                name
                for name in normalized_main_ingredients
                if any(ingredient_matches_term(matched_name, name) for matched_name in matched_ingredients)
            ]
        )
        main_ingredient_present = 1 if main_ingredient_matches > 0 else 0
        if normalized_main_ingredients:
            main_ingredient_bonus = 6.0 * (main_ingredient_matches / len(normalized_main_ingredients))
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
                "recipe": build_recipe_summary(
                    recipe,
                    current_feedback=feedback_by_recipe_id.get(recipe.id),
                ),
                "score": round(base_score, 4),
                "inventory_match_count": match_count,
                "required_ingredient_count": required_count,
                "matched_ingredients": matched_ingredients,
                "missing_ingredients": missing_ingredients,
                "main_ingredient_match_count": main_ingredient_matches,
                "main_ingredient_present": main_ingredient_present,
            }
        )

    ranked_results.sort(
        key=lambda row: (
            row["main_ingredient_present"],
            row["main_ingredient_match_count"],
            row["score"],
            row["inventory_match_count"],
            -(row["recipe"]["total_minutes"] if row["recipe"]["total_minutes"] is not None else 10**9),
            row["recipe"]["title"],
        ),
        reverse=True,
    )
    normalized_page_size = max(1, min(page_size, 50))
    normalized_page = max(1, page)
    total_results = len(ranked_results)
    total_pages = (total_results + normalized_page_size - 1) // normalized_page_size
    start_index = (normalized_page - 1) * normalized_page_size
    end_index = start_index + normalized_page_size
    return {
        "page": normalized_page,
        "page_size": normalized_page_size,
        "total_results": total_results,
        "total_pages": total_pages,
        "results": ranked_results[start_index:end_index],
    }


def upsert_recipe_feedback(
    *,
    db: Session,
    current_user: User,
    recipe_id: int,
    feedback_type: str,
) -> dict[str, Any] | None:
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if recipe is None:
        return None

    feedback = (
        db.query(RecipeFeedback)
        .filter(
            RecipeFeedback.user_id == current_user.id,
            RecipeFeedback.recipe_id == recipe_id,
        )
        .first()
    )
    if feedback is None:
        feedback = RecipeFeedback(
            user_id=current_user.id,
            recipe_id=recipe_id,
            feedback_type=feedback_type,
        )
        db.add(feedback)
    else:
        feedback.feedback_type = feedback_type

    db.commit()
    return {
        "recipe_id": recipe_id,
        "feedback_type": feedback.feedback_type,
    }


def list_saved_recipes(
    *,
    db: Session,
    current_user: User,
) -> list[dict[str, Any]]:
    liked_recipe_ids = [
        row[0]
        for row in db.query(RecipeFeedback.recipe_id)
        .filter(
            RecipeFeedback.user_id == current_user.id,
            RecipeFeedback.feedback_type == "like",
        )
        .order_by(RecipeFeedback.created_at.desc(), RecipeFeedback.id.desc())
        .all()
    ]
    if not liked_recipe_ids:
        return []

    recipes = db.query(Recipe).filter(Recipe.id.in_(liked_recipe_ids)).all()
    recipes_by_id = {recipe.id: recipe for recipe in recipes}
    return [
        build_recipe_summary(recipes_by_id[recipe_id], current_feedback="like")
        for recipe_id in liked_recipe_ids
        if recipe_id in recipes_by_id
    ]
