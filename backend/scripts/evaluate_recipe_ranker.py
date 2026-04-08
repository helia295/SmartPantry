from __future__ import annotations

import argparse
import json
from pathlib import Path

import xgboost as xgb

from app.services.ranking_modeling import (
    deterministic_scores_for_rows,
    evaluate_grouped_ranking,
    extract_matrix_and_labels,
    load_dataset_rows,
    split_rows_by_context,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate the SmartPantry XGBoost recipe reranker.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("artifacts/recipe_ranker_dataset.csv"),
        help="Input dataset CSV path relative to backend/ unless absolute.",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("artifacts/recipe_ranker.json"),
        help="Trained model path relative to backend/ unless absolute.",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("artifacts/recipe_ranker_metadata.json"),
        help="Model metadata path relative to backend/ unless absolute.",
    )
    parser.add_argument(
        "--split",
        choices=("validation", "train", "all"),
        default="validation",
        help="Which dataset split to evaluate.",
    )
    return parser


def _resolve(path: Path) -> Path:
    project_root = Path(__file__).resolve().parents[1]
    return path if path.is_absolute() else project_root / path


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    dataset_path = _resolve(args.dataset)
    model_path = _resolve(args.model)
    metadata_path = _resolve(args.metadata)

    with metadata_path.open("r", encoding="utf-8") as handle:
        metadata = json.load(handle)
    feature_names = metadata["feature_names"]
    validation_fraction = float(metadata.get("validation_fraction", 0.2))
    split_seed = int(metadata.get("split_seed", 7))

    rows = load_dataset_rows(dataset_path)
    train_rows, validation_rows = split_rows_by_context(
        rows,
        validation_fraction=validation_fraction,
        seed=split_seed,
    )
    if args.split == "validation":
        evaluation_rows = validation_rows
    elif args.split == "train":
        evaluation_rows = train_rows
    else:
        evaluation_rows = rows

    model = xgb.XGBClassifier()
    model.load_model(model_path)
    matrix, _labels = extract_matrix_and_labels(evaluation_rows, feature_names=feature_names)
    model_scores = [float(score) for score in model.predict_proba(matrix)[:, 1]]
    deterministic_scores = deterministic_scores_for_rows(evaluation_rows)

    model_metrics = evaluate_grouped_ranking(rows=evaluation_rows, scores=model_scores)
    baseline_metrics = evaluate_grouped_ranking(rows=evaluation_rows, scores=deterministic_scores)

    print(
        json.dumps(
            {
                "split": args.split,
                "xgboost": model_metrics,
                "deterministic_baseline": baseline_metrics,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
