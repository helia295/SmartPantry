from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db import SessionLocal
from app.services.ranking_dataset import (
    build_bootstrap_ranking_examples,
    ranking_examples_to_rows,
    write_ranking_dataset_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a bootstrap ranking dataset for SmartPantry recipes.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/recipe_ranker_dataset.csv"),
        help="CSV output path relative to backend/ unless an absolute path is provided.",
    )
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--max-examples-per-recipe", type=int, default=2)
    parser.add_argument("--negatives-per-positive", type=int, default=2)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    output_path = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output

    with SessionLocal() as db:
        examples = build_bootstrap_ranking_examples(
            db=db,
            seed=args.seed,
            max_examples_per_recipe=max(args.max_examples_per_recipe, 1),
            negatives_per_positive=max(args.negatives_per_positive, 0),
        )

    rows = ranking_examples_to_rows(examples)
    write_ranking_dataset_csv(output_path=output_path, rows=rows)
    print(f"Wrote {len(rows)} ranking examples to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
