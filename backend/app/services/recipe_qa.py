from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import InventoryItem, User
from app.schemas.assistant import (
    RecipeQuestionAnswerRead,
    RecipeQuestionAnswerRequest,
    RecipeQuestionReferenceRead,
)
from app.services.embeddings import (
    EmbeddingServiceUnavailableError,
    EmbeddingServiceUpstreamError,
)
from app.services.llm import (
    RecipeQuestionAnswerUnavailableError,
    RecipeQuestionAnswerUpstreamError,
    build_preview_rag_response,
    generate_recipe_question_answer,
)
from app.services.retrieval import retrieve_recipe_candidates


def _pantry_context(*, pantry_items: list[InventoryItem]) -> list[str]:
    return [item.name for item in pantry_items[:8]]


def _build_prompt_payload(
    *,
    payload: RecipeQuestionAnswerRequest,
    pantry_items: list[InventoryItem],
    candidate_results: list[dict[str, Any]],
) -> dict[str, Any]:
    settings = get_settings()
    return {
        "question": payload.question.strip(),
        "max_total_minutes": payload.max_total_minutes,
        "pantry_items_considered": _pantry_context(pantry_items=pantry_items),
        "candidate_recipes": [
            {
                "recipe_id": row["recipe"]["id"],
                "title": row["recipe"]["title"],
                "total_minutes": row["recipe"].get("total_minutes"),
                "matched_ingredients": row.get("matched_ingredients", []),
                "missing_ingredients": row.get("missing_ingredients", []),
                "similarity": row.get("similarity"),
                "document_text": row.get("document_text", "")[:1800],
            }
            for row in candidate_results[: max(settings.openai_rag_max_context_recipes, 1)]
        ],
    }


def build_recipe_question_answer(
    *,
    db: Session,
    current_user: User,
    payload: RecipeQuestionAnswerRequest,
) -> RecipeQuestionAnswerRead:
    settings = get_settings()
    if settings.openai_rag_preview_only:
        return build_preview_rag_response()
    if not settings.openai_rag_enabled:
        raise RecipeQuestionAnswerUnavailableError("Recipe Q&A is disabled.")

    pantry_items = (
        db.query(InventoryItem)
        .filter(InventoryItem.user_id == current_user.id)
        .order_by(InventoryItem.created_at.asc().nulls_last(), InventoryItem.id.asc())
        .all()
    )
    try:
        candidate_results = retrieve_recipe_candidates(
            db=db,
            current_user=current_user,
            question=payload.question,
            max_total_minutes=payload.max_total_minutes,
            limit=max(settings.openai_rag_max_retrievals, 1),
        )
    except EmbeddingServiceUnavailableError as exc:
        raise RecipeQuestionAnswerUnavailableError(str(exc)) from exc
    except EmbeddingServiceUpstreamError as exc:
        raise RecipeQuestionAnswerUpstreamError(str(exc)) from exc
    pantry_items_considered = _pantry_context(pantry_items=pantry_items)

    if not candidate_results:
        return RecipeQuestionAnswerRead(
            answer="I couldn’t find a strong recipe match for that question yet.",
            strategy_note="Try broadening the question or adding a few more pantry items first.",
            pantry_items_considered=pantry_items_considered,
            recipes=[],
        )

    prompt_payload = _build_prompt_payload(
        payload=payload,
        pantry_items=pantry_items,
        candidate_results=candidate_results,
    )
    llm_response = generate_recipe_question_answer(prompt_payload=prompt_payload)

    allowed_recipe_ids = {row["recipe"]["id"] for row in candidate_results}
    allowed_title_by_id = {row["recipe"]["id"]: row["recipe"]["title"] for row in candidate_results}
    filtered_recipes: list[RecipeQuestionReferenceRead] = []
    for recipe in llm_response.recipes:
        if recipe.recipe_id not in allowed_recipe_ids:
            continue
        filtered_recipes.append(
            RecipeQuestionReferenceRead(
                recipe_id=recipe.recipe_id,
                title=allowed_title_by_id[recipe.recipe_id],
                reason=recipe.reason,
                pantry_fit=recipe.pantry_fit,
                missing_ingredients=recipe.missing_ingredients,
                time_note=recipe.time_note,
            )
        )

    return RecipeQuestionAnswerRead(
        answer=llm_response.answer,
        strategy_note=llm_response.strategy_note,
        pantry_items_considered=pantry_items_considered,
        recipes=filtered_recipes,
    )
