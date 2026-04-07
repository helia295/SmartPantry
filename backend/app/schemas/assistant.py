from typing import Optional

from pydantic import BaseModel, Field


class RecipeAssistantUseUpRequest(BaseModel):
    user_goal: Optional[str] = Field(default=None, max_length=240)
    main_ingredients: Optional[str] = Field(default=None, max_length=240)
    max_total_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    prioritize_oldest_items: bool = True
    prioritized_ingredients: list[str] = Field(default_factory=list, max_length=12)


class RecipeAssistantSuggestionRead(BaseModel):
    recipe_id: int
    title: str
    reason: str
    uses_up: list[str] = []
    missing_ingredients: list[str] = []
    substitution_ideas: list[str] = []
    time_note: Optional[str] = None


class RecipeAssistantUseUpRead(BaseModel):
    mode: str = "live"
    summary: str
    strategy_note: Optional[str] = None
    availability_note: Optional[str] = None
    cta_label: Optional[str] = None
    cta_url: Optional[str] = None
    pantry_items_to_use_first: list[str] = []
    recipes: list[RecipeAssistantSuggestionRead] = []


class RecipeQuestionAnswerRequest(BaseModel):
    question: str = Field(min_length=3, max_length=400)
    max_total_minutes: Optional[int] = Field(default=None, ge=1, le=1440)


class RecipeQuestionReferenceRead(BaseModel):
    recipe_id: int
    title: str
    reason: str
    pantry_fit: Optional[str] = None
    missing_ingredients: list[str] = []
    time_note: Optional[str] = None


class RecipeQuestionAnswerRead(BaseModel):
    mode: str = "live"
    answer: str
    strategy_note: Optional[str] = None
    availability_note: Optional[str] = None
    cta_label: Optional[str] = None
    cta_url: Optional[str] = None
    pantry_items_considered: list[str] = []
    recipes: list[RecipeQuestionReferenceRead] = []
