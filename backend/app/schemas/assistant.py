from typing import Optional

from pydantic import BaseModel, Field


class RecipeAssistantUseUpRequest(BaseModel):
    user_goal: Optional[str] = Field(default=None, max_length=240)
    main_ingredients: Optional[str] = Field(default=None, max_length=240)
    max_total_minutes: Optional[int] = Field(default=None, ge=1, le=1440)


class RecipeAssistantSuggestionRead(BaseModel):
    recipe_id: int
    title: str
    reason: str
    uses_up: list[str] = []
    missing_ingredients: list[str] = []
    substitution_ideas: list[str] = []
    time_note: Optional[str] = None


class RecipeAssistantUseUpRead(BaseModel):
    summary: str
    strategy_note: Optional[str] = None
    pantry_items_to_use_first: list[str] = []
    recipes: list[RecipeAssistantSuggestionRead] = []
