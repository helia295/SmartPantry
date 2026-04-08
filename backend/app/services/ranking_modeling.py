from __future__ import annotations

import csv
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from app.services.ranking_features import score_recipe_candidate_deterministically


NON_FEATURE_COLUMNS = {
    "context_id",
    "user_id",
    "recipe_id",
    "label",
    "source",
    "matched_ingredients",
    "missing_ingredients",
}


def coerce_feature_value(value: str) -> float:
    if value == "":
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def load_dataset_rows(dataset_path: Path) -> list[dict[str, str]]:
    with dataset_path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("Dataset is empty. Build the ranking dataset before training or evaluation.")
    return rows


def extract_feature_names(rows: list[dict[str, str]]) -> list[str]:
    return [column for column in rows[0].keys() if column not in NON_FEATURE_COLUMNS]


def extract_matrix_and_labels(
    rows: list[dict[str, str]],
    *,
    feature_names: list[str],
) -> tuple[list[list[float]], list[int]]:
    matrix: list[list[float]] = []
    labels: list[int] = []
    for row in rows:
        matrix.append([coerce_feature_value(row.get(name, "")) for name in feature_names])
        labels.append(int(float(row["label"])))
    return matrix, labels


def split_rows_by_context(
    rows: list[dict[str, str]],
    *,
    validation_fraction: float,
    seed: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation_fraction must be between 0 and 1.")

    context_ids = sorted({row["context_id"] for row in rows})
    if len(context_ids) < 2:
        raise ValueError("Need at least two contexts to create a train/validation split.")

    rng = random.Random(seed)
    rng.shuffle(context_ids)

    validation_count = max(1, int(round(len(context_ids) * validation_fraction)))
    validation_count = min(validation_count, len(context_ids) - 1)
    validation_contexts = set(context_ids[:validation_count])

    train_rows = [row for row in rows if row["context_id"] not in validation_contexts]
    validation_rows = [row for row in rows if row["context_id"] in validation_contexts]
    return train_rows, validation_rows


def deterministic_scores_for_rows(rows: list[dict[str, str]]) -> list[float]:
    return [
        score_recipe_candidate_deterministically(
            features={
                key: coerce_feature_value(value)
                for key, value in row.items()
                if key not in NON_FEATURE_COLUMNS
            }
        )
        for row in rows
    ]


def precision_at_k(labels: list[int], k: int) -> float:
    top_k = labels[:k]
    return sum(top_k) / max(len(top_k), 1)


def hit_at_1(labels: list[int]) -> float:
    return float(labels[0]) if labels else 0.0


def dcg(labels: list[int], k: int) -> float:
    total = 0.0
    for idx, label in enumerate(labels[:k], start=1):
        total += (2**label - 1) / math.log2(idx + 1)
    return total


def ndcg_at_k(labels: list[int], k: int) -> float:
    actual = dcg(labels, k)
    ideal = dcg(sorted(labels, reverse=True), k)
    if ideal == 0:
        return 0.0
    return actual / ideal


def evaluate_grouped_ranking(
    *,
    rows: list[dict[str, str]],
    scores: Iterable[float],
) -> dict[str, float]:
    grouped: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for row, score in zip(rows, scores):
        grouped[row["context_id"]].append((float(score), int(float(row["label"]))))

    precision_scores: list[float] = []
    ndcg_scores: list[float] = []
    hit_scores: list[float] = []
    for context_rows in grouped.values():
        ordered_labels = [label for _score, label in sorted(context_rows, key=lambda item: item[0], reverse=True)]
        precision_scores.append(precision_at_k(ordered_labels, 3))
        ndcg_scores.append(ndcg_at_k(ordered_labels, 5))
        hit_scores.append(hit_at_1(ordered_labels))

    return {
        "precision_at_3": sum(precision_scores) / max(len(precision_scores), 1),
        "ndcg_at_5": sum(ndcg_scores) / max(len(ndcg_scores), 1),
        "hit_at_1": sum(hit_scores) / max(len(hit_scores), 1),
        "contexts": len(grouped),
    }
