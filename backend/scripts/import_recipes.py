from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import Recipe, RecipeIngredient
from app.services.recipes import canonicalize_ingredient_phrase, normalize_term


SLUG_INVALID_CHARS = re.compile(r"[^a-z0-9]+")
LEADING_QUANTITY_RE = re.compile(
    r"^\s*(?:(?:\d+\s+\d+/\d+)|(?:\d+/\d+)|(?:\d+(?:\.\d+)?)|a|an)\s+",
    re.IGNORECASE,
)
UNICODE_FRACTIONS = str.maketrans(
    {
        "¼": " 1/4 ",
        "½": " 1/2 ",
        "¾": " 3/4 ",
        "⅐": " 1/7 ",
        "⅑": " 1/9 ",
        "⅒": " 1/10 ",
        "⅓": " 1/3 ",
        "⅔": " 2/3 ",
        "⅕": " 1/5 ",
        "⅖": " 2/5 ",
        "⅗": " 3/5 ",
        "⅘": " 4/5 ",
        "⅙": " 1/6 ",
        "⅚": " 5/6 ",
        "⅛": " 1/8 ",
        "⅜": " 3/8 ",
        "⅝": " 5/8 ",
        "⅞": " 7/8 ",
    }
)
UNIT_WORDS = {
    "teaspoon",
    "teaspoons",
    "tsp",
    "tablespoon",
    "tablespoons",
    "tbsp",
    "cup",
    "cups",
    "ounce",
    "ounces",
    "oz",
    "pound",
    "pounds",
    "lb",
    "lbs",
    "gram",
    "grams",
    "g",
    "kilogram",
    "kilograms",
    "kg",
    "ml",
    "liter",
    "liters",
    "pinch",
    "dash",
    "can",
    "cans",
    "jar",
    "jars",
    "package",
    "packages",
    "pkg",
    "clove",
    "cloves",
    "slice",
    "slices",
    "sprig",
    "sprigs",
    "bunch",
    "bunches",
    "head",
    "heads",
    "stalk",
    "stalks",
}
PREP_WORDS = {
    "chopped",
    "diced",
    "sliced",
    "minced",
    "drained",
    "softened",
    "melted",
    "peeled",
    "crushed",
    "fresh",
    "freshly",
    "ground",
    "ripe",
    "large",
    "small",
    "medium",
    "optional",
    "divided",
    "halved",
    "beaten",
    "to",
    "taste",
    "or",
    "more",
    "for",
    "garnish",
    "seeded",
    "cored",
    "reserved",
}
TIME_PART_RE = re.compile(r"(?P<value>\d+)\s*(?P<unit>hr|hrs|hour|hours|min|mins|minute|minutes)\b", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import Kaggle Allrecipes CSV into SmartPantry")
    parser.add_argument("--input-csv", required=True, help="Path to the Allrecipes CSV file")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of imported recipe rows",
    )
    return parser.parse_args()


def parse_minutes(raw_value: Any) -> int | None:
    if raw_value is None:
        return None

    text = str(raw_value).strip().lower()
    if not text or text == "none":
        return None

    total = 0
    for match in TIME_PART_RE.finditer(text):
        value = int(match.group("value"))
        unit = match.group("unit").lower()
        if unit.startswith("hr") or unit.startswith("hour"):
            total += value * 60
        else:
            total += value

    return total or None


def parse_servings(raw_value: Any) -> int | None:
    if raw_value is None:
        return None

    text = str(raw_value).strip()
    if not text or text.lower() == "none":
        return None

    match = re.search(r"\d+", text)
    if not match:
        return None
    return int(match.group(0))


def parse_rating(raw_value: Any) -> float | None:
    if raw_value is None:
        return None

    text = str(raw_value).strip()
    if not text or text.lower() == "none":
        return None

    try:
        return round(float(text), 2)
    except ValueError:
        return None


def singularize_token(token: str) -> str:
    if len(token) <= 3:
        return token
    if token.endswith("ches") or token.endswith("shes"):
        return token[:-2]
    if token.endswith("ies") and len(token) > 4:
        return f"{token[:-3]}y"
    if token.endswith("oes") and len(token) > 4:
        return token[:-2]
    if token.endswith("ses") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def normalize_ingredient_value(raw_value: str) -> str:
    normalized = normalize_term(raw_value.translate(UNICODE_FRACTIONS))
    if not normalized:
        return ""

    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"\([^)]*\)", " ", normalized)
    normalized = re.split(r"\s[-–]\s|,", normalized)[0]
    normalized = LEADING_QUANTITY_RE.sub("", normalized).strip()

    tokens = [token for token in normalized.split() if token]
    while tokens and (tokens[0] in UNIT_WORDS or re.fullmatch(r"\d+", tokens[0])):
        tokens.pop(0)

    filtered_tokens = [token for token in tokens if token not in PREP_WORDS]
    if not filtered_tokens:
        filtered_tokens = tokens

    singular_tokens = [singularize_token(token) for token in filtered_tokens]
    result = " ".join(singular_tokens).strip()
    return canonicalize_ingredient_phrase(result)


def split_ingredients(raw_value: Any) -> list[str]:
    if raw_value is None:
        return []

    text = str(raw_value).strip()
    if not text or text.lower() == "none":
        return []

    return [part.strip() for part in text.split("|") if part.strip()]


def slugify(value: str) -> str:
    normalized = normalize_term(value)
    slug = SLUG_INVALID_CHARS.sub("-", normalized).strip("-")
    return slug or "recipe"


def make_unique_slug(base_slug: str, used_slugs: set[str]) -> str:
    if base_slug not in used_slugs:
        used_slugs.add(base_slug)
        return base_slug

    suffix = 2
    while f"{base_slug}-{suffix}" in used_slugs:
        suffix += 1
    unique_slug = f"{base_slug}-{suffix}"
    used_slugs.add(unique_slug)
    return unique_slug


def build_allrecipes_search_url(title: str) -> str:
    return f"https://www.allrecipes.com/search?q={quote_plus(title)}"


def import_allrecipes_csv(
    *,
    input_path: Path,
    db: Session,
    limit: int | None = None,
) -> dict[str, int]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    used_slugs = {row[0] for row in db.query(Recipe.slug).all()}
    inserted = 0
    skipped = 0
    ingredients_inserted = 0

    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if limit is not None and inserted >= limit:
                break

            title = str(row.get("Name", "")).strip()
            ingredients = split_ingredients(row.get("Ingredients"))
            if not title or not ingredients:
                skipped += 1
                continue

            slug = make_unique_slug(slugify(title), used_slugs)
            prep_minutes = parse_minutes(row.get("Prep Time"))
            cook_minutes = parse_minutes(row.get("Cook Time"))
            total_minutes = parse_minutes(row.get("Total Time"))
            if total_minutes is None and (prep_minutes is not None or cook_minutes is not None):
                total_minutes = (prep_minutes or 0) + (cook_minutes or 0)

            description = str(row.get("Description", "")).strip()
            rating = parse_rating(row.get("Rating"))
            image_url = str(row.get("Image URL", "")).strip()
            if not image_url or image_url.lower() == "none":
                image_url = None

            recipe = Recipe(
                title=title,
                slug=slug,
                source_name="allrecipes-search",
                source_url=None,
                image_url=image_url,
                rating=rating,
                prep_minutes=prep_minutes,
                cook_minutes=cook_minutes,
                total_minutes=total_minutes,
                servings=parse_servings(row.get("Servings")),
                cuisine=None,
                dietary_tags_json="[]",
                nutrition_json="{}",
                instructions_text=None,
                search_text=" ".join(
                    [
                        normalize_term(title),
                        normalize_term(description),
                        *(normalize_term(ingredient) for ingredient in ingredients),
                    ]
                ).strip(),
            )
            db.add(recipe)
            db.flush()

            for ingredient_raw in ingredients:
                ingredient_normalized = normalize_ingredient_value(ingredient_raw)
                if not ingredient_normalized:
                    continue
                db.add(
                    RecipeIngredient(
                        recipe_id=recipe.id,
                        ingredient_raw=ingredient_raw,
                        ingredient_normalized=ingredient_normalized,
                        quantity_text=None,
                        is_optional=False,
                    )
                )
                ingredients_inserted += 1

            inserted += 1

    db.commit()
    return {
        "inserted": inserted,
        "skipped": skipped,
        "ingredients_inserted": ingredients_inserted,
    }


def main() -> None:
    args = parse_args()

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        result = import_allrecipes_csv(
            input_path=Path(args.input_csv),
            db=db,
            limit=args.limit,
        )

    print("Recipe import complete")
    print(f"Inserted recipes: {result['inserted']}")
    print(f"Inserted ingredients: {result['ingredients_inserted']}")
    print(f"Skipped rows: {result['skipped']}")


if __name__ == "__main__":
    main()
