from datetime import datetime
from typing import Any, Literal, Optional

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
    current_feedback: Optional[Literal["like", "dislike"]] = None
    prep_minutes: Optional[int] = None
    cook_minutes: Optional[int] = None
    total_minutes: Optional[int] = None
    servings: Optional[int] = None
    cuisine: Optional[str] = None
    dietary_tags: list[str] = []
    favorite_tags: list[str] = []
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
    page: int
    page_size: int
    total_results: int
    total_pages: int
    results: list[RecipeRecommendationRead]


class RecipeBookListResponse(BaseModel):
    available_tags: list[str] = []
    results: list[RecipeSummaryRead]


class RecipeFeedbackRequest(BaseModel):
    feedback_type: Literal["like", "dislike"]


class RecipeFeedbackRead(BaseModel):
    recipe_id: int
    feedback_type: Literal["like", "dislike"]


class RecipeTagUpdateRequest(BaseModel):
    tags: list[str]


class RecipeTagUpdateRead(BaseModel):
    recipe_id: int
    tags: list[str]


class RecipeCookPreviewRequest(BaseModel):
    multiplier: float = 1.0


class RecipeCookInventoryOptionRead(BaseModel):
    id: int
    name: str
    normalized_name: str
    quantity: float
    unit: str
    category: Optional[str] = None


class RecipeCookPreviewItemRead(BaseModel):
    ingredient_key: str
    ingredient_raw: str
    ingredient_normalized: str
    quantity_text: Optional[str] = None
    match_status: Literal["matched", "needs_review", "unmatched"] = "unmatched"
    selected_inventory_item_id: Optional[int] = None
    selected_inventory_item_name: Optional[str] = None
    inventory_item_quantity: Optional[float] = None
    inventory_item_unit: Optional[str] = None
    reliable_quantity_match: bool = False
    suggested_used_quantity: Optional[float] = None
    suggested_remaining_quantity: Optional[float] = None
    notes: list[str] = []


class RecipeCookPreviewRead(BaseModel):
    recipe_id: int
    multiplier: float
    inventory_options: list[RecipeCookInventoryOptionRead]
    items: list[RecipeCookPreviewItemRead]


class RecipeCookApplyItem(BaseModel):
    ingredient_key: str
    ingredient_raw: str
    ingredient_normalized: str
    inventory_item_id: Optional[int] = None
    decision: Literal["ignore", "update", "remove"]
    new_quantity: Optional[float] = None
    new_unit: Optional[str] = None


class RecipeCookApplyRequest(BaseModel):
    multiplier: float = 1.0
    actions: list[RecipeCookApplyItem]


class RecipeCookApplyRead(BaseModel):
    recipe_id: int
    multiplier: float
    updated: int
    removed: int
    ignored: int
