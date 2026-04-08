from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _resolve_model_path(raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return Path(__file__).resolve().parents[2] / raw_path


@lru_cache(maxsize=1)
def _load_xgboost_model():
    settings = get_settings()
    model_path = _resolve_model_path(settings.recipe_ranker_model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Recipe ranker model not found at {model_path}")

    import xgboost as xgb

    model = xgb.XGBClassifier()
    model.load_model(model_path)
    return model


def clear_ranker_model_cache() -> None:
    _load_xgboost_model.cache_clear()


def learned_ranker_is_enabled() -> bool:
    settings = get_settings()
    return settings.recipe_ranker_mode == "learned"


def score_feature_rows_with_learned_ranker(feature_rows: list[list[float]]) -> Optional[list[float]]:
    if not feature_rows:
        return []

    settings = get_settings()
    if settings.recipe_ranker_mode != "learned":
        return None

    try:
        model = _load_xgboost_model()
        probabilities = model.predict_proba(feature_rows)[:, 1]
        return [float(score) for score in probabilities]
    except Exception as exc:  # pragma: no cover - exercised through fallback behavior
        logger.warning("Falling back to deterministic recipe ranking: %s", exc)
        return None
