from __future__ import annotations

import json
import math
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import InventoryItem, Recipe, RecipeEmbedding, RecipeFeedback, RecipeIngredient, User
from app.services.embeddings import embed_text
from app.services.recipes import (
    build_recipe_summary,
    canonicalize_ingredient_phrase,
    ingredient_matches_any_term,
)


def build_recipe_embedding_document(*, recipe: Recipe, ingredients: list[RecipeIngredient]) -> str:
    try:
        dietary_tags = json.loads(recipe.dietary_tags_json or "[]")
    except json.JSONDecodeError:
        dietary_tags = []

    ingredient_names = [
        ingredient.ingredient_normalized
        for ingredient in ingredients
        if ingredient.ingredient_normalized
    ]
    instructions_summary = (recipe.instructions_text or "").strip().replace("\n", " ")
    if len(instructions_summary) > 420:
        instructions_summary = f"{instructions_summary[:417].rstrip()}..."

    lines = [
        f"Title: {recipe.title}",
        f"Cuisine: {recipe.cuisine or 'unspecified'}",
        f"Dietary tags: {', '.join(tag for tag in dietary_tags if isinstance(tag, str)) or 'none'}",
        f"Total minutes: {recipe.total_minutes if recipe.total_minutes is not None else 'unknown'}",
        f"Ingredients: {', '.join(ingredient_names[:20]) or 'unknown'}",
        f"Instructions: {instructions_summary or 'No instructions summary available.'}",
    ]
    return "\n".join(lines)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return -1.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return -1.0
    return dot / (left_norm * right_norm)


def upsert_recipe_embedding(
    *,
    db: Session,
    recipe: Recipe,
    document_text: str,
    embedding: list[float],
) -> RecipeEmbedding:
    existing = db.query(RecipeEmbedding).filter(RecipeEmbedding.recipe_id == recipe.id).one_or_none()
    if existing is None:
        existing = RecipeEmbedding(
            recipe_id=recipe.id,
            document_type="recipe",
        )
        db.add(existing)

    existing.document_text = document_text
    existing.title_snapshot = recipe.title
    existing.total_minutes_snapshot = recipe.total_minutes
    existing.embedding = embedding
    db.flush()
    return existing


def indexable_recipe_rows(*, db: Session, recipe_ids: Optional[list[int]] = None) -> list[tuple[Recipe, list[RecipeIngredient]]]:
    query = db.query(Recipe)
    if recipe_ids:
        query = query.filter(Recipe.id.in_(recipe_ids))
    recipes = query.order_by(Recipe.id.asc()).all()
    if not recipes:
        return []

    ingredients = (
        db.query(RecipeIngredient)
        .filter(RecipeIngredient.recipe_id.in_([recipe.id for recipe in recipes]))
        .order_by(RecipeIngredient.recipe_id.asc(), RecipeIngredient.id.asc())
        .all()
    )
    by_recipe_id: dict[int, list[RecipeIngredient]] = {}
    for ingredient in ingredients:
        by_recipe_id.setdefault(ingredient.recipe_id, []).append(ingredient)

    return [(recipe, by_recipe_id.get(recipe.id, [])) for recipe in recipes]


def _retrieve_candidates_postgres(
    *,
    db: Session,
    query_embedding: list[float],
    limit: int,
) -> list[dict[str, Any]]:
    embedding_literal = "[" + ",".join(f"{value:.8f}" for value in query_embedding) + "]"
    rows = db.execute(
        text(
            """
            SELECT
                recipe_id,
                title_snapshot,
                total_minutes_snapshot,
                document_text,
                1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM recipe_embeddings
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
            """
        ),
        {"embedding": embedding_literal, "limit": limit},
    ).mappings().all()
    return [dict(row) for row in rows]


def _retrieve_candidates_fallback(
    *,
    db: Session,
    query_embedding: list[float],
    limit: int,
) -> list[dict[str, Any]]:
    rows = db.query(RecipeEmbedding).all()
    ranked = [
        {
            "recipe_id": row.recipe_id,
            "title_snapshot": row.title_snapshot,
            "total_minutes_snapshot": row.total_minutes_snapshot,
            "document_text": row.document_text,
            "similarity": _cosine_similarity(list(row.embedding or []), query_embedding),
        }
        for row in rows
    ]
    ranked.sort(key=lambda item: item["similarity"], reverse=True)
    return ranked[:limit]


def retrieve_recipe_candidates(
    *,
    db: Session,
    current_user: User,
    question: str,
    max_total_minutes: Optional[int],
    limit: int,
) -> list[dict[str, Any]]:
    query_embedding = embed_text(text=question)
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        raw_candidates = _retrieve_candidates_postgres(
            db=db,
            query_embedding=query_embedding,
            limit=max(limit, 1),
        )
    else:
        raw_candidates = _retrieve_candidates_fallback(
            db=db,
            query_embedding=query_embedding,
            limit=max(limit, 1),
        )

    if not raw_candidates:
        return []

    candidate_ids = [int(candidate["recipe_id"]) for candidate in raw_candidates]
    recipes = {
        recipe.id: recipe
        for recipe in db.query(Recipe).filter(Recipe.id.in_(candidate_ids)).all()
    }
    ingredients = (
        db.query(RecipeIngredient)
        .filter(RecipeIngredient.recipe_id.in_(candidate_ids))
        .order_by(RecipeIngredient.recipe_id.asc(), RecipeIngredient.id.asc())
        .all()
    )
    by_recipe_id: dict[int, list[RecipeIngredient]] = {}
    for ingredient in ingredients:
        by_recipe_id.setdefault(ingredient.recipe_id, []).append(ingredient)

    inventory_names = {
        canonicalize_ingredient_phrase(item.normalized_name or item.name)
        for item in db.query(InventoryItem)
        .filter(InventoryItem.user_id == current_user.id)
        .all()
    }
    feedback_rows = (
        db.query(RecipeFeedback.recipe_id, RecipeFeedback.feedback_type)
        .filter(RecipeFeedback.user_id == current_user.id)
        .all()
    )
    disliked_recipe_ids = {
        int(recipe_id) for recipe_id, feedback_type in feedback_rows if feedback_type == "dislike"
    }

    ranked_results: list[dict[str, Any]] = []
    for candidate in raw_candidates:
        recipe_id = int(candidate["recipe_id"])
        recipe = recipes.get(recipe_id)
        if recipe is None or recipe_id in disliked_recipe_ids:
            continue
        if max_total_minutes is not None and recipe.total_minutes is not None and recipe.total_minutes > max_total_minutes:
            continue

        recipe_ingredients = by_recipe_id.get(recipe_id, [])
        required_names = [
            ingredient.ingredient_normalized
            for ingredient in recipe_ingredients
            if not ingredient.is_optional and ingredient.ingredient_normalized
        ]
        matched_ingredients = sorted(
            {name for name in required_names if ingredient_matches_any_term(name, inventory_names)}
        )
        missing_ingredients = sorted(
            {name for name in required_names if not ingredient_matches_any_term(name, inventory_names)}
        )
        pantry_overlap = len(matched_ingredients)
        adjusted_score = (
            float(candidate.get("similarity") or 0.0)
            + 0.08 * pantry_overlap
            - 0.04 * len(missing_ingredients)
        )

        ranked_results.append(
            {
                "recipe": build_recipe_summary(recipe),
                "document_text": candidate["document_text"],
                "similarity": round(float(candidate.get("similarity") or 0.0), 4),
                "adjusted_score": round(adjusted_score, 4),
                "matched_ingredients": matched_ingredients,
                "missing_ingredients": missing_ingredients,
                "inventory_match_count": pantry_overlap,
            }
        )

    ranked_results.sort(
        key=lambda row: (
            row["adjusted_score"],
            row["inventory_match_count"],
            -(row["recipe"]["total_minutes"] if row["recipe"]["total_minutes"] is not None else 10**9),
            row["recipe"]["title"],
        ),
        reverse=True,
    )
    return ranked_results[:limit]
