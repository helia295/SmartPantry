from pathlib import Path

import pytest

from app.db import Base, SessionLocal, engine, ensure_sqlite_schema_compatibility
from app.models import Recipe, RecipeIngredient
from scripts.import_recipes import (
    import_allrecipes_csv,
    normalize_ingredient_value,
    parse_minutes,
    parse_rating,
    parse_servings,
    split_ingredients,
)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema_compatibility()
    yield


@pytest.fixture(autouse=True)
def clear_recipe_tables():
    with SessionLocal() as db:
        db.query(RecipeIngredient).delete()
        db.query(Recipe).delete()
        db.commit()
    yield
    with SessionLocal() as db:
        db.query(RecipeIngredient).delete()
        db.query(Recipe).delete()
        db.commit()


def test_parse_minutes():
    assert parse_minutes("45 mins") == 45
    assert parse_minutes("1 hr 30 mins") == 90
    assert parse_minutes("2 hrs") == 120
    assert parse_minutes(None) is None
    assert parse_minutes("not-a-duration") is None


def test_parse_servings():
    assert parse_servings("12") == 12
    assert parse_servings("Serves 6") == 6
    assert parse_servings(None) is None
    assert parse_servings("a crowd") is None


def test_parse_rating():
    assert parse_rating("4.7") == 4.7
    assert parse_rating("None") is None
    assert parse_rating(None) is None


def test_split_ingredients_splits_pipe_delimited_values():
    assert split_ingredients("1 cup flour | 2 eggs | 1 tsp salt") == [
        "1 cup flour",
        "2 eggs",
        "1 tsp salt",
    ]


def test_normalize_ingredient_value_removes_quantity_units_and_plural_noise():
    assert normalize_ingredient_value("2 peaches, sliced") == "peach"
    assert normalize_ingredient_value("1 can whole kernel corn") == "whole kernel corn"
    assert normalize_ingredient_value("1/2 teaspoon Salt") == "salt"
    assert normalize_ingredient_value("3 cups All-purpose Flour") == "all-purpose flour"
    assert normalize_ingredient_value("¼ cup olive oil") == "olive oil"


def test_import_allrecipes_csv(tmp_path: Path):
    input_path = tmp_path / "allrecipes.csv"
    input_path.write_text(
        "\n".join(
            [
                "Name,Rating,Description,Prep Time,Cook Time,Total Time,Servings,Ingredients,Image URL",
                "\"Tomato Pasta\",4.8,\"A quick pasta.\",\"10 mins\",\"10 mins\",\"20 mins\",4,\"1 pound pasta | 2 tomatoes | 2 cloves garlic\",https://images.example.com/tomato.jpg",
                "\"Simple Toast\",,\"Crunchy toast.\",\"5 mins\",\"2 mins\",\"7 mins\",2,\"2 slices bread | 1 tablespoon butter\",None",
            ]
        ),
        encoding="utf-8",
    )

    with SessionLocal() as db:
        result = import_allrecipes_csv(input_path=input_path, db=db)

    assert result["inserted"] == 2
    assert result["skipped"] == 0
    assert result["ingredients_inserted"] == 5

    with SessionLocal() as db:
        recipes = db.query(Recipe).order_by(Recipe.id.asc()).all()
        assert len(recipes) == 2
        assert recipes[0].title == "Tomato Pasta"
        assert recipes[0].source_name == "allrecipes-search"
        assert recipes[0].source_url is None
        assert recipes[0].image_url == "https://images.example.com/tomato.jpg"
        assert recipes[0].rating == 4.8
        assert recipes[0].total_minutes == 20
        assert recipes[1].total_minutes == 7

        ingredients = (
            db.query(RecipeIngredient)
            .filter(RecipeIngredient.recipe_id == recipes[0].id)
            .order_by(RecipeIngredient.id.asc())
            .all()
        )
        assert [ingredient.ingredient_normalized for ingredient in ingredients] == [
            "pasta",
            "tomato",
            "garlic",
        ]


def test_import_allrecipes_skips_invalid_rows_and_respects_limit(tmp_path: Path):
    input_path = tmp_path / "allrecipes.csv"
    input_path.write_text(
        "\n".join(
            [
                "Name,Rating,Description,Prep Time,Cook Time,Total Time,Servings,Ingredients,Image URL",
                "\"Valid Salad\",4.5,\"Fresh salad.\",\"10 mins\",,\"10 mins\",2,\"Lettuce | Olive oil\",https://images.example.com/salad.jpg",
                "\"Missing Ingredients\",4.2,\"No ingredient row.\",\"5 mins\",,\"5 mins\",1,,None",
                "\"Second Valid Recipe\",4.1,\"Rice bowl.\",\"15 mins\",,\"15 mins\",3,\"Rice | Soy sauce\",None",
            ]
        ),
        encoding="utf-8",
    )

    with SessionLocal() as db:
        result = import_allrecipes_csv(input_path=input_path, db=db, limit=1)

    assert result["inserted"] == 1
    assert result["skipped"] == 0

    with SessionLocal() as db:
        recipes = db.query(Recipe).all()
        assert len(recipes) == 1
        assert recipes[0].title == "Valid Salad"


def test_import_allrecipes_maps_csv_fields_into_recipe_model(tmp_path: Path):
    input_path = tmp_path / "allrecipes.csv"
    input_path.write_text(
        "\n".join(
            [
                "Name,Rating,Description,Prep Time,Cook Time,Total Time,Servings,Ingredients,Image URL",
                "\"Vegetable Quesadillas\",4.7,\"A veggie-friendly dinner.\",\"20 mins\",\"10 mins\",\"30 mins\",4,\"1 zucchini, cubed | 1 red bell pepper, chopped | 4 flour tortillas | 1/2 cup shredded sharp Cheddar cheese\",https://images.example.com/quesadillas.jpg",
            ]
        ),
        encoding="utf-8",
    )

    with SessionLocal() as db:
        result = import_allrecipes_csv(input_path=input_path, db=db)

    assert result["inserted"] == 1
    assert result["ingredients_inserted"] == 4

    with SessionLocal() as db:
        recipe = db.query(Recipe).first()
        assert recipe is not None
        assert recipe.source_name == "allrecipes-search"
        assert recipe.total_minutes == 30
        assert recipe.servings == 4
        assert recipe.rating == 4.7
        assert "veggie-friendly dinner" in recipe.search_text

        ingredients = (
            db.query(RecipeIngredient)
            .filter(RecipeIngredient.recipe_id == recipe.id)
            .order_by(RecipeIngredient.id.asc())
            .all()
        )
        assert [ingredient.ingredient_raw for ingredient in ingredients] == [
            "1 zucchini, cubed",
            "1 red bell pepper, chopped",
            "4 flour tortillas",
            "1/2 cup shredded sharp Cheddar cheese",
        ]
        assert [ingredient.ingredient_normalized for ingredient in ingredients] == [
            "zucchini",
            "red bell pepper",
            "flour tortilla",
            "shredded sharp cheddar cheese",
        ]
