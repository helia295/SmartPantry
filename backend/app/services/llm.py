from __future__ import annotations

import json
from typing import Any

from app.core.config import get_settings
from app.schemas.assistant import RecipeAssistantUseUpRead


class RecipeAssistantError(RuntimeError):
    pass


class RecipeAssistantUnavailableError(RecipeAssistantError):
    pass


class RecipeAssistantUpstreamError(RecipeAssistantError):
    pass


RECIPE_ASSISTANT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "strategy_note": {"type": ["string", "null"]},
        "pantry_items_to_use_first": {
            "type": "array",
            "items": {"type": "string"},
        },
        "recipes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "recipe_id": {"type": "integer"},
                    "title": {"type": "string"},
                    "reason": {"type": "string"},
                    "uses_up": {"type": "array", "items": {"type": "string"}},
                    "missing_ingredients": {"type": "array", "items": {"type": "string"}},
                    "substitution_ideas": {"type": "array", "items": {"type": "string"}},
                    "time_note": {"type": ["string", "null"]},
                },
                "required": [
                    "recipe_id",
                    "title",
                    "reason",
                    "uses_up",
                    "missing_ingredients",
                    "substitution_ideas",
                    "time_note",
                ],
            },
        },
    },
    "required": ["summary", "strategy_note", "pantry_items_to_use_first", "recipes"],
}


RECIPE_ASSISTANT_INSTRUCTIONS = """
You are SmartPantry's recipe planning assistant.

Your job is to help the user choose the best recipes from the candidate recipes already provided.
You must stay grounded in the pantry items and candidate recipes in the input.

Rules:
- Only recommend recipes from the provided candidate list.
- Use the exact recipe_id and title from the provided candidate list.
- Prioritize perishable and older pantry items when possible.
- Be honest about missing ingredients.
- Keep substitution ideas practical and short.
- Do not invent new recipes, pantry items, or unavailable ingredients.
- Keep the tone concise, helpful, and professional.
""".strip()


def generate_recipe_assistant_plan(*, prompt_payload: dict[str, Any]) -> RecipeAssistantUseUpRead:
    settings = get_settings()
    if not settings.openai_assistant_enabled:
        raise RecipeAssistantUnavailableError("The pantry assistant is disabled.")
    if not settings.openai_api_key:
        raise RecipeAssistantUnavailableError("The pantry assistant is not configured yet.")

    try:
        from openai import APIError, APITimeoutError, OpenAI
    except ImportError as exc:
        raise RecipeAssistantUnavailableError(
            "The OpenAI client is not installed in this environment."
        ) from exc

    client = OpenAI(
        api_key=settings.openai_api_key,
        timeout=max(settings.openai_assistant_timeout_seconds, 1),
    )

    try:
        response = client.responses.create(
            model=settings.openai_model,
            instructions=RECIPE_ASSISTANT_INSTRUCTIONS,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(prompt_payload, ensure_ascii=True),
                        }
                    ],
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "smartpantry_recipe_assistant",
                    "schema": RECIPE_ASSISTANT_JSON_SCHEMA,
                    "strict": True,
                }
            },
        )
    except APITimeoutError as exc:
        raise RecipeAssistantUpstreamError("The pantry assistant timed out.") from exc
    except APIError as exc:
        raise RecipeAssistantUpstreamError("The pantry assistant request failed.") from exc
    except Exception as exc:
        raise RecipeAssistantUpstreamError("The pantry assistant is temporarily unavailable.") from exc

    output_text = getattr(response, "output_text", None)
    if not output_text:
        raise RecipeAssistantUpstreamError("The pantry assistant returned an empty response.")

    try:
        return RecipeAssistantUseUpRead.model_validate_json(output_text)
    except Exception as exc:
        raise RecipeAssistantUpstreamError("The pantry assistant returned an invalid response format.") from exc
