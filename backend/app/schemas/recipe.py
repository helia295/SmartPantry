from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class RecipeIngredientRead(BaseModel):
    ingredient_raw: str
    ingredient_normalized: str
    quantity_text: Optional[str] = None
    is_optional: bool = False

    class Config:
        from_attributes = True


class RecipeSummaryRead(BaseModel):
    id: int
    title: str
    slug: str
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    rating: Optional[float] = None
    prep_minutes: Optional[int] = None
    cook_minutes: Optional[int] = None
    total_minutes: Optional[int] = None
    servings: Optional[int] = None
    cuisine: Optional[str] = None
    dietary_tags: list[str] = []
    nutrition: dict[str, Any] = {}
    created_at: datetime


class RecipeDetailRead(RecipeSummaryRead):
    instructions_text: Optional[str] = None
    ingredients: list[RecipeIngredientRead]


class RecipeRecommendationRead(BaseModel):
    recipe: RecipeSummaryRead
    score: float
    inventory_match_count: int
    required_ingredient_count: int
    matched_ingredients: list[str]
    missing_ingredients: list[str]


class RecipeRecommendationListResponse(BaseModel):
    results: list[RecipeRecommendationRead]
