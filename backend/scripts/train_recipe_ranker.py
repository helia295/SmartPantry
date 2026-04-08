from __future__ import annotations

import argparse
import json
from pathlib import Path

import xgboost as xgb

from app.services.ranking_modeling import (
    evaluate_grouped_ranking,
    extract_feature_names,
    extract_matrix_and_labels,
    load_dataset_rows,
    split_rows_by_context,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train the SmartPantry XGBoost recipe reranker.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("artifacts/recipe_ranker_dataset.csv"),
        help="Input dataset CSV path relative to backend/ unless absolute.",
    )
    parser.add_argument(
        "--model-out",
        type=Path,
        default=Path("artifacts/recipe_ranker.json"),
        help="Output XGBoost model path relative to backend/ unless absolute.",
    )
    parser.add_argument(
        "--metadata-out",
        type=Path,
        default=Path("artifacts/recipe_ranker_metadata.json"),
        help="Output metadata path relative to backend/ unless absolute.",
    )
    parser.add_argument(
        "--validation-fraction",
        type=float,
        default=0.2,
        help="Fraction of contexts reserved for validation.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Random seed used for the context-level train/validation split.",
    )
    return parser


def _resolve(path: Path) -> Path:
    project_root = Path(__file__).resolve().parents[1]
    return path if path.is_absolute() else project_root / path


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    dataset_path = _resolve(args.dataset)
    model_path = _resolve(args.model_out)
    metadata_path = _resolve(args.metadata_out)

    rows = load_dataset_rows(dataset_path)
    feature_names = extract_feature_names(rows)
    train_rows, validation_rows = split_rows_by_context(
        rows,
        validation_fraction=args.validation_fraction,
        seed=args.seed,
    )
    train_matrix, train_labels = extract_matrix_and_labels(train_rows, feature_names=feature_names)
    validation_matrix, validation_labels = extract_matrix_and_labels(validation_rows, feature_names=feature_names)

    model = xgb.XGBClassifier(
        n_estimators=120,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=7,
        n_jobs=1,
    )
    model.fit(train_matrix, train_labels)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(model_path)
    validation_scores = [float(score) for score in model.predict_proba(validation_matrix)[:, 1]]
    validation_metrics = evaluate_grouped_ranking(rows=validation_rows, scores=validation_scores)
    metadata_path.write_text(
        json.dumps(
            {
                "feature_names": feature_names,
                "training_examples": len(train_matrix),
                "validation_examples": len(validation_matrix),
                "training_positive_labels": int(sum(train_labels)),
                "training_negative_labels": int(len(train_labels) - sum(train_labels)),
                "validation_positive_labels": int(sum(validation_labels)),
                "validation_negative_labels": int(len(validation_labels) - sum(validation_labels)),
                "validation_fraction": args.validation_fraction,
                "split_seed": args.seed,
                "validation_metrics": validation_metrics,
            },
            indent=2,
        )
    )

    print(f"Saved model to {model_path}")
    print(f"Saved metadata to {metadata_path}")
    print(json.dumps({"validation_metrics": validation_metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
