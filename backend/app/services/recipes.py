from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import (
    InventoryChangeLog,
    InventoryItem,
    Recipe,
    RecipeFeedback,
    RecipeIngredient,
    RecipeTag,
    RecipeTagLink,
    User,
)


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

UNICODE_FRACTIONS = str.maketrans(
    {
        "¼": " 1/4 ",
        "½": " 1/2 ",
        "¾": " 3/4 ",
        "⅓": " 1/3 ",
        "⅔": " 2/3 ",
        "⅛": " 1/8 ",
        "⅜": " 3/8 ",
        "⅝": " 5/8 ",
        "⅞": " 7/8 ",
    }
)
LEADING_QUANTITY_CAPTURE_RE = re.compile(
    r"^\s*(?P<quantity>(?:\d+\s+\d+/\d+)|(?:\d+/\d+)|(?:\d+(?:\.\d+)?)|a|an)\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
RECIPE_UNIT_ALIASES = {
    "count": "count",
    "piece": "piece",
    "pieces": "piece",
    "egg": "count",
    "eggs": "count",
    "clove": "count",
    "cloves": "count",
    "slice": "slice",
    "slices": "slice",
    "can": "can",
    "cans": "can",
    "jar": "jar",
    "jars": "jar",
    "bottle": "bottle",
    "bottles": "bottle",
    "box": "box",
    "boxes": "box",
    "bag": "bag",
    "bags": "bag",
    "carton": "carton",
    "cartons": "carton",
    "pack": "pack",
    "packs": "pack",
    "g": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "oz": "oz",
    "ounce": "oz",
    "ounces": "oz",
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",
    "ml": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "l": "l",
    "liter": "l",
    "liters": "l",
    "cup": "cup",
    "cups": "cup",
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


def normalize_recipe_tag(value: str) -> str:
    normalized = normalize_term(value).lstrip("#")
    normalized = "".join(ch for ch in normalized if ch.isalnum() or ch in {"-", "_", " "})
    return normalized.replace(" ", "-")[:32].strip("-_")


def clean_recipe_tags(tags: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = normalize_recipe_tag(tag)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
        if len(cleaned) >= 12:
            break
    return cleaned


def parse_fractional_value(raw_value: str) -> float | None:
    text = raw_value.strip().lower()
    if text in {"a", "an"}:
        return 1.0
    if " " in text:
        parts = text.split()
        if len(parts) == 2 and "/" in parts[1]:
            try:
                whole = float(parts[0])
                numerator, denominator = parts[1].split("/", 1)
                return whole + (float(numerator) / float(denominator))
            except ValueError:
                return None
    if "/" in text:
        try:
            numerator, denominator = text.split("/", 1)
            return float(numerator) / float(denominator)
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_recipe_quantity(raw_ingredient: str) -> tuple[float | None, str | None, str | None]:
    normalized = normalize_term(raw_ingredient.translate(UNICODE_FRACTIONS))
    if not normalized:
        return None, None, None

    match = LEADING_QUANTITY_CAPTURE_RE.match(normalized)
    if not match:
        return None, None, None

    quantity_value = parse_fractional_value(match.group("quantity"))
    remainder = (match.group("rest") or "").strip()
    if quantity_value is None or not remainder:
        return None, None, None

    parts = remainder.split()
    first_token = parts[0].rstrip(".,")
    canonical_unit = RECIPE_UNIT_ALIASES.get(first_token)
    if canonical_unit:
        return quantity_value, canonical_unit, f"{match.group('quantity')} {first_token}"

    if quantity_value.is_integer():
        return quantity_value, "count", match.group("quantity")
    return None, None, match.group("quantity")


def convert_quantity_to_inventory_unit(quantity: float, recipe_unit: str, inventory_unit: str) -> float | None:
    if recipe_unit == inventory_unit:
        return quantity
    if {recipe_unit, inventory_unit} <= {"count", "piece"}:
        return quantity

    mass_to_grams = {"g": 1.0, "kg": 1000.0, "oz": 28.3495, "lb": 453.592}
    volume_to_ml = {"ml": 1.0, "l": 1000.0}

    if recipe_unit in mass_to_grams and inventory_unit in mass_to_grams:
        grams = quantity * mass_to_grams[recipe_unit]
        return grams / mass_to_grams[inventory_unit]

    if recipe_unit in volume_to_ml and inventory_unit in volume_to_ml:
        milliliters = quantity * volume_to_ml[recipe_unit]
        return milliliters / volume_to_ml[inventory_unit]

    return None


def build_inventory_options(*, db: Session, user_id: int) -> list[dict[str, Any]]:
    items = (
        db.query(InventoryItem)
        .filter(InventoryItem.user_id == user_id)
        .order_by(InventoryItem.name.asc(), InventoryItem.id.asc())
        .all()
    )
    return [
        {
            "id": item.id,
            "name": item.name,
            "normalized_name": item.normalized_name,
            "quantity": float(item.quantity),
            "unit": item.unit,
            "category": item.category,
        }
        for item in items
    ]


def find_best_inventory_match(
    *,
    inventory_items: list[InventoryItem],
    ingredient_name: str,
) -> InventoryItem | None:
    exact_matches = [
        item for item in inventory_items if canonicalize_ingredient_phrase(item.normalized_name or item.name) == ingredient_name
    ]
    if exact_matches:
        return exact_matches[0]

    loose_matches = [
        item for item in inventory_items if ingredient_matches_term(item.normalized_name or item.name, ingredient_name)
    ]
    if loose_matches:
        return loose_matches[0]
    return None


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
    favorite_tags: Optional[list[str]] = None,
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
        "favorite_tags": favorite_tags or [],
        "nutrition": nutrition if isinstance(nutrition, dict) else {},
        "created_at": recipe.created_at,
    }


def get_recipe_tags_map(
    *,
    db: Session,
    user_id: int,
    recipe_ids: list[int],
) -> dict[int, list[str]]:
    if not recipe_ids:
        return {}

    rows = (
        db.query(RecipeTagLink.recipe_id, RecipeTag.tag_name)
        .join(RecipeTag, RecipeTag.id == RecipeTagLink.tag_id)
        .filter(
            RecipeTagLink.user_id == user_id,
            RecipeTagLink.recipe_id.in_(recipe_ids),
        )
        .order_by(RecipeTag.tag_name.asc())
        .all()
    )
    tags_by_recipe: dict[int, list[str]] = defaultdict(list)
    for recipe_id, tag_name in rows:
        tags_by_recipe[int(recipe_id)].append(tag_name)
    return tags_by_recipe


def list_user_recipe_tags(
    *,
    db: Session,
    user_id: int,
) -> list[str]:
    rows = (
        db.query(RecipeTag.tag_name)
        .filter(RecipeTag.user_id == user_id)
        .order_by(RecipeTag.tag_name.asc())
        .all()
    )
    return [row[0] for row in rows]


def clear_recipe_tags_for_recipe(
    *,
    db: Session,
    user_id: int,
    recipe_id: int,
) -> None:
    db.query(RecipeTagLink).filter(
        RecipeTagLink.user_id == user_id,
        RecipeTagLink.recipe_id == recipe_id,
    ).delete(synchronize_session=False)
    prune_unused_recipe_tags(db=db, user_id=user_id)


def prune_unused_recipe_tags(*, db: Session, user_id: int) -> None:
    orphan_ids = [
        row[0]
        for row in db.query(RecipeTag.id)
        .outerjoin(
            RecipeTagLink,
            (RecipeTagLink.tag_id == RecipeTag.id) & (RecipeTagLink.user_id == user_id),
        )
        .filter(
            RecipeTag.user_id == user_id,
            RecipeTagLink.id.is_(None),
        )
        .all()
    ]
    if orphan_ids:
        db.query(RecipeTag).filter(
            RecipeTag.user_id == user_id,
            RecipeTag.id.in_(orphan_ids),
        ).delete(synchronize_session=False)


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
    favorite_tags: list[str] = []
    if current_user is not None:
        feedback_type = (
            db.query(RecipeFeedback.feedback_type)
            .filter(
                RecipeFeedback.user_id == current_user.id,
                RecipeFeedback.recipe_id == recipe.id,
            )
            .scalar()
        )
        favorite_tags = get_recipe_tags_map(
            db=db,
            user_id=current_user.id,
            recipe_ids=[recipe.id],
        ).get(recipe.id, [])

    detail = build_recipe_summary(
        recipe,
        current_feedback=feedback_type,
        favorite_tags=favorite_tags,
    )
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
    from app.core.config import get_settings
    from app.services.ranking_features import (
        build_recipe_candidate_features,
        score_recipe_candidate_deterministically,
    )
    from app.services.recommendation_ranker import score_feature_rows_with_learned_ranker

    settings = get_settings()
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
    learned_feature_rows: list[list[float]] = []
    learned_feature_names: list[str] = []
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

        features = build_recipe_candidate_features(
            recipe=recipe,
            recipe_ingredients=ingredients_by_recipe.get(recipe.id, []),
            inventory_names=inventory_names,
            normalized_main_ingredients=normalized_main_ingredients,
            normalized_cuisine=normalized_cuisine,
            max_total_minutes=max_total_minutes,
        )
        deterministic_score = score_recipe_candidate_deterministically(features=features)
        if not learned_feature_names:
            learned_feature_names = [
                key
                for key in features.keys()
                if key not in {"matched_ingredients", "missing_ingredients"}
            ]
        learned_feature_rows.append(
            [
                float(features.get(name) or 0.0)
                for name in learned_feature_names
            ]
        )

        ranked_results.append(
            {
                "recipe": build_recipe_summary(
                    recipe,
                    current_feedback=feedback_by_recipe_id.get(recipe.id),
                ),
                "score": deterministic_score,
                "deterministic_score": deterministic_score,
                "inventory_match_count": features["inventory_match_count"],
                "required_ingredient_count": features["required_ingredient_count"],
                "matched_ingredients": features["matched_ingredients"],
                "missing_ingredients": features["missing_ingredients"],
                "main_ingredient_match_count": features["main_ingredient_match_count"],
                "main_ingredient_present": features["main_ingredient_present"],
            }
        )

    learned_scores = score_feature_rows_with_learned_ranker(learned_feature_rows)
    if learned_scores is not None:
        for row, learned_score in zip(ranked_results, learned_scores):
            row["score"] = learned_score
            row["ranking_mode"] = settings.recipe_ranker_mode
        ranked_results.sort(
            key=lambda row: (
                row["score"],
                row["deterministic_score"],
                row["inventory_match_count"],
                -(row["recipe"]["total_minutes"] if row["recipe"]["total_minutes"] is not None else 10**9),
                row["recipe"]["title"],
            ),
            reverse=True,
        )
    else:
        for row in ranked_results:
            row["ranking_mode"] = "deterministic"
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
        "results": [
            {
                "recipe": row["recipe"],
                "score": row["score"],
                "inventory_match_count": row["inventory_match_count"],
                "required_ingredient_count": row["required_ingredient_count"],
                "matched_ingredients": row["matched_ingredients"],
                "missing_ingredients": row["missing_ingredients"],
            }
            for row in ranked_results[start_index:end_index]
        ],
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

    if feedback_type != "like":
        clear_recipe_tags_for_recipe(
            db=db,
            user_id=current_user.id,
            recipe_id=recipe_id,
        )

    db.commit()
    return {
        "recipe_id": recipe_id,
        "feedback_type": feedback.feedback_type,
    }


def remove_recipe_feedback(
    *,
    db: Session,
    current_user: User,
    recipe_id: int,
) -> bool:
    feedback = (
        db.query(RecipeFeedback)
        .filter(
            RecipeFeedback.user_id == current_user.id,
            RecipeFeedback.recipe_id == recipe_id,
        )
        .first()
    )
    if feedback is None:
        return False

    clear_recipe_tags_for_recipe(
        db=db,
        user_id=current_user.id,
        recipe_id=recipe_id,
    )
    db.delete(feedback)
    db.commit()
    return True


def set_recipe_tags(
    *,
    db: Session,
    current_user: User,
    recipe_id: int,
    tags: list[str],
) -> dict[str, Any] | None:
    feedback = (
        db.query(RecipeFeedback)
        .filter(
            RecipeFeedback.user_id == current_user.id,
            RecipeFeedback.recipe_id == recipe_id,
            RecipeFeedback.feedback_type == "like",
        )
        .first()
    )
    if feedback is None:
        return None

    cleaned_tags = clean_recipe_tags(tags)
    existing_tags = (
        db.query(RecipeTag)
        .filter(
            RecipeTag.user_id == current_user.id,
            RecipeTag.tag_name.in_(cleaned_tags) if cleaned_tags else False,
        )
        .all()
        if cleaned_tags
        else []
    )
    tag_by_name = {tag.tag_name: tag for tag in existing_tags}
    for tag_name in cleaned_tags:
        if tag_name in tag_by_name:
            continue
        tag = RecipeTag(user_id=current_user.id, tag_name=tag_name)
        db.add(tag)
        db.flush()
        tag_by_name[tag_name] = tag

    existing_links = (
        db.query(RecipeTagLink, RecipeTag.tag_name)
        .join(RecipeTag, RecipeTag.id == RecipeTagLink.tag_id)
        .filter(
            RecipeTagLink.user_id == current_user.id,
            RecipeTagLink.recipe_id == recipe_id,
        )
        .all()
    )
    linked_tag_names = {tag_name for _, tag_name in existing_links}

    desired_tag_names = set(cleaned_tags)
    for link, tag_name in existing_links:
        if tag_name not in desired_tag_names:
            db.delete(link)

    for tag_name in cleaned_tags:
        if tag_name in linked_tag_names:
            continue
        db.add(
            RecipeTagLink(
                user_id=current_user.id,
                recipe_id=recipe_id,
                tag_id=tag_by_name[tag_name].id,
            )
        )

    db.flush()
    prune_unused_recipe_tags(db=db, user_id=current_user.id)
    db.commit()
    return {
        "recipe_id": recipe_id,
        "tags": cleaned_tags,
    }


def list_saved_recipes(
    *,
    db: Session,
    current_user: User,
) -> dict[str, Any]:
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
        return {"available_tags": list_user_recipe_tags(db=db, user_id=current_user.id), "results": []}

    recipes = db.query(Recipe).filter(Recipe.id.in_(liked_recipe_ids)).all()
    recipes_by_id = {recipe.id: recipe for recipe in recipes}
    tags_by_recipe_id = get_recipe_tags_map(
        db=db,
        user_id=current_user.id,
        recipe_ids=liked_recipe_ids,
    )
    return {
        "available_tags": list_user_recipe_tags(db=db, user_id=current_user.id),
        "results": [
            build_recipe_summary(
                recipes_by_id[recipe_id],
                current_feedback="like",
                favorite_tags=tags_by_recipe_id.get(recipe_id, []),
            )
            for recipe_id in liked_recipe_ids
            if recipe_id in recipes_by_id
        ],
    }


def preview_recipe_cook_updates(
    *,
    db: Session,
    current_user: User,
    recipe_id: int,
    multiplier: float,
) -> dict[str, Any] | None:
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if recipe is None:
        return None

    inventory_items = (
        db.query(InventoryItem)
        .filter(InventoryItem.user_id == current_user.id)
        .order_by(InventoryItem.name.asc(), InventoryItem.id.asc())
        .all()
    )
    ingredients = (
        db.query(RecipeIngredient)
        .filter(RecipeIngredient.recipe_id == recipe_id)
        .order_by(RecipeIngredient.id.asc())
        .all()
    )

    preview_items: list[dict[str, Any]] = []
    scaled_multiplier = max(multiplier, 0.1)
    for index, ingredient in enumerate(ingredients):
        parsed_quantity, parsed_unit, quantity_text = parse_recipe_quantity(ingredient.ingredient_raw)
        inventory_match = find_best_inventory_match(
            inventory_items=inventory_items,
            ingredient_name=ingredient.ingredient_normalized,
        )

        item_preview: dict[str, Any] = {
            "ingredient_key": f"{recipe_id}:{index}",
            "ingredient_raw": ingredient.ingredient_raw,
            "ingredient_normalized": ingredient.ingredient_normalized,
            "quantity_text": quantity_text or ingredient.quantity_text,
            "match_status": "unmatched",
            "selected_inventory_item_id": None,
            "selected_inventory_item_name": None,
            "inventory_item_quantity": None,
            "inventory_item_unit": None,
            "reliable_quantity_match": False,
            "suggested_used_quantity": None,
            "suggested_remaining_quantity": None,
            "notes": [],
        }

        if inventory_match is not None:
            item_preview["selected_inventory_item_id"] = inventory_match.id
            item_preview["selected_inventory_item_name"] = inventory_match.name
            item_preview["inventory_item_quantity"] = float(inventory_match.quantity)
            item_preview["inventory_item_unit"] = inventory_match.unit
            item_preview["match_status"] = "needs_review"

            if parsed_quantity is not None and parsed_unit is not None:
                converted_quantity = convert_quantity_to_inventory_unit(
                    parsed_quantity * scaled_multiplier,
                    parsed_unit,
                    inventory_match.unit,
                )
                if converted_quantity is not None:
                    item_preview["reliable_quantity_match"] = True
                    item_preview["match_status"] = "matched"
                    item_preview["suggested_used_quantity"] = round(converted_quantity, 3)
                    item_preview["suggested_remaining_quantity"] = round(
                        float(inventory_match.quantity) - converted_quantity,
                        3,
                    )
                    if item_preview["suggested_remaining_quantity"] <= 0:
                        item_preview["notes"].append(
                            "This update would use up the matched pantry item. Choose whether to remove it or set a manual quantity."
                        )
                    else:
                        item_preview["notes"].append(
                            "Suggested remaining quantity is ready to review. You can still edit it before applying."
                        )
                else:
                    item_preview["notes"].append(
                        "A pantry match was found, but unit conversion needs review before we update quantities."
                    )
            else:
                item_preview["notes"].append(
                    "A pantry match was found, but this ingredient needs manual review because its quantity is not structured."
                )
        else:
            item_preview["notes"].append(
                "No pantry match found yet. You can ignore this ingredient or manually choose an inventory item in the review step."
            )

        preview_items.append(item_preview)

    return {
        "recipe_id": recipe_id,
        "multiplier": scaled_multiplier,
        "inventory_options": build_inventory_options(db=db, user_id=current_user.id),
        "items": preview_items,
    }


def apply_recipe_cook_updates(
    *,
    db: Session,
    current_user: User,
    recipe_id: int,
    multiplier: float,
    actions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if recipe is None:
        return None

    updated = 0
    removed = 0
    ignored = 0

    for action in actions:
        decision = action["decision"]
        if decision == "ignore":
            ignored += 1
            continue

        inventory_item_id = action.get("inventory_item_id")
        if inventory_item_id is None:
            ignored += 1
            continue

        inventory_item = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.id == inventory_item_id,
                InventoryItem.user_id == current_user.id,
            )
            .first()
        )
        if inventory_item is None:
            ignored += 1
            continue

        previous_quantity = float(inventory_item.quantity)
        if decision == "remove":
            log = InventoryChangeLog(
                user_id=current_user.id,
                inventory_item_id=inventory_item.id,
                session_id=None,
                proposal_id=None,
                change_type="recipe_cooked_remove",
                delta_quantity=-previous_quantity,
                details_json=json.dumps(
                {
                    "recipe_id": recipe_id,
                    "recipe_title": recipe.title,
                    "multiplier": multiplier,
                    "ingredient_raw": action["ingredient_raw"],
                    "ingredient_normalized": action["ingredient_normalized"],
                    "decision": "remove",
                    "previous_unit": inventory_item.unit,
                }
            ),
        )
            db.add(log)
            db.delete(inventory_item)
            removed += 1
            continue

        new_quantity = action.get("new_quantity")
        if new_quantity is None:
            ignored += 1
            continue

        new_quantity_value = max(float(new_quantity), 0.0)
        previous_unit = inventory_item.unit
        new_unit = action.get("new_unit") or previous_unit
        inventory_item.quantity = new_quantity_value
        inventory_item.unit = new_unit
        db.add(inventory_item)
        delta_quantity = new_quantity_value - previous_quantity
        log = InventoryChangeLog(
            user_id=current_user.id,
            inventory_item_id=inventory_item.id,
            session_id=None,
            proposal_id=None,
            change_type="recipe_cooked_update",
            delta_quantity=delta_quantity,
            details_json=json.dumps(
                {
                    "recipe_id": recipe_id,
                    "recipe_title": recipe.title,
                    "multiplier": multiplier,
                    "ingredient_raw": action["ingredient_raw"],
                    "ingredient_normalized": action["ingredient_normalized"],
                    "decision": "update",
                    "new_quantity": new_quantity_value,
                    "new_unit": new_unit,
                    "previous_unit": previous_unit,
                    "previous_quantity": previous_quantity,
                }
            ),
        )
        db.add(log)
        updated += 1

    db.commit()
    return {
        "recipe_id": recipe_id,
        "multiplier": multiplier,
        "updated": updated,
        "removed": removed,
        "ignored": ignored,
    }
