from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import RecipeDetailRead, RecipeRecommendationListResponse
from app.services.recipes import get_recipe_detail, recommend_recipes


router = APIRouter()


@router.get("/recommendations", response_model=RecipeRecommendationListResponse)
def list_recipe_recommendations(
    main_ingredients: Optional[str] = Query(default=None),
    cuisine: Optional[str] = Query(default=None),
    max_total_minutes: Optional[int] = Query(default=None, ge=1),
    dietary_tags: Optional[str] = Query(default=None),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeRecommendationListResponse:
    return RecipeRecommendationListResponse(
        results=recommend_recipes(
            db=db,
            current_user=current_user,
            main_ingredients=main_ingredients,
            cuisine=cuisine,
            max_total_minutes=max_total_minutes,
            dietary_tags=dietary_tags,
            limit=limit,
        )
    )


@router.get("/{recipe_id}", response_model=RecipeDetailRead)
def read_recipe_detail(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeDetailRead:
    detail = get_recipe_detail(recipe_id=recipe_id, db=db)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return RecipeDetailRead(**detail)
