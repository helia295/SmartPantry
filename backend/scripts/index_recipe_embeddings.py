from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db import SessionLocal
from app.services.embeddings import embed_texts
from app.services.retrieval import (
    build_recipe_embedding_document,
    indexable_recipe_rows,
    upsert_recipe_embedding,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Index recipe embeddings for SmartPantry recipe Q&A.")
    parser.add_argument("--recipe-id", type=int, action="append", dest="recipe_ids", default=[])
    parser.add_argument("--limit", type=int, default=None)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    with SessionLocal() as db:
        recipe_rows = indexable_recipe_rows(db=db, recipe_ids=args.recipe_ids or None)
        if args.limit is not None:
            recipe_rows = recipe_rows[: max(args.limit, 0)]
        if not recipe_rows:
            print("No recipes found to index.")
            return 0

        documents = [
            build_recipe_embedding_document(recipe=recipe, ingredients=ingredients)
            for recipe, ingredients in recipe_rows
        ]
        embeddings = embed_texts(texts=documents)

        for (recipe, _ingredients), document_text, embedding in zip(recipe_rows, documents, embeddings):
            upsert_recipe_embedding(
                db=db,
                recipe=recipe,
                document_text=document_text,
                embedding=embedding,
            )
        db.commit()

    print(f"Indexed {len(recipe_rows)} recipe embeddings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
