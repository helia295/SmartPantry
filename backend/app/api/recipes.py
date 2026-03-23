from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import (
    RecipeBookListResponse,
    RecipeCookApplyRead,
    RecipeCookApplyRequest,
    RecipeCookPreviewRead,
    RecipeCookPreviewRequest,
    RecipeDetailRead,
    RecipeFeedbackRead,
    RecipeFeedbackRequest,
    RecipeRecommendationListResponse,
    RecipeTagUpdateRead,
    RecipeTagUpdateRequest,
)
from app.services.recipes import (
    apply_recipe_cook_updates,
    get_recipe_detail,
    list_saved_recipes,
    preview_recipe_cook_updates,
    remove_recipe_feedback,
    recommend_recipes,
    set_recipe_tags,
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
    return RecipeBookListResponse(**list_saved_recipes(db=db, current_user=current_user))


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


@router.delete("/{recipe_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe_feedback(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    removed = remove_recipe_feedback(
        db=db,
        current_user=current_user,
        recipe_id=recipe_id,
    )
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe feedback not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{recipe_id}/tags", response_model=RecipeTagUpdateRead)
def update_recipe_tags(
    recipe_id: int,
    payload: RecipeTagUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeTagUpdateRead:
    updated = set_recipe_tags(
        db=db,
        current_user=current_user,
        recipe_id=recipe_id,
        tags=payload.tags,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recipe must be in Favorites before it can be tagged",
        )
    return RecipeTagUpdateRead(**updated)


@router.post("/{recipe_id}/cook-preview", response_model=RecipeCookPreviewRead)
def preview_recipe_cook(
    recipe_id: int,
    payload: RecipeCookPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeCookPreviewRead:
    preview = preview_recipe_cook_updates(
        db=db,
        current_user=current_user,
        recipe_id=recipe_id,
        multiplier=payload.multiplier,
    )
    if preview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return RecipeCookPreviewRead(**preview)


@router.post("/{recipe_id}/cook-apply", response_model=RecipeCookApplyRead)
def apply_recipe_cook(
    recipe_id: int,
    payload: RecipeCookApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeCookApplyRead:
    result = apply_recipe_cook_updates(
        db=db,
        current_user=current_user,
        recipe_id=recipe_id,
        multiplier=payload.multiplier,
        actions=[action.model_dump() for action in payload.actions],
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return RecipeCookApplyRead(**result)


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
