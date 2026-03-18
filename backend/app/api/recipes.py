from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import (
    RecipeBookListResponse,
    RecipeDetailRead,
    RecipeFeedbackRead,
    RecipeFeedbackRequest,
    RecipeRecommendationListResponse,
)
from app.services.recipes import (
    get_recipe_detail,
    list_saved_recipes,
    recommend_recipes,
    upsert_recipe_feedback,
)


router = APIRouter()


@router.get("/recommendations", response_model=RecipeRecommendationListResponse)
def list_recipe_recommendations(
    main_ingredients: Optional[str] = Query(default=None),
    cuisine: Optional[str] = Query(default=None),
    max_total_minutes: Optional[int] = Query(default=None, ge=1),
    dietary_tags: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeRecommendationListResponse:
    return RecipeRecommendationListResponse(
        **recommend_recipes(
            db=db,
            current_user=current_user,
            main_ingredients=main_ingredients,
            cuisine=cuisine,
            max_total_minutes=max_total_minutes,
            dietary_tags=dietary_tags,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/book", response_model=RecipeBookListResponse)
def read_saved_recipe_book(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeBookListResponse:
    return RecipeBookListResponse(results=list_saved_recipes(db=db, current_user=current_user))


@router.post("/{recipe_id}/feedback", response_model=RecipeFeedbackRead)
def write_recipe_feedback(
    recipe_id: int,
    payload: RecipeFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeFeedbackRead:
    feedback = upsert_recipe_feedback(
        db=db,
        current_user=current_user,
        recipe_id=recipe_id,
        feedback_type=payload.feedback_type,
    )
    if feedback is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return RecipeFeedbackRead(**feedback)


@router.get("/{recipe_id}", response_model=RecipeDetailRead)
def read_recipe_detail(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeDetailRead:
    detail = get_recipe_detail(recipe_id=recipe_id, db=db, current_user=current_user)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return RecipeDetailRead(**detail)
