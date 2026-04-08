from __future__ import annotations

from typing import Any, Optional

from app.models import Recipe, RecipeIngredient


def build_recipe_candidate_features(
    *,
    recipe: Recipe,
    recipe_ingredients: list[RecipeIngredient],
    inventory_names: set[str],
    normalized_main_ingredients: set[str],
    normalized_cuisine: Optional[str],
    max_total_minutes: Optional[int],
) -> dict[str, Any]:
    from app.services.recipes import ingredient_matches_any_term, ingredient_matches_term, normalize_term

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

    recipe_cuisine = normalize_term(recipe.cuisine) if recipe.cuisine else None
    cuisine_bonus = 1.0 if normalized_cuisine and recipe_cuisine == normalized_cuisine else 0.0
    time_bonus = 0.75 if max_total_minutes is not None and recipe.total_minutes is not None else 0.0
    overlap_bonus = 3.0 if match_count > 0 else -6.0

    return {
        "required_ingredient_count": required_count,
        "inventory_match_count": match_count,
        "match_ratio": round(match_ratio, 6),
        "matched_ingredients": matched_ingredients,
        "missing_ingredients": missing_ingredients,
        "missing_ingredient_count": len(missing_ingredients),
        "main_ingredient_match_count": main_ingredient_matches,
        "main_ingredient_present": main_ingredient_present,
        "main_ingredient_bonus": round(main_ingredient_bonus, 6),
        "cuisine_bonus": cuisine_bonus,
        "time_bonus": time_bonus,
        "overlap_bonus": overlap_bonus,
        "recipe_total_minutes": recipe.total_minutes,
        "recipe_rating": recipe.rating if recipe.rating is not None else 0.0,
        "has_inventory": 1 if inventory_names else 0,
    }


def score_recipe_candidate_deterministically(*, features: dict[str, Any]) -> float:
    required_count = int(features["required_ingredient_count"])
    if not features["has_inventory"]:
        base_score = -float(required_count or 999)
        total_minutes = features["recipe_total_minutes"]
        if total_minutes is not None:
            base_score -= float(total_minutes) / 1000.0
        return round(base_score, 4)

    base_score = (
        6.0 * float(features["match_ratio"])
        - 1.25 * int(features["missing_ingredient_count"])
        + float(features["main_ingredient_bonus"])
        + float(features["cuisine_bonus"])
        + float(features["time_bonus"])
        + float(features["overlap_bonus"])
    )
    return round(base_score, 4)
