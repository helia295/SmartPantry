from __future__ import annotations

import csv
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from app.models import InventoryItem, Recipe, RecipeFeedback, RecipeIngredient
from app.services.ranking_features import build_recipe_candidate_features
from app.services.recipes import canonicalize_ingredient_phrase


@dataclass
class RankingExample:
    context_id: str
    user_id: int
    recipe_id: int
    label: int
    source: str
    features: dict[str, Any]


def _recipe_rows_with_ingredients(db: Session) -> list[tuple[Recipe, list[RecipeIngredient]]]:
    recipes = db.query(Recipe).order_by(Recipe.id.asc()).all()
    ingredients = (
        db.query(RecipeIngredient)
        .order_by(RecipeIngredient.recipe_id.asc(), RecipeIngredient.id.asc())
        .all()
    )
    ingredients_by_recipe: dict[int, list[RecipeIngredient]] = defaultdict(list)
    for ingredient in ingredients:
        ingredients_by_recipe[ingredient.recipe_id].append(ingredient)
    return [(recipe, ingredients_by_recipe.get(recipe.id, [])) for recipe in recipes]


def _inventory_names_by_user(db: Session) -> dict[int, set[str]]:
    rows = (
        db.query(InventoryItem.user_id, InventoryItem.normalized_name, InventoryItem.name)
        .order_by(InventoryItem.user_id.asc(), InventoryItem.id.asc())
        .all()
    )
    inventory_by_user: dict[int, set[str]] = defaultdict(set)
    for user_id, normalized_name, fallback_name in rows:
        normalized = canonicalize_ingredient_phrase(normalized_name or fallback_name or "")
        if normalized:
            inventory_by_user[int(user_id)].add(normalized)
    return inventory_by_user


def _feedback_rows(db: Session) -> list[RecipeFeedback]:
    return db.query(RecipeFeedback).order_by(RecipeFeedback.user_id.asc(), RecipeFeedback.id.asc()).all()


def _required_ingredient_names(recipe_ingredients: list[RecipeIngredient]) -> list[str]:
    return [
        ingredient.ingredient_normalized
        for ingredient in recipe_ingredients
        if not ingredient.is_optional and ingredient.ingredient_normalized
    ]


def _select_positive_pantry_context(
    *,
    ingredient_names: list[str],
    rng: random.Random,
) -> tuple[set[str], set[str]]:
    if not ingredient_names:
        return set(), set()

    sample_size = max(1, min(len(ingredient_names), rng.randint(1, max(1, len(ingredient_names)))))
    pantry_names = set(rng.sample(ingredient_names, sample_size))
    main_ingredients = {rng.choice(sorted(pantry_names))} if pantry_names and rng.random() < 0.6 else set()
    return pantry_names, main_ingredients


def _build_example(
    *,
    context_id: str,
    user_id: int,
    recipe: Recipe,
    recipe_ingredients: list[RecipeIngredient],
    pantry_names: set[str],
    main_ingredients: set[str],
    normalized_cuisine: Optional[str],
    max_total_minutes: Optional[int],
    label: int,
    source: str,
) -> RankingExample:
    features = build_recipe_candidate_features(
        recipe=recipe,
        recipe_ingredients=recipe_ingredients,
        inventory_names=pantry_names,
        normalized_main_ingredients=main_ingredients,
        normalized_cuisine=normalized_cuisine,
        max_total_minutes=max_total_minutes,
    )
    features["user_id"] = user_id
    features["recipe_id"] = recipe.id
    features["label"] = label
    features["source"] = source
    return RankingExample(
        context_id=context_id,
        user_id=user_id,
        recipe_id=recipe.id,
        label=label,
        source=source,
        features=features,
    )


def build_bootstrap_ranking_examples(
    *,
    db: Session,
    seed: int = 7,
    max_examples_per_recipe: int = 2,
    negatives_per_positive: int = 2,
) -> list[RankingExample]:
    rng = random.Random(seed)
    recipe_rows = _recipe_rows_with_ingredients(db)
    if not recipe_rows:
        return []

    recipe_ids = [recipe.id for recipe, _ingredients in recipe_rows]
    recipe_by_id = {recipe.id: recipe for recipe, _ingredients in recipe_rows}
    ingredients_by_id = {recipe.id: ingredients for recipe, ingredients in recipe_rows}
    examples: list[RankingExample] = []

    for recipe, recipe_ingredients in recipe_rows:
        required_names = _required_ingredient_names(recipe_ingredients)
        if not required_names:
            continue

        recipe_examples = min(max_examples_per_recipe, max(1, len(required_names)))
        for example_index in range(recipe_examples):
            pantry_names, main_ingredients = _select_positive_pantry_context(
                ingredient_names=required_names,
                rng=rng,
            )
            context_id = f"bootstrap:{recipe.id}:{example_index}"
            examples.append(
                _build_example(
                    context_id=context_id,
                    user_id=0,
                    recipe=recipe,
                    recipe_ingredients=recipe_ingredients,
                    pantry_names=pantry_names,
                    main_ingredients=main_ingredients,
                    normalized_cuisine=None,
                    max_total_minutes=recipe.total_minutes if rng.random() < 0.4 else None,
                    label=1,
                    source="bootstrap_positive",
                )
            )

            negative_candidates = [candidate_id for candidate_id in recipe_ids if candidate_id != recipe.id]
            rng.shuffle(negative_candidates)
            for negative_id in negative_candidates[: max(negatives_per_positive, 0)]:
                examples.append(
                    _build_example(
                        context_id=context_id,
                        user_id=0,
                        recipe=recipe_by_id[negative_id],
                        recipe_ingredients=ingredients_by_id[negative_id],
                        pantry_names=pantry_names,
                        main_ingredients=main_ingredients,
                        normalized_cuisine=None,
                        max_total_minutes=recipe.total_minutes if rng.random() < 0.4 else None,
                        label=0,
                        source="bootstrap_negative",
                    )
                )

    inventory_names_by_user = _inventory_names_by_user(db)
    explicit_feedback = _feedback_rows(db)
    for feedback in explicit_feedback:
        recipe = recipe_by_id.get(feedback.recipe_id)
        if recipe is None:
            continue
        pantry_names = inventory_names_by_user.get(feedback.user_id, set())
        main_ingredients = set()
        label = 1 if feedback.feedback_type == "like" else 0
        examples.append(
            _build_example(
                context_id=f"feedback:{feedback.user_id}:{feedback.recipe_id}",
                user_id=int(feedback.user_id),
                recipe=recipe,
                recipe_ingredients=ingredients_by_id.get(recipe.id, []),
                pantry_names=pantry_names,
                main_ingredients=main_ingredients,
                normalized_cuisine=None,
                max_total_minutes=None,
                label=label,
                source=f"explicit_{feedback.feedback_type}",
            )
        )

    return examples


def ranking_examples_to_rows(examples: Iterable[RankingExample]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for example in examples:
        row = {
            "context_id": example.context_id,
            "user_id": example.user_id,
            "recipe_id": example.recipe_id,
            "label": example.label,
            "source": example.source,
        }
        row.update(example.features)
        rows.append(row)
    return rows


def write_ranking_dataset_csv(*, output_path: Path, rows: list[dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output_path.write_text("")
        return

    fieldnames = list(rows[0].keys())
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
